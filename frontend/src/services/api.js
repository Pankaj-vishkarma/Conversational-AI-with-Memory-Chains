const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:20373";

function getToken() {
  return localStorage.getItem('token');
}

function headers(json = true) {
  const h = {};
  if (json) h['Content-Type'] = 'application/json';

  const token = getToken();
  if (token) h['Authorization'] = `Bearer ${token}`;

  return h;
}

async function request(method, path, body = null) {
  const opts = { method, headers: headers(!!body) };

  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);

  if (res.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err.message || err.error || 'Request failed');
  }

  if (res.status === 204) {
    return null;
  }

  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// Auth
export function register(data) {
  return request('POST', '/api/auth/register', data);
}

export function login(data) {
  return request('POST', '/api/auth/login', data);
}

export function logout() {
  return request('POST', '/api/auth/logout', {});
}

// Conversations
export function getConversations() {
  return request('GET', '/api/conversations/');
}

export function createConversation(data) {
  return request('POST', '/api/conversations/', data || {});
}

export function deleteConversation(conversationId) {
  return request('DELETE', `/api/conversations/${conversationId}`);
}

// Messages
export function getMessages(conversationId) {
  return request('GET', `/api/messages/${conversationId}`);
}

export function sendMessage(data) {
  return request('POST', '/api/messages/', data);
}

// Memory
export function getEntities(conversationId) {
  return request('GET', `/api/memory/${conversationId}/entities`);
}

export function getGraph(conversationId) {
  return request('GET', `/api/memory/${conversationId}/graph`);
}

export function getSummary(conversationId) {
  return request('GET', `/api/memory/${conversationId}/summary`);
}

export function getTokens(conversationId) {
  return request('GET', `/api/memory/${conversationId}/tokens`);
}

export function getMemoryCompare(conversationId) {
  return request('GET', `/api/memory/compare/${conversationId}`);
}

// Export
export function exportConversation(conversationId) {
  return request('GET', `/api/export/${conversationId}`);
}

// Personas
export function getPersonas() {
  return request('GET', '/api/personas');
}
