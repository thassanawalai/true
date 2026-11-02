const API_URL = '/api';
export const getToken = () => sessionStorage.getItem('demo_token');
export const api = async (path, options = {}) => {
  const response = await fetch(API_URL + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: 'Bearer ' + getToken() } : {}), ...options.headers }
  });
  if (!response.ok) throw new Error((await response.text()) || 'Request failed');
  return response.json();
};
export const getTickets = () => api('/tickets/');
export const createTicket = data => api('/tickets/', { method: 'POST', body: JSON.stringify(data) });
export const updateTicketStatus = (id, status) => api('/tickets/' + id + '/status', { method: 'PATCH', body: JSON.stringify({ status }) });
export const assignTicket = (id, assignee_id) => api('/tickets/' + id + '/assign', { method: 'PATCH', body: JSON.stringify({ assignee_id }) });
