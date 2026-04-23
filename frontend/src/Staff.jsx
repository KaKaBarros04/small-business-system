import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { useNavigate, useOutletContext } from "react-router-dom";
import "./Staff.css";

function normalize(s) {
  return String(s || "").trim().toLowerCase();
}

export default function Staff() {
  const navigate = useNavigate();
  const { user, company } = useOutletContext() || {};

  const isAdmin = ["ADMIN", "GROUP_ADMIN"].includes((user?.role || "").toUpperCase());

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [changingRoleId, setChangingRoleId] = useState(null);

  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [q, setQ] = useState("");

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
  });

  async function load() {
    setLoading(true);
    setMsg("");
    setErr("");
    try {
      const data = await api.listCompanyUsers();
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.message || "Erro ao carregar funcionários.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const qq = normalize(q);
    if (!qq) return rows;

    return rows.filter((r) => {
      const hay = `${r.name || ""} ${r.email || ""} ${r.role || ""} ${r.id || ""}`.toLowerCase();
      return hay.includes(qq);
    });
  }, [rows, q]);

  function onChangeField(key, val) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  function resetForm() {
    setForm({
      name: "",
      email: "",
      password: "",
    });
  }

  async function onCreate(e) {
    e.preventDefault();
    if (!isAdmin) return;

    setMsg("");
    setErr("");

    const name = form.name.trim();
    const email = form.email.trim();
    const password = form.password;

    if (name.length < 2) {
      setErr("Nome muito curto.");
      return;
    }
    if (!email.includes("@")) {
      setErr("Email inválido.");
      return;
    }
    if (password.length < 6) {
      setErr("Password deve ter no mínimo 6 caracteres.");
      return;
    }

    setSaving(true);

    try {
      await api.createStaff({ name, email, password });
      resetForm();
      setMsg("✅ Funcionário criado com sucesso.");
      await load();
    } catch (e2) {
      setErr(e2?.message || "Erro ao criar funcionário.");
    } finally {
      setSaving(false);
    }
  }

  async function onChangeRole(userId, nextRole) {
    if (!isAdmin) return;

    setMsg("");
    setErr("");
    setChangingRoleId(userId);

    try {
      await api.updateUserRole(userId, nextRole);
      setRows((prev) =>
        prev.map((u) =>
          u.id === userId
            ? { ...u, role: nextRole }
            : u
        )
      );
      setMsg("✅ Role atualizada com sucesso.");
    } catch (e) {
      setErr(e?.message || "Erro ao atualizar role.");
      await load();
    } finally {
      setChangingRoleId(null);
    }
  }

  function goToPermissions(userId) {
    const slug = company?.slug || "";
    if (!slug) return;

    navigate(`/${slug}/app/permissoes?userId=${userId}`);
  }

  return (
    <div className="card-cliente">
      <div className="clientsTop">
        <div>
          <h2 className="clientsTitle">Funcionários</h2>
          <div className="status">
            Criar e gerir utilizadores da empresa. Por padrão, novos utilizadores entram como <b>STAFF</b>.
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <input
            className="input"
            placeholder="Pesquisar (nome/email/role/id)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ minWidth: 260 }}
          />

          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "A atualizar..." : "Atualizar"}
          </button>
        </div>
      </div>

      {msg ? <div className="msg ok">{msg}</div> : null}
      {err ? <div className="msg error">{err}</div> : null}

      <form onSubmit={onCreate} className="card" style={{ padding: 12, marginBottom: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 10 }}>
          <div>
            <div className="label">Nome</div>
            <input
              className="input"
              value={form.name}
              onChange={(e) => onChangeField("name", e.target.value)}
              placeholder="Ex: João Silva"
              disabled={!isAdmin || saving}
            />
          </div>

          <div>
            <div className="label">Email</div>
            <input
              className="input"
              value={form.email}
              onChange={(e) => onChangeField("email", e.target.value)}
              placeholder="ex: joao@email.com"
              disabled={!isAdmin || saving}
            />
          </div>

          <div>
            <div className="label">Password</div>
            <input
              className="input"
              type="password"
              value={form.password}
              onChange={(e) => onChangeField("password", e.target.value)}
              placeholder="mínimo 6 caracteres"
              disabled={!isAdmin || saving}
            />
          </div>

          <div style={{ display: "flex", alignItems: "end" }}>
            <button className="btn btn-primary" type="submit" disabled={!isAdmin || saving}>
              {saving ? "A criar..." : "Criar"}
            </button>
          </div>
        </div>

        {!isAdmin ? (
          <div className="status" style={{ marginTop: 10 }}>
            Apenas ADMIN pode criar funcionários.
          </div>
        ) : null}
      </form>

      <div className="card" style={{ padding: 12 }}>
        <div className="status" style={{ marginTop: 0 }}>
          Total: <b>{filtered.length}</b>
        </div>

        {loading ? (
          <div className="status">A carregar...</div>
        ) : filtered.length === 0 ? (
          <div className="status">Nenhum funcionário encontrado.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>Nome</th>
                  <th style={{ textAlign: "left" }}>Email</th>
                  <th style={{ textAlign: "left" }}>Role</th>
                  <th style={{ textAlign: "left" }}>ID</th>
                  <th style={{ textAlign: "left" }}>Ações</th>
                </tr>
              </thead>

              <tbody>
                {filtered.map((u) => {
                  const isMe = Number(u.id) === Number(user?.id);
                  const busy = changingRoleId === u.id;

                  return (
                    <tr key={u.id}>
                      <td>{u.name || "—"}</td>
                      <td>{u.email || "—"}</td>

                      <td>
                        {isAdmin ? (
                          <select
                            className="input"
                            value={(u.role || "STAFF").toUpperCase()}
                            onChange={(e) => onChangeRole(u.id, e.target.value)}
                            disabled={busy || (isMe && (u.role || "").toUpperCase() === "ADMIN")}
                            style={{ minWidth: 120 }}
                            title={
                              isMe && (u.role || "").toUpperCase() === "ADMIN"
                                ? "Não podes trocar o teu próprio role aqui"
                                : ""
                            }
                          >
                            <option value="STAFF">STAFF</option>
                            <option value="ADMIN">ADMIN</option>
                          </select>
                        ) : (
                          <span>{u.role || "—"}</span>
                        )}
                      </td>

                      <td>{u.id}</td>

                      <td>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button
                            className="btn"
                            type="button"
                            onClick={() => goToPermissions(u.id)}
                            disabled={!isAdmin}
                          >
                            Permissões
                          </button>

                          {busy ? <span className="status">A guardar...</span> : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}