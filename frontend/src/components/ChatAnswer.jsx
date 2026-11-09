import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatAnswer({ content, onAnalyze, canAnalyze, disabled }) {
  const briefAnalysis = content.startsWith('## สรุปการวิเคราะห์ Log\n');
  const technicalAnalysis = content.startsWith('## Incident Summary\n');
  const references = content.match(/\n\n### แหล่งอ้างอิง\n((?:- [^\n]+(?:\n|$))+)/);
  const body = references ? content.replace(references[0], '\n\n').trim() : content;
  // Old transcripts remain readable, with technical records hidden by default.
  const oldKB = body.match(/\[KB-\d{3}\] [^\n]+\n([\s\S]*?)\nแหล่งอ้างอิง:/)?.[1];
  const long = !briefAnalysis && body.length > 850;
  const preview = technicalAnalysis ? body.split('\n\n## Evidence')[0] : oldKB || body;
  const excerpt = preview.length > 650 ? preview.slice(0, 650) + '…' : preview;
  return <div className="chat-answer">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{long ? excerpt : body}</ReactMarkdown>
    {references && <details className="chat-details chat-citations">
      <summary>แหล่งอ้างอิงจาก KB</summary>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{references[1]}</ReactMarkdown>
    </details>}
    {long && <details className="chat-details"><summary>รายละเอียดและคำตอบฉบับเต็ม</summary>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </details>}
    {onAnalyze && (briefAnalysis || technicalAnalysis || canAnalyze) && <div className="soc-analysis-actions">
      <button type="button" disabled={disabled} onClick={() => onAnalyze(briefAnalysis || technicalAnalysis)}>
        {briefAnalysis || technicalAnalysis ? 'ดูรายละเอียดทางเทคนิค' : 'วิเคราะห์ Log'}
      </button>
      {!briefAnalysis && !technicalAnalysis && <small>ตรวจเฉพาะ Log ของบริษัทคุณ เมื่อกดปุ่มนี้</small>}
    </div>}
  </div>;
}
