import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatAnswer({ content }) {
  // Keep all five incident sections visible instead of a KB-only preview.
  const analysis = content.startsWith('## Incident Summary\n');
  const long = !analysis && content.length > 600;
  const sources = [...content.matchAll(/\[(KB-\d{3})\] ([^\n]+)\n[\s\S]*?แหล่งอ้างอิง: \[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g)];
  const advice = content.split('คำแนะนำทั่วไปจาก Gemini (ไม่ใช่ผลตรวจระบบ):\n')[1];
  const kb = content.match(/\[KB-\d{3}\] [^\n]+\n([\s\S]*?)\nแหล่งอ้างอิง:/)?.[1];
  const preview = advice || kb || content;
  const excerpt = preview.length > 550 ? preview.slice(0, 550) + '…' : preview;
  return <div className="chat-answer">
    {long && (advice || kb) && <p className="text-xs text-slate-400">{advice ? 'คำแนะนำจาก Gemini • ยังไม่ใช่ข้อยืนยันเหตุการณ์' : 'คำแนะนำจาก Knowledge Base • ยังไม่ใช่ข้อยืนยันเหตุการณ์'}</p>}
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{long ? excerpt : content}</ReactMarkdown>
    {long && <>
      {sources.length > 0 && <div className="chat-citations" aria-label="KB citations">
        {sources.map((source, i) => <a key={i} href={source[4]} target="_blank" rel="noopener noreferrer" title={source[2]}>{source[1]} · {source[3]}</a>)}
      </div>}
      <details className="chat-details"><summary>รายละเอียดและคำตอบฉบับเต็ม</summary>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </details>
    </>}
  </div>;
}
