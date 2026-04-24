export const API_BASE_URL = "http://small-business-system.onrender.com";

// =========================
// Auth tokens
// =========================
export function getToken() {
  return sessionStorage.getItem("token");
}

export function setToken(token) {
  sessionStorage.setItem("token", token);
}

export function clearToken() {
  sessionStorage.removeItem("token");
}

export function getRefreshToken() {
  return localStorage.getItem("refresh_token");
}

export function setRefreshToken(token) {
  if (!token) {
    localStorage.removeItem("refresh_token");
    return;
  }
  localStorage.setItem("refresh_token", token);
}

export function clearRefreshToken() {
  localStorage.removeItem("refresh_token");
}

export function clearAuth() {
  clearToken();
  clearRefreshToken();
}

// =========================
// Active company (multi-empresa)
// =========================
const ACTIVE_COMPANY_KEY = "active_company_id";

export function getActiveCompanyId() {
  const v = localStorage.getItem(ACTIVE_COMPANY_KEY);
  return v ? Number(v) : null;
}

export function setActiveCompanyId(companyId) {
  if (companyId == null) {
    localStorage.removeItem(ACTIVE_COMPANY_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_COMPANY_KEY, String(companyId));
}

export function clearActiveCompanyId() {
  localStorage.removeItem(ACTIVE_COMPANY_KEY);
}

export function resolveApiUrl(pathOrUrl) {
  if (!pathOrUrl) return "";
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;

  const p = String(pathOrUrl);
  const normalized = p.startsWith("/") ? p : `/${p}`;
  return `${API_BASE_URL}${normalized}`;
}

function isFormData(value) {
  return typeof FormData !== "undefined" && value instanceof FormData;
}

async function parseResponse(res) {
  const contentType = res.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }

  const text = await res.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

let refreshPromise = null;

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("Sessão expirada. Faça login novamente.");
  }

  refreshPromise = (async () => {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const data = await parseResponse(res);

    if (!res.ok || !data?.access_token) {
      clearAuth();
      throw new Error(data?.detail || "Sessão expirada. Faça login novamente.");
    }

    setToken(data.access_token);
    if (data.refresh_token) {
      setRefreshToken(data.refresh_token);
    }

    return data.access_token;
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function request(path, { method = "GET", body, _retry = true } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const activeCompanyId = getActiveCompanyId();
  if (activeCompanyId) headers["X-Company-Id"] = String(activeCompanyId);

  const init = { method, headers };

  if (body !== undefined) {
    if (isFormData(body)) {
      init.body = body;
    } else {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
  }

  let res = await fetch(`${API_BASE_URL}${path}`, init);

  if (res.status === 401 && _retry) {
    try {
      const newAccessToken = await refreshAccessToken();

      const retryHeaders = { ...headers, Authorization: `Bearer ${newAccessToken}` };
      const retryInit = { ...init, headers: retryHeaders };

      res = await fetch(`${API_BASE_URL}${path}`, retryInit);
    } catch (e) {
      clearAuth();
      throw e;
    }
  }

  const data = await parseResponse(res);

  if (!res.ok) {
    const msg =
      data?.detail ||
      data?.message ||
      (typeof data === "string" ? data : null) ||
      `Erro ${res.status}`;

    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

async function requestFile(path, { method = "GET", _retry = true } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const activeCompanyId = getActiveCompanyId();
  if (activeCompanyId) headers["X-Company-Id"] = String(activeCompanyId);

  let res = await fetch(`${API_BASE_URL}${path}`, { method, headers });

  if (res.status === 401 && _retry) {
    try {
      const newAccessToken = await refreshAccessToken();
      const retryHeaders = { ...headers, Authorization: `Bearer ${newAccessToken}` };
      res = await fetch(`${API_BASE_URL}${path}`, { method, headers: retryHeaders });
    } catch (e) {
      clearAuth();
      throw e;
    }
  }

  if (!res.ok) {
    let msg = `Erro ${res.status}`;
    try {
      msg = await res.text();
    } catch {}
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }

  return await res.blob();
}

export const api = {
  // =========================
  // Auth
  // =========================
  login: async (email, password) => {
    const data = await request("/auth/login", { method: "POST", body: { email, password } });
    if (data?.access_token) setToken(data.access_token);
    if (data?.refresh_token) setRefreshToken(data.refresh_token);
    return data;
  },

  register: async (name, email, password, company_slug) => {
    let company = null;

    try {
      company = await request(`/company/by-slug/${encodeURIComponent(company_slug)}`);
    } catch {
      try {
        company = await request("/company/me");
      } catch {
        company = null;
      }
    }

    const company_id = company?.id;
    if (!company_id) {
      throw new Error(
        "Não consegui identificar a empresa pelo URL. Precisamos criar o endpoint /company/by-slug/{slug}."
      );
    }

    return request("/auth/register", {
      method: "POST",
      body: { name, email, password, company_id },
    });
  },

  logout: () => {
    clearAuth();
    clearActiveCompanyId();
  },

  me: () => request("/me"),

  // =========================
  // Multi-company
  // =========================
  listMyCompanies: () => request("/companies/mine"),

  setActiveCompany: async (companyId) => {
    setActiveCompanyId(companyId);

    try {
      return await request("/company/me");
    } catch (e) {
      clearActiveCompanyId();
      throw e;
    }
  },

  // =========================
  // Company
  // =========================
  getMyCompany: () => request("/company/me"),

  uploadCompanyLogo: async (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/company/logo", { method: "POST", body: form });
  },

  updateMyCompany: (payload) => request("/company/me", { method: "PUT", body: payload }),

  // =========================
  // Clients
  // =========================
  listClients: () => request("/clients"),
  createClient: (payload) => request("/clients", { method: "POST", body: payload }),
  updateClient: (id, payload) => request(`/clients/${id}`, { method: "PUT", body: payload }),
  deleteClient: (id) => request(`/clients/${id}`, { method: "DELETE" }),
  bulkDeleteClients: (payload) => request("/clients/bulk", { method: "DELETE", body: payload }),

  generateContractVisits: (clientId, replace = true) =>
    request(`/clients/${clientId}/contract-visits?replace=${replace ? "true" : "false"}`, {
      method: "POST",
    }),

  renewContract: (clientId, payload) =>
    request(`/clients/${clientId}/contract/renew`, { method: "POST", body: payload }),

  // =========================
  // Services
  // =========================
  listServices: () => request("/services"),
  createService: (payload) => request("/services", { method: "POST", body: payload }),
  updateService: (id, payload) => request(`/services/${id}`, { method: "PUT", body: payload }),
  deleteService: (id) => request(`/services/${id}`, { method: "DELETE" }),

  // =========================
  // Appointments
  // =========================
  listAppointments: () => request("/appointments"),
  createAppointment: (payload) => request("/appointments", { method: "POST", body: payload }),
  updateAppointment: (id, payload) => request(`/appointments/${id}`, { method: "PUT", body: payload }),
  deleteAppointment: (id) => request(`/appointments/${id}`, { method: "DELETE" }),
  bulkDeleteAppointments: (payload) => request("/appointments/bulk", { method: "DELETE", body: payload }),
  syncAppointmentGoogle: (id) => request(`/appointments/${id}/sync-google`, { method: "POST" }),

  // =========================
  // Dashboard
  // =========================
  getDashboardSummary: (year, month) => {
    const params = {};
    if (year != null) params.year = year;
    if (month != null) params.month = month;

    const qs = new URLSearchParams(params).toString();
    return request(`/dashboard/summary${qs ? `?${qs}` : ""}`);
  },

  getGroupDashboard: (year, month) => {
    const params = {};
    if (year != null) params.year = year;
    if (month != null) params.month = month;

    const qs = new URLSearchParams(params).toString();
    return request(`/group/dashboard${qs ? `?${qs}` : ""}`);
  },

  // =========================
  // Expenses
  // =========================
  listExpenses: () => request("/expenses"),
  createExpense: (payload) => request("/expenses", { method: "POST", body: payload }),
  updateExpense: (id, payload) => request(`/expenses/${id}`, { method: "PUT", body: payload }),
  deleteExpense: (id) => request(`/expenses/${id}`, { method: "DELETE" }),

  // =========================
  // Manual Invoices
  // =========================
  listManualInvoices: () => request("/manual-invoices"),
  getManualInvoice: (id) => request(`/manual-invoices/${id}`),
  createManualInvoice: (payload) => request("/manual-invoices", { method: "POST", body: payload }),
  updateManualInvoice: (id, payload) => request(`/manual-invoices/${id}`, { method: "PUT", body: payload }),
  deleteManualInvoice: (id) => request(`/manual-invoices/${id}`, { method: "DELETE" }),
  updateManualInvoiceStatus: (id, status) =>
    request(`/manual-invoices/${id}/status`, { method: "PATCH", body: { status } }),

  uploadManualInvoicePdf: async (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/manual-invoices/${id}/pdf`, { method: "POST", body: form });
  },

  // =========================
  // Audit
  // =========================
  listAuditLogs: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/audit-logs${qs ? `?${qs}` : ""}`);
  },

  getUser: async (id) => {
    try {
      return await request(`/users/${id}`);
    } catch {
      return null;
    }
  },

  // =========================
  // Stock (CRUD)
  // =========================
  listStockItems: () => request("/stock"),
  createStockItem: (payload) => request("/stock", { method: "POST", body: payload }),
  updateStockItem: (id, payload) => request(`/stock/${id}`, { method: "PUT", body: payload }),
  deleteStockItem: (id) => request(`/stock/${id}`, { method: "DELETE" }),
  moveStockItem: (id, payload) => request(`/stock/${id}/move`, { method: "POST", body: payload }),

    // =========================
  // Reports
  // =========================
  openVisitsPdf: async (year, month) => {
    const params = new URLSearchParams();
    if (year != null) params.set("year", String(year));
    if (month != null) params.set("month", String(month));

    const blob = await requestFile(`/reports/visits.pdf?${params.toString()}`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  openStockPdf: async ({ only_restock = false, threshold = null, q = "" } = {}) => {
    const params = new URLSearchParams();
    if (only_restock) params.set("only_restock", "true");
    if (threshold != null) params.set("threshold", String(threshold));
    if (q) params.set("q", q);

    const blob = await requestFile(`/reports/stock.pdf?${params.toString()}`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  openClientsPdf: async ({ contract_only = false } = {}) => {
    const params = new URLSearchParams();
    if (contract_only) params.set("contract_only", "true");

    const blob = await requestFile(`/reports/clients.pdf?${params.toString()}`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  openExpensesPdf: async (year, month) => {
    const params = new URLSearchParams();
    params.set("year", String(year));
    params.set("month", String(month ?? 0));

    const blob = await requestFile(`/reports/expenses.pdf?${params.toString()}`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  openPendingInvoicesPdf: async ({ year = null, month = null, invoice_kind = null } = {}) => {
    const params = new URLSearchParams();

    if (year != null) params.set("year", String(year));
    if (month != null) params.set("month", String(month));
    if (invoice_kind != null) params.set("invoice_kind", invoice_kind);

    const blob = await requestFile(`/reports/pending-invoices.pdf?${params.toString()}`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  openClientPendingInvoicesAviPdf: async (clientId, { year = null, month = null, invoice_kind = null } = {}) => {
    const params = new URLSearchParams();

    if (year != null) params.set("year", String(year));
    if (month != null) params.set("month", String(month));
    if (invoice_kind != null) params.set("invoice_kind", invoice_kind);

    const qs = params.toString();
    const path = `/reports/client/${clientId}/pending-invoices-avi.pdf${qs ? `?${qs}` : ""}`;

    const blob = await requestFile(path);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  // =========================
  // Site Maps / Monitoring
  // =========================
  listClientSiteMaps: (clientId) => request(`/site-maps/client/${clientId}`),
  getSiteMap: (mapId) => request(`/site-maps/${mapId}`),
  createSiteMap: (formData) => request("/site-maps", { method: "POST", body: formData }),
  updateSiteMap: (mapId, payload) => request(`/site-maps/${mapId}`, { method: "PUT", body: payload }),
  deleteSiteMap: (mapId) => request(`/site-maps/${mapId}`, { method: "DELETE" }),
  listMapPoints: (mapId) => request(`/site-maps/${mapId}/points`),
  createMapPoint: (mapId, payload) => request(`/site-maps/${mapId}/points`, { method: "POST", body: payload }),
  updateMapPoint: (pointId, payload) => request(`/site-maps/points/${pointId}`, { method: "PUT", body: payload }),
  deleteMapPoint: (pointId) => request(`/site-maps/points/${pointId}`, { method: "DELETE" }),
  listMonitoringVisitsByClient: (clientId) => request(`/site-maps/visits/client/${clientId}`),
  getMonitoringVisit: (visitId) => request(`/site-maps/visits/${visitId}`),
  createMonitoringVisit: (payload) => request(`/site-maps/visits`, { method: "POST", body: payload }),
  updateMonitoringVisit: (visitId, payload) => request(`/site-maps/visits/${visitId}`, { method: "PUT", body: payload }),

  openSiteMapPdf: async (mapId) => {
    const blob = await requestFile(`/site-maps/${mapId}/pdf`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  openMonitoringVisitPdf: async (visitId) => {
    const blob = await requestFile(`/site-maps/visits/${visitId}/pdf`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  // =========================
  // Admin Permissions (antigo)
  // =========================
  getPermissions: () => request("/admin/permissions"),
  updatePermissions: (payload) => request("/admin/permissions", { method: "PUT", body: payload }),

  // =========================
  // Permissions (novo)
  // =========================
  getCompanyPermissions: () => request("/permissions/company"),

  updateCompanyPermissions: (permissions) =>
    request("/permissions/company", {
      method: "PUT",
      body: { permissions },
    }),

  getUserPermissions: (userId) => request(`/permissions/user/${userId}`),

  updateUserPermissions: (userId, permissions) =>
    request(`/permissions/user/${userId}`, {
      method: "PUT",
      body: { permissions },
    }),

  deleteUserPermissions: (userId) =>
    request(`/permissions/user/${userId}`, {
      method: "DELETE",
    }),

  updateUserRole: (userId, role) =>
    request(`/permissions/user/${userId}/role`, {
      method: "PUT",
      body: { role },
    }),

  getMyPermissions: () => request("/permissions/me"),

  // =========================
  // Admin Users
  // =========================
  listCompanyUsers: () => request("/admin/users"),
  createStaff: (payload) => request("/admin/users", { method: "POST", body: payload }),

  // =========================
  // Dossier (Cliente)
  // =========================
  openClientDossierPdf: async (clientId) => {
    const blob = await requestFile(`/clients/${clientId}/dossier.pdf`);
    const url = URL.createObjectURL(blob);
    const win = window.open("", "_blank");
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },
};