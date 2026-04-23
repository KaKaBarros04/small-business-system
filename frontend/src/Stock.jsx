// Stock.jsx
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import "./Stock.css";

const emptyItem = {
  name: "",
  sku: "",
  unit: "un",
  min_qty: 5,
  notes: "",
};

const emptyMove = {
  type: "IN", // IN | OUT | ADJUST
  qty: 1,
  unit_cost: "", // opcional (para IN)
  total_cost: "", // opcional (para IN)
  notes: "",
  create_expense: true, // só faz sentido no IN
};

function eur(n) {
  return new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(
    Number(n || 0)
  );
}

function num(v) {
  const x = Number(String(v ?? "").replace(",", "."));
  return Number.isFinite(x) ? x : 0;
}

// ✅ unidades inteiras
function isIntUnit(unit) {
  const u = String(unit || "").toLowerCase();
  return u === "un" || u === "cx";
}

// ✅ sanitiza inteiro (remove tudo que não for dígito)
function toIntInput(v) {
  const s = String(v ?? "");
  const digits = s.replace(/\D/g, "");
  return digits === "" ? "" : String(parseInt(digits, 10) || 0);
}

// ✅ sanitiza decimal pt (permite vírgula/ponto)
function toDecInput(v) {
  const s = String(v ?? "");
  const cleaned = s.replace(/[^\d.,]/g, "");
  if (cleaned.includes(",") && cleaned.includes(".")) {
    return cleaned.replace(/\./g, "").replace(",", ".");
  }
  return cleaned.replace(",", ".");
}

export default function Stock() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [form, setForm] = useState({ ...emptyItem });
  const [editingId, setEditingId] = useState(null);

  // modal de movimento
  const [moveOpen, setMoveOpen] = useState(false);
  const [moveItem, setMoveItem] = useState(null);
  const [move, setMove] = useState({ ...emptyMove });

  const sorted = useMemo(() => {
    return [...items].sort((a, b) => (b.id || 0) - (a.id || 0));
  }, [items]);

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const res = await api.listStockItems();
      setItems(res || []);
    } catch (e) {
      setErr(e?.message || "Erro ao carregar stock");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function resetForm() {
    setForm({ ...emptyItem });
    setEditingId(null);
  }

  function setField(k, v) {
    setForm((p) => ({ ...p, [k]: v }));
  }

  function startEdit(it) {
    setMsg("");
    setErr("");
    setEditingId(it.id);
    setForm({
      name: it?.name || "",
      sku: it?.sku || "",
      unit: it?.unit || "un",
      min_qty: Number(it?.min_qty ?? 5),
      notes: it?.notes || "",
    });
  }

  function validateItem(payload) {
    if (!payload.name?.trim()) return "Nome é obrigatório";
    if (!payload.unit?.trim()) return "Unidade é obrigatória";
    const mq = Number(payload.min_qty);
    if (!Number.isFinite(mq) || mq < 0) return "Stock mínimo inválido";
    if (isIntUnit(payload.unit) && !Number.isInteger(mq)) return "Stock mínimo deve ser inteiro para un/cx";
    return "";
  }

  async function saveItem(e) {
    e.preventDefault();
    setMsg("");
    setErr("");

    const payload = {
      name: form.name?.trim(),
      sku: form.sku?.trim() || null,
      unit: form.unit?.trim() || "un",
      min_qty: Number(form.min_qty ?? 5),
      notes: form.notes?.trim() || null,
    };

    // ✅ força inteiro no payload se unit un/cx
    if (isIntUnit(payload.unit)) payload.min_qty = parseInt(String(payload.min_qty || 0), 10) || 0;

    const v = validateItem(payload);
    if (v) {
      setErr(v);
      return;
    }

    setLoading(true);
    try {
      if (editingId) {
        await api.updateStockItem(editingId, payload);
        setMsg("✅ Item atualizado");
      } else {
        await api.createStockItem(payload);
        setMsg("✅ Item criado");
      }
      resetForm();
      await load();
    } catch (e2) {
      setErr(e2?.message || "Erro ao guardar item");
    } finally {
      setLoading(false);
    }
  }

  async function removeItem(id) {
    if (!window.confirm("Apagar este item de stock?")) return;
    setMsg("");
    setErr("");
    setLoading(true);
    try {
      await api.deleteStockItem(id);
      setMsg("✅ Item apagado");
      await load();
    } catch (e) {
      setErr(e?.message || "Erro ao apagar item");
    } finally {
      setLoading(false);
    }
  }

  // -------------------------
  // Movimentos
  // -------------------------
  function openMove(it, type = "IN") {
    setMsg("");
    setErr("");
    setMoveItem(it);
    setMove({
      ...emptyMove,
      type,
      qty: 1,
      unit_cost: "",
      total_cost: "",
      notes: "",
      create_expense: true,
    });
    setMoveOpen(true);
  }

  function closeMove() {
    setMoveOpen(false);
    setMoveItem(null);
    setMove({ ...emptyMove });
  }

  function setMoveField(k, v) {
    setMove((p) => ({ ...p, [k]: v }));
  }

  // auto-cálculo unit_cost <-> total_cost (só para IN)
  useEffect(() => {
    if (!moveOpen) return;
    if (move.type !== "IN") return;

    const q = num(move.qty);
    const uc = move.unit_cost === "" ? null : num(move.unit_cost);
    const tc = move.total_cost === "" ? null : num(move.total_cost);

    if (uc != null && (move.total_cost === "" || move.total_cost == null)) {
      const calc = q > 0 ? uc * q : 0;
      setMove((p) => ({ ...p, total_cost: String(calc || 0) }));
    }

    if (tc != null && (move.unit_cost === "" || move.unit_cost == null)) {
      const calc = q > 0 ? tc / q : 0;
      setMove((p) => ({ ...p, unit_cost: String(calc || 0) }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moveOpen, move.type, move.qty]);

  function validateMove(payload) {
    const q = Number(payload.qty);
    if (!Number.isFinite(q) || q <= 0) return "Quantidade inválida";
    if (isIntUnit(moveItem?.unit) && !Number.isInteger(q)) return "Quantidade tem de ser inteira para un/cx";

    if (payload.type === "IN") {
      if (payload.total_cost != null) {
        const t = Number(payload.total_cost);
        if (!Number.isFinite(t) || t < 0) return "Custo total inválido";
      }
      if (payload.unit_cost != null) {
        const u = Number(payload.unit_cost);
        if (!Number.isFinite(u) || u < 0) return "Custo unitário inválido";
      }
    }
    return "";
  }

  async function submitMove(e) {
    e.preventDefault();
    if (!moveItem) return;

    setMsg("");
    setErr("");
    setLoading(true);

    const qtyFinal = isIntUnit(moveItem.unit)
      ? (parseInt(String(move.qty || 0), 10) || 0)
      : num(move.qty);

    const payload = {
      type: move.type,
      qty: qtyFinal,
      notes: move.notes?.trim() || null,
      unit_cost: move.type === "IN" && move.unit_cost !== "" ? num(move.unit_cost) : null,
      total_cost: move.type === "IN" && move.total_cost !== "" ? num(move.total_cost) : null,
      create_expense: move.type === "IN" ? !!move.create_expense : false,
    };

    const v = validateMove(payload);
    if (v) {
      setLoading(false);
      setErr(v);
      return;
    }

    try {
      await api.moveStockItem(moveItem.id, payload);
      setMsg("✅ Movimento registado");
      closeMove();
      await load();
    } catch (e2) {
      setErr(e2?.message || "Erro ao registar movimento");
    } finally {
      setLoading(false);
    }
  }

  function isLow(it) {
    const q = Number(it?.qty_on_hand ?? 0);
    const min = Number(it?.min_qty ?? 0);
    return Number.isFinite(q) && Number.isFinite(min) && q <= min;
  }

  return (
    <div className="stockPage">
      <div className="card-cliente">
        <div className="clientsTop">
          <h2 className="clientsTitle">Stock</h2>

          <div className="btn-form">
            <button className="btn ghost" onClick={resetForm} disabled={loading}>
              Novo item
            </button>
            <button className="btn" onClick={load} disabled={loading}>
              Atualizar
            </button>
          </div>
        </div>

        {loading && <p className="status">A carregar...</p>}
        {msg && <p className="msg ok">{msg}</p>}
        {err && <p className="msg error">{err}</p>}

        {/* FORM ITEM */}
        <div className="novo-cliente">
          <form onSubmit={saveItem} className="edit-form">
            <div className="formHeader">
              <h3 className="formTitle">{editingId ? `Editar Item #${editingId}` : "Novo Item"}</h3>
            </div>

            <div className="fields">
              <label>
                <div>Nome *</div>
                <input value={form.name} onChange={(e) => setField("name", e.target.value)} />
              </label>

              <label>
                <div>SKU</div>
                <input value={form.sku} onChange={(e) => setField("sku", e.target.value)} />
              </label>

              <label>
                <div>Unidade</div>
                <select value={form.unit} onChange={(e) => setField("unit", e.target.value)}>
                  <option value="un">un</option>
                  <option value="kg">kg</option>
                  <option value="L">L</option>
                  <option value="cx">cx</option>
                </select>
              </label>

              <label>
                <div>Stock mínimo (alerta)</div>
                <input
                  type="number"
                  min={0}
                  step={isIntUnit(form.unit) ? 1 : 0.01}
                  value={form.min_qty}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (isIntUnit(form.unit)) {
                      setField("min_qty", v === "" ? "" : parseInt(v, 10) || 0);
                    } else {
                      setField("min_qty", v === "" ? "" : num(v));
                    }
                  }}
                />
              </label>

              <label className="spanAll">
                <div>Notas</div>
                <textarea
                  rows={3}
                  value={form.notes}
                  onChange={(e) => setField("notes", e.target.value)}
                />
              </label>
            </div>

            <div className="btn-form">
              <button className="btn formS" type="submit" disabled={loading}>
                {editingId ? "Guardar alterações" : "Criar item"}
              </button>

              {editingId && (
                <button className="btn formC" type="button" onClick={resetForm} disabled={loading}>
                  Cancelar edição
                </button>
              )}
            </div>
          </form>
        </div>

        {/* LISTA */}
        <div className="lista">
          <h3 className="listTitle">Itens</h3>

          {sorted.length === 0 ? (
            <p className="status">Sem itens</p>
          ) : (
            <>
              <div className="rowHeader">
                <div className="idcl">ID</div>
                <div>Item</div>
                <div>Stock</div>
                <div>Preço médio</div>
                <div className="actionsHeader">Ações</div>
              </div>

              <ul className="ul">
                {sorted.map((it) => (
                  <li key={it.id} className="li">
                    <div className="clientCard">
                      <div className="row">
                        <div className="idcl">{it.id}</div>

                        <div className="cell nameCell">
                          <b>{it.name}</b>
                          <div className="subLine">
                            {it.sku ? `SKU: ${it.sku}` : "—"} • Unidade: {it.unit || "—"}
                          </div>
                        </div>

                        <div className="cell">
                          <b>
                            {Number(it.qty_on_hand ?? 0)} {it.unit || ""}
                          </b>

                          {isLow(it) ? (
                            <div className="subLine" style={{ color: "var(--danger, #ef4444)" }}>
                              ⚠️ Repor (mín. {Number(it.min_qty ?? 0)} {it.unit || ""})
                            </div>
                          ) : (
                            <div className="subLine">OK</div>
                          )}
                        </div>

                        <div className="cell">
                          {it.avg_unit_cost != null ? eur(it.avg_unit_cost) : "—"}
                          <div className="subLine">Valor em stock: {eur(Number(it.stock_value || 0))}</div>
                        </div>

                        <div className="actionsCell">
                          <button className="btn" onClick={() => openMove(it, "IN")} disabled={loading}>
                            + Entrada
                          </button>
                          <button className="btn" onClick={() => openMove(it, "OUT")} disabled={loading}>
                            - Saída
                          </button>
                          <button className="btn" onClick={() => openMove(it, "ADJUST")} disabled={loading}>
                            Ajuste
                          </button>

                          <button className="btn" onClick={() => startEdit(it)} disabled={loading}>
                            Editar
                          </button>
                          <button className="btn danger" onClick={() => removeItem(it.id)} disabled={loading}>
                            Apagar
                          </button>
                        </div>
                      </div>

                      <div className="badgesRow">
                        {isLow(it) ? (
                          <span className="badge">⚠️ Stock baixo</span>
                        ) : (
                          <span className="badge">Stock OK</span>
                        )}
                        {it.notes ? <span className="badge">📝 {it.notes}</span> : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {/* MODAL MOVIMENTO */}
        {moveOpen && moveItem && (
          <div className="stockModalBackdrop" onClick={closeMove}>
            <div className="stockModalCard" onClick={(e) => e.stopPropagation()}>
              <div className="stockModalTop">
                <h3>
                  Movimento — <b>{moveItem.name}</b>
                </h3>
                <button className="btn" onClick={closeMove} disabled={loading}>
                  Fechar
                </button>
              </div>

              <form onSubmit={submitMove} style={{ marginTop: 10 }}>
                <div className="fields">
                  <label>
                    <div>Tipo</div>
                    <select value={move.type} onChange={(e) => setMoveField("type", e.target.value)}>
                      <option value="IN">Entrada</option>
                      <option value="OUT">Saída</option>
                      <option value="ADJUST">Ajuste</option>
                    </select>
                  </label>

                  <label>
                    <div>Quantidade *</div>

                    {isIntUnit(moveItem.unit) ? (
                      <input
                        type="number"
                        min={1}
                        step={1}
                        inputMode="numeric"
                        value={move.qty}
                        onChange={(e) => setMoveField("qty", toIntInput(e.target.value))}
                        onBlur={() => {
                          if (move.qty === "") setMoveField("qty", 1);
                        }}
                      />
                    ) : (
                      <input
                        type="text"
                        inputMode="decimal"
                        value={move.qty}
                        onChange={(e) => setMoveField("qty", toDecInput(e.target.value))}
                        onBlur={() => {
                          if (move.qty === "") setMoveField("qty", 1);
                        }}
                        placeholder="ex: 1,25"
                      />
                    )}

                    <small className="status">Unidade: {moveItem.unit || "—"}</small>
                  </label>

                  {move.type === "IN" ? (
                    <>
                      <label>
                        <div>Custo unitário (opcional)</div>
                        <input
                          type="text"
                          value={move.unit_cost}
                          onChange={(e) => setMoveField("unit_cost", toDecInput(e.target.value))}
                          placeholder="ex: 12,50"
                        />
                      </label>

                      <label>
                        <div>Custo total (opcional)</div>
                        <input
                          type="text"
                          value={move.total_cost}
                          onChange={(e) => setMoveField("total_cost", toDecInput(e.target.value))}
                          placeholder="ex: 50,00"
                        />
                      </label>
                    </>
                  ) : null}

                  <label className="spanAll">
                    <div>Notas</div>
                    <textarea
                      rows={3}
                      value={move.notes}
                      onChange={(e) => setMoveField("notes", e.target.value)}
                    />
                  </label>
                </div>

                <div className="btn-form" style={{ marginTop: 10 }}>
                  <button className="btn formS" type="submit" disabled={loading}>
                    Guardar movimento
                  </button>
                  <button className="btn formC" type="button" onClick={closeMove} disabled={loading}>
                    Cancelar
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
