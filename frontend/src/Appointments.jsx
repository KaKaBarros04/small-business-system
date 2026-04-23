import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import "./Appointments.css";

function statusLabel(s) {
  if (s === "DONE") return "Concluído";
  if (s === "CANCELED") return "Cancelado";
  return "Agendado";
}

function statusClass(s) {
  if (s === "DONE") return "done";
  if (s === "CANCELED") return "canceled";
  return "scheduled";
}

function formatClientLabel(client) {
  if (!client) return "—";
  const code = client.client_code?.trim();
  const name = client.business_name?.trim() || client.name || "—";
  return code ? `${code} — ${name}` : name;
}

export default function Appointments() {
  const [clients, setClients] = useState([]);
  const [appointments, setAppointments] = useState([]);

  const [clientId, setClientId] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [price, setPrice] = useState("");

  const [editingId, setEditingId] = useState(null);
  const [editScheduledAt, setEditScheduledAt] = useState("");
  const [editAddress, setEditAddress] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [editStatus, setEditStatus] = useState("SCHEDULED");
  const [editServiceName, setEditServiceName] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);

  async function refreshAppointments() {
    const apptsData = await api.listAppointments();
    setAppointments(apptsData || []);
  }

  async function loadAll() {
    setError("");
    setLoading(true);
    try {
      const [clientsData, apptsData] = await Promise.all([
        api.listClients(),
        api.listAppointments(),
      ]);
      setClients(clientsData || []);
      setAppointments(apptsData || []);
    } catch (err) {
      setError(err?.message || "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");

    if (!clientId) return setError("Escolha um cliente");
    if (!serviceName.trim()) return setError("Informe o serviço");
    if (!scheduledAt) return setError("Escolha data e hora");
    if (!address.trim()) return setError("Morada é obrigatória");

    const iso = new Date(scheduledAt).toISOString();

    let priceNumber = null;
    if (price !== "") {
      const n = Number(price);
      if (Number.isNaN(n) || n < 0) return setError("Preço inválido");
      priceNumber = n;
    }

    setLoading(true);
    try {
      await api.createAppointment({
        client_id: Number(clientId),
        service_name: serviceName.trim(),
        scheduled_at: iso,
        address: address.trim(),
        notes: notes.trim() || null,
        price: priceNumber,
      });

      setClientId("");
      setServiceName("");
      setScheduledAt("");
      setAddress("");
      setNotes("");
      setPrice("");

      await refreshAppointments();
    } catch (err) {
      setError(err?.message || "Erro ao criar agendamento");
    } finally {
      setLoading(false);
    }
  }

  function startEdit(a) {
    setEditingId(a.id);

    const dtLocal = a.scheduled_at ? a.scheduled_at.slice(0, 16) : "";
    setEditScheduledAt(dtLocal);
    setEditAddress(a.address ?? "");
    setEditNotes(a.notes ?? "");
    setEditPrice(String(a.price ?? ""));
    setEditStatus(a.status ?? "SCHEDULED");
    setEditServiceName(a.service_name ?? "");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditScheduledAt("");
    setEditAddress("");
    setEditNotes("");
    setEditPrice("");
    setEditStatus("SCHEDULED");
    setEditServiceName("");
  }

  async function saveEdit(id) {
    setError("");

    if (!editServiceName.trim()) return setError("Serviço é obrigatório");
    if (!editScheduledAt) return setError("Data/hora é obrigatória");
    if (!editAddress.trim()) return setError("Morada é obrigatória");

    const iso = new Date(editScheduledAt).toISOString();

    let priceNumber = null;
    if (editPrice !== "") {
      const n = Number(editPrice);
      if (Number.isNaN(n) || n < 0) return setError("Preço inválido");
      priceNumber = n;
    }

    setLoading(true);
    try {
      await api.updateAppointment(id, {
        service_name: editServiceName.trim(),
        scheduled_at: iso,
        address: editAddress.trim(),
        notes: editNotes.trim() || null,
        price: priceNumber,
        status: editStatus,
      });

      cancelEdit();
      await refreshAppointments();
    } catch (err) {
      setError(err?.message || "Erro ao salvar alterações");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id) {
    setError("");
    const ok = confirm("Apagar este agendamento?");
    if (!ok) return;

    setLoading(true);
    try {
      await api.deleteAppointment(id);
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      await refreshAppointments();
    } catch (err) {
      setError(err?.message || "Erro ao apagar");
    } finally {
      setLoading(false);
    }
  }

  async function handleBulkDelete() {
    setError("");

    if (!selectedIds.length) return;

    const ok = confirm(`Apagar ${selectedIds.length} agendamento(s) selecionado(s)?`);
    if (!ok) return;

    setLoading(true);
    try {
      const res = await api.bulkDeleteAppointments({ ids: selectedIds });
      const deletedIds = Array.isArray(res?.deleted_ids) ? res.deleted_ids : [];

      if (deletedIds.length > 0) {
        setAppointments((prev) => prev.filter((a) => !deletedIds.includes(a.id)));
      }

      setSelectedIds((prev) => prev.filter((id) => !deletedIds.includes(id)));
    } catch (err) {
      setError(err?.message || "Erro ao apagar agendamentos selecionados");
    } finally {
      setLoading(false);
    }
  }

  async function markStatus(id, status) {
    setError("");
    setLoading(true);
    try {
      await api.updateAppointment(id, { status });
      await refreshAppointments();
    } catch (err) {
      setError(err?.message || "Erro ao alterar status");
    } finally {
      setLoading(false);
    }
  }

  async function syncGoogle(id) {
    setError("");
    setLoading(true);
    try {
      await api.syncAppointmentGoogle(id);
      await refreshAppointments();
    } catch (err) {
      setError(err?.message || "Erro ao sincronizar com Google Calendar");
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return appointments;

    return appointments.filter((a) => {
      const clientName =
        a.client?.business_name?.toLowerCase() ||
        a.client?.name?.toLowerCase() ||
        "";
      const clientCode = a.client?.client_code?.toLowerCase() || "";
      const serviceNameTxt = (a.service_name || "").toLowerCase();
      const addr = (a.address || "").toLowerCase();
      const notesTxt = (a.notes || "").toLowerCase();

      return (
        clientName.includes(q) ||
        clientCode.includes(q) ||
        serviceNameTxt.includes(q) ||
        addr.includes(q) ||
        notesTxt.includes(q)
      );
    });
  }, [appointments, query]);

  const visibleIds = useMemo(() => filtered.map((a) => a.id), [filtered]);

  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  function toggleSelected(id) {
    setSelectedIds((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : [...prev, id]
    );
  }

  function toggleSelectAllVisible() {
    if (allVisibleSelected) {
      setSelectedIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    }
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  return (
    <div className="appts">
      <div className="apptsHeader">
        <div>
          <h2>Agendamentos</h2>
          <p>Crie, edite e sincronize com Google Calendar.</p>
        </div>
        {loading ? <span className="apptsHint">A carregar...</span> : null}
      </div>

      {error && <div className="apptsMsg error">{error}</div>}

      <section className="apptsCard">
        <h3>Novo agendamento</h3>

        <form onSubmit={handleCreate} className="apptsForm">
          <div className="apptsFields">
            <label>
              <span>Cliente</span>
              <select
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                disabled={loading}
              >
                <option value="">-- selecione --</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.client_code ? `${c.client_code} — ${c.name}` : c.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Serviço</span>
              <input
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="Ex: Desinfecção T2"
                disabled={loading}
              />
            </label>

            <label>
              <span>Data e hora</span>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                disabled={loading}
              />
            </label>

            <label>
              <span>Morada</span>
              <input
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                disabled={loading}
              />
            </label>

            <label className="apptsSpanAll">
              <span>Observações (opcional)</span>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={loading}
              />
            </label>

            <label className="apptsSpanAll">
              <span>Preço (opcional)</span>
              <input
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="ex: 90"
                disabled={loading}
              />
            </label>
          </div>

          <div className="apptsActions">
            <button className="btn" type="submit" disabled={loading}>
              Criar agendamento
            </button>
            <button className="btn ghost" type="button" onClick={loadAll} disabled={loading}>
              Atualizar lista
            </button>
            <span className="apptsHint">
              Dica: use o botão “Sync Google” quando precisar atualizar o evento.
            </span>
          </div>
        </form>
      </section>

      <div className="apptsToolbar">
        <input
          className="apptsSearch"
          placeholder="Pesquisar (cliente, código, serviço, morada...)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn ghost" type="button" onClick={toggleSelectAllVisible} disabled={loading || visibleIds.length === 0}>
          {allVisibleSelected ? "Desmarcar visíveis" : "Selecionar visíveis"}
        </button>
        <button className="btn danger" type="button" onClick={handleBulkDelete} disabled={loading || selectedIds.length === 0}>
          Apagar selecionados ({selectedIds.length})
        </button>
        <button className="btn ghost" type="button" onClick={clearSelection} disabled={loading || selectedIds.length === 0}>
          Limpar seleção
        </button>
        <button className="btn" onClick={loadAll} disabled={loading}>
          Recarregar
        </button>
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        <h3 className="apptsListTitle">Lista</h3>

        <p className="status">
          Mostrando <b>{filtered.length}</b> de <b>{appointments.length}</b> • Selecionados: <b>{selectedIds.length}</b>
        </p>

        {loading ? (
          <p className="status">A carregar...</p>
        ) : filtered.length === 0 ? (
          <p className="status">Nenhum agendamento.</p>
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={allVisibleSelected}
                onChange={toggleSelectAllVisible}
                title="Selecionar todos os agendamentos visíveis"
              />
              <span className="apptsHint">Selecionar todos os visíveis</span>
            </div>

            <ul className="apptsList">
              {filtered.map((a) => (
                <li key={a.id} className={`apptItem ${selectedIds.includes(a.id) ? "selected" : ""}`}>
                  {editingId === a.id ? (
                    <div className="apptEdit">
                      <div className="apptTop">
                        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(a.id)}
                            onChange={() => toggleSelected(a.id)}
                          />
                          <div className="apptTitle">
                            <b>{formatClientLabel(a.client)}</b> — {a.service_name || "—"}
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                          <span className={`apptBadge ${statusClass(a.status)}`}>{statusLabel(a.status)}</span>
                          {a.google_event_html_link ? (
                            <span className="apptBadge scheduled" title="Sincronizado com Google Calendar">
                              GC ✅
                            </span>
                          ) : (
                            <span className="apptBadge" title="Ainda não sincronizado">
                              GC —
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="apptEditGrid">
                        <label className="apptsSpanAll">
                          <span>Serviço</span>
                          <input
                            value={editServiceName}
                            onChange={(e) => setEditServiceName(e.target.value)}
                            disabled={loading}
                          />
                        </label>

                        <label>
                          <span>Data e hora</span>
                          <input
                            type="datetime-local"
                            value={editScheduledAt}
                            onChange={(e) => setEditScheduledAt(e.target.value)}
                            disabled={loading}
                          />
                        </label>

                        <label>
                          <span>Status</span>
                          <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)} disabled={loading}>
                            <option value="SCHEDULED">SCHEDULED</option>
                            <option value="DONE">DONE</option>
                            <option value="CANCELED">CANCELED</option>
                          </select>
                        </label>

                        <label className="apptsSpanAll">
                          <span>Morada</span>
                          <input
                            value={editAddress}
                            onChange={(e) => setEditAddress(e.target.value)}
                            disabled={loading}
                          />
                        </label>

                        <label className="apptsSpanAll">
                          <span>Observações</span>
                          <input
                            value={editNotes}
                            onChange={(e) => setEditNotes(e.target.value)}
                            disabled={loading}
                          />
                        </label>

                        <label>
                          <span>Preço</span>
                          <input
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            disabled={loading}
                          />
                        </label>
                      </div>

                      <div className="apptEditActions">
                        <button className="btn" onClick={() => saveEdit(a.id)} disabled={loading}>
                          Salvar
                        </button>
                        <button className="btn ghost" onClick={cancelEdit} disabled={loading}>
                          Cancelar
                        </button>

                        {editStatus === "SCHEDULED" && (
                          <button className="btn" type="button" onClick={() => syncGoogle(a.id)} disabled={loading}>
                            🔄 Sync Google
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="apptTop">
                        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(a.id)}
                            onChange={() => toggleSelected(a.id)}
                          />
                          <div className="apptTitle">
                            <b>{formatClientLabel(a.client)}</b> — {a.service_name || "—"}
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                          <span className={`apptBadge ${statusClass(a.status)}`}>{statusLabel(a.status)}</span>
                          {a.google_event_html_link ? (
                            <span className="apptBadge scheduled" title="Sincronizado com Google Calendar">
                              GC ✅
                            </span>
                          ) : (
                            <span className="apptBadge" title="Ainda não sincronizado">
                              GC —
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="apptMeta">
                        <b>Quando:</b> {a.scheduled_at?.slice(0, 16).replace("T", " ")} &nbsp; • &nbsp;
                        <b>Preço:</b> €{a.price ?? "—"} &nbsp; • &nbsp;
                        <b>Morada:</b> {a.address}
                        {a.notes ? ` • (${a.notes})` : ""}
                      </div>

                      <div className="apptButtons">
                        <button className="btn" onClick={() => startEdit(a)} disabled={loading}>
                          Editar
                        </button>

                        <button className="btn danger" onClick={() => handleDelete(a.id)} disabled={loading}>
                          Apagar
                        </button>

                        {a.status === "SCHEDULED" && (
                          <button className="btn" onClick={() => syncGoogle(a.id)} disabled={loading}>
                            🔄 Sync Google
                          </button>
                        )}

                        {a.google_event_html_link && (
                          <a
                            href={a.google_event_html_link}
                            target="_blank"
                            rel="noreferrer"
                            className="btn ghost"
                            title="Abrir evento no Google Calendar"
                          >
                            📆 Abrir no Google Calendar
                          </a>
                        )}

                        {a.status === "SCHEDULED" && (
                          <>
                            <button className="btn" onClick={() => markStatus(a.id, "DONE")} disabled={loading}>
                              Concluir
                            </button>
                            <button
                              className="btn ghost"
                              onClick={() => markStatus(a.id, "CANCELED")}
                              disabled={loading}
                            >
                              Cancelar
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}