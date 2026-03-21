const BASE = "/api";

function getToken() { return localStorage.getItem("bb_token"); }

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  signup:           (data) => request("POST", "/auth/signup", data),
  login:            (data) => request("POST", "/auth/login",  data),
  me:               ()     => request("GET",  "/auth/me"),
  getBusiness:      ()     => request("GET",  "/business"),
  updateBusiness:   (data) => request("PATCH","/business",    data),
  getKnowledge:     ()     => request("GET",  "/business/knowledge"),
  chat:             (data) => request("POST", "/chat",         data),
  listConversations:()     => request("GET",  "/chat/conversations"),
  getConversation:  (id)   => request("GET",  `/chat/conversations/${id}`),
  getSnapshot:      ()     => request("GET",  "/business/snapshot"),
  generateTest:     ()     => request("POST", "/business/test/generate"),
  scoreTest:        (data) => request("POST", "/business/test/score", data),
  listDocuments:    ()     => request("GET",  "/documents"),
  getDocument:      (id)   => request("GET",  `/documents/${id}`),
  deleteDocument:   (id)   => request("DELETE",`/documents/${id}`),
};

export const billingApi = {
  status:   ()     => request("GET",  "/billing/status"),
  checkout: (plan) => request("POST", "/billing/checkout", { plan }),
  portal:   ()     => request("POST", "/billing/portal"),
};

export const teamApi = {
  listMembers: ()            => request("GET",    "/team/members"),
  listInvites: ()            => request("GET",    "/team/invites"),
  invite:    (email, role)   => request("POST",   "/team/invite",  { email, role }),
  getInvite:   (token)       => request("GET",    `/team/invite/${token}`),
  acceptInvite:(token, data) => request("POST",   `/team/invite/${token}/accept`, data),
  removeMember:(id)          => request("DELETE", `/team/members/${id}`),
};

export const integrationApi = {
  list:         ()     => request("GET",    "/integrations"),
  connectEmail: (data) => request("POST",   "/integrations/email", data),
  connectSlack: (data) => request("POST",   "/integrations/slack", data),
  sync:         (id)   => request("POST",   `/integrations/${id}/sync`),
  remove:       (id)   => request("DELETE", `/integrations/${id}`),
};

export async function uploadDocument(file) {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/documents`, { method:"POST", headers, body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function saveToken(token)  { localStorage.setItem("bb_token", token); }
export function clearToken()      { localStorage.removeItem("bb_token"); }
export function hasToken()        { return !!getToken(); }
