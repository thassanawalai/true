import { useEffect, useRef, useState } from 'react';
import Tickets from './pages/Tickets';
import PrivateChat from './components/PrivateChat';
import { ShieldAlert, MessageSquare, Ticket, LogOut, BookOpen, Send, Bot, UserRound } from 'lucide-react';
import ChatAnswer from './components/ChatAnswer';
import { api, getToken } from './services/api';

function Chat({ companyId, companyName, internal }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const controller = useRef(null);
  const messageEnd = useRef(null);
  useEffect(() => { messageEnd.current?.scrollIntoView({ block: 'nearest' }); }, [messages, busy]);
  useEffect(() => () => controller.current?.abort(), []);
  const send = async (question = input, action = 'knowledge', details = false) => {
    const message = question.trim();
    if (!message || pending.current || (internal && !companyId)) return;
    pending.current = true;
    controller.current = new AbortController();
    setBusy(true); setError(''); setInput('');
    setMessages(previous => [...previous, { role: 'user', content: message }]);
    try {
      const result = await api('/customer-data/ask', {
        method: 'POST', signal: controller.current.signal,
        body: JSON.stringify({ message, action, details, ...(internal ? { company_id: companyId } : {}) }),
      });
      setMessages(previous => [...previous, { role: 'assistant', content: result.answer, question: message }]);
    } catch (error) {
      if (error.name !== 'AbortError') { setError(error.message); setInput(message); }
    } finally { pending.current = false; setBusy(false); }
  };
  const disabled = busy || (internal && !companyId);
  const suggestions = [
    'phishing คืออะไร และควรรับมืออย่างไร',
    'MFA ช่วยป้องกันบัญชีอย่างไร',
    'suspicious login ควรตรวจสอบอะไร',
    'log หายควรทำอย่างไร',
  ];
  return <main className="security-insights">
    <div><h2 className="text-xl font-bold">Security Insights</h2>
      <p className="text-sm text-slate-400 mt-1">ถามความรู้ด้านความปลอดภัยจาก KB หรือกดวิเคราะห์ Log ของบริษัทที่เลือก</p>
      <p className="insights-company">{companyId ? companyName : 'Select a company to begin'}</p>
    </div>
    <div className="insights-suggestions" aria-label="Suggested questions">
      {suggestions.map(question => <button key={question} disabled={disabled} onClick={() => send(question)}>{question}</button>)}
    </div>
    <div className="chat-messages" aria-live="polite" aria-label="Security Insights conversation">
      {!messages.length && <p className="text-sm text-slate-400">{companyId ? 'Choose a suggested question or ask your own. This conversation stays separate from customer conversations.' : 'Choose a company above to explore its security information.'}</p>}
      {messages.map((message, index) => <article key={index} className={'chat-bubble ' + (message.role === 'user' ? 'chat-customer' : 'chat-assistant')}>
        <p className="chat-sender">{message.role === 'user' ? <UserRound size={16}/> : <Bot size={16}/>} {message.role === 'user' ? 'You' : 'SOC Assistant'}</p>
        <ChatAnswer content={message.content} disabled={disabled} canAnalyze={message.role === 'assistant'} onAnalyze={message.role === 'assistant' ? details => send(message.question, 'analyze_log', details) : undefined}/>
      </article>)}
      {busy && <p role="status" className="text-sm text-blue-300">Reviewing {companyName}'s security information…</p>}
      <div ref={messageEnd}/>
    </div>
    {error && <p role="alert" className="text-red-300 text-sm">{error} Please try again.</p>}
    <form onSubmit={event => { event.preventDefault(); send(); }} className="chat-composer">
      <input aria-label="Security Insights question" maxLength={1000} disabled={disabled} className="min-w-0 flex-1 bg-slate-800 rounded p-3" value={input} onChange={event => setInput(event.target.value)} placeholder={companyId ? 'Ask about this company’s security…' : 'Select a company first'}/>
      <button aria-label="Send question" disabled={disabled || !input.trim()} className="bg-blue-600 px-4 rounded disabled:opacity-50"><Send size={17}/><span>Send</span></button>
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
  return <div className="soc-portal bg-slate-950 text-white">
    <aside className="portal-sidebar">
      <div className="portal-brand"><ShieldAlert size={30}/><div><strong>SOC COPILOT</strong><p>Security Support Assistant</p></div></div>
      <nav aria-label="Portal navigation">
        <button aria-current={view === 'rooms' ? 'page' : undefined} onClick={() => setView('rooms')}><MessageSquare size={19}/>{internal ? 'Customer Conversations' : 'Chat'}</button>
        {internal && <button aria-current={view === 'chat' ? 'page' : undefined} onClick={() => setView('chat')}><BookOpen size={19}/>Security Insights</button>}
        <button aria-current={view === 'tickets' ? 'page' : undefined} onClick={() => setView('tickets')}><Ticket size={19}/>{internal ? 'Ticket Management' : 'My Company Tickets'}</button>
      </nav>
      <div className="portal-account"><strong>{user.name}</strong><p>{user.company}</p><button onClick={logout}><LogOut size={16}/>Logout</button></div>
    </aside>
    <div className="portal-workspace">
      <header className="portal-heading"><div><strong>{internal ? 'SOC Internal Portal' : 'SOC Customer Portal'}</strong><p>พื้นที่ช่วยเหลือด้านความปลอดภัยของคุณ</p></div><span>{user.role}</span></header>
    {internal && <section className="company-context">
      <label htmlFor="company">Select customer company</label>
      <select id="company" disabled={loading} className="block w-full bg-slate-800 rounded p-3 mt-2" value={companyId} onChange={event => setCompanyId(event.target.value)}>
        <option value="">{view === 'rooms' ? 'All companies (conversations)' : 'Select a company'}</option>
        {companies.map(company => <option key={company.id} value={company.id}>{company.name}</option>)}
      </select>
      {loading && <p role="status">Loading companies…</p>}
      {error && <p role="alert">{error} <button onClick={() => { setError(''); setLoading(true); setRetry(value => value + 1); }}>Retry</button></p>}
      {!loading && !error && !companies.length && <p>No customer companies available.</p>}
    </section>}
    {view === 'tickets'
      ? <div className="bg-slate-50 text-slate-900 min-h-screen">{internal && !companyId ? <p className="p-6">Select a customer company to view tickets.</p> : <Tickets key={companyId || user.company_id} user={user} companyId={internal ? companyId : undefined}/>}</div>
      : view === 'rooms' ? <PrivateChat key={companyId || user.id} user={user} companyId={companyId}/> : <Chat key={companyId || user.company_id} internal={internal} companyId={companyId} companyName={companies.find(company => company.id === companyId)?.name || 'Selected company'}/>}
    </div>
  </div>;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState('');
  const [password, setPassword] = useState('');
  const passwordRequired = users.some(user => user.id === selected && user.password_required);
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
    if (busy || !selected || (passwordRequired && !password)) return;
    setBusy(true); setError('');
    try {
      const result = await api('/demo-auth/login', { method: 'POST', body: JSON.stringify({ user_id: selected, ...(passwordRequired ? { password } : {}) }) });
      sessionStorage.setItem('demo_token', result.token); setPassword(''); setUser(result.user);
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
      <select aria-label="Select demo user" disabled={loading || busy} className="w-full bg-slate-800 p-3 rounded" value={selected} onChange={event => { setSelected(event.target.value); setPassword(''); }}>
        <option value="">Select demo user</option>
        {users.map(user => <option key={user.id} value={user.id}>{user.name} — {user.company} ({user.role})</option>)}
      </select>
      {passwordRequired && <input aria-label="Demo password" type="password" autoComplete="current-password"
        className="w-full bg-slate-800 p-3 rounded" value={password} maxLength={256} disabled={busy}
        onChange={event => setPassword(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter') login(); }} />}
      <button disabled={!selected || busy || loading || (passwordRequired && !password)} onClick={login} className="w-full rounded bg-blue-600 p-3 disabled:opacity-50">{busy ? 'Logging in…' : 'Login'}</button>
      {error && <p role="alert" className="text-red-400">{error}</p>}
      {!loading && !users.length && !error && <p>No demo users available.</p>}
      {!loading && <button onClick={() => { setLoading(true); setError(''); setRetry(value => value + 1); }}>Reload demo users</button>}
    </section>
  </main>;
}
