import { useEffect, useMemo, useState } from "react";
import { api, resolveApiUrl } from "./api";
import "./Manual_Invoices.css";

function fmtDateTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat("pt-PT", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return String(iso).slice(0, 16).replace("T", " ");
  }
}

function money(v) {
  const n = Number(v || 0);
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
  }).format(n);
}

function statusLabel(status) {
  return {
    DRAFT: "Rascunho",
    ISSUED: "Emitida",
    PAID: "Paga",
    CANCELED: "Cancelada",
  }[status] || status;
}

function displayClientTitle(row) {
  const code = row?.client?.client_code?.trim();
  const name =
    row?.client?.business_name?.trim() ||
    row?.client?.name?.trim() ||
    row?.supplier_name ||
    "—";

  return code ? `${code} — ${name}` : name;
}

function displayClientMeta(row) {
  const parts = [];

  if (row?.client?.address) parts.push(row.client.address);

  const pcCity = [row?.client?.postal_code, row?.client?.city].filter(Boolean).join(" ");
  if (pcCity) parts.push(pcCity);

  return parts.join(" • ");
}

function currentYearMonthLocal() {
  const now = new Date();
  return {
    year: now.getFullYear(),
    month: now.getMonth() + 1,
  };
}

export default function ManualInvoices() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [me, setMe] = useState(null);
  const [editing, setEditing] = useState(null);

  const isAdmin = (me?.role || "").toUpperCase() === "ADMIN";

  const [clientName, setClientName] = useState("");
  const [number, setNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [taxRate, setTaxRate] = useState("23");
  const [notes, setNotes] = useState("");
  const [invoiceStatus, setInvoiceStatus] = useState("ISSUED");
  const [invoiceKind, setInvoiceKind] = useState("MANUAL");

  const [items, setItems] = useState([]);
  const [itemDesc, setItemDesc] = useState("");
  const [itemQty, setItemQty] = useState("1");
  const [itemUnit, setItemUnit] = useState("0");

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const nowRef = currentYearMonthLocal();
  const [reportYear, setReportYear] = useState(String(nowRef.year));
  const [reportMonth, setReportMonth] = useState(String(nowRef.month));
  const [reportKind, setReportKind] = useState("CONTRACT");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api.listManualInvoices();
      setRows(
        Array.isArray(data)
          ? data.sort((a, b) => new Date(b.issue_date) - new Date(a.issue_date))
          : []
      );
    } catch (e) {
      setError("Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    api.me().then(setMe).catch(() => {});
  }, []);

  useEffect(() => {
    if (!editing) return;

    setClientName(editing.supplier_name || "");
    setNumber(editing.invoice_number || "");
    setIssueDate(editing.issue_date?.slice(0, 16) || "");
    setNotes(editing.notes || "");
    setItems(editing.items || []);
    setInvoiceStatus(editing.status || "DRAFT");
    setInvoiceKind(editing.invoice_kind || "MANUAL");
  }, [editing]);

  function resetForm() {
    setEditing(null);
    setClientName("");
    setNumber("");
    setIssueDate("");
    setTaxRate("23");
    setNotes("");
    setInvoiceStatus("ISSUED");
    setInvoiceKind("MANUAL");
    setItems([]);
    setItemDesc("");
    setItemQty("1");
    setItemUnit("0");
  }

  function addItem() {
    if (!itemDesc.trim()) {
      setError("Descrição do item é obrigatória");
      return;
    }

    const qty = Number(itemQty);
    const unit = Number(itemUnit);

    if (!Number.isFinite(qty) || qty <= 0) {
      setError("Quantidade inválida");
      return;
    }

    if (!Number.isFinite(unit) || unit < 0) {
      setError("Preço inválido");
      return;
    }

    setItems((prev) => [
      ...prev,
      {
        description: itemDesc.trim(),
        qty,
        unit_price: unit,
      },
    ]);

    setItemDesc("");
    setItemQty("1");
    setItemUnit("0");
    setError("");
  }

  const preview = useMemo(() => {
    const subtotal = items.reduce((a, i) => a + Number(i.qty || 0) * Number(i.unit_price || 0), 0);
    const tax = subtotal * (Number(taxRate) / 100);
    return { subtotal, tax, total: subtotal + tax };
  }, [items, taxRate]);

  async function submit(e) {
    e.preventDefault();
    setError("");

    if (!clientName.trim()) return setError("Cliente obrigatório");
    if (!issueDate) return setError("Data obrigatória");
    if (!items.length) return setError("Adiciona pelo menos 1 item");

    if (invoiceStatus === "ISSUED" && !number.trim()) {
      return setError("Número obrigatório para fatura emitida");
    }

    const payload = {
      supplier_name: clientName.trim(),
      invoice_number: number.trim() || null,
      issue_date: new Date(issueDate).toISOString(),
      notes: notes.trim() || null,
      items,
      tax_rate: Number(taxRate),
      status: invoiceStatus,
      invoice_kind: invoiceKind,
    };

    try {
      if (editing) {
        await api.updateManualInvoice(editing.id, payload);
      } else {
        await api.createManualInvoice(payload);
      }
      resetForm();
      load();
    } catch (e) {
      setError("Erro ao guardar");
    }
  }

  async function uploadPdf(id, file) {
    setError("");
    setLoading(true);
    try {
      await api.uploadManualInvoicePdf(id, file);
      await load();
    } catch (e) {
      setError(e?.message || "Erro no upload");
    } finally {
      setLoading(false);
    }
  }

  async function setStatus(id, status) {
    setError("");
    setLoading(true);
    try {
      await api.updateManualInvoiceStatus(id, status);
      await load();
    } catch (e) {
      setError(e?.message || "Erro ao atualizar status");
    } finally {
      setLoading(false);
    }
  }

  async function del(id) {
    if (!confirm("Apagar esta fatura?")) return;

    setError("");
    setLoading(true);
    try {
      await api.deleteManualInvoice(id);
      await load();
    } catch (e) {
      setError(e?.message || "Erro ao apagar");
    } finally {
      setLoading(false);
    }
  }

  async function openPendingPdf() {
    setError("");

    try {
      await api.openPendingInvoicesPdf({
        year: reportYear ? Number(reportYear) : null,
        month: reportMonth ? Number(reportMonth) : null,
        invoice_kind: reportKind || "",
      });
    } catch (e) {
      setError(e?.message || "Erro ao abrir PDF de pendentes");
    }
  }

  async function openClientAvi(clientId) {
    setError("");

    try {
      await api.openClientPendingInvoicesAviPdf(clientId, {
        year: reportYear ? Number(reportYear) : null,
        month: reportMonth ? Number(reportMonth) : null,
        invoice_kind: reportKind || "",
      });
    } catch (e) {
      setError(e?.message || "Erro ao abrir AVI do cliente");
    }
  }

  const filtered = rows.filter((r) => {
    if (statusFilter !== "ALL" && r.status !== statusFilter) return false;
    if (!query.trim()) return true;

    const q = query.toLowerCase();

    const fiscalAddress = (r.client?.address || "").toLowerCase();
    const fiscalPostalCode = (r.client?.postal_code || "").toLowerCase();
    const fiscalCity = (r.client?.city || "").toLowerCase();

    const serviceAddress = (r.client?.service_address || "").toLowerCase();
    const servicePostalCode = (r.client?.service_postal_code || "").toLowerCase();
    const serviceCity = (r.client?.service_city || "").toLowerCase();

    const fullFiscalAddress = [fiscalAddress, fiscalPostalCode, fiscalCity]
      .filter(Boolean)
      .join(" ");

    const fullServiceAddress = [serviceAddress, servicePostalCode, serviceCity]
      .filter(Boolean)
      .join(" ");

    return (
      (r.supplier_name || "").toLowerCase().includes(q) ||
      (r.invoice_number || "").toLowerCase().includes(q) ||
      (r.invoice_kind || "").toLowerCase().includes(q) ||
      (r.client?.client_code || "").toLowerCase().includes(q) ||
      (r.client?.business_name || "").toLowerCase().includes(q) ||
      (r.client?.name || "").toLowerCase().includes(q) ||
      fiscalAddress.includes(q) ||
      fiscalPostalCode.includes(q) ||
      fiscalCity.includes(q) ||
      fullFiscalAddress.includes(q) ||
      serviceAddress.includes(q) ||
      servicePostalCode.includes(q) ||
      serviceCity.includes(q) ||
      fullServiceAddress.includes(q)
    );
  });

  return (
    <div className="mi">
      <div className="miHeader">
        <div>
          <h2>Faturas</h2>
          <p>Faturas e pré-faturas de clientes</p>
        </div>
        {loading ? <span className="status">A carregar...</span> : null}
      </div>

      {error && <div className="miMsg error">{error}</div>}

      <section className="miCard">
        <h3>PDF de pré-faturas pendentes</h3>

        <div className="miPendingBar">
          <label>
            <span>Ano</span>
            <input
              type="number"
              value={reportYear}
              onChange={(e) => setReportYear(e.target.value)}
              placeholder="2026"
            />
          </label>

          <label>
            <span>Mês</span>
            <select value={reportMonth} onChange={(e) => setReportMonth(e.target.value)}>
              <option value="">Todos</option>
              <option value="1">01</option>
              <option value="2">02</option>
              <option value="3">03</option>
              <option value="4">04</option>
              <option value="5">05</option>
              <option value="6">06</option>
              <option value="7">07</option>
              <option value="8">08</option>
              <option value="9">09</option>
              <option value="10">10</option>
              <option value="11">11</option>
              <option value="12">12</option>
            </select>
          </label>

          <label>
            <span>Tipo</span>
            <select value={reportKind} onChange={(e) => setReportKind(e.target.value)}>
              <option value="">Todos</option>
              <option value="CONTRACT">CONTRACT</option>
              <option value="MANUAL">MANUAL</option>
            </select>
          </label>

          <button className="btn" type="button" onClick={openPendingPdf}>
            PDF pendentes
          </button>
        </div>
      </section>

      <form onSubmit={submit} className="miCard miForm">
        <div className="miFields">
          <label>
            <span>Cliente</span>
            <input
              placeholder="Cliente"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
            />
          </label>

          <label>
            <span>Número</span>
            <input
              placeholder={invoiceStatus === "DRAFT" ? "Opcional no rascunho" : "Número"}
              value={number}
              onChange={(e) => setNumber(e.target.value)}
            />
          </label>

          <label>
            <span>Data</span>
            <input
              type="datetime-local"
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
            />
          </label>

          <label>
            <span>Tipo</span>
            <select value={invoiceKind} onChange={(e) => setInvoiceKind(e.target.value)}>
              <option value="MANUAL">MANUAL</option>
              <option value="CONTRACT">CONTRACT</option>
            </select>
          </label>

          <label>
            <span>Status</span>
            <select value={invoiceStatus} onChange={(e) => setInvoiceStatus(e.target.value)}>
              <option value="DRAFT">DRAFT</option>
              <option value="ISSUED">ISSUED</option>
              <option value="PAID">PAID</option>
              <option value="CANCELED">CANCELED</option>
            </select>
          </label>

          <label>
            <span>IVA (%)</span>
            <select value={taxRate} onChange={(e) => setTaxRate(e.target.value)}>
              <option value="23">23%</option>
              <option value="13">13%</option>
              <option value="6">6%</option>
              <option value="0">0%</option>
            </select>
          </label>

          <label className="miSpanAll">
            <span>Notas</span>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>

        <div className="miDivider">
          <div className="miItemsHeader">
            <b>Itens</b>
            <span className="miPreview">
              Subtotal {money(preview.subtotal)} — IVA {money(preview.tax)} — Total {money(preview.total)}
            </span>
          </div>

          <div className="miItemsRowLabels">
            <span className="miLbl">Descrição:</span>
            <input
              placeholder="Descrição"
              value={itemDesc}
              onChange={(e) => setItemDesc(e.target.value)}
            />

            <span className="miLbl">Quantidade:</span>
            <input
              placeholder="Qty"
              value={itemQty}
              onChange={(e) => setItemQty(e.target.value)}
            />

            <span className="miLbl">Preço:</span>
            <input
              placeholder="Preço"
              value={itemUnit}
              onChange={(e) => setItemUnit(e.target.value)}
            />

            <span className="miLbl miLblSpacer" aria-hidden="true"></span>
            <button type="button" className="btn miItemsBtn" onClick={addItem} disabled={loading}>
              Adicionar
            </button>
          </div>

          {items.length > 0 && (
            <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
              {items.map((it, idx) => (
                <div key={idx} className="miCard" style={{ padding: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                    <div style={{ fontWeight: 950 }}>
                      {it.description} — {it.qty} x €{it.unit_price}
                    </div>
                    <button
                      type="button"
                      className="btn danger"
                      onClick={() => setItems((prev) => prev.filter((_, i) => i !== idx))}
                      disabled={loading}
                    >
                      Remover
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="miFormActions">
          <button className="btn" type="submit" disabled={loading}>
            {editing ? "Salvar" : "Criar"}
          </button>

          {editing && (
            <button className="btn ghost" type="button" onClick={resetForm} disabled={loading}>
              Cancelar edição
            </button>
          )}
        </div>
      </form>

      <div className="miToolbar">
        <input
          className="miSearch"
          placeholder="Pesquisar cliente, código, número, morada fiscal ou morada de serviço..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="ALL">Todos</option>
          <option value="DRAFT">Rascunhos</option>
          <option value="ISSUED">Emitidas</option>
          <option value="PAID">Pagas</option>
          <option value="CANCELED">Canceladas</option>
        </select>

        <button className="btn ghost" onClick={load} disabled={loading}>
          Recarregar
        </button>
      </div>

      {loading ? (
        <p className="status">A carregar...</p>
      ) : filtered.length === 0 ? (
        <p className="status">Nenhuma fatura.</p>
      ) : (
        <div className="miTable">
          <div className="miTHead">
            <div>Cliente</div>
            <div>Número</div>
            <div>Data</div>
            <div>Total</div>
            <div>Status</div>
            <div>PDF</div>
            <div style={{ textAlign: "right" }}>Ações</div>
          </div>

          <div className="miTBody">
            {filtered.map((r) => (
              <div key={r.id} className="miTRow">
                <div className="miCell" data-label="Cliente">
                  <div className="miCellStrong">{displayClientTitle(r)}</div>
                  <div className="miMuted">
                    #{r.id}
                    {r.invoice_kind && (
                      <span className={`miKind ${r.invoice_kind}`}>
                        {r.invoice_kind}
                      </span>
                    )}
                  </div>
                  {displayClientMeta(r) && (
                    <div className="miMuted" style={{ marginTop: 4 }}>
                      {displayClientMeta(r)}
                    </div>
                  )}
                </div>

                <div className="miCell" data-label="Número">
                  <div className="miCellStrong">{r.invoice_number || "—"}</div>
                </div>

                <div className="miCell" data-label="Data">
                  <div className="miCellStrong">{fmtDateTime(r.issue_date)}</div>
                </div>

                <div className="miCell" data-label="Total">
                  <div className="miCellStrong">{money(r.total)}</div>
                </div>

                <div className="miCell" data-label="Status">
                  <span className={`miStatus ${r.status}`}>
                    {statusLabel(r.status)}
                  </span>
                </div>

                <div className="miCell" data-label="PDF">
                  {r.pdf_path ? (
                    <button
                      className="btn ghost"
                      onClick={() => window.open(resolveApiUrl(r.pdf_path), "_blank")}
                    >
                      Abrir
                    </button>
                  ) : (
                    <span className="miPdfPill">Sem PDF</span>
                  )}
                </div>

                <div className="miCell" data-label="Ações">
                  <div className="miActions">
                    {r.client?.id && r.status === "DRAFT" && (
                      <button
                        className="btn ghost"
                        type="button"
                        onClick={() => openClientAvi(r.client.id)}
                        disabled={loading}
                      >
                        AVI
                      </button>
                    )}

                    {!r.pdf_path && (
                      <label className="miUpload" title="Anexar PDF da fatura">
                        PDF
                        <input
                          type="file"
                          accept="application/pdf"
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) uploadPdf(r.id, f);
                            e.target.value = "";
                          }}
                          disabled={loading}
                        />
                      </label>
                    )}

                    {(r.status === "DRAFT" || r.status === "ISSUED") && (
                      <button className="btn" type="button" onClick={() => setEditing(r)} disabled={loading}>
                        Editar
                      </button>
                    )}

                    {r.status === "DRAFT" && isAdmin && (
                      <button
                        className="btn"
                        type="button"
                        onClick={() => {
                          if (!r.invoice_number) {
                            alert("Preencha o número antes de emitir");
                            return;
                          }
                          setStatus(r.id, "ISSUED");
                        }}
                        disabled={loading}
                      >
                        Emitir
                      </button>
                    )}

                    {r.status !== "PAID" && r.status !== "CANCELED" && (
                      <button className="btn" type="button" onClick={() => setStatus(r.id, "PAID")} disabled={loading}>
                        PAGO
                      </button>
                    )}

                    {r.status !== "CANCELED" && (
                      <button className="btn ghost" type="button" onClick={() => setStatus(r.id, "CANCELED")} disabled={loading}>
                        Cancelar
                      </button>
                    )}

                    {isAdmin && (r.status === "DRAFT" || r.status === "ISSUED") && (
                      <button className="btn danger" type="button" onClick={() => del(r.id)} disabled={loading}>
                        Apagar
                      </button>
                    )}
                  </div>

                  {r.notes && (
                    <div className="miRowMeta" style={{ marginTop: 8 }}>
                      Notas: {r.notes}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}