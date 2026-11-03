import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Tickets from './pages/Tickets';
import PrivateChat from './components/PrivateChat';
import { api, getToken } from './services/api';

function Chat({ companyId, internal }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const controller = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  const send = async event => {
    event.preventDefault();
    const message = input.trim();
    if (!message || pending.current || (internal && !companyId)) return;
    pending.current = true;
    controller.current = new AbortController();
    setBusy(true); setError(''); setInput('');
    setMessages(previous => [...previous, { role: 'user', content: message }]);
    try {
      const result = await api('/customer-data/ask', {
        method: 'POST', signal: controller.current.signal,
        body: JSON.stringify({ message, ...(internal ? { company_id: companyId } : {}) }),
      });
      setMessages(previous => [...previous, { role: 'assistant', content: result.answer }]);
    } catch (error) {
      if (error.name !== 'AbortError') { setError(error.message); setInput(message); }
    } finally { pending.current = false; setBusy(false); }
  };
  const disabled = busy || (internal && !companyId);
  return <main className="max-w-3xl mx-auto p-5">
    <h2 className="text-xl font-bold mb-2">{internal ? 'Company Q&A' : 'Support Assistant'}</h2>
    <p className="text-sm text-slate-400 mb-4">Demo telemetry Q&A with rule-based fallback. Chat stays in this view only.</p>
    <div className="space-y-3 min-h-[55vh]" aria-live="polite">
      {!messages.length && <p className="text-slate-400">{internal && !companyId ? 'Select a customer company to begin.' : 'Ask about assets, IP addresses, log collectors, or security events.'}</p>}
      {messages.map((message, index) => <div key={index} className={'rounded-xl p-3 ' + (message.role === 'user' ? 'bg-blue-900 ml-12' : 'bg-slate-800 mr-12')}><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></div>)}
      {busy && <p role="status">Loading answer…</p>}
    </div>
    {error && <p role="alert" className="text-red-300 my-3">{error} Please try again.</p>}
    <form onSubmit={send} className="flex gap-2 mt-4">
      <input aria-label="Chat message" maxLength={1000} disabled={disabled} className="min-w-0 flex-1 bg-slate-800 rounded p-3" value={input} onChange={event => setInput(event.target.value)} placeholder="Ask about your company telemetry…" />
      <button disabled={disabled || !input.trim()} className="bg-blue-600 px-5 rounded disabled:opacity-50">Send</button>
    </form>
  </main>;
}

function Portal({ user, logout }) {
  const internal = ['ADMIN', 'SUPPORT'].includes(user.role);
  const [view, setView] = useState('rooms');
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState('');
  const [loading, setLoading] = useState(internal);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!internal) return;
    const controller = new AbortController();
    api('/demo-auth/companies', { signal: controller.signal }).then(setCompanies)
      .catch(error => { if (error.name !== 'AbortError') setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [internal, retry]);
  return <div className="min-h-screen bg-slate-950 text-white">
    <header className="p-4 bg-slate-900 flex flex-wrap items-center justify-between gap-3">
      <div><strong>{internal ? 'SOC Internal Portal' : 'SOC Customer Portal'}</strong><p className="text-xs text-slate-400">{user.name} · {user.company} · {user.role}</p></div>
      <nav className="flex gap-3" aria-label="Portal navigation">
        <button aria-current={view === 'rooms' ? 'page' : undefined} onClick={() => setView('rooms')}>{internal ? 'Customer Chats' : 'Chat'}</button>
        {internal && <button aria-current={view === 'chat' ? 'page' : undefined} onClick={() => setView('chat')}>Company Q&A</button>}
        <button aria-current={view === 'tickets' ? 'page' : undefined} onClick={() => setView('tickets')}>{internal ? 'Company Tickets' : 'My Company Tickets'}</button>
        <button onClick={logout} className="text-red-300">Logout</button>
      </nav>
    </header>
    {internal && <section className="max-w-3xl mx-auto p-5">
      <label htmlFor="company">Customer company</label>
      <select id="company" disabled={loading} className="block w-full bg-slate-800 rounded p-3 mt-2" value={companyId} onChange={event => setCompanyId(event.target.value)}>
        <option value="">All companies (chat rooms)</option>
        {companies.map(company => <option key={company.id} value={company.id}>{company.name}</option>)}
      </select>
      {loading && <p role="status">Loading companies…</p>}
      {error && <p role="alert">{error} <button onClick={() => { setError(''); setLoading(true); setRetry(value => value + 1); }}>Retry</button></p>}
      {!loading && !error && !companies.length && <p>No customer companies available.</p>}
    </section>}
    {view === 'tickets'
      ? <div className="bg-slate-50 text-slate-900 min-h-screen">{internal && !companyId ? <p className="p-6">Select a customer company to view tickets.</p> : <Tickets key={companyId || user.company_id} user={user} companyId={internal ? companyId : undefined}/>}</div>
      : view === 'rooms' ? <PrivateChat key={companyId || user.id} user={user} companyId={companyId}/> : <Chat key={companyId || user.company_id} internal={internal} companyId={companyId}/>}
  </div>;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const expired = () => { setUser(null); setSelected(''); setError('Session expired. Please log in again.'); };
    window.addEventListener('demo-session-expired', expired);
    return () => window.removeEventListener('demo-session-expired', expired);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const list = await api('/demo-auth/users', { signal: controller.signal });
        setUsers(list);
        if (getToken()) setUser(await api('/demo-auth/me', { signal: controller.signal }));
      } catch (error) { if (error.name !== 'AbortError') setError(error.message); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    };
    load();
    return () => controller.abort();
  }, [retry]);
  const login = async () => {
    if (busy || !selected) return;
    setBusy(true); setError('');
    try {
      const result = await api('/demo-auth/login', { method: 'POST', body: JSON.stringify({ user_id: selected }) });
      sessionStorage.setItem('demo_token', result.token); setUser(result.user);
    } catch (error) { setError(error.message); }
    finally { setBusy(false); }
  };
  const logout = () => { sessionStorage.removeItem('demo_token'); setUser(null); setSelected(''); setError(''); };
  if (user) return <Portal key={user.id} user={user} logout={logout}/>;
  return <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
    <section className="w-full max-w-md rounded-xl bg-slate-900 p-8 space-y-5">
      <h1 className="text-2xl font-bold">SOC AI Support — Demo Login</h1>
      <p className="text-slate-400 text-sm">Demo identities only. Not production authentication.</p>
      {loading && <p role="status">Loading demo session…</p>}
      <select aria-label="Select demo user" disabled={loading || busy} className="w-full bg-slate-800 p-3 rounded" value={selected} onChange={event => setSelected(event.target.value)}>
        <option value="">Select demo user</option>
        {users.map(user => <option key={user.id} value={user.id}>{user.name} — {user.company} ({user.role})</option>)}
      </select>
      <button disabled={!selected || busy || loading} onClick={login} className="w-full rounded bg-blue-600 p-3 disabled:opacity-50">{busy ? 'Logging in…' : 'Login'}</button>
      {error && <p role="alert" className="text-red-400">{error}</p>}
      {!loading && !users.length && !error && <p>No demo users available.</p>}
      {!loading && <button onClick={() => { setLoading(true); setError(''); setRetry(value => value + 1); }}>Reload demo users</button>}
    </section>
  </main>;
}
