import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import "./Expenses.css";

function eur(n) {
  return new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(Number(n || 0));
}

function toLocalInput(iso) {
  if (!iso) return "";
  return String(iso).slice(0, 16);
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-PT");
  } catch {
    return String(iso).slice(0, 16).replace("T", " ");
  }
}

function monthKey(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

const CATEGORIES = [
  { value: "SUPPLIES", label: "🧴 Consumíveis / Produtos" },
  { value: "FUEL", label: "⛽ Combustível" },
  { value: "EQUIPMENT", label: "🧰 Equipamentos / Ferramentas" },
  { value: "VEHICLE", label: "🚐 Viatura / Manutenção" },
  { value: "RENT", label: "🏠 Renda / Espaço" },
  { value: "UTILITIES", label: "💡 Água/Luz/Internet" },
  { value: "TAXES", label: "🧾 Taxas / Impostos" },
  { value: "OTHER", label: "➕ Outro" },
];

export default function Expenses() {
  const [expenses, setExpenses] = useState([]);

  // create
  const [date, setDate] = useState("");
  const [category, setCategory] = useState("SUPPLIES");
  const [customCategory, setCustomCategory] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");

  // edit
  const [editingId, setEditingId] = useState(null);
  const [editDate, setEditDate] = useState("");
  const [editCategory, setEditCategory] = useState("SUPPLIES");
  const [editCustomCategory, setEditCustomCategory] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editAmount, setEditAmount] = useState("");

  // ui
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // filter: texto
  const [query, setQuery] = useState("");

  // filter: período
  const now = useMemo(() => new Date(), []);
  const [periodMode, setPeriodMode] = useState("MONTH"); // MONTH | YEAR | ALL
  const [selectedMonth, setSelectedMonth] = useState(monthKey(now)); // yyyy-mm
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());

  async function load() {
    setError("");
    setLoading(true);
    try {
      const data = await api.listExpenses();
      setExpenses(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e?.message || "Erro ao carregar despesas");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function resolvedCategory(base, custom) {
    if ((base || "").toUpperCase() === "OTHER") {
      return (custom || "").trim() || "OTHER";
    }
    return (base || "").trim();
  }

  async function create(e) {
    e.preventDefault();
    setError("");

    if (!description.trim()) return setError("Descrição é obrigatória");
    const n = Number(amount);
    if (Number.isNaN(n) || n < 0) return setError("Valor inválido");

    const cat = resolvedCategory(category, customCategory);
    if (!cat) return setError("Categoria é obrigatória");

    const payload = {
      category: cat,
      description: description.trim(),
      amount: n,
      date: date ? new Date(date).toISOString() : null,
    };

    setLoading(true);
    try {
      await api.createExpense(payload);
      setDate("");
      setCategory("SUPPLIES");
      setCustomCategory("");
      setDescription("");
      setAmount("");
      await load();
    } catch (e2) {
      setError(e2?.message || "Erro ao criar despesa");
    } finally {
      setLoading(false);
    }
  }

  function startEdit(exp) {
    setEditingId(exp.id);
    setEditDate(toLocalInput(exp.date));
    setEditDescription(exp.description || "");
    setEditAmount(String(exp.amount ?? ""));

    // se categoria não for uma das conhecidas, cai em OTHER + custom
    const known = CATEGORIES.some((c) => c.value === exp.category);
    if (known) {
      setEditCategory(exp.category || "SUPPLIES");
      setEditCustomCategory("");
    } else {
      setEditCategory("OTHER");
      setEditCustomCategory(exp.category || "");
    }
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDate("");
    setEditCategory("SUPPLIES");
    setEditCustomCategory("");
    setEditDescription("");
    setEditAmount("");
  }

  async function saveEdit(id) {
    setError("");

    if (!editDescription.trim()) return setError("Descrição é obrigatória");
    const n = Number(editAmount);
    if (Number.isNaN(n) || n < 0) return setError("Valor inválido");
    if (!editDate) return setError("Data/hora é obrigatória");

    const cat = resolvedCategory(editCategory, editCustomCategory);
    if (!cat) return setError("Categoria é obrigatória");

    setLoading(true);
    try {
      await api.updateExpense(id, {
        date: new Date(editDate).toISOString(),
        category: cat,
        description: editDescription.trim(),
        amount: n,
      });
      cancelEdit();
      await load();
    } catch (e2) {
      setError(e2?.message || "Erro ao salvar alterações");
    } finally {
      setLoading(false);
    }
  }

  async function del(id) {
    setError("");
    const ok = confirm("Apagar esta despesa?");
    if (!ok) return;

    setLoading(true);
    try {
      await api.deleteExpense(id);
      await load();
    } catch (e2) {
      setError(e2?.message || "Erro ao apagar despesa");
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    let base = expenses || [];

    // período
    if (periodMode !== "ALL") {
      base = base.filter((e) => {
        const d = e.date ? new Date(e.date) : null;
        if (!d || Number.isNaN(d.getTime())) return false;

        if (periodMode === "MONTH") {
          const [y, m] = String(selectedMonth || "").split("-").map(Number);
          if (!y || !m) return true;
          return d.getFullYear() === y && d.getMonth() + 1 === m;
        }

        if (periodMode === "YEAR") {
          const y = Number(selectedYear);
          if (!y) return true;
          return d.getFullYear() === y;
        }

        return true;
      });
    }

    // texto
    if (!q) return base;

    return base.filter((e) => {
      const c = (e.category || "").toLowerCase();
      const d = (e.description || "").toLowerCase();
      return c.includes(q) || d.includes(q);
    });
  }, [expenses, query, periodMode, selectedMonth, selectedYear]);

  const total = useMemo(() => {
    return (filtered || []).reduce((acc, e) => acc + Number(e.amount || 0), 0);
  }, [filtered]);

  const periodLabel = useMemo(() => {
    if (periodMode === "ALL") return "Todos";
    if (periodMode === "YEAR") return `Ano ${selectedYear}`;
    return `Mês ${selectedMonth}`;
  }, [periodMode, selectedMonth, selectedYear]);

  const pdfYearMonth = useMemo(() => {
    if (periodMode === "MONTH") {
      const [y, m] = String(selectedMonth || "").split("-").map(Number);
      return { y: Number(y || 0), m: Number(m || 0) };
    }
    if (periodMode === "YEAR") return { y: Number(selectedYear || 0), m: 0 };
    return { y: 0, m: 0 };
  }, [periodMode, selectedMonth, selectedYear]);

  function exportPdf() {
    // teu endpoint: openExpensesPdf(year, month) (month 0 = ano/todos)
    if (periodMode === "ALL") {
      // melhor comportamento: exportar ano atual inteiro
      api.openExpensesPdf(new Date().getFullYear(), 0);
      return;
    }
    api.openExpensesPdf(pdfYearMonth.y, pdfYearMonth.m);
  }

  return (
    <div className="exp">
      <div className="expHeader">
        <div>
          <h2>Despesas</h2>
          <p>Regista, filtra por período e exporta PDF.</p>
        </div>
        {loading ? <span className="status">A carregar...</span> : null}
      </div>

      {error && <div className="expMsg error">{error}</div>}

      <section className="expCard">
        <h3>Nova despesa</h3>

        <form onSubmit={create} className="expForm">
          <div className="expFields">
            <label>
              <span>Data e hora (opcional — se vazio usa agora)</span>
              <input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>

            <label>
              <span>Categoria</span>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>

            {category === "OTHER" && (
              <label className="expSpanAll">
                <span>Categoria personalizada</span>
                <input
                  value={customCategory}
                  onChange={(e) => setCustomCategory(e.target.value)}
                  placeholder="ex: PUBLICIDADE, SEGURO, SUBSCRIÇÃO..."
                />
              </label>
            )}

            <label className="expSpanAll">
              <span>Descrição</span>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="ex: Produtos de limpeza"
              />
            </label>

            <label>
              <span>Valor (€)</span>
              <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="ex: 25.50" />
            </label>
          </div>

          <div className="expActions">
            <button className="btn" type="submit" disabled={loading}>
              Adicionar
            </button>
          </div>
        </form>
      </section>

      <div className="expFilters">
        <div className="expPills" role="group" aria-label="Filtro de período">
          <button className={`expPill ${periodMode === "MONTH" ? "active" : ""}`} onClick={() => setPeriodMode("MONTH")}>
            Mês
          </button>
          <button className={`expPill ${periodMode === "YEAR" ? "active" : ""}`} onClick={() => setPeriodMode("YEAR")}>
            Ano
          </button>
          <button className={`expPill ${periodMode === "ALL" ? "active" : ""}`} onClick={() => setPeriodMode("ALL")}>
            Todos
          </button>
        </div>

        {periodMode === "MONTH" && (
          <input type="month" value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)} />
        )}

        {periodMode === "YEAR" && (
          <input
            type="number"
            min={1900}
            max={3000}
            step={1}
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            style={{ width: 120 }}
          />
        )}

        <button className="btn ghost" onClick={exportPdf} disabled={loading}>
          📄 Exportar PDF ({periodLabel})
        </button>
      </div>

      <div className="expToolbar">
        <input
          className="expSearch"
          placeholder="Pesquisar (categoria/descrição...)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn ghost" onClick={load} disabled={loading}>
          Recarregar
        </button>
        <div className="expTotal">
          Total: {eur(total)} <small>({filtered.length} itens)</small>
        </div>
      </div>

      {loading ? (
        <p className="status">A carregar...</p>
      ) : filtered.length === 0 ? (
        <p className="status">Nenhuma despesa.</p>
      ) : (
        <div className="expTable">
          <div className="expHead">
            <div>ID</div>
            <div>Data</div>
            <div>Descrição</div>
            <div>Categoria</div>
            <div>Valor</div>
            <div style={{ textAlign: "right" }}>Ações</div>
          </div>


          <div className="expBody">
            {filtered.map((e) => (
              <div key={e.id} className="expRow">
                
                <div className="expCell" data-label="ID">
                  <div className="expStrong">#{e.id}</div>
                  <div className="expMuted">{fmtDate(e.date)}</div>
                </div>

                <div className="expCell" data-label="Data">
                  <div className="expStrong">{fmtDate(e.date)}</div>
                </div>

                <div className="expCell" data-label="Descrição">
                  <div className="expStrong">{e.description}</div>
                </div>

                <div className="expCell" data-label="Categoria">
                  <div className="expStrong">{e.category}</div>
                </div>

                <div className="expCell" data-label="Valor">
                  <div className="expAmount">{eur(e.amount)}</div>
                </div>

                <div className="expCell expRight" data-label="Ações">
                  <div className="expRowActions">
                    <button
                      className="btn"
                      onClick={() => startEdit(e)}
                      disabled={loading}
                    >
                      Editar
                    </button>
                    <button
                      className="btn danger"
                      onClick={() => del(e.id)}
                      disabled={loading}
                    >
                      Apagar
                    </button>
                  </div>
                </div>

                {editingId === e.id && (
                  <div className="expEditBox">
                    <div className="expEditFields">
                      <label>
                        <span>Data e hora</span>
                        <input
                          type="datetime-local"
                          value={editDate}
                          onChange={(ev) => setEditDate(ev.target.value)}
                        />
                      </label>

                      <label>
                        <span>Categoria</span>
                        <select
                          value={editCategory}
                          onChange={(ev) => setEditCategory(ev.target.value)}
                        >
                          {CATEGORIES.map((c) => (
                            <option key={c.value} value={c.value}>
                              {c.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      {editCategory === "OTHER" && (
                        <label className="expSpanAll">
                          <span>Categoria personalizada</span>
                          <input
                            value={editCustomCategory}
                            onChange={(ev) => setEditCustomCategory(ev.target.value)}
                          />
                        </label>
                      )}

                      <label className="expSpanAll">
                        <span>Descrição</span>
                        <input
                          value={editDescription}
                          onChange={(ev) => setEditDescription(ev.target.value)}
                        />
                      </label>

                      <label>
                        <span>Valor (€)</span>
                        <input
                          value={editAmount}
                          onChange={(ev) => setEditAmount(ev.target.value)}
                        />
                      </label>
                    </div>

                    <div className="expActions">
                      <button
                        className="btn"
                        onClick={() => saveEdit(e.id)}
                        disabled={loading}
                      >
                        Salvar
                      </button>
                      <button
                        className="btn ghost"
                        onClick={cancelEdit}
                        disabled={loading}
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
