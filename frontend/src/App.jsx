import { useEffect, useMemo, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams,
  NavLink,
  Outlet,
} from "react-router-dom";

import Login from "./Login";
import { api, clearToken, getToken, resolveApiUrl } from "./api";
import { parseJwt } from "./auth/auth";

import Clients from "./Clients";
import Appointments from "./Appointments";
import Schedule from "./Schedule";
import Dashboard from "./Dashboard";
import VendorInvoices from "./manual_invoices";
import Expenses from "./Expenses";
import AuditLogs from "./Auditlogs";
import GroupDashboard from "./GroupDashboard";
import Stock from "./Stock";
import Permissions from "./Permissions";
import Staff from "./Staff";
import MonitoringMaps from "./MonitoringMaps";

import "./App.css";

/** Protege rotas de empresa */
function RequireCompanyAuth({ children }) {
  const token = getToken();
  const { companySlug } = useParams();

  if (!token) return <Navigate to={`/${companySlug}/login`} replace />;

  const payload = parseJwt(token);
  if (payload?.role === "GROUP_ADMIN") return <Navigate to="/group/app" replace />;

  return children;
}

/** Protege rotas do grupo */
function RequireGroup({ children }) {
  const token = getToken();
  if (!token) return <Navigate to="/group/login" replace />;

  const payload = parseJwt(token);
  if (payload?.role !== "GROUP_ADMIN") {
    return <Navigate to="/empresa-a/login" replace />;
  }

  return children;
}

/** Protege rotas apenas ADMIN (empresa) */
function RequireAdmin({ children }) {
  const token = getToken();
  const { companySlug } = useParams();

  if (!token) return <Navigate to={`/${companySlug}/login`} replace />;

  const payload = parseJwt(token);
  if ((payload?.role || "").toUpperCase() !== "ADMIN") {
    return <Navigate to={`/${companySlug}/app/dashboard`} replace />;
  }

  return children;
}

/** Protege módulo só para Desinfex */
function RequireDesinfex({ children }) {
  const { companySlug } = useParams();

  if ((companySlug || "").toLowerCase() !== "desinfex") {
    return <Navigate to={`/${companySlug}/app/dashboard`} replace />;
  }

  return children;
}

/** Theme hook */
function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "system");

  useEffect(() => {
    if (theme === "system") {
      document.documentElement.removeAttribute("data-theme");
      localStorage.removeItem("theme");
    } else {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
    }
  }, [theme]);

  return { theme, setTheme };
}

function ShellTopbar({ left, right }) {
  return (
    <header className="topbar">
      <div className="topbar-left">{left}</div>
      <div className="topbar-right">{right}</div>
    </header>
  );
}

function ThemeSwitch({ theme, setTheme }) {
  return (
    <div className="themeSwitch" role="group" aria-label="Tema">
      <button
        className={`tbtn ${theme === "light" ? "active" : ""}`}
        onClick={() => setTheme("light")}
        aria-pressed={theme === "light"}
        title="Claro"
      >
        ☀️
      </button>
      <button
        className={`tbtn ${theme === "dark" ? "active" : ""}`}
        onClick={() => setTheme("dark")}
        aria-pressed={theme === "dark"}
        title="Escuro"
      >
        🌙
      </button>
      <button
        className={`tbtn ${theme === "system" ? "active" : ""}`}
        onClick={() => setTheme("system")}
        aria-pressed={theme === "system"}
        title="Sistema"
      >
        ⚙️
      </button>
      <span className={`tthumb pos-${theme}`} aria-hidden="true" />
    </div>
  );
}

/** Sidebar (Empresa) */
function CompanySidebar({ companySlug, user, staffPermissions }) {
  const role = (user?.role || "").toUpperCase();
  const isAdmin = role === "ADMIN";
  const isDesinfex = (companySlug || "").toLowerCase() === "desinfex";

  const can = (module, action) => {
    if (isAdmin) return true;
    return staffPermissions?.[module]?.[action] === true;
  };

  const items = useMemo(() => {
    const all = [
      { to: `/${companySlug}/app/dashboard`, label: "Dashboard", icon: "📊" },

      { to: `/${companySlug}/app/clientes`, label: "Clientes", icon: "👥", perm: { module: "clients", action: "read" } },

      ...(isDesinfex
        ? [{ to: `/${companySlug}/app/mapas`, label: "Mapas", icon: "🗺️", perm: { module: "clients", action: "read" } }]
        : []),

      { to: `/${companySlug}/app/agendamentos`, label: "Agendamentos", icon: "📅", perm: { module: "appointments", action: "read" } },

      { to: `/${companySlug}/app/agenda`, label: "Agenda", icon: "🗓️", perm: { module: "schedule", action: "read" } },

      { to: `/${companySlug}/app/faturas`, label: "Faturas", icon: "💳", perm: { module: "invoices", action: "read" } },

      { to: `/${companySlug}/app/despesas`, label: "Despesas", icon: "💸", perm: { module: "expenses", action: "read" } },

      { to: `/${companySlug}/app/auditoria`, label: "Auditoria", icon: "🧾", perm: { module: "audit", action: "read" } },

      { to: `/${companySlug}/app/stock`, label: "Stock", icon: "📦", perm: { module: "stock", action: "read" } },
    ];

    const filtered = all.filter((it) => {
      if (!it.perm) return true;
      return can(it.perm.module, it.perm.action);
    });

    if (isAdmin) {
      filtered.push({ to: `/${companySlug}/app/funcionarios`, label: "Funcionários", icon: "👤" });
      filtered.push({ to: `/${companySlug}/app/permissoes`, label: "Permissões", icon: "🔐" });
    }

    return filtered;
  }, [companySlug, isAdmin, isDesinfex, staffPermissions]);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-dot" aria-hidden="true" />
        <div className="sidebar-title">
          <div className="sidebar-name">Painel</div>
          <div className="sidebar-sub">{companySlug}</div>
        </div>
      </div>

      <nav className="nav" aria-label="Menu">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            end
          >
            <span className="nav-icn" aria-hidden="true">
              {it.icon}
            </span>
            <span>{it.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="hint">Small Business System</div>
      </div>
    </aside>
  );
}

/** Sidebar (Grupo) */
function GroupSidebar() {
  const items = useMemo(() => [{ to: `/group/app/dashboard`, label: "Dashboard", icon: "🧠" }], []);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-dot" aria-hidden="true" />
        <div className="sidebar-title">
          <div className="sidebar-name">Grupo</div>
          <div className="sidebar-sub">Admin</div>
        </div>
      </div>

      <nav className="nav" aria-label="Menu">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            end
          >
            <span className="nav-icn" aria-hidden="true">
              {it.icon}
            </span>
            <span>{it.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

/** Layout Empresa */
function CompanyLayout() {
  const { companySlug } = useParams();
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  const [user, setUser] = useState(null);
  const [company, setCompany] = useState(null);
  const [staffPermissions, setStaffPermissions] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.setAttribute("data-brand", companySlug || "default");
  }, [companySlug]);

  async function loadAll() {
    setLoading(true);
    try {
      const [me, myCompany] = await Promise.all([api.me(), api.getMyCompany()]);
      setUser(me);
      setCompany(myCompany);

      if (myCompany?.slug && companySlug && myCompany.slug !== companySlug) {
        navigate(`/${myCompany.slug}/app/dashboard`, { replace: true });
      }

      const role = (me?.role || "").toUpperCase();
      if (role !== "ADMIN") {
        try {
          const perms = await api.getMyPermissions();
          setStaffPermissions(perms?.staff_permissions || {});
        } catch {
          setStaffPermissions({});
        }
      } else {
        setStaffPermissions(null);
      }
    } catch (err) {
      clearToken();
      setUser(null);
      setCompany(null);
      setStaffPermissions(null);
      navigate(`/${companySlug}/login`, { replace: true });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companySlug]);

  function logout() {
    clearToken();
    setUser(null);
    setCompany(null);
    setStaffPermissions(null);
    navigate(`/${companySlug}/login`, { replace: true });
  }

  if (loading) return <p className="status">A carregar...</p>;

  return (
    <div className="layout">
      <CompanySidebar companySlug={companySlug} user={user} staffPermissions={staffPermissions} />

      <div className="main">
        <ShellTopbar
          left={
            <div className="brandline">
              {company?.logo_path ? (
                <img src={resolveApiUrl(company.logo_path)} alt={company.name} className="logoImg" />
              ) : (
                <div className="logoMark" aria-hidden="true" />
              )}

              <div className="brandtext">
                <div className="companyRow">
                  <span className="companyBadge">
                    <span className="dot" aria-hidden="true" />
                    <span className="companyName">{company?.name || companySlug}</span>
                  </span>
                  <span className="sep">•</span>
                  <span className="userName">{user?.name || user?.email || ""}</span>
                </div>
                <div className="subRow">Painel da empresa</div>
              </div>
            </div>
          }
          right={
            <div className="top-actions">
              <ThemeSwitch theme={theme} setTheme={setTheme} />
              <button className="btn btn-danger" onClick={logout}>
                Sair
              </button>
            </div>
          }
        />

        <main className="content">
          <Outlet context={{ company, user, staffPermissions }} />
        </main>

        <footer className="footer">
          <p>Small Business System &copy; 2026</p>
        </footer>
      </div>
    </div>
  );
}

/** Layout Grupo */
function GroupLayout() {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    document.documentElement.setAttribute("data-brand", "group");
  }, []);

  function logout() {
    clearToken();
    navigate("/empresa/login", { replace: true });
  }

  return (
    <div className="layout">
      <GroupSidebar />

      <div className="main">
        <ShellTopbar
          left={
            <div className="brandline">
              <div className="logoMark" aria-hidden="true" />
              <div className="brandtext">
                <div className="companyRow">
                  <span className="companyBadge">
                    <span className="dot" aria-hidden="true" />
                    <span className="companyName">Grupo</span>
                  </span>
                  <span className="sep">•</span>
                  <span className="userName">Dashboard Consolidado</span>
                </div>
                <div className="subRow">Visão geral das empresas</div>
              </div>
            </div>
          }
          right={
            <div className="top-actions">
              <ThemeSwitch theme={theme} setTheme={setTheme} />
              <button className="btn btn-danger" onClick={logout}>
                Sair
              </button>
            </div>
          }
        />

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** Router root */
function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/empresa-a/login" replace />} />

      <Route path="/:companySlug/login" element={<Login />} />
      <Route path="/group/login" element={<Login />} />

      {/* EMPRESA */}
      <Route
        path="/:companySlug/app"
        element={
          <RequireCompanyAuth>
            <CompanyLayout />
          </RequireCompanyAuth>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<section className="card"><Dashboard /></section>} />
        <Route path="clientes" element={<section className="card"><Clients /></section>} />

        <Route
          path="mapas"
          element={
            <RequireDesinfex>
              <section className="card"><MonitoringMaps /></section>
            </RequireDesinfex>
          }
        />

        <Route path="agendamentos" element={<section className="card"><Appointments /></section>} />
        <Route path="agenda" element={<section className="card"><Schedule /></section>} />
        <Route path="faturas" element={<section className="card"><VendorInvoices /></section>} />
        <Route path="despesas" element={<section className="card"><Expenses /></section>} />
        <Route path="auditoria" element={<section className="card"><AuditLogs /></section>} />
        <Route path="stock" element={<section className="card"><Stock /></section>} />

        <Route
          path="funcionarios"
          element={
            <RequireAdmin>
              <section className="card"><Staff /></section>
            </RequireAdmin>
          }
        />

        <Route
          path="permissoes"
          element={
            <RequireAdmin>
              <section className="card"><Permissions /></section>
            </RequireAdmin>
          }
        />
      </Route>

      {/* GRUPO */}
      <Route
        path="/group/app"
        element={
          <RequireGroup>
            <GroupLayout />
          </RequireGroup>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<section className="card"><GroupDashboard /></section>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}