import React, { useEffect, useState } from 'react';
import { getTickets, createTicket, updateTicketStatus, assignTicket } from '../services/api';
import { Plus, X, Clock, AlertCircle } from 'lucide-react';
import { UserCircle } from 'lucide-react';

const Tickets = () => {
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [selectedTicket, setSelectedTicket] = useState(null);
    
    const [formData, setFormData] = useState({
        subject: '',
        description: '',
        impact: 'MODERATE',
        urgency: 'MEDIUM'
    });

    const fetchTickets = async () => {
        try {
            const data = await getTickets();
            setTickets(data);
        } catch (error) {
            console.error("Error fetching tickets:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTickets();
    }, []);

    const handleCreateSubmit = async (e) => {
        e.preventDefault();
        try {
            await createTicket({
                ...formData,
                category_id: "00000000-0000-0000-0000-000000000000",
                company_id: "00000000-0000-0000-0000-000000000000"
            });
            setIsCreateModalOpen(false);
            setFormData({ subject: '', description: '', impact: 'MODERATE', urgency: 'MEDIUM' });
            fetchTickets(); 
        } catch (error) {
            console.error("Error creating ticket:", error);
            alert(`Failed to create ticket:\n\n${error.message}`);
        }
    };

    const handleStatusChange = async (e) => {
        const newStatus = e.target.value;
        if (!selectedTicket) return;
        
        try {
            await updateTicketStatus(selectedTicket.id, newStatus);
            // Update the local state to reflect the change immediately
            setSelectedTicket({ ...selectedTicket, status: newStatus });
            fetchTickets();
        } catch (error) {
            console.error("Error updating status:", error);
            alert(`Failed to update status:\n\n${error.message}`);
        }
    };

    if (loading) return <div className="p-6 text-slate-500">Loading data...</div>;

    return (
        <div className="p-6 relative h-full">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-800">All Tickets</h2>
                <button 
                    onClick={() => setIsCreateModalOpen(true)}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition shadow-sm"
                >
                    <Plus className="w-4 h-4" /> Create Ticket
                </button>
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
                                <td colSpan="4" className="py-8 text-center text-slate-500 text-sm">No tickets found in the system</td>
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
                            <div>
                                <label className="block text-xs font-semibold text-slate-600 mb-1">Subject</label>
                                <input 
                                    type="text" 
                                    required
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
                                    value={formData.description}
                                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none min-h-[100px]"
                                    placeholder="Provide additional details..."
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-600 mb-1">Impact</label>
                                    <select 
                                        value={formData.impact}
                                        onChange={(e) => setFormData({...formData, impact: e.target.value})}
                                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none bg-white"
                                    >
                                        <option value="EXTENSIVE">EXTENSIVE</option>
                                        <option value="SIGNIFICANT">SIGNIFICANT</option>
                                        <option value="MODERATE">MODERATE</option>
                                        <option value="MINOR">MINOR</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-600 mb-1">Urgency</label>
                                    <select 
                                        value={formData.urgency}
                                        onChange={(e) => setFormData({...formData, urgency: e.target.value})}
                                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none bg-white"
                                    >
                                        <option value="CRITICAL">CRITICAL</option>
                                        <option value="HIGH">HIGH</option>
                                        <option value="MEDIUM">MEDIUM</option>
                                        <option value="LOW">LOW</option>
                                    </select>
                                </div>
                            </div>
                            <div className="pt-4 flex justify-end gap-2">
                                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition">Cancel</button>
                                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition">Create Ticket</button>
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

                            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-600 mb-2">Update Ticket Status</label>
                                    <select 
                                        value={selectedTicket.status}
                                        onChange={handleStatusChange}
                                        className="w-full sm:w-64 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none bg-white focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="NEW">NEW (Unassigned)</option>
                                        <option value="OPEN">OPEN</option>
                                        <option value="IN_PROGRESS">IN PROGRESS</option>
                                        <option value="RESOLVED">RESOLVED (Stop SLA Timer)</option>
                                        <option value="CLOSED">CLOSED</option>
                                    </select>
                                </div>
                                
                                {/* ปุ่ม Assign to Me จะโชว์ก็ต่อเมื่อตั๋วยังไม่มีใครรับงาน */}
                                {!selectedTicket.assignee_id && (
                                    <button 
                                        onClick={async () => {
                                            try {
                                                await assignTicket(selectedTicket.id, "00000000-0000-0000-0000-000000000000"); // ส่ง dummy ID ให้ backend ไปหาตัว Support ให้อัตโนมัติ
                                                fetchTickets();
                                                setSelectedTicket(null); // ปิด modal
                                            } catch (err) {
                                                alert("Failed to assign ticket: " + err.message);
                                            }
                                        }}
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