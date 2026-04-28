import { useOutletContext } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import "./Clients.css";

function toNum(v) {
  if (v == null || v === "") return null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function eur(n) {
  const x = Number(n || 0);
  return new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(x);
}

function fixText(s) {
  if (s == null) return "";
  let text = String(s);

  const hasMojibake = /Ã|Â|├|┬/.test(text);
  if (!hasMojibake) return text;

  const map = {
    "├º": "ç",
    "├ú": "ã",
    "├í": "á",
    "├®": "é",
    "├¡": "í",
    "├│": "ó",
    "├║": "ú",
    "├Á": "Á",
    "├Ç": "Ç",
    "├É": "É",
    "├Õ": "Õ",
    "┬º": "º",
    "┬ª": "ª",
    "Âº": "º",
    "Âª": "ª",
    "Ã§": "ç",
    "Ã£": "ã",
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ãµ": "õ",
    "Ãª": "ê",
    "Ã¢": "â",
  };

  for (const [bad, good] of Object.entries(map)) {
    text = text.split(bad).join(good);
  }

  return text;
}

function norm(s) {
  return fixText(s)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

const DEFAULT_NOTES = `SERVICE_ADDR: 
SERVICE_PC: 
SERVICE_CITY: `;

function createEmptyForm() {
  return {
    name: "",
    email: "",
    phone: "",

    client_code: "",
    business_name: "",
    contact_name: "",
    nickname: "",

    vat_number: "",
    address: "",
    postal_code: "",
    city: "",
    pest_type: "",
    notes: DEFAULT_NOTES,

    has_contract: false,
    contract_start_date: "",
    visits_per_year: 1,

    contract_value_yearly: "",

    is_active: true,
  };
}

export default function Clients() {
  const { company } = useOutletContext() || {};
  const isDesinfex = (company?.slug || "").toLowerCase() === "desinfex";

  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [form, setForm] = useState(createEmptyForm());
  const [editingId, setEditingId] = useState(null);

  const [q, setQ] = useState("");
  const [onlyActive, setOnlyActive] = useState(false);

  const [selectedIds, setSelectedIds] = useState([]);

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const [renewOpen, setRenewOpen] = useState(false);
  const [renewClient, setRenewClient] = useState(null);
  const [renewDate, setRenewDate] = useState("");
  const [renewVPY, setRenewVPY] = useState(6);
  const [renewValue, setRenewValue] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const res = await api.listClients();
      setClients(
        (res || []).map((c) => ({
          ...c,
          name: fixText(c?.name),
          business_name: fixText(c?.business_name),
          contact_name: fixText(c?.contact_name),
          nickname: fixText(c?.nickname),
          address: fixText(c?.address),
          postal_code: fixText(c?.postal_code),
          city: fixText(c?.city),
          pest_type: fixText(c?.pest_type),
          notes: fixText(c?.notes),
        }))
      );
    } catch (e) {
      setErr(e?.message || "Erro ao carregar clientes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filteredClients = useMemo(() => {
    const qq = norm(q).trim();
    const base = onlyActive ? clients.filter((c) => c?.is_active !== false) : clients;

    const filtered = !qq
      ? base
      : base.filter((c) => {
          const hay = [
            c?.id,
            c?.client_code,
            c?.business_name,
            c?.name,
            c?.nickname,
            c?.contact_name,
            c?.email,
            c?.phone,
            c?.vat_number,
            c?.address,
            c?.postal_code,
            c?.city,
            c?.notes,
            c?.pest_type,
          ]
            .map(norm)
            .join(" • ");

          const tokens = qq.split(/\s+/).filter(Boolean);
          return tokens.every((t) => hay.includes(t));
        });

    return [...filtered].sort((a, b) => (b.id || 0) - (a.id || 0));
  }, [clients, q, onlyActive]);

  const visibleIds = useMemo(() => filteredClients.map((c) => c.id), [filteredClients]);

  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
  const someVisibleSelected = visibleIds.length > 0 && visibleIds.some((id) => selectedIds.includes(id));

  function toggleSelected(id) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
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

  function setField(k, v) {
    setForm((prev) => ({ ...prev, [k]: v }));
  }

  function resetForm() {
    setForm(createEmptyForm());
    setEditingId(null);
  }

  function startEdit(c) {
    setMsg("");
    setErr("");
    setEditingId(c.id);

    setForm({
      name: fixText(c?.name) || "",
      email: c?.email || "",
      phone: c?.phone || "",

      client_code: c?.client_code || "",
      business_name: fixText(c?.business_name) || "",
      contact_name: fixText(c?.contact_name) || "",
      nickname: fixText(c?.nickname) || "",

      vat_number: c?.vat_number || "",
      address: fixText(c?.address) || "",
      postal_code: fixText(c?.postal_code) || "",
      city: fixText(c?.city) || "",

      pest_type: isDesinfex ? fixText(c?.pest_type) || "" : "",
      notes: fixText(c?.notes) || "",

      has_contract: isDesinfex ? !!c?.has_contract : false,
      contract_start_date: isDesinfex && c?.contract_start_date ? String(c.contract_start_date).slice(0, 10) : "",
      visits_per_year: isDesinfex ? Number(c?.visits_per_year || 1) : 1,

      contract_value_yearly:
        c?.contract_value_yearly != null && c.contract_value_yearly !== "" ? String(c.contract_value_yearly) : "",

      is_active: c?.is_active !== false,
    });
  }

  function validatePayload(payload) {
    if (!payload.business_name?.trim()) return "Cliente (nome para PDF) é obrigatório";

    if (payload.client_code && String(payload.client_code).length > 50) {
      return "Código do cliente muito longo (máx 50)";
    }

    if (isDesinfex && payload.has_contract) {
      const v = Number(payload.visits_per_year || 0);
      if (!Number.isFinite(v) || v < 1 || v > 12) return "Visitas por ano tem de ser entre 1 e 12";
      if (!payload.contract_start_date) return "Data de início do contrato é obrigatória";

      if (payload.contract_value_yearly != null) {
        const cv = Number(payload.contract_value_yearly);
        if (!Number.isFinite(cv) || cv < 0) return "Valor do contrato (€/ano) inválido";
      }
    }

    return "";
  }

  async function save(e) {
    e.preventDefault();
    setMsg("");
    setErr("");

    const payload = {
      name: form.name?.trim() || "",
      email: form.email?.trim() || null,
      phone: form.phone?.trim() || null,
      client_code: form.client_code?.trim() || null,
      business_name: form.business_name?.trim() || null,
      contact_name: form.contact_name?.trim() || null,
      nickname: form.nickname?.trim() || null,
      vat_number: form.vat_number?.trim() || null,
      address: form.address?.trim() || null,
      postal_code: form.postal_code?.trim() || null,
      city: form.city?.trim() || null,
      notes: form.notes?.trim() || null,
      is_active: editingId ? !!form.is_active : true,
    };

    if (isDesinfex) {
      payload.pest_type = form.pest_type?.trim() || null;
      payload.has_contract = !!form.has_contract;
      payload.contract_start_date = form.has_contract ? form.contract_start_date || null : null;
      payload.visits_per_year = form.has_contract ? Number(form.visits_per_year || 1) : null;
      payload.contract_value_yearly = form.has_contract ? toNum(form.contract_value_yearly) : null;
    } else {
      payload.pest_type = null;
      payload.has_contract = false;
      payload.contract_start_date = null;
      payload.visits_per_year = null;
      payload.contract_value_yearly = null;
    }

    const vmsg = validatePayload(payload);
    if (vmsg) {
      setErr(vmsg);
      return;
    }

    setLoading(true);
    try {
      if (editingId) {
        await api.updateClient(editingId, payload);
        setMsg("✅ Cliente atualizado");
      } else {
        await api.createClient(payload);
        setMsg("✅ Cliente criado");
      }
      resetForm();
      await load();
    } catch (e2) {
      setErr(e2?.message || "Erro ao guardar cliente");
    } finally {
      setLoading(false);
    }
  }

  async function remove(id) {
    if (!window.confirm("Apagar este cliente?")) return;
    setMsg("");
    setErr("");
    setLoading(true);
    try {
      await api.deleteClient(id);
      setMsg("✅ Cliente apagado");
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      await load();
    } catch (e) {
      setErr(e?.message || "Erro ao apagar cliente");
    } finally {
      setLoading(false);
    }
  }

  async function removeSelected(force = false) {
    if (!selectedIds.length) return;

    const ok = window.confirm(
      force
        ? `Apagar ${selectedIds.length} cliente(s) e os respetivos registos associados?`
        : `Apagar ${selectedIds.length} cliente(s) selecionado(s)?`
    );
    if (!ok) return;

    setMsg("");
    setErr("");
    setLoading(true);

    try {
      const res = await api.bulkDeleteClients({ ids: selectedIds, force });
      const deletedIds = Array.isArray(res?.deleted_ids) ? res.deleted_ids : [];
      const blocked = Array.isArray(res?.blocked) ? res.blocked : [];

      if (deletedIds.length > 0) {
        setClients((prev) => prev.filter((c) => !deletedIds.includes(c.id)));
      }

      setSelectedIds((prev) => prev.filter((id) => !deletedIds.includes(id)));

      if (blocked.length > 0) {
        const names = blocked.map((x) => x?.name || `#${x?.client_id}`).join(", ");
        setErr(`Alguns clientes não foram apagados: ${names}`);
      }

      if ((res?.deleted_count || 0) > 0) {
        setMsg(`✅ ${res.deleted_count} cliente(s) apagado(s)`);
      } else if (!blocked.length) {
        setMsg("Nenhum cliente foi apagado.");
      }
    } catch (e) {
      setErr(e?.message || "Erro ao apagar clientes selecionados");
    } finally {
      setLoading(false);
    }
  }

  async function generateVisits(clientId) {
    setMsg("");
    setErr("");
    setLoading(true);
    try {
      await api.generateContractVisits(clientId, true);
      setMsg("✅ Visitas do contrato geradas (ver Agenda/Agendamentos)");
      await load();
    } catch (e) {
      setErr(e?.message || "Erro ao gerar visitas do contrato");
    } finally {
      setLoading(false);
    }
  }

  function openRenew(c) {
    setMsg("");
    setErr("");
    setRenewClient(c);
    setRenewDate("");
    setRenewVPY(Number(c?.visits_per_year || 6));
    setRenewValue(c?.contract_value_yearly != null && c.contract_value_yearly !== "" ? String(c.contract_value_yearly) : "");
    setRenewOpen(true);
  }

  async function openDossier(clientId) {
    setMsg("");
    setErr("");
    setLoading(true);
    try {
      await api.openClientDossierPdf(clientId);
    } catch (e) {
      setErr(e?.message || "Erro ao gerar dossiê (PDF)");
    } finally {
      setLoading(false);
    }
  }

  async function doRenew() {
    if (!renewClient?.id) return;
    if (!renewDate) {
      setErr("Escolhe a data de início do novo ciclo (renew_start_date)");
      return;
    }

    const v = Number(renewVPY || 0);
    if (!Number.isFinite(v) || v < 1 || v > 12) {
      setErr("Visitas por ano tem de ser entre 1 e 12");
      return;
    }

    const cv = toNum(renewValue);
    if (renewValue !== "" && (cv == null || cv < 0)) {
      setErr("Valor do contrato (€/ano) inválido");
      return;
    }

    setLoading(true);
    setMsg("");
    setErr("");
    try {
      await api.renewContract(renewClient.id, {
        renew_start_date: renewDate,
        visits_per_year: v,
        contract_value_yearly: cv,
        replace: true,
      });
      setMsg("✅ Contrato renovado e visitas do novo ciclo geradas");
      setRenewOpen(false);
      setRenewClient(null);
      setRenewDate("");
      setRenewValue("");
      await load();
    } catch (e) {
      setErr(e?.message || "Erro ao renovar contrato");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card-cliente">
      <p className="status"></p>

      <div className="clientsTop">
        <h2 className="clientsTitle">Clientes</h2>

        <div className="btn-form">
          <button className="btn ghost" onClick={resetForm} disabled={loading}>
            Novo cliente
          </button>
          <button className="btn" onClick={load} disabled={loading}>
            Atualizar
          </button>
        </div>
      </div>

      {loading && <p className="status">A carregar...</p>}
      {msg && <p className="msg ok">{msg}</p>}
      {err && <p className="msg error">{err}</p>}

      <div className="pdfQuickPanel">
        <div className="dashPeriod">
          <label>
            <div>Ano</div>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value || 0))}
              min={1900}
              max={3000}
            />
          </label>

          <label>
            <div>Mês</div>
            <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              <option value={1}>Janeiro</option>
              <option value={2}>Fevereiro</option>
              <option value={3}>Março</option>
              <option value={4}>Abril</option>
              <option value={5}>Maio</option>
              <option value={6}>Junho</option>
              <option value={7}>Julho</option>
              <option value={8}>Agosto</option>
              <option value={9}>Setembro</option>
              <option value={10}>Outubro</option>
              <option value={11}>Novembro</option>
              <option value={12}>Dezembro</option>
            </select>
          </label>
        </div>

        <div className="dashActions">
          <button
            className="btn btn-soft"
            onClick={() => {
              const y = Number(year);
              const m = Number(month);
              if (!y || !m) return alert("Seleciona ano e mês primeiro.");
              api.openVisitsPdf(y, m);
            }}
          >
            📄 PDF Visitas
          </button>

          <button className="btn btn-soft" onClick={() => api.openStockPdf({ only_restock: true })}>
            🧾 Stock (Repor)
          </button>

          <button className="btn btn-soft" onClick={() => api.openClientsPdf({ contract_only: true })}>
            👥 Clientes (Contrato)
          </button>

          <button
            className="btn btn-soft"
            onClick={() => {
              const y = Number(year);
              const m = Number(month);
              if (!y || !m) return alert("Seleciona ano e mês primeiro.");
              api.openExpensesPdf(y, m);
            }}
          >
            💸 Despesas (período)
          </button>
        </div>
      </div>

      <div className="novo-cliente">
        <form onSubmit={save} className="edit-form">
          <div className="formHeader">
            <h3 className="formTitle">{editingId ? "Editar Cliente" : "Novo Cliente"}</h3>
          </div>

          <div className="fields">
            <label>
              <div>Código do Cliente</div>
              <input
                value={form.client_code}
                onChange={(e) => setField("client_code", e.target.value)}
                placeholder="Ex: 001, 7001, CLI-123..."
              />
            </label>

            <label className="spanAll">
              <div>Nome Fantasia</div>
              <input
                value={form.business_name}
                onChange={(e) => setField("business_name", e.target.value)}
                placeholder="Ex: EUROPOUPANÇA / CAFÉ ORFEU / TENDREX..."
              />
            </label>

            <label className="spanAll">
              <div>Responsável</div>
              <input value={form.name} onChange={(e) => setField("name", e.target.value)} placeholder="Ex: Helena / Paulo..." />
            </label>

            <label>
              <div>Apelido</div>
              <input value={form.nickname} onChange={(e) => setField("nickname", e.target.value)} />
            </label>

            <label>
              <div>Email</div>
              <input value={form.email} onChange={(e) => setField("email", e.target.value)} />
            </label>

            <label>
              <div>Telefone</div>
              <input value={form.phone} onChange={(e) => setField("phone", e.target.value)} />
            </label>

            <label>
              <div>NIF</div>
              <input value={form.vat_number} onChange={(e) => setField("vat_number", e.target.value)} />
            </label>

            <label className="spanAll">
              <div>Morada</div>
              <input value={form.address} onChange={(e) => setField("address", e.target.value)} />
            </label>

            <label>
              <div>Código Postal</div>
              <input value={form.postal_code} onChange={(e) => setField("postal_code", e.target.value)} />
            </label>

            <label>
              <div>Localidade</div>
              <input value={form.city} onChange={(e) => setField("city", e.target.value)} />
            </label>

            {isDesinfex && (
              <label className="spanAll">
                <div>Tipo de praga (texto livre)</div>
                <input value={form.pest_type} onChange={(e) => setField("pest_type", e.target.value)} />
              </label>
            )}

            <label className="spanAll">
              <div>Notas</div>
              <textarea
                rows={3}
                value={form.notes}
                onChange={(e) => setField("notes", e.target.value)}
                placeholder={`SERVICE_ADDR: (morada de serviço)
SERVICE_PC: (código postal)
SERVICE_CITY: (cidade)

(outras notas...)`}
              />
            </label>
          </div>

          {isDesinfex && (
            <div className="contractBox">
              <div className="contractHeader">
                <h4 className="contractTitle">Contrato</h4>

                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={!!form.has_contract}
                    onChange={(e) => setField("has_contract", e.target.checked)}
                  />
                  <span>Tem contrato</span>
                </label>
              </div>

              {form.has_contract ? (
                <div className="fields contractFields">
                  <label>
                    <div>Início do contrato *</div>
                    <input
                      type="date"
                      value={form.contract_start_date}
                      onChange={(e) => setField("contract_start_date", e.target.value)}
                    />
                  </label>

                  <label>
                    <div>Visitas por ano (1 a 12) *</div>
                    <input
                      type="number"
                      min={1}
                      max={12}
                      value={form.visits_per_year}
                      onChange={(e) => setField("visits_per_year", Number(e.target.value))}
                    />
                  </label>

                  <label>
                    <div>Valor do contrato (€/ano)</div>
                    <input
                      type="text"
                      value={form.contract_value_yearly}
                      onChange={(e) => setField("contract_value_yearly", e.target.value)}
                      placeholder="ex: 200"
                    />
                  </label>

                  {editingId && (
                    <div className="contractAction">
                      <button
                        type="button"
                        className="btn rec"
                        onClick={() => generateVisits(editingId)}
                        disabled={loading}
                        title="Cria agendamentos do contrato distribuídos ao longo do ano"
                      >
                        Gerar visitas do contrato
                      </button>

                      <button
                        type="button"
                        className="btn"
                        onClick={() =>
                          openRenew(
                            clients.find((x) => x.id === editingId) || {
                              id: editingId,
                              business_name: form.business_name,
                              visits_per_year: form.visits_per_year,
                              contract_value_yearly: toNum(form.contract_value_yearly),
                            }
                          )
                        }
                        disabled={loading}
                        title="Renova o contrato e gera visitas do novo ciclo (escolhe a data no modal)"
                      >
                        Renovar contrato
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <p className="status contractHint">Sem contrato — podes usar agendamentos manuais normalmente.</p>
              )}
            </div>
          )}

          <div className="btn-form">
            <button className="btn formS" type="submit" disabled={loading}>
              {editingId ? "Guardar alterações" : "Criar cliente"}
            </button>

            {editingId && (
              <button className="btn formC" type="button" onClick={resetForm} disabled={loading}>
                Cancelar edição
              </button>
            )}
          </div>
        </form>
      </div>

      {renewOpen && (
        <div className="modalBackdrop" onClick={() => !loading && setRenewOpen(false)}>
          <div className="modalCard" onClick={(e) => e.stopPropagation()}>
            <h3>Renovar contrato</h3>
            <p>
              Cliente: <b>{fixText(renewClient?.business_name || renewClient?.name || "—")}</b>
            </p>

            <div className="modalGrid">
              <label>
                <div>Data do novo ciclo *</div>
                <input type="date" value={renewDate} onChange={(e) => setRenewDate(e.target.value)} />
              </label>

              <label>
                <div>Visitas por ano (1 a 12)</div>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={renewVPY}
                  onChange={(e) => setRenewVPY(Number(e.target.value))}
                />
              </label>

              <label className="spanAll">
                <div>Valor do contrato (€/ano) (opcional)</div>
                <input
                  type="text"
                  value={renewValue}
                  onChange={(e) => setRenewValue(e.target.value)}
                  placeholder="ex: 200"
                />
                <small>Atual: {renewClient?.contract_value_yearly != null ? eur(renewClient.contract_value_yearly) : "—"}</small>
              </label>
            </div>

            <div className="modalActions">
              <button className="btn ghost" type="button" onClick={() => setRenewOpen(false)} disabled={loading}>
                Cancelar
              </button>
              <button className="btn formS" type="button" onClick={doRenew} disabled={loading}>
                Confirmar renovação
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="lista">
        <div className="listTop">
          <h3 className="listTitle">Lista</h3>

          <div className="searchBar">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Pesquisar por id/código, nome, morada, email, telefone, NIF, cidade..."
            />

            <label className="toggle">
              <input type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} />
              <span>Só ativos</span>
            </label>

            {q ? (
              <button className="btn ghost" type="button" onClick={() => setQ("")} disabled={loading}>
                Limpar
              </button>
            ) : null}
          </div>
        </div>

        <div className="btn-form" style={{ marginBottom: 12, gap: 8, flexWrap: "wrap" }}>
          <button
            className="btn ghost"
            type="button"
            onClick={toggleSelectAllVisible}
            disabled={loading || visibleIds.length === 0}
          >
            {allVisibleSelected ? "Desmarcar visíveis" : "Selecionar visíveis"}
          </button>

          <button className="btn" type="button" onClick={() => removeSelected(false)} disabled={loading || selectedIds.length === 0}>
            Apagar selecionados ({selectedIds.length})
          </button>

          <button
            className="btn danger"
            type="button"
            onClick={() => removeSelected(true)}
            disabled={loading || selectedIds.length === 0}
            title="Apaga também agendamentos e faturas associadas"
          >
            Apagar com force ({selectedIds.length})
          </button>

          <button className="btn ghost" type="button" onClick={clearSelection} disabled={loading || selectedIds.length === 0}>
            Limpar seleção
          </button>
        </div>

        <p className="status">
          Mostrando <b>{filteredClients.length}</b> de <b>{clients.length}</b>
          {onlyActive ? " (só ativos)" : ""}
          {" • "}
          Selecionados: <b>{selectedIds.length}</b>
          {someVisibleSelected && !allVisibleSelected ? " • seleção parcial" : ""}
        </p>

        {filteredClients.length === 0 ? (
          <p className="status">{clients.length === 0 ? "Sem clientes" : "Sem resultados para a pesquisa"}</p>
        ) : (
          <>
            <div className="clientsRowHeader">
              <div style={{ width: 40, textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleSelectAllVisible}
                  title="Selecionar todos os clientes visíveis"
                />
              </div>
              <div className="idcl">Código</div>
              <div>Cliente</div>
              <div>Email</div>
              <div>Telefone</div>
              <div className="actionsHeader">Ações</div>
            </div>

            <ul className="ul">
              {filteredClients.map((c) => (
                <li key={c.id} className={`li ${selectedIds.includes(c.id) ? "selected" : ""}`}>
                  <div className="clientCard">
                    <div className="clientsRow">
                      <div style={{ width: 40, display: "flex", justifyContent: "center", alignItems: "center" }}>
                        <input type="checkbox" checked={selectedIds.includes(c.id)} onChange={() => toggleSelected(c.id)} />
                      </div>

                      <div className="idcl">{c.client_code || c.id}</div>

                      <div className="clientsCell nameCell">
                        <b>{fixText(c.business_name || c.name)}</b>
                        <div className="subLine">
                          {c.name ? <span>Resp: {fixText(c.name)}</span> : null}
                          {c.city ? ` • ${fixText(c.city)}` : " • —"}
                          {c.postal_code ? ` (${fixText(c.postal_code)})` : ""}
                          {c.contact_name ? ` • ${fixText(c.contact_name)}` : ""}
                        </div>
                      </div>

                      <div className="clientsCell emailCell">{c.email || "—"}</div>
                      <div className="clientsCell phoneCell">{c.phone || "—"}</div>

                      <div className="actionsCell">
                        <button className="btn" onClick={() => startEdit(c)} disabled={loading}>
                          Editar
                        </button>
                        {isDesinfex && (
                          <button
                            className="btn rec"
                            onClick={() => openDossier(c.id)}
                            disabled={loading}
                            title="Gera o dossiê do cliente em PDF"
                          >
                            Dossiê (PDF)
                          </button>
                        )}
                        <button className="btn danger" onClick={() => remove(c.id)} disabled={loading}>
                          Apagar
                        </button>
                      </div>
                    </div>

                    <div className="badgesRow">
                      {c.is_active === false ? <span className="badge">Inativo</span> : <span className="badge">Ativo</span>}

                      {isDesinfex ? (
                        <>
                          {c.has_contract ? (
                            <span className="badge">Contrato • {c.visits_per_year || "?"}/ano</span>
                          ) : (
                            <span className="badge">Sem contrato</span>
                          )}

                          {c.contract_value_yearly != null && Number(c.contract_value_yearly) > 0 ? (
                            <span className="badge">€ {Number(c.contract_value_yearly)}/ano</span>
                          ) : null}

                          {c.pest_type ? <span className="badge">Praga: {fixText(c.pest_type)}</span> : null}
                        </>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
