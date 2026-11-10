const API_URL = '/api';
export const getToken = () => sessionStorage.getItem('demo_token');
export const api = async (path, options = {}) => {
  const token = getToken();
  const response = await fetch(API_URL + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}), ...options.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const { detail } = await response.json();
      if (typeof detail === 'string') message = detail;
      else if (Array.isArray(detail)) message = detail.map(item => item.msg).join('; ');
    } catch { /* Keep a readable fallback for proxy/network errors. */ }
    if (response.status === 401 && token && token === getToken()) {
      sessionStorage.removeItem('demo_token');
      window.dispatchEvent(new Event('demo-session-expired'));
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
};
export const getTickets = (companyId, signal) => api('/tickets/' + (companyId ? '?company_id=' + encodeURIComponent(companyId) : ''), { signal });
export const createTicket = data => api('/tickets/', { method: 'POST', body: JSON.stringify(data) });
export const updateTicketStatus = (id, status) => api('/tickets/' + id + '/status', { method: 'PATCH', body: JSON.stringify({ status }) });
export const assignTicket = (id, assignee_id) => api('/tickets/' + id + '/assign', { method: 'PATCH', body: JSON.stringify({ assignee_id }) });
