const API_URL = '/api'; 

export const getTickets = async () => {
    const response = await fetch(`${API_URL}/tickets/`);
    if (!response.ok) throw new Error('Failed to fetch tickets');
    return response.json();
};

export const createTicket = async (ticketData) => {
    const response = await fetch(`${API_URL}/tickets/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ticketData)
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const errorMessage = errorData ? JSON.stringify(errorData.detail) : `HTTP Status ${response.status} (Network/Server Issue)`;
        throw new Error(errorMessage);
    }
    return response.json();
};
export const updateTicketStatus = async (ticketId, status) => {
    const response = await fetch(`${API_URL}/tickets/${ticketId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData ? JSON.stringify(errorData.detail) : 'Failed to update status');
    }
    return response.json();
};

export const assignTicket = async (ticketId, assigneeId) => {
    const response = await fetch(`${API_URL}/tickets/${ticketId}/assign`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignee_id: assigneeId })
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData ? JSON.stringify(errorData.detail) : 'Failed to assign ticket');
    }
    return response.json();
};