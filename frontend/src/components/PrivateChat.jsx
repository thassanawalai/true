import { useEffect, useRef, useState } from 'react';
import { Bot, UserRound, Send, MessageSquarePlus, ShieldCheck, Info, ChevronDown, Ticket, Trash2, ArrowDown, MessageSquare, X } from 'lucide-react';
import ChatAnswer from './ChatAnswer';
import { api } from '../services/api';
import './PrivateChat.css';

export function RoomConversation({ roomId, user, onLinked }) {
  const [room, setRoom] = useState(null);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState('');
  const [subject, setSubject] = useState('');
  const [confirming, setConfirming] = useState(false);
  const pending = useRef(false);
  const messageList = useRef(null);
  const followLatest = useRef(true);
  const [readingEarlier, setReadingEarlier] = useState(false);
  const actions = useRef(null);
  const ticketDialog = useRef(null);
  useEffect(() => {
    const list = messageList.current;
    if (list && followLatest.current) list.scrollTop = list.scrollHeight;
  }, [room?.messages.length, loading, busy]);
  useEffect(() => {
    const dialog = ticketDialog.current;
    if (confirming && dialog) dialog.showModal();
    return () => dialog?.close();
  }, [confirming]);
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
    if (suffix === '/messages') { followLatest.current = true; setReadingEarlier(false); }
    try {
      const result = await api('/chat-rooms/' + roomId + suffix, { method: 'POST', body: JSON.stringify(payload) });
      setRoom(result);
      if (suffix === '/messages') setInput('');
      else { setConfirming(false); onLinked?.(); }
    } catch (error) { setError(error.message); }
    finally { pending.current = false; setBusy(false); }
  };
  const discard = async () => {
    if (pending.current || !window.confirm('ลบบทสนทนาชั่วคราวนี้? การลบไม่สามารถย้อนกลับได้')) return;
    pending.current = true; setBusy(true); setError('');
    try { await api('/chat-rooms/' + roomId, { method: 'DELETE' }); setRoom(null); setPollError('ลบบทสนทนาแล้ว คุณสามารถเริ่มแชทใหม่ได้'); onLinked?.(); }
    catch (error) { setError(error.message); }
    finally { pending.current = false; setBusy(false); }
  };
  if (loading) return <div className="soc-chat-empty" role="status"><span className="soc-chat-orb"><MessageSquare size={28}/></span><p>กำลังเปิดบทสนทนา…</p></div>;
  return <section className="room-conversation soc-conversation" aria-label="บทสนทนาส่วนตัว">
    {(error || pollError) && <p role="alert" className="soc-chat-error">{error || pollError}</p>}
    {room && <>
      <header className="soc-conversation-bar">
        <div className="soc-room-identity"><span className="soc-presence"/><span>{internal ? room.owner_name : 'SOC Support'}</span><small>{room.ticket_number || 'แชทส่วนตัว'}</small></div>
        <div className="soc-room-controls">
          <details className="soc-chat-popover"><summary aria-label="ข้อมูลความเป็นส่วนตัว"><Info size={18}/></summary><div>
            <strong>ความเป็นส่วนตัวของคุณ</strong><p>{room.temporary
              ? 'เฉพาะคุณและทีม SOC เข้าถึงแชทนี้ได้ แชทชั่วคราวหมดอายุหลังหยุดใช้งาน 30 นาทีหรือเมื่อระบบเริ่มใหม่ ยืนยันสร้างรายการแจ้งปัญหาเพื่อเก็บประวัติ'
              : 'ประวัติบันทึกกับรายการแจ้งปัญหาแล้ว เฉพาะเจ้าของแชทและทีม SOC เข้าถึงบทสนทนาได้'}</p>
          </div></details>
          {!internal && room.temporary && <details ref={actions} className="soc-chat-popover soc-chat-actions"><summary>การดำเนินการ <ChevronDown size={15}/></summary><div>
            <button disabled={busy || !room.messages.some(message => message.role === 'assistant')} onClick={() => { actions.current.open = false; setConfirming(true); }}><Ticket size={17}/>สร้างรายการแจ้งปัญหา</button>
            <button className="soc-danger" disabled={busy} onClick={() => { actions.current.open = false; discard(); }}><Trash2 size={17}/>ลบแชทชั่วคราว</button>
          </div></details>}
        </div>
      </header>
      <div className="soc-message-stage">
        <div className="chat-messages" ref={messageList} role="log" aria-label="ข้อความสนทนา" aria-live="polite" onScroll={event => {
          const list = event.currentTarget;
          const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 70;
          followLatest.current = nearBottom; setReadingEarlier(!nearBottom);
        }}>
          {!room.messages.length && <div className="soc-chat-empty"><span className="soc-chat-orb"><ShieldCheck size={32}/></span><h3>มีเรื่องใดให้เราช่วยดูแล?</h3><p>{internal ? 'รอข้อความและคำตอบแรกจากผู้ช่วย ก่อนตอบกลับในนาม SOC' : 'ถามเรื่องความปลอดภัยได้เลย เช่น “phishing คืออะไร” หรือ “MFA ช่วยอย่างไร”\nคำถามทั่วไปตอบจาก KB โดยไม่อ่าน Log; กดวิเคราะห์ Log เมื่อต้องการตรวจเหตุการณ์'}</p></div>}
          {room.messages.map((message, index) => <article key={message.id} className={'chat-bubble ' + (message.role === 'customer' ? 'chat-customer' : message.role === 'assistant' ? 'chat-assistant' : 'chat-analyst')}>
            <p className="chat-sender">{message.role === 'customer' ? <UserRound size={15}/> : message.role === 'assistant' ? <Bot size={16}/> : <ShieldCheck size={16}/>}
              {message.role === 'customer' ? (internal ? message.sender_name : 'คุณ') : message.role === 'assistant' ? 'ผู้ช่วย SOC' : message.sender_name}
              {message.role !== 'customer' && <span className="soc-role-label">{message.role === 'assistant' ? 'ผู้ช่วยความปลอดภัย' : 'SOC Analyst'}</span>}
            </p>
            <ChatAnswer content={message.content} disabled={busy} onAnalyze={!internal && message.role === 'assistant' ? (details = false) => {
              const previous = room.messages.slice(0, index).findLast(item => item.role === 'customer');
              if (!previous) return;
              const content = previous.content.replace(/^(?:วิเคราะห์ Log|รายละเอียด Log): /, '');
              mutate('/messages', { content, action: 'analyze_log', details });
            } : undefined} canAnalyze={message.role === 'assistant' && /login|log|alert|phishing|malware|ransomware|scan|siem|incident|เข้าสู่ระบบ|ล็อกอิน|ฟิชชิง|มัลแวร์|เหตุการณ์|สแกน|เรียกค่าไถ่/i.test(room.messages.slice(0, index).findLast(item => item.role === 'customer')?.content || '')}/>
          </article>)}
          {busy && <p className="soc-sending" role="status"><span/>กำลังเตรียมคำตอบ…</p>}
        </div>
        {readingEarlier && <button className="soc-latest" onClick={() => { followLatest.current = true; messageList.current.scrollTop = messageList.current.scrollHeight; setReadingEarlier(false); }}><ArrowDown size={15}/>ข้อความล่าสุด</button>}
      </div>
      <form className="chat-composer" onSubmit={event => { event.preventDefault(); if (input.trim()) mutate('/messages', { content: input.trim() }); }}>
        <div className="soc-composer-field"><textarea rows={2} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form.requestSubmit(); } }} aria-label="ข้อความ" maxLength={1000} value={input} onChange={event => setInput(event.target.value)} disabled={busy || (internal && !room.messages.length)} placeholder={internal ? 'ตอบกลับในนาม SOC…' : 'ถามเรื่องความปลอดภัย เช่น phishing หรือ MFA…'}/>
          <button aria-label={internal ? 'ตอบกลับ' : 'ส่งข้อความ'} disabled={busy || !input.trim() || (internal && !room.messages.length)}><Send size={19}/></button>
        </div>
        <p>Enter เพื่อส่ง · Shift + Enter เพื่อขึ้นบรรทัดใหม่</p>
      </form>
      {confirming && <dialog ref={ticketDialog} className="soc-ticket-confirm" aria-labelledby="soc-ticket-title" onCancel={() => setConfirming(false)}>
        <form onSubmit={event => { event.preventDefault(); if (subject.trim()) mutate('/ticket', { subject: subject.trim() }); }}>
          <header><h3 id="soc-ticket-title">สร้างรายการแจ้งปัญหา</h3><button type="button" aria-label="ปิด" disabled={busy} onClick={() => setConfirming(false)}><X size={19}/></button></header>
          <p>หัวข้อจะปรากฏให้คนในบริษัทเห็น ประวัติแชทจะบันทึกไว้ให้คุณและทีม SOC เท่านั้น</p>
          {error && <p role="alert" className="soc-chat-error">{error}</p>}
          <label>หัวข้อปัญหา<input autoFocus aria-label="หัวข้อปัญหา" required maxLength={200} value={subject} onChange={event => setSubject(event.target.value)} placeholder="สรุปปัญหาที่ต้องการให้ตรวจสอบ"/></label>
          <footer><button type="button" disabled={busy} onClick={() => setConfirming(false)}>ยกเลิก</button><button className="soc-primary" disabled={busy || !subject.trim()}>ยืนยันสร้างรายการ</button></footer>
        </form>
      </dialog>}
    </>}
  </section>;

}

export function TicketChatHistory({ ticketId, user }) {
  const [room, setRoom] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    api('/chat-rooms/by-ticket/' + ticketId, { signal: controller.signal }).then(setRoom)
      .catch(error => { if (error.name !== 'AbortError') setError(error.status === 404 ? 'ไม่มีประวัติแชทที่คุณมีสิทธิ์เข้าถึงสำหรับ Ticket นี้' : error.message); });
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
  return <main className="private-chat soc-chat-page">
    <header className="soc-chat-toolbar">
      <div className="soc-toolbar-title"><MessageSquare size={20}/><h2>{internal ? 'Customer Conversations' : 'แชทช่วยเหลือ'}</h2></div>
      <div className="soc-room-picker"><label className="sr-only" htmlFor="private-room-picker">{internal ? 'ห้องแชทลูกค้า' : 'เลือกบทสนทนา'}</label>
        <select id="private-room-picker" value={roomId} onChange={event => setRoomId(event.target.value)}>
          <option value="">{loading ? 'กำลังโหลด…' : 'เลือกบทสนทนา'}</option>
          {rooms.map(room => <option key={room.id} value={room.id}>{internal ? room.owner_name + ' — ' : ''}{room.ticket_number || 'แชทส่วนตัว'}</option>)}
        </select>
        {!internal && <button disabled={busy} onClick={open} className="soc-new-chat"><MessageSquarePlus size={17}/><span>{busy ? 'กำลังเปิด…' : 'แชทใหม่'}</span></button>}
      </div>
    </header>
    {internal && <p className="soc-internal-purpose">View and assist with customer conversations.</p>}
    {error && <p role="alert" className="soc-chat-error">{error}</p>}
    {roomId ? <RoomConversation key={roomId} roomId={roomId} user={user} onLinked={() => setRefresh(value => value + 1)}/> :
      <div className="soc-chat-empty"><span className="soc-chat-orb"><ShieldCheck size={36}/></span><p className="soc-eyebrow">SECURITY SUPPORT</p><h3>{internal ? 'เลือกบทสนทนาเพื่อเริ่มช่วยเหลือ' : 'ความช่วยเหลือที่เริ่มจากบทสนทนา'}</h3>
        <p>{loading ? 'กำลังโหลดบทสนทนา…' : internal ? 'เลือกห้องแชทของลูกค้าจากแถบด้านบน' : 'สอบถามเรื่องความปลอดภัย รับคำแนะนำที่มีแหล่งอ้างอิง\nและส่งต่อให้ทีม SOC เมื่อต้องการความช่วยเหลือ'}</p>
        {!internal && <button className="soc-primary" disabled={busy} onClick={open}><MessageSquarePlus size={18}/>เริ่มแชทส่วนตัว</button>}
      </div>}
  </main>;
}
