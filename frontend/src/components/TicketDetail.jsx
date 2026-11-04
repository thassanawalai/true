import { useEffect, useRef, useState } from 'react';
import { X, Clock, MessageSquare, LockKeyhole } from 'lucide-react';
import { api, updateTicketStatus, assignTicket } from '../services/api';
import { TicketChatHistory } from './PrivateChat';
import './TicketDetail.css';

function timestamp(value) {
  if (!value) return 'ไม่ระบุ';
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z');
  return Number.isNaN(date.getTime()) ? 'ไม่ระบุ' : date.toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
}

export default function TicketDetail({ ticketId, user, onClose, onChanged }) {
  const dialog = useRef(null);
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [retry, setRetry] = useState(0);
  const internal = ['SUPPORT', 'ADMIN'].includes(user.role);
  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    api('/tickets/' + ticketId, { signal: controller.signal }).then(setTicket)
      .catch(e => { if (e.name !== 'AbortError') setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [ticketId, retry]);
  const change = async action => {
    if (saving) return;
    setSaving(true); setError('');
    try {
      await action();
      setTicket(await api('/tickets/' + ticketId));
      onChanged();
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };
  const metadata = ticket ? [
    ['Priority', ticket.priority], ['Category', ticket.category_name],
    ['Impact', ticket.impact], ['Urgency', ticket.urgency],
    ['Company', ticket.company_name], ['Requester', ticket.requester_name],
    ['Assigned Support', ticket.assignee_name || (ticket.assignee_id ? 'ไม่ระบุชื่อ' : 'ยังไม่มอบหมาย')],
    ['Created At', timestamp(ticket.created_at)], ['Updated At', timestamp(ticket.updated_at)],
  ] : [];
  return <dialog ref={dialog} className="ticket-detail" aria-labelledby="ticket-detail-title" onCancel={onClose}>
    <header className="ticket-detail-header">
      <div><p>{ticket?.ticket_number || 'Ticket Detail'}</p><h2 id="ticket-detail-title">{ticket?.subject || 'รายละเอียด Ticket'}</h2></div>
      <button onClick={onClose} aria-label="Close ticket detail"><X size={22}/></button>
    </header>
    <div className="ticket-detail-body">
      {loading && <p role="status">กำลังโหลดรายละเอียด…</p>}
      {error && <p role="alert" className="ticket-error">{error} <button disabled={saving} onClick={() => { setError(''); setLoading(true); setRetry(x => x + 1); }}>ลองอีกครั้ง</button></p>}
      {ticket && <>
        <div className="ticket-status-row"><span className={'ticket-status status-' + ticket.status}>{ticket.status.replaceAll('_', ' ')}</span><span>เวลาตามเขตเวลาของ Browser</span></div>
        <dl className="ticket-metadata">{metadata.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value || 'ไม่ระบุ'}</dd></div>)}</dl>
        <section><h3>Description</h3><p className="ticket-description">{ticket.description || 'ไม่มีรายละเอียดเพิ่มเติม'}</p></section>
        {internal && <section className="ticket-actions" aria-label="Support actions">
          <label>Update Ticket Status<select aria-label="Update Ticket Status" value={ticket.status} disabled={saving} onChange={e => change(() => updateTicketStatus(ticketId, e.target.value))}>
            {['NEW', 'IN_PROGRESS', 'PENDING', 'RESOLVED'].map(status => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}
          </select></label>
          <div>{ticket.assignee_id !== user.id && <button disabled={saving} onClick={() => change(() => assignTicket(ticketId, user.id))}>Assign to Me</button>}
            {ticket.assignee_id && <button disabled={saving} onClick={() => change(() => assignTicket(ticketId, null))}>Unassign</button>}</div>
          {saving && <p role="status">กำลังบันทึก…</p>}
        </section>}
        <section aria-label="Activity and comments"><h3>Activity / Comments</h3>
          <ol className="ticket-timeline">
            <li><Clock size={17}/><div><strong>สร้าง Ticket</strong><time>{timestamp(ticket.created_at)}</time><p>{ticket.requester_name || 'ไม่ระบุผู้แจ้ง'}</p></div></li>
            {ticket.comments.map(comment => <li key={comment.id} className={comment.is_internal ? 'internal-note' : ''}>
              {comment.is_internal ? <LockKeyhole size={17}/> : <MessageSquare size={17}/>}
              <div><strong>{comment.sender_name || 'ไม่ระบุชื่อ'}</strong><span className="comment-visibility">{comment.is_internal ? 'Internal note · SOC only' : 'Public comment'}</span><time>{timestamp(comment.created_at)}</time><p>{comment.message}</p></div>
            </li>)}
          </ol>
          {!ticket.comments.length && <p className="ticket-empty">{internal ? 'ยังไม่มีความคิดเห็นหรือบันทึกภายใน' : 'ยังไม่มีความคิดเห็นสาธารณะ'}</p>}
          <p className="ticket-empty">{internal ? 'ระบบยังไม่รองรับการเพิ่ม public comments หรือ internal notes' : 'ระบบยังไม่รองรับการตอบ public comments'}</p>
        </section>
        {(internal || ticket.requester_id === user.id) && <details className="ticket-private-chat" onToggle={e => setChatOpen(e.currentTarget.open)}>
          <summary>Private chat history · เฉพาะเจ้าของแชทและ SOC</summary>
          {chatOpen && <TicketChatHistory ticketId={ticketId} user={user}/>}
        </details>}
      </>}
    </div>
  </dialog>;
}
