import React, { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import "./AuditLogs.css";

function fmtDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("pt-PT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function prettyEntity(entity) {
  if (!entity) return "";
  const map = {
    clients: "Clientes",
    services: "Serviços",
    appointments: "Agendamentos",
    expenses: "Despesas",
    manual_invoices: "Faturas",
    invoices: "Faturas",
    stock_items: "Stock",
    stock_movement: "Movimentos de Stock",
    company_settings: "Empresa",
    companies: "Empresas",
    users: "Utilizadores",
  };
  return map[entity] || entity;
}

function actionLabel(a) {
  const x = (a || "").toUpperCase();
  if (x === "CREATE") return "Criou";
  if (x === "UPDATE") return "Editou";
  if (x === "DELETE") return "Apagou";
  return x || "";
}

/* =========================
   Resumos “humanos”
========================= */
function labelKey(k) {
  const map = {
    scheduled_at: "Data/Hora",
    date: "Data/Hora",
    issue_date: "Data Fatura",

    category: "Categoria",
    description: "Descrição",
    notes: "Notas",
    address: "Morada",

    amount: "Valor",
    price: "Preço",
    tax_rate: "IVA",

    status: "Estado",

    supplier_name: "Cliente",
    invoice_number: "Nº Fatura",

    client_id: "Cliente",
    service_id: "Serviço",

    name: "Nome",
    business_name: "Cliente",
    sku: "SKU",
    unit: "Unidade",
    qty_on_hand: "Em stock",
    min_qty: "Mínimo",

    movement: "Movimento",
    item: "Item",
  };
  return map[k] || k;
}

function isIsoDateString(v) {
  return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v);
}

function fmtMoney(n) {
  return new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(Number(n || 0));
}

function fmtNice(v, keyHint = "") {
  if (v == null || v === "") return "—";

  if (isIsoDateString(v)) {
    const d = new Date(v);
    if (!Number.isNaN(d.getTime())) return fmtDateTime(v);
  }

  if (typeof v === "boolean") return v ? "Sim" : "Não";

  if (typeof v === "number" && Number.isFinite(v)) {
    if (["amount", "price", "total", "subtotal", "tax", "vat", "vat_paid", "vat_issued"].includes(keyHint)) {
      return fmtMoney(v);
    }
    return String(v);
  }

  if (typeof v === "string") {
    const s = v.trim();
    if (["amount", "price", "total", "subtotal", "tax", "vat", "vat_paid", "vat_issued"].includes(keyHint)) {
      const n = Number(s.replace(",", "."));
      if (Number.isFinite(n)) return fmtMoney(n);
    }
    return s;
  }

  if (typeof v === "object") {
    const id = v.id ?? v.item_id ?? v.client_id ?? v.service_id;
    const name = v.name ?? v.business_name ?? v.description ?? v.sku ?? v.invoice_number;
    if (id != null && name) return `${name} (#${id})`;
    if (name) return String(name);
    if (id != null) return `#${id}`;
    return "Detalhes";
  }

  return String(v);
}

function summarizeChange(log) {
  const action = (log.action || "").toUpperCase();

  const IGNORE = new Set([
    "id",
    "company_id",
    "user_id",
    "created_at",
    "updated_at",
    "created_by_user_id",
    "updated_by_user_id",
    "google_event_id",
    "google_sync_error",
  ]);

  const PREFER = [
    "name",
    "business_name",
    "supplier_name",
    "invoice_number",
    "issue_date",
    "scheduled_at",
    "date",
    "category",
    "description",
    "amount",
    "price",
    "status",
    "address",
    "notes",
    "sku",
    "unit",
    "qty_on_hand",
    "min_qty",
    "item",
    "movement",
  ];

  const pickTop = (obj) => {
    const keys = Object.keys(obj || {}).filter((k) => !IGNORE.has(k) && obj[k] != null && obj[k] !== "");
    keys.sort((a, b) => {
      const ai = PREFER.indexOf(a);
      const bi = PREFER.indexOf(b);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });
    return keys.slice(0, 3).map((k) => `${labelKey(k)}: ${fmtNice(obj[k], k)}`);
  };

  if (action === "CREATE") {
    const parts = pickTop(log.new_values || {});
    return parts.length ? parts.join(" • ") : "—";
  }

  if (action === "DELETE") {
    const parts = pickTop(log.old_values || {});
    return parts.length ? parts.join(" • ") : "—";
  }

  const oldV = log.old_values || {};
  const newV = log.new_values || {};

  const keys = Array.from(new Set([...Object.keys(oldV), ...Object.keys(newV)])).filter((k) => !IGNORE.has(k));
  const changed = keys.filter((k) => String(oldV?.[k] ?? "") !== String(newV?.[k] ?? ""));
  if (!changed.length) return "—";

  changed.sort((a, b) => {
    const ai = PREFER.indexOf(a);
    const bi = PREFER.indexOf(b);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });

  const pick = changed.slice(0, 2).map((k) => `${labelKey(k)}: ${fmtNice(oldV?.[k], k)} → ${fmtNice(newV?.[k], k)}`);
  return pick.join(" • ") + (changed.length > 2 ? " …" : "");
}
/* ========================= */

function JsonBox({ title, data }) {
  return (
    <div className="jsonBox">
      <div className="jsonTitle">{title}</div>
      <pre className="jsonPre">{JSON.stringify(data ?? null, null, 2)}</pre>
    </div>
  );
}

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [entity, setEntity] = useState("");
  const [action, setAction] = useState("");
  const [limit, setLimit] = useState(200);
  const [query, setQuery] = useState("");

  const [openId, setOpenId] = useState(null);

  async function load() {
    setError("");
    setLoading(true);
    try {
      const params = { limit: String(limit) };
      if (entity) params.entity = entity;
      if (action) params.action = action;

      const data = await api.listAuditLogs(params);
      setLogs(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.message || "Erro ao carregar audit logs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity, action, limit]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return logs;

    return logs.filter((l) => {
      const who = l.user?.name || l.user?.email || (l.user_id ? `user #${l.user_id}` : "sistema");
      const text = [
        who,
        l.action,
        l.entity,
        l.entity_id,
        JSON.stringify(l.old_values || {}),
        JSON.stringify(l.new_values || {}),
      ]
        .join(" ")
        .toLowerCase();

      return text.includes(q);
    });
  }, [logs, query]);

  return (
    <div className="audit">
      <div className="auditTop">
        <div className="auditTitleWrap">
          <h2 className="auditTitle">Histórico (Audit Logs)</h2>
          <div className="auditHint">Criações, edições e apagamentos no sistema</div>
        </div>

        <div className="auditActions">
          <button className="btn" onClick={load} disabled={loading}>
            Recarregar
          </button>
        </div>
      </div>

      {error && <p className="msg error">{error}</p>}

      <div className="auditFilters">
        <label className="f">
          <span>Entidade</span>
          <select value={entity} onChange={(e) => setEntity(e.target.value)}>
            <option value="">Todas</option>
            <option value="clients">Clientes</option>
            <option value="services">Serviços</option>
            <option value="appointments">Agendamentos</option>
            <option value="manual_invoices">Faturas</option>
            <option value="expenses">Despesas</option>
            <option value="stock_items">Stock</option>
            <option value="stock_movement">Movimentos de Stock</option>
            <option value="companies">Empresas</option>
            <option value="users">Utilizadores</option>
          </select>
        </label>

        <label className="f">
          <span>Ação</span>
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">Todas</option>
            <option value="CREATE">CREATE</option>
            <option value="UPDATE">UPDATE</option>
            <option value="DELETE">DELETE</option>
          </select>
        </label>

        <label className="f">
          <span>Limite</span>
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
            <option value={500}>500</option>
            <option value={1000}>1000</option>
          </select>
        </label>

        <label className="f span2">
          <span>Pesquisar</span>
          <input
            placeholder="ex: Kauan, Gasóleo, 13/02..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>

      {loading ? (
        <p className="status">A carregar...</p>
      ) : filtered.length === 0 ? (
        <p className="status">Sem registos.</p>
      ) : (
        <div className="auditTableWrap">
          <table className="auditTable">
            <thead>
              <tr>
                <th>Data</th>
                <th>Quem</th>
                <th>O que fez</th>
                <th>Entidade</th>
                <th>Resumo</th>
                <th className="thRight">Ações</th>
              </tr>
            </thead>

            <tbody>
              {filtered.map((l) => {
                const who =
                  l.user?.name ||
                  l.user?.email ||
                  (typeof l.user_id === "number" ? `User #${l.user_id}` : "Sistema");

                const isOpen = openId === l.id;

                return (
                  <FragmentRow
                    key={l.id}
                    log={l}
                    who={who}
                    isOpen={isOpen}
                    onToggle={() => setOpenId((prev) => (prev === l.id ? null : l.id))}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FragmentRow({ log, who, isOpen, onToggle }) {
  const act = String(log.action || "").toUpperCase();

  return (
    <Fragment>
      <tr className="auditRow">
        <td className="td nowrap">{fmtDateTime(log.created_at)}</td>

        <td className="td">
          <b className="who">{who}</b>
        </td>

        <td className="td">
          <span className={`pill ${act}`}>{actionLabel(log.action)}</span>
        </td>

        <td className="td">
          {prettyEntity(log.entity)}{" "}
          {log.entity_id != null ? <span className="muted">#{log.entity_id}</span> : null}
        </td>

        <td className="td">
          <span className="summary">{summarizeChange(log)}</span>
        </td>

        <td className="td tdRight">
          <button className="btn ghost" onClick={onToggle}>
            {isOpen ? "Fechar" : "Ver detalhes"}
          </button>
        </td>
      </tr>

      {isOpen && (
        <tr className="detailsRow">
          <td className="td detailsCell" colSpan={6}>
            <div className="detailsGrid">
              <JsonBox title="Old Values" data={log.old_values} />
              <JsonBox title="New Values" data={log.new_values} />
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}
