import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Tickets from './pages/Tickets';
import { api } from './services/api';

export default function App() {
  const [user, setUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState('');
  const [view, setView] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    api('/demo-auth/users').then(setUsers).catch(e => setError(e.message));
    if (sessionStorage.getItem('demo_token')) api('/demo-auth/me').then(setUser).catch(() => sessionStorage.removeItem('demo_token'));
  }, []);
  const login = async () => {
    try {
      const result = await api('/demo-auth/login', { method: 'POST', body: JSON.stringify({ user_id: selected }) });
      sessionStorage.setItem('demo_token', result.token);
      setUser(result.user); setMessages([]); setError('');
    } catch (e) { setError(e.message); }
  };
  const logout = () => { sessionStorage.removeItem('demo_token'); setUser(null); setMessages([]); setView('chat'); };
  const send = async e => {
    e.preventDefault(); if (!input.trim() || busy) return;
    const message = input; const history = messages;
    setInput(''); setMessages([...history, { role: 'user', content: message }]); setBusy(true);
    try {
      const result = await api('/chat', { method: 'POST', body: JSON.stringify({ message, history }) });
      setMessages(prev => [...prev, { role: 'assistant', content: result.reply || result.message || 'No response' }]);
    } catch (e) { setMessages(prev => [...prev, { role: 'assistant', content: 'Request failed: ' + e.message }]); }
    finally { setBusy(false); }
  };
  if (!user) return <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
    <section className="w-full max-w-md rounded-xl bg-slate-900 p-8 space-y-5">
      <h1 className="text-2xl font-bold">SOC AI Support — Demo Login</h1>
      <p className="text-slate-400 text-sm">Demo identities only. Not production authentication.</p>
      <select aria-label="Select demo user" className="w-full bg-slate-800 p-3 rounded" value={selected} onChange={e => setSelected(e.target.value)}>
        <option value="">Select demo user</option>
        {users.map(u => <option key={u.id} value={u.id}>{u.name} — {u.company} ({u.role})</option>)}
      </select>
      <button disabled={!selected} onClick={login} className="w-full rounded bg-blue-600 p-3 disabled:opacity-50">Login</button>
      {error && <p role="alert" className="text-red-400">{error}</p>}
      {!users.length && <p className="text-sm text-amber-300">Run backend/scripts/seed_phase1.py to load demo users.</p>}
    </section>
  </main>;
  return <div className="min-h-screen bg-slate-950 text-white">
    <header className="p-4 bg-slate-900 flex flex-wrap items-center justify-between gap-3">
      <div><strong>SOC AI Support</strong><p className="text-xs text-slate-400">{user.name} · {user.company} · {user.role}</p></div>
      <nav className="flex gap-3">
        <button onClick={() => setView('chat')}>AI Chat</button>
        <button onClick={() => setView('tickets')}>{user.role === 'CUSTOMER' ? 'My Company Tickets' : 'All Tickets'}</button>
        <button onClick={logout} className="text-red-300">Logout</button>
      </nav>
    </header>
    {view === 'tickets' ? <div className="bg-slate-50 text-slate-900 min-h-screen"><Tickets user={user}/></div> :
      <main className="max-w-3xl mx-auto p-5">
        <h2 className="text-xl font-bold mb-4">AI Support Assistant</h2>
        <div className="space-y-3 min-h-[55vh]">
          {messages.map((m, i) => <div key={i} className={'rounded-xl p-3 ' + (m.role === 'user' ? 'bg-blue-900 ml-12' : 'bg-slate-800 mr-12')}><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>)}
        </div>
        <form onSubmit={send} className="flex gap-2 mt-4">
          <input aria-label="Chat message" className="flex-1 bg-slate-800 rounded p-3" value={input} onChange={e => setInput(e.target.value)} placeholder="Describe your issue..." />
          <button disabled={busy} className="bg-blue-600 px-5 rounded disabled:opacity-50">Send</button>
        </form>
      </main>}
  </div>;
}
