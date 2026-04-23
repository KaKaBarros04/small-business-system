import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import "./Schedule.css";

const DONE_RETENTION_DAYS = 30;
const CANCELED_RETENTION_DAYS = 15;

function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function endOfDay(d) {
  const x = new Date(d);
  x.setHours(23, 59, 59, 999);
  return x;
}

function addDays(d, days) {
  const x = new Date(d);
  x.setDate(x.getDate() + days);
  return x;
}

function fmtDay(d) {
  return new Intl.DateTimeFormat("pt-PT", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
  }).format(d);
}

function fmtDayShort(d) {
  return new Intl.DateTimeFormat("pt-PT", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  }).format(d);
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("pt-PT", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function badgeClass(status) {
  if (status === "DONE") return "done";
  if (status === "CANCELED") return "canceled";
  return "scheduled";
}

function badgeLabel(status) {
  if (status === "DONE") return "✅ Concluído";
  if (status === "CANCELED") return "❌ Cancelado";
  return "🕒 Agendado";
}

function statusGroupLabel(status) {
  if (status === "DONE") return "Concluídos";
  if (status === "CANCELED") return "Cancelados";
  return "Agendados";
}

export default function Schedule() {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [mode, setMode] = useState("WEEK");
  const [query, setQuery] = useState("");
  const [selectedDate, setSelectedDate] = useState(startOfDay(new Date()));
  const [showHistory, setShowHistory] = useState(false);

  async function loadAll() {
    setError("");
    setLoading(true);
    try {
      const appts = await api.listAppointments();
      setAppointments(appts || []);
    } catch (err) {
      setError(err?.message || "Erro ao carregar agendamentos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function markAppointmentStatus(id, status) {
    setError("");
    setLoading(true);
    try {
      await api.updateAppointment(id, { status });
      await loadAll();
    } catch (err) {
      setError(err?.message || "Erro ao atualizar status");
    } finally {
      setLoading(false);
    }
  }

  const weekDays = useMemo(() => {
    const start = startOfDay(selectedDate);
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
  }, [selectedDate]);

  const { from, to } = useMemo(() => {
    const now = new Date();

    if (showHistory) {
      return { from: null, to: null };
    }

    if (mode === "TODAY") {
      return { from: startOfDay(now), to: endOfDay(now) };
    }

    if (mode === "TOMORROW") {
      const t = addDays(now, 1);
      return { from: startOfDay(t), to: endOfDay(t) };
    }

    if (mode === "WEEK") {
      return {
        from: startOfDay(selectedDate),
        to: endOfDay(addDays(selectedDate, 6)),
      };
    }

    return { from: null, to: null };
  }, [mode, selectedDate, showHistory]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const now = new Date();
    const doneCutoff = addDays(startOfDay(now), -DONE_RETENTION_DAYS);
    const canceledCutoff = addDays(startOfDay(now), -CANCELED_RETENTION_DAYS);

    const base = (appointments || []).filter((a) => {
      const dt = a.scheduled_at ? new Date(a.scheduled_at) : null;
      const status = a.status || "SCHEDULED";

      if (!dt || Number.isNaN(dt.getTime())) return false;

      if (!showHistory) {
        if (status === "DONE" && dt < doneCutoff) return false;
        if (status === "CANCELED" && dt < canceledCutoff) return false;

        if (from && to) {
          if (dt < from || dt > to) return false;
        }
      } else {
        const isOldDone = status === "DONE" && dt < doneCutoff;
        const isOldCanceled = status === "CANCELED" && dt < canceledCutoff;

        if (!isOldDone && !isOldCanceled) return false;
      }

      if (!q) return true;

      const clientName =
        a.client?.business_name?.toLowerCase() ||
        a.client?.name?.toLowerCase() ||
        "";

      const serviceName =
        a.service_name?.toLowerCase() ||
        a.service?.name?.toLowerCase() ||
        "";

      const address = (a.address || "").toLowerCase();
      const notes = (a.notes || "").toLowerCase();

      return (
        clientName.includes(q) ||
        serviceName.includes(q) ||
        address.includes(q) ||
        notes.includes(q)
      );
    });

    base.sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at));
    return base;
  }, [appointments, from, to, query, showHistory]);

  const groupedWeek = useMemo(() => {
    return weekDays.map((day) => {
      const items = filtered.filter((a) => {
        if (!a.scheduled_at) return false;
        return sameDay(new Date(a.scheduled_at), day);
      });

      return {
        key: day.toISOString(),
        day,
        items,
      };
    });
  }, [filtered, weekDays]);

  const groupedList = useMemo(() => {
    const map = new Map();

    for (const a of filtered) {
      const d = new Date(a.scheduled_at);
      const key = d.toISOString().slice(0, 10);

      if (!map.has(key)) map.set(key, []);
      map.get(key).push(a);
    }

    return Array.from(map.entries()).map(([key, items]) => ({
      key,
      day: new Date(`${key}T00:00:00`),
      items,
    }));
  }, [filtered]);

  const groupedHistory = useMemo(() => {
    const map = new Map();

    for (const a of filtered) {
      const statusKey = a.status || "SCHEDULED";
      if (!map.has(statusKey)) map.set(statusKey, []);
      map.get(statusKey).push(a);
    }

    const orderedStatuses = ["DONE", "CANCELED"];

    return orderedStatuses
      .filter((status) => map.has(status))
      .map((status) => ({
        status,
        label: statusGroupLabel(status),
        items: map.get(status),
      }));
  }, [filtered]);

  const isWeekMode = mode === "WEEK" && !showHistory;

  function moveWeek(direction) {
    setSelectedDate((prev) => addDays(prev, direction * 7));
  }

  function goToToday() {
    setSelectedDate(startOfDay(new Date()));
    setMode("TODAY");
    setShowHistory(false);
  }

  function activateMode(nextMode) {
    setShowHistory(false);
    setMode(nextMode);
  }

  return (
    <div className="schedule">
      <div className="scheduleHeader">
        <div>
          <h2>Agenda</h2>
          <p>
            Vista semanal com foco no presente. Concluídos antigos vão para o
            histórico.
          </p>
        </div>

        {loading ? <span className="status">A carregar...</span> : null}
      </div>

      {error && <div className="scheduleMsg error">{error}</div>}

      <div className="scheduleToolbar">
        <div className="modePills" role="group" aria-label="Filtro de período">
          <button
            className={`pill ${mode === "TODAY" && !showHistory ? "active" : ""}`}
            onClick={() => activateMode("TODAY")}
          >
            Hoje
          </button>

          <button
            className={`pill ${mode === "TOMORROW" && !showHistory ? "active" : ""}`}
            onClick={() => activateMode("TOMORROW")}
          >
            Amanhã
          </button>

          <button
            className={`pill ${mode === "WEEK" && !showHistory ? "active" : ""}`}
            onClick={() => activateMode("WEEK")}
          >
            Semana
          </button>

          <button
            className={`pill ${mode === "ALL" && !showHistory ? "active" : ""}`}
            onClick={() => activateMode("ALL")}
          >
            Lista
          </button>

          <button
            className={`pill historyPill ${showHistory ? "active" : ""}`}
            onClick={() => setShowHistory((prev) => !prev)}
          >
            Histórico
          </button>
        </div>

        <button className="btn ghost" onClick={loadAll} disabled={loading}>
          Recarregar
        </button>

        <input
          className="scheduleSearch"
          placeholder="Pesquisar cliente, serviço, morada..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {!showHistory && isWeekMode && (
        <div className="weekNav">
          <button className="btn ghost" onClick={() => moveWeek(-1)}>
            ← Semana anterior
          </button>

          <div className="weekLabel">
            {fmtDayShort(weekDays[0])} — {fmtDayShort(weekDays[6])}
          </div>

          <div className="weekNavActions">
            <button className="btn ghost" onClick={() => activateMode("TODAY")}>
              Ver hoje
            </button>
            <button className="btn" onClick={goToToday}>
              Ir para hoje
            </button>
            <button className="btn ghost" onClick={() => moveWeek(1)}>
              Próxima semana →
            </button>
          </div>
        </div>
      )}

      {!showHistory && (
        <div className="schedulePolicy">
          <span>✅ Concluídos visíveis por {DONE_RETENTION_DAYS} dias</span>
          <span>❌ Cancelados visíveis por {CANCELED_RETENTION_DAYS} dias</span>
        </div>
      )}

      {loading ? (
        <p className="status">A carregar...</p>
      ) : showHistory ? (
        groupedHistory.length === 0 ? (
          <p className="status">Nenhum agendamento antigo no histórico.</p>
        ) : (
          <div className="historyBoard">
            {groupedHistory.map((group) => (
              <section key={group.status} className="historySection">
                <div className="historyHeader">
                  <h3>{group.label}</h3>
                  <span className="dayCount">{group.items.length} registo(s)</span>
                </div>

                <div className="historyList">
                  {group.items.map((a) => (
                    <article key={a.id} className={`eventCard compact ${badgeClass(a.status)}`}>
                      <div className="eventTimeRow">
                        <span className="eventTime">{fmtTime(a.scheduled_at)}</span>
                        <span className={`badge ${badgeClass(a.status)}`}>
                          {badgeLabel(a.status)}
                        </span>
                      </div>

                      <div className="historyDate">
                        {fmtDay(new Date(a.scheduled_at))}
                      </div>

                      <div className="eventClient">
                        {a.client?.client_code ? `${a.client.client_code} — ` : ""}
                        {a.client?.business_name || a.client?.name || "—"}
                      </div>

                      <div className="eventService">
                        {a.service_name || a.service?.name || "—"}
                      </div>

                      <div className="eventMeta">
                        <span>📍 {a.address || "Morada não informada"}</span>
                        <span>💶 € {a.price ?? "0"}</span>
                      </div>

                      {a.notes ? <div className="eventNotes">📝 {a.notes}</div> : null}
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )
      ) : isWeekMode ? (
        <div className="weekBoard">
          {groupedWeek.map((g) => {
            const isToday = sameDay(g.day, new Date());

            return (
              <section
                key={g.key}
                className={`weekDayColumn ${isToday ? "today" : ""}`}
              >
                <div className="weekDayHeader">
                  <h3>{fmtDay(g.day)}</h3>
                  <span className="dayCount">{g.items.length} agendamento(s)</span>
                </div>

                {g.items.length === 0 ? (
                  <div className="emptyDay">Sem agendamentos</div>
                ) : (
                  <div className="weekCards">
                    {g.items.map((a) => (
                      <article key={a.id} className={`eventCard ${badgeClass(a.status)}`}>
                        <div className="eventTimeRow">
                          <span className="eventTime">{fmtTime(a.scheduled_at)}</span>
                          <span className={`badge ${badgeClass(a.status)}`}>
                            {badgeLabel(a.status)}
                          </span>
                        </div>

                        <div className="eventClient">
                          {a.client?.client_code ? `${a.client.client_code} — ` : ""}
                          {a.client?.business_name || a.client?.name || "—"}
                        </div>

                        <div className="eventService">
                          {a.service_name || a.service?.name || "—"}
                        </div>

                        <div className="eventMeta">
                          <span>📍 {a.address || "Morada não informada"}</span>
                          <span>💶 € {a.price ?? "0"}</span>
                        </div>

                        {a.notes ? <div className="eventNotes">📝 {a.notes}</div> : null}

                        {a.status === "SCHEDULED" && (
                          <div className="apptActions">
                            <button
                              className="btn"
                              onClick={() => markAppointmentStatus(a.id, "DONE")}
                              disabled={loading}
                            >
                              Concluir
                            </button>

                            <button
                              className="btn ghost"
                              onClick={() => markAppointmentStatus(a.id, "CANCELED")}
                              disabled={loading}
                            >
                              Cancelar
                            </button>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      ) : groupedList.length === 0 ? (
        <p className="status">Nenhum agendamento nesse período.</p>
      ) : (
        <div className="scheduleBody">
          {groupedList.map((g) => (
            <section key={g.key} className="dayCard">
              <div className="dayHeader">
                <h3>{fmtDay(g.day)}</h3>
                <span className="dayCount">{g.items.length} agendamento(s)</span>
              </div>

              <ul className="apptList">
                {g.items.map((a) => (
                  <li key={a.id} className="apptRow">
                    <div className="apptTopline">
                      <div className="apptMain">
                        <b>{fmtTime(a.scheduled_at)}</b> —{" "}
                        <b>
                          {a.client?.client_code ? `${a.client.client_code} — ` : ""}
                          {a.client?.business_name || a.client?.name || "—"}
                        </b>{" "}
                        — {a.service_name || a.service?.name || "—"} — € {a.price}
                      </div>

                      <span className={`badge ${badgeClass(a.status)}`}>
                        {badgeLabel(a.status)}
                      </span>
                    </div>

                    <div className="apptMeta">
                      <b>Morada:</b> {a.address || "—"}
                      {a.notes ? ` • (${a.notes})` : ""}
                    </div>

                    <div className="apptActions">
                      {a.status === "SCHEDULED" && (
                        <>
                          <button
                            className="btn"
                            onClick={() => markAppointmentStatus(a.id, "DONE")}
                            disabled={loading}
                          >
                            Concluir
                          </button>
                          <button
                            className="btn ghost"
                            onClick={() => markAppointmentStatus(a.id, "CANCELED")}
                            disabled={loading}
                          >
                            Cancelar
                          </button>
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}