import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../services/api';

export function RoomConversation({ roomId, user, onLinked }) {
  const [room, setRoom] = useState(null);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState('');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [confirming, setConfirming] = useState(false);
  const pending = useRef(false);
  const internal = ['ADMIN', 'SUPPORT'].includes(user.role);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    const poll = async () => {
      try {
        const result = await api('/chat-rooms/' + roomId, { signal: controller.signal });
        if (!pending.current) {
          setRoom(previous => previous && (previous.messages.length > result.messages.length || (previous.ticket_id && !result.ticket_id)) ? previous : result);
          setPollError('');
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          setPollError(error.message);
          if (error.status === 404) setRoom(null);
        }
      } finally {
        if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(poll, 1500); }
      }
    };
    poll();
    return () => { clearTimeout(timer); controller.abort(); };
  }, [roomId]);
  const mutate = async (suffix, payload) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try {
      const result = await api('/chat-rooms/' + roomId + suffix, { method: 'POST', body: JSON.stringify(payload) });
      setRoom(result);
      if (suffix === '/messages') setInput('');
      else { setConfirming(false); onLinked?.(); }
    } catch (error) { setError(error.message); }
    finally { pending.current = false; setBusy(false); }
  };
  if (loading) return <p role="status">Loading conversation…</p>;
  return <section className="bg-slate-950 text-white rounded-xl p-4 space-y-4" aria-label="Private conversation">
    {(error || pollError) && <p role="alert" className="text-red-300">{error || pollError}</p>}
    {room && <>
      <h3 className="font-bold">{room.owner_name} — {room.ticket_number || 'Temporary private chat'}</h3>
      <p className="text-sm text-slate-400">{room.temporary
        ? 'Temporary live chat: expires 30 minutes after the last message and disappears on backend restart. Refresh/navigation reconnects only while it is active. SOC can view and reply. No durable history until you create a ticket.'
        : 'Ticket-linked history is saved. Only this chat owner and SOC staff can access this conversation.'}</p>
      {!room.messages.length && <p>Ask the chatbot about playbooks, assets, collectors, or security events to begin.</p>}
      <div className="space-y-3" aria-live="polite">
        {room.messages.map(message => <article key={message.id} className={'rounded-xl p-3 ' + (message.role === 'customer' ? 'bg-blue-900 ml-8' : 'bg-slate-800 mr-8')}>
          <p className="text-xs text-slate-300 mb-1">{message.sender_name} · {message.role}</p>
          <ReactMarkdown remarkPlugins={[remarkGfm]} disallowedElements={['img', 'a']} unwrapDisallowed>{message.content}</ReactMarkdown>
        </article>)}
      </div>
      {busy && <p role="status">Sending…</p>}
      <form className="flex gap-2" onSubmit={event => { event.preventDefault(); if (input.trim()) mutate('/messages', { content: input.trim() }); }}>
        <input aria-label="Private chat message" maxLength={1000} value={input} onChange={event => setInput(event.target.value)} disabled={busy || (internal && !room.messages.length)} className="min-w-0 flex-1 bg-slate-800 rounded p-3" placeholder={internal ? 'Reply as SOC…' : 'Ask the chatbot…'}/>
        <button disabled={busy || !input.trim() || (internal && !room.messages.length)} className="bg-blue-600 rounded px-4 disabled:opacity-50">{internal ? 'Reply' : 'Send message'}</button>
      </form>
      {!internal && room.temporary && <button disabled={busy} className="text-red-300" onClick={async () => {
        if (!window.confirm('Discard this temporary conversation? It cannot be recovered.')) return;
        pending.current = true; setBusy(true); setError('');
        try { await api('/chat-rooms/' + roomId, { method: 'DELETE' }); setRoom(null); setPollError('Temporary chat discarded. Open a new private chat to continue.'); }
        catch (error) { setError(error.message); }
        finally { pending.current = false; setBusy(false); }
      }}>Discard temporary chat</button>}
      {!internal && room.temporary && room.messages.some(message => message.role === 'assistant') && <>
        <button disabled={busy} onClick={() => setConfirming(!confirming)} className="bg-blue-600 rounded p-2">Create ticket from chat</button>
        {confirming && <form className="space-y-2" onSubmit={event => { event.preventDefault(); if (subject.trim()) mutate('/ticket', { subject: subject.trim(), ...(description.trim() ? { description: description.trim() } : {}) }); }}>
          <p className="text-sm">Create a company-visible ticket and save this private conversation for you and SOC. The ticket subject and description are visible to your company; chat messages remain private.</p>
          <input aria-label="Chat ticket subject" required maxLength={200} value={subject} onChange={event => setSubject(event.target.value)} className="bg-slate-800 rounded p-3 w-full" placeholder="Ticket subject"/>
          <textarea aria-label="Chat ticket description" maxLength={5000} value={description}
            onChange={event => setDescription(event.target.value)} className="bg-slate-800 rounded p-3 w-full"
            placeholder="Incident description for assessment (optional)"/>
          <button disabled={busy || !subject.trim()} className="bg-blue-600 rounded p-2 mr-3">Confirm create ticket</button>
          <button type="button" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
        </form>}
      </>}
    </>}
  </section>;
}

export function TicketChatHistory({ ticketId, user }) {
  const [room, setRoom] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    api('/chat-rooms/by-ticket/' + ticketId, { signal: controller.signal }).then(setRoom)
      .catch(error => { if (error.name !== 'AbortError') setError(error.message); });
    return () => controller.abort();
  }, [ticketId]);
  return error ? <p role="status">{error}</p> : room ? <RoomConversation key={room.id} roomId={room.id} user={user}/> : <p role="status">Loading ticket chat…</p>;
}

export default function PrivateChat({ user, companyId }) {
  const internal = ['ADMIN', 'SUPPORT'].includes(user.role);
  const [rooms, setRooms] = useState([]);
  const [roomId, setRoomId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    const load = async () => {
      try {
        const result = await api('/chat-rooms' + (internal && companyId ? '?company_id=' + encodeURIComponent(companyId) : ''), { signal: controller.signal });
        setRooms(result); setError('');
      } catch (error) { if (error.name !== 'AbortError') setError(error.message); }
      finally { if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(load, 3000); } }
    };
    load();
    return () => { clearTimeout(timer); controller.abort(); };
  }, [companyId, internal, refresh]);
  const open = async () => {
    if (busy) return;
    setBusy(true); setError('');
    try { const room = await api('/chat-rooms', { method: 'POST' }); setRoomId(room.id); setRefresh(value => value + 1); }
    catch (error) { setError(error.message); }
    finally { setBusy(false); }
  };
  return <main className="max-w-3xl mx-auto p-5 space-y-4">
    <h2 className="text-xl font-bold">{internal ? 'Customer Chat Rooms' : 'My Private Chats'}</h2>
    <p className="text-slate-400 text-sm">Chatbot answers first using demo telemetry, with rule-based fallback. Unticketed messages are temporary; only ticket-linked history is saved.</p>
    {!internal && <button disabled={busy} onClick={open} className="bg-blue-600 rounded p-2">Open private chat</button>}
    {loading && <p role="status">Loading chat rooms…</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {!loading && !error && !rooms.length && <p>No chat rooms available.</p>}
    <label className="block">{internal ? 'Customer chat room' : 'My chat room'}
      <select aria-label="Chat room" className="block bg-slate-800 w-full rounded p-3 mt-2" value={roomId} onChange={event => setRoomId(event.target.value)}>
        <option value="">Select chat room</option>
        {rooms.map(room => <option key={room.id} value={room.id}>{room.owner_name} — {room.ticket_number || 'Temporary chat'}</option>)}
      </select>
    </label>
    {roomId && <RoomConversation key={roomId} roomId={roomId} user={user} onLinked={() => setRefresh(value => value + 1)}/>}
    {!roomId && internal && <p>Select a room to view and reply to its owner.</p>}
  </main>;
}
