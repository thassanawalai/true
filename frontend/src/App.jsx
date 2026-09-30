import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, ShieldAlert, Terminal, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello, I am your **SOC AI Assistant**. I am ready to investigate security threats and assist with IT operations. How can I help you today?'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    const newMessages = [...messages, { role: 'user', content: query }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          user_company: 'Demeter ICT' // Change according to your organization context
        }),
      });

      const data = await response.json();
      if (data.status === 'success') {
        setMessages([...newMessages, { role: 'assistant', content: data.reply }]);
      } else {
        setMessages([...newMessages, { role: 'assistant', content: `⚠️ **Error:** ${data.message || 'Unable to connect to the AI engine.'}` }]);
      }
    } catch (err) {
      setMessages([...newMessages, { role: 'assistant', content: '❌ **Network Error:** Unable to connect to the backend. Please ensure the FastAPI server is running.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar: Quick Actions & System Info */}
      <aside className="w-72 border-r border-slate-800 bg-slate-900/60 p-4 flex flex-col justify-between hidden md:flex">
        <div>
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-blue-600/20 rounded-lg border border-blue-500/30">
              <ShieldAlert className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-wide">SOC COPILOT</h1>
              <p className="text-xs text-emerald-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Core Ready (Qwen-27B)
              </p>
            </div>
          </div>

          <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Quick Actions</p>
          <div className="space-y-2">
            <button 
              onClick={() => handleSend("What are the pending cases for my company? Please list them.")}
              className="w-full text-left p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 text-xs flex items-center gap-2 transition"
            >
              <RefreshCw className="w-4 h-4 text-blue-400" /> Check All Tickets
            </button>
            <button 
              onClick={() => handleSend("Are there any critical Ransomware or Malware cases pending?")}
              className="w-full text-left p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 text-xs flex items-center gap-2 transition"
            >
              <AlertTriangle className="w-4 h-4 text-amber-400" /> Filter Critical Cases
            </button>
            <button 
              onClick={() => handleSend("Please open a ticket ASAP: CrowdStrike detected malware on Server 01.")}
              className="w-full text-left p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 text-xs flex items-center gap-2 transition"
            >
              <Terminal className="w-4 h-4 text-rose-400" /> Simulate Incident Ticket
            </button>
          </div>
        </div>

        <div className="text-xs text-slate-400 border-t border-slate-800 pt-4">
          <p className="font-semibold text-slate-300">FastAPI + Groq Agent</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Automated Incident Triage</p>
        </div>
      </aside>

      {/* Main Chat Interface */}
      <main className="flex-1 flex flex-col h-full bg-slate-950">
        {/* Chat Stream */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
          {messages.map((m, idx) => (
            <div 
              key={idx} 
              className={`flex gap-3 max-w-3xl ${m.role === 'user' ? 'ml-auto justify-end' : 'mr-auto justify-start'}`}
            >
              {m.role === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center flex-shrink-0 mt-1">
                  <Terminal className="w-4 h-4 text-blue-400" />
                </div>
              )}

              <div 
                className={`p-4 rounded-xl text-sm leading-relaxed ${
                  m.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-br-none shadow-md' 
                    : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none shadow-sm markdown-content w-full'
                }`}
              >
                {m.role === 'assistant' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.content}
                  </ReactMarkdown>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 max-w-xl mr-auto items-center">
              <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center animate-spin">
                <RefreshCw className="w-4 h-4 text-blue-400" />
              </div>
              <p className="text-xs text-slate-400 animate-pulse">processing...</p>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/40">
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }} 
            className="max-w-3xl mx-auto flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 focus-within:border-blue-500/50 transition"
          >
            <input 
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything... "
              className="flex-1 bg-transparent border-none text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
            />
            <button 
              type="submit" 
              disabled={loading || !input.trim()}
              className="p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white rounded-lg transition"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}