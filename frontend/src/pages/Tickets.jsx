import { useCallback, useEffect, useState } from 'react';
import { getTickets, createTicket, updateTicketStatus, assignTicket } from '../services/api';
import { Plus, X, Clock, AlertCircle } from 'lucide-react';
import { UserCircle } from 'lucide-react';
import { TicketChatHistory } from '../components/PrivateChat';

const Tickets = ({ user, companyId }) => {
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [selectedTicket, setSelectedTicket] = useState(null);

    const [formData, setFormData] = useState({
        subject: '',
        description: ''
    });

    const fetchTickets = useCallback(async (signal) => {
        try {
            const data = await getTickets(companyId, signal);
            setTickets(data);
        } catch (error) {
            if (error.name !== "AbortError") setError(error.message);
        } finally {
            if (!signal?.aborted) setLoading(false);
        }
    }, [companyId]);

    useEffect(() => {
        const controller = new AbortController();
        getTickets(companyId, controller.signal)
            .then(setTickets)
            .catch(error => { if (error.name !== "AbortError") setError(error.message); })
            .finally(() => { if (!controller.signal.aborted) setLoading(false); });
        return () => controller.abort();
    }, [companyId]);

    const handleCreateSubmit = async (e) => {
        e.preventDefault();
        if (saving) return;
        setSaving(true); setError('');
        try {
            await createTicket(formData);
            setIsCreateModalOpen(false);
            setFormData({ subject: '', description: '' });
            fetchTickets();
        } catch (error) {
            setError(error.message);
        } finally { setSaving(false); }
    };

    const handleStatusChange = async (e) => {
        const newStatus = e.target.value;
        if (!selectedTicket || saving) return;
        setSaving(true); setError('');

        try {
            await updateTicketStatus(selectedTicket.id, newStatus);
            // Update the local state to reflect the change immediately
            setSelectedTicket({ ...selectedTicket, status: newStatus });
            fetchTickets();
        } catch (error) {
            setError(error.message);
        } finally { setSaving(false); }
    };

    if (loading) return <div role="status" className="p-6 text-slate-500">Loading tickets…</div>;

    return (
        <div className="p-6 relative h-full">
            {error && <p role="alert" className="text-red-700 mb-4">{error} <button onClick={() => { setError(''); setLoading(true); fetchTickets(); }}>Reload tickets</button></p>}
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-800">{user?.role === "CUSTOMER" ? "My Company Tickets" : "Company Tickets"}</h2>
                {user.role === "CUSTOMER" && <button
                    onClick={() => setIsCreateModalOpen(true)}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition shadow-sm"
                >
                    <Plus className="w-4 h-4" /> Create Ticket
                </button>}
            </div>

            {/* Ticket List Table */}
            <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
                <table className="min-w-full bg-white">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                            <th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase">Ticket Number</th>
                            <th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase">Subject</th>
                            <th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase">Status</th>
                            <th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase">Priority</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {tickets.length === 0 ? (
                            <tr>
                                <td colSpan="4" className="py-8 text-center text-slate-500 text-sm">{error ? "Tickets could not be loaded." : "No tickets found for this company."}</td>
                            </tr>
                        ) : (
                            tickets.map(ticket => (
                                <tr
                                    key={ticket.id}
                                    onClick={() => setSelectedTicket(ticket)}
                                    className="hover:bg-slate-50 transition cursor-pointer"
                                >
                                    <td className="py-3 px-4 text-blue-600 font-medium text-sm">{ticket.ticket_number}</td>
                                    <td className="py-3 px-4 text-slate-800 text-sm truncate max-w-xs">{ticket.subject}</td>
                                    <td className="py-3 px-4">
                                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide border ${
                                            ticket.status === 'RESOLVED' || ticket.status === 'CLOSED'
                                                ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                                                : ticket.status === 'IN_PROGRESS'
                                                ? 'bg-blue-100 text-blue-800 border-blue-200'
                                                : 'bg-yellow-100 text-yellow-800 border-yellow-200'
                                        }`}>
                                            {ticket.status}
                                        </span>
                                    </td>
                                    <td className="py-3 px-4">
                                        <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-800 border border-slate-200 uppercase tracking-wide">
                                            {ticket.priority}
                                        </span>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Create Ticket Modal */}
            {isCreateModalOpen && (
                <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
                        <div className="flex justify-between items-center p-4 border-b border-slate-100 bg-slate-50">
                            <h3 className="font-bold text-slate-800 text-lg">Create New Ticket</h3>
                            <button onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <form onSubmit={handleCreateSubmit} className="p-4 space-y-4">
                            {error && <p role="alert" className="text-red-700">{error}</p>}
                            <div>
                                <label className="block text-xs font-semibold text-slate-600 mb-1">Subject</label>
                                <input
                                    type="text"
                                    required
                                    maxLength={200}
                                    value={formData.subject}
                                    onChange={(e) => setFormData({...formData, subject: e.target.value})}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                                    placeholder="e.g., Server anomaly detected"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-600 mb-1">Description</label>
                                <textarea
                                    required
                                    maxLength={5000}
                                    value={formData.description}
                                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none min-h-[100px]"
                                    placeholder="Provide additional details..."
                                />
                            </div>
                            <div className="pt-4 flex justify-end gap-2">
                                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition">Cancel</button>
                                <button type="submit" disabled={saving || !formData.subject.trim() || !formData.description.trim()} className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition">Create Ticket</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Ticket Detail Modal */}
            {selectedTicket && (
                <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
                        <div className="flex justify-between items-center p-4 border-b border-slate-100 bg-slate-50">
                            <div className="flex items-center gap-3">
                                <h3 className="font-bold text-slate-800 text-lg">{selectedTicket.ticket_number}</h3>
                                <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-200 text-slate-800 uppercase tracking-wide">
                                    {selectedTicket.priority}
                                </span>
                            </div>
                            <button onClick={() => setSelectedTicket(null)} className="text-slate-400 hover:text-slate-600">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-6 overflow-y-auto flex-1 space-y-6">
                            {error && <p role="alert" className="text-red-700">{error}</p>}
                            <div>
                                <h4 className="text-xl font-bold text-slate-900 mb-2">{selectedTicket.subject}</h4>
                                <div className="flex items-center gap-4 text-xs text-slate-500">
                                    <div className="flex items-center gap-1">
                                        <Clock className="w-3.5 h-3.5" />
                                        <span>Created: {new Date(selectedTicket.created_at).toLocaleString()}</span>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <AlertCircle className="w-3.5 h-3.5" />
                                        <span>Impact: {selectedTicket.impact} | Urgency: {selectedTicket.urgency}</span>
                                    </div>
                                    <div className="flex items-center gap-1 font-semibold text-blue-600">
                                        <UserCircle className="w-3.5 h-3.5" />
                                        <span>{selectedTicket.assignee_id ? 'Assigned' : 'Unassigned'}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="p-4 bg-slate-50 rounded-lg border border-slate-100 text-sm text-slate-700 whitespace-pre-wrap">
                                {selectedTicket.description || "No additional description provided."}
                            </div>

                            <section className="p-4 bg-slate-50 rounded-lg border border-slate-100 text-sm space-y-2" aria-label="AI Assessment">
                                <h5 className="font-semibold text-slate-900">AI Assessment</h5>
                                {selectedTicket.assessment ? (
                                    <>
                                        <p><strong>Source:</strong> {{
                                            gemini: 'Gemini', fallback: 'Fallback — SOC review required', manual_override: 'Manual override',
                                        }[selectedTicket.assessment.source] || selectedTicket.assessment.source}
                                            {selectedTicket.assessment.model && ` (${selectedTicket.assessment.model})`}
                                        </p>
                                        <p><strong>Incident type:</strong> {selectedTicket.assessment.incident_type}</p>
                                        <p><strong>Reason:</strong> {selectedTicket.assessment.reason}</p>
                                        <p><strong>Recommendation:</strong> {selectedTicket.assessment.recommendation}</p>
                                        <p><strong>Priority policy:</strong> {selectedTicket.assessment.priority_policy}</p>
                                    </>
                                ) : <p>No assessment recorded for this ticket.</p>}
                            </section>

                            <TicketChatHistory key={selectedTicket.id} ticketId={selectedTicket.id} user={user}/>
                            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-600 mb-2">Update Ticket Status</label>
                                    <select disabled={saving || user?.role === "CUSTOMER"} value={selectedTicket.status}
                                        onChange={handleStatusChange}
                                        className="w-full sm:w-64 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none bg-white focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="NEW">NEW</option>
                                        <option value="IN_PROGRESS">IN PROGRESS</option>
                                        <option value="RESOLVED">RESOLVED (Stop SLA Timer)</option>
                                        <option value="PENDING">PENDING</option>
                                    </select>
                                </div>

                                {/* ปุ่ม Assign to Me จะโชว์ก็ต่อเมื่อตั๋วยังไม่มีใครรับงาน */}
                                {user?.role !== "CUSTOMER" && !selectedTicket.assignee_id && (
                                    <button
                                        onClick={async () => {
                                            if (saving) return;
                                            setSaving(true); setError('');
                                            try {
                                                await assignTicket(selectedTicket.id, user.id);
                                                fetchTickets();
                                                setSelectedTicket(null); // ปิด modal
                                            } catch (err) {
                                                setError(err.message);
                                            } finally { setSaving(false); }
                                        }}
                                        disabled={saving}
                                        className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition shadow-sm mt-5"
                                    >
                                        Assign to Me
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Tickets;
