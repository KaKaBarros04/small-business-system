import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "./api";
import "./Permissions.css";

const DEFAULT_MATRIX = {
  dashboard: { view: true },
  company: { view: true, edit: false },

  clients: { view: true, create: true, edit: true, delete: false },
  services: { view: true, create: false, edit: false, delete: false },
  appointments: { view: true, create: true, edit: true, delete: true },
  agenda: { view: true },

  invoices: { view: false, create: false, edit: false, delete: false },
  expenses: { view: false, create: false, edit: false, delete: false },
  stock: { view: false, create: false, edit: false, delete: false },

  audit: { view: false },
  employees: { view: false, create: false, edit: false, delete: false },
  permissions: { view: false, edit: false },

  site_maps: { view: true, create: true, edit: true, delete: true },
};

const MODULE_LABELS = {
  dashboard: "Dashboard",
  company: "Empresa",

  clients: "Clientes",
  services: "Serviços",
  appointments: "Agendamentos",
  agenda: "Agenda",

  invoices: "Faturas",
  expenses: "Despesas",
  stock: "Stock",

  audit: "Auditoria",
  employees: "Funcionários",
  permissions: "Permissões",

  site_maps: "Mapas / Monitorização",
};

const ACTION_LABELS = {
  view: "Ver",
  create: "Criar",
  edit: "Editar",
  delete: "Apagar",
};

function deepMerge(base, incoming) {
  const out = { ...(base || {}) };
  for (const k of Object.keys(incoming || {})) {
    const v = incoming[k];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      out[k] = deepMerge(out[k] || {}, v);
    } else {
      out[k] = v;
    }
  }
  return out;
}

export default function Permissions() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialUserIdFromUrl = searchParams.get("userId") || "";

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resettingUser, setResettingUser] = useState(false);

  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(initialUserIdFromUrl);

  const [perms, setPerms] = useState(DEFAULT_MATRIX);
  const [selectedUserRole, setSelectedUserRole] = useState("");
  const [scope, setScope] = useState("company");

  const modules = useMemo(() => Object.keys(DEFAULT_MATRIX), []);
  const actionsByModule = useMemo(() => {
    const map = {};
    for (const mod of modules) map[mod] = Object.keys(DEFAULT_MATRIX[mod] || {});
    return map;
  }, [modules]);

  async function loadUsers() {
    try {
      const data = await api.listCompanyUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.message || "Não foi possível carregar funcionários.");
    }
  }

  async function loadPermissions(userId = "") {
    setLoading(true);
    setMsg("");
    setErr("");

    try {
      if (userId) {
        const data = await api.getUserPermissions(userId);
        const merged = deepMerge(DEFAULT_MATRIX, data?.permissions || {});
        setPerms(merged);
        setSelectedUserRole(data?.role || "");
        setScope(data?.scope || "user");
      } else {
        const data = await api.getCompanyPermissions();
        const merged = deepMerge(DEFAULT_MATRIX, data?.permissions || {});
        setPerms(merged);
        setSelectedUserRole("");
        setScope("company");
      }
    } catch (e) {
      setErr(e?.message || "Não foi possível carregar permissões.");
      setPerms(DEFAULT_MATRIX);
      setSelectedUserRole("");
      setScope("company");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (!mounted) return;

      await loadUsers();
      if (!mounted) return;

      const userIdFromUrl = searchParams.get("userId") || "";
      setSelectedUserId(userIdFromUrl);
      await loadPermissions(userIdFromUrl);
    })();

    return () => {
      mounted = false;
    };
  }, []);

  function toggle(mod, action) {
    setPerms((prev) => {
      const next = structuredClone(prev);
      if (!next[mod]) next[mod] = {};
      next[mod][action] = !Boolean(next[mod][action]);
      return next;
    });
  }

  function setAllInModule(mod, value) {
    setPerms((prev) => {
      const next = structuredClone(prev);
      const actions = actionsByModule[mod] || [];
      if (!next[mod]) next[mod] = {};
      for (const a of actions) next[mod][a] = Boolean(value);
      return next;
    });
  }

  async function onChangeTarget(userId) {
    setSelectedUserId(userId);

    if (userId) {
      setSearchParams({ userId: String(userId) });
    } else {
      setSearchParams({});
    }

    await loadPermissions(userId);
  }

  async function onSave() {
    setSaving(true);
    setMsg("");
    setErr("");

    try {
      if (selectedUserId) {
        await api.updateUserPermissions(selectedUserId, perms);
        setMsg("✅ Permissões do funcionário guardadas.");
        setScope("user");
      } else {
        await api.updateCompanyPermissions(perms);
        setMsg("✅ Permissões padrão da empresa guardadas.");
        setScope("company");
      }
    } catch (e) {
      setErr(e?.message || "Erro ao guardar permissões.");
    } finally {
      setSaving(false);
    }
  }

  async function resetUserPermissions() {
    if (!selectedUserId) return;

    const ok = window.confirm("Remover permissões próprias deste funcionário e voltar ao padrão da empresa?");
    if (!ok) return;

    setResettingUser(true);
    setMsg("");
    setErr("");

    try {
      await api.deleteUserPermissions(selectedUserId);
      await loadPermissions(selectedUserId);
      setMsg("✅ O funcionário voltou a usar as permissões padrão da empresa.");
      setScope("company");
    } catch (e) {
      setErr(e?.message || "Erro ao repor permissões padrão.");
    } finally {
      setResettingUser(false);
    }
  }

  const selectedUser = users.find((u) => String(u.id) === String(selectedUserId));

  return (
    <div className="permCard">
      <div className="permTop">
        <div>
          <h2 className="permTitle">Permissões</h2>
          <p className="permSubtitle">
            Define o que cada funcionário pode fazer. O ADMIN continua com acesso total.
          </p>
        </div>

        <button className="btnPrimary" onClick={onSave} disabled={loading || saving}>
          {saving ? "A guardar..." : "Salvar"}
        </button>
      </div>

      <div className="permScopeBox">
        <label className="permTarget">
          <span className="permTargetLabel">Aplicar permissões a</span>
          <select
            className="permSelect"
            value={selectedUserId}
            onChange={(e) => onChangeTarget(e.target.value)}
            disabled={loading || saving || resettingUser}
          >
            <option value="">STAFF por defeito da empresa</option>
            {users
              .filter((u) => (u.role || "").toUpperCase() !== "GROUP_ADMIN")
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} — {u.email} ({u.role})
                </option>
              ))}
          </select>
        </label>

        {selectedUserId ? (
          <div className="permTargetInfo">
            <div>
              <strong>Funcionário:</strong> {selectedUser?.name || "—"}
            </div>
            <div>
              <strong>Role:</strong> {selectedUserRole || selectedUser?.role || "—"}
            </div>
            <div>
              <strong>Modo atual:</strong>{" "}
              {scope === "user" ? "Permissões próprias" : "Permissões padrão da empresa"}
            </div>

            <button
              className="btnGhost"
              type="button"
              onClick={resetUserPermissions}
              disabled={loading || saving || resettingUser}
            >
              {resettingUser ? "A repor..." : "Usar permissões padrão da empresa"}
            </button>
          </div>
        ) : (
          <div className="permTargetInfo">
            <div>
              <strong>Modo atual:</strong> Permissões padrão aplicadas ao STAFF sem configuração própria
            </div>
          </div>
        )}
      </div>

      {msg ? <div className="permMsg ok">{msg}</div> : null}
      {err ? <div className="permMsg error">{err}</div> : null}

      {loading ? (
        <div className="permLoading">A carregar...</div>
      ) : (
        <div className="permGrid">
          {modules.map((mod) => {
            const actions = actionsByModule[mod] || [];
            return (
              <div key={mod} className="permModule">
                <div className="permModuleHeader">
                  <div className="permModuleTitle">{MODULE_LABELS[mod] || mod}</div>

                  <div className="permModuleBulk">
                    <button
                      className="btnGhost"
                      onClick={() => setAllInModule(mod, true)}
                      type="button"
                      disabled={saving}
                    >
                      Marcar tudo
                    </button>
                    <button
                      className="btnGhost"
                      onClick={() => setAllInModule(mod, false)}
                      type="button"
                      disabled={saving}
                    >
                      Desmarcar
                    </button>
                  </div>
                </div>

                <div className="permRows">
                  {actions.map((action) => {
                    const checked = Boolean(perms?.[mod]?.[action]);
                    return (
                      <label key={action} className="permRow">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggle(mod, action)}
                          disabled={saving}
                        />
                        <span className="permRowLabel">{ACTION_LABELS[action] || action}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}