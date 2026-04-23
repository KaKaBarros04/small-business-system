// GroupDashboard.jsx
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
  BarChart,
  Bar,
} from "recharts";

import "./GroupDashboard.css";

function eur(n) {
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(n || 0));
}

function monthKey(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function labelFromYM(year, month) {
  return `${String(month).padStart(2, "0")}/${year}`;
}

export default function GroupDashboard() {
  const now = useMemo(() => new Date(), []);
  const [selectedKey, setSelectedKey] = useState(monthKey(now));

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [mode, setMode] = useState("month");
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());

  const [year, month] = useMemo(() => {
    const [y, m] = (selectedKey || "").split("-");
    return [Number(y), Number(m)];
  }, [selectedKey]);

  async function load(y, m) {
    setLoading(true);
    setError("");
    try {
      const res = await api.getGroupDashboard(y, m);
      setData(res);
    } catch (e) {
      setError(e?.message || "Erro ao carregar dashboard do grupo");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (mode === "year") {
      if (Number.isFinite(selectedYear) && selectedYear >= 1900 && selectedYear <= 3000) {
        load(selectedYear, 0);
      }
      return;
    }

    if (Number.isFinite(year) && Number.isFinite(month) && month >= 1 && month <= 12) {
      load(year, month);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, year, month, selectedYear]);

  // ✅ filtra empresas do grupo (remove Empresa A/B)
  const ALLOWED_COMPANIES = ["Desinfex", "L&A Limpezas"];
  const companies = useMemo(() => {
    const arr = data?.companies || [];
    return arr.filter((c) => ALLOWED_COMPANIES.includes(String(c?.name || "").trim()));
  }, [data]);

  // ✅ Totais somados no front (inclui IVA)
  const totals = useMemo(() => {
    const t = {
      invoices_total: 0,
      invoices_paid_count: 0,
      revenue_paid_total: 0,
      revenue_issued_total: 0,
      expenses_total: 0,
      profit_total: 0,
      appointments_total: 0,
      appointments_scheduled: 0,
      appointments_done: 0,
      appointments_canceled: 0,
      vat_issued_total: 0,
      vat_paid_total: 0,
      vat_pending_total: 0,
    };

    for (const c of companies) {
      const x = c?.data?.totals || {};
      t.invoices_total += Number(x.invoices_total || 0);
      t.invoices_paid_count += Number(x.invoices_paid_count || 0);
      t.revenue_paid_total += Number(x.revenue_paid_total || 0);
      t.revenue_issued_total += Number(x.revenue_issued_total || 0);
      t.expenses_total += Number(x.expenses_total || 0);
      t.profit_total += Number(x.profit_total || 0);
      t.appointments_total += Number(x.appointments_total || 0);
      t.appointments_scheduled += Number(x.appointments_scheduled || 0);
      t.appointments_done += Number(x.appointments_done || 0);
      t.appointments_canceled += Number(x.appointments_canceled || 0);

      t.vat_issued_total += Number(x.vat_issued_total || 0);
      t.vat_paid_total += Number(x.vat_paid_total || 0);
      t.vat_pending_total += Number(x.vat_pending_total || 0);
    }

    return t;
  }, [companies]);

  // ✅ Série de lucro por mês somada (grupo)
  const profitSeries = useMemo(() => {
    const map = new Map(); // key: "YYYY-MM"
    for (const c of companies) {
      const arr = c?.data?.revenue_by_month || [];
      for (const x of arr) {
        const key = `${x.year}-${String(x.month).padStart(2, "0")}`;
        const prev = map.get(key) || { year: x.year, month: x.month, profit: 0 };
        prev.profit += Number(x.profit || 0);
        map.set(key, prev);
      }
    }
    return Array.from(map.values())
      .sort((a, b) => a.year - b.year || a.month - b.month)
      .map((x) => ({ label: labelFromYM(x.year, x.month), profit: x.profit }));
  }, [companies]);

  // ✅ Série IVA por mês somada (grupo) — precisa que backend mande vat_paid/vat_issued em revenue_by_month
  const vatSeries = useMemo(() => {
    const map = new Map();
    for (const c of companies) {
      const arr = c?.data?.revenue_by_month || [];
      for (const x of arr) {
        const key = `${x.year}-${String(x.month).padStart(2, "0")}`;
        const prev = map.get(key) || { year: x.year, month: x.month, vat_paid: 0, vat_issued: 0 };
        prev.vat_paid += Number(x.vat_paid || 0);
        prev.vat_issued += Number(x.vat_issued || 0);
        map.set(key, prev);
      }
    }
    return Array.from(map.values())
      .sort((a, b) => a.year - b.year || a.month - b.month)
      .map((x) => ({
        label: labelFromYM(x.year, x.month),
        vat_paid: x.vat_paid,
        vat_issued: x.vat_issued,
      }));
  }, [companies]);

  // ✅ Donut Lucro vs Despesas (grupo)
  const profit = Number(totals.profit_total || 0);
  const expenses = Number(totals.expenses_total || 0);
  const donutProfit = Math.max(0, profit);

  const donutData = [
    { name: "Lucro", value: donutProfit },
    { name: "Despesas", value: Math.max(0, expenses) },
  ];

  const donutColors = ["#22c55e", "#ef4444"];

  // ✅ dados do gráfico por empresa
  const companyBars = useMemo(() => {
    return companies.map((c) => {
      const t = c?.data?.totals || {};
      return {
        name: c.name,
        recebido: Number(t.revenue_paid_total || 0),
        despesas: Number(t.expenses_total || 0),
        lucro: Number(t.profit_total || 0),
        emitido: Number(t.revenue_issued_total || 0),
      };
    });
  }, [companies]);

  return (
    <div className="groupDash">
      <div className="groupDashTop">
        <div className="groupDashTitleRow">
          <h2 className="groupDashTitle">Dashboard do Grupo</h2>

          <div className="gdPills">
            {loading ? <span className="gdPill ok">A carregar…</span> : null}
            {error ? <span className="gdPill err">{error}</span> : null}
          </div>
        </div>

        <div className="groupDashControls">
          <label className="gdField">
            <span>Modo</span>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="month">Mês</option>
              <option value="year">Ano</option>
            </select>
          </label>

          {mode === "year" ? (
            <label className="gdField">
              <span>Ano</span>
              <input
                type="number"
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                min={1900}
                max={3000}
                step={1}
              />
            </label>
          ) : (
            <label className="gdField">
              <span>Mês</span>
              <input
                type="month"
                value={selectedKey}
                onChange={(e) => setSelectedKey(e.target.value)}
              />
            </label>
          )}
        </div>
      </div>

      {/* Totais do grupo */}
      <div className="groupTotals">
        <div className="gdCard">
          <div className="k">Recebido</div>
          <div className="v">{eur(totals.revenue_paid_total)}</div>
          <small>Pagos: {totals.invoices_paid_count || 0}</small>
        </div>

        <div className="gdCard">
          <div className="k">Emitido (não pago)</div>
          <div className="v">{eur(totals.revenue_issued_total)}</div>
          <small>Faturas: {totals.invoices_total || 0}</small>
        </div>

        <div className="gdCard">
          <div className="k">Despesas</div>
          <div className="v">{eur(totals.expenses_total)}</div>
        </div>

        <div className="gdCard">
          <div className="k">Lucro</div>
          <div className="v">{eur(totals.profit_total)}</div>
          <small>{profit < 0 ? "⚠️ lucro negativo" : "\u00A0"}</small>
        </div>

        <div className="gdCard">
          <div className="k">IVA (pago)</div>
          <div className="kpiValue">
            {eur((totals.vat_paid_total || 0) + (totals.vat_issued_total || 0))}
          </div>
          <small>Emitido: {eur(totals.vat_issued_total)} • Pendente: {eur(totals.vat_pending_total)}</small>
        </div>
      </div>

      {/* Gráficos do grupo */}
      <div className="groupCharts">
        <section className="gdCard">
          <h3 className="gdSectionTitle">Lucro por mês</h3>
          <div className="gdChartBox">
            <ResponsiveContainer>
              <LineChart data={profitSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(v) => eur(v)} />
                <Line type="monotone" dataKey="profit" stroke="#2563eb" strokeWidth={3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="gdCard">
          <h3 className="gdSectionTitle">Lucro vs Despesas</h3>
          <div className="gdChartBox">
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={donutData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={70}
                  outerRadius={105}
                  paddingAngle={4}
                >
                  {donutData.map((_, idx) => (
                    <Cell key={idx} fill={donutColors[idx % donutColors.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => eur(v)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="gdRowBetween">
            <small>
              <b>Lucro:</b> {eur(totals.profit_total)}
            </small>
            <small>
              <b>Despesas:</b> {eur(totals.expenses_total)}
            </small>
          </div>
        </section>

        <section className="gdCard">
          <h3 className="gdSectionTitle">IVA por mês</h3>
          <div className="gdChartBox">
            <ResponsiveContainer>
              <LineChart data={vatSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(v) => eur(v)} />
                <Legend />
                <Line type="monotone" dataKey="vat_paid" name="IVA pago" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="vat_issued" name="IVA emitido" strokeWidth={3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Empresas */}
      <div className="groupCompanies">
        <h3>Empresas</h3>

        {companies.length === 0 ? (
          <p className="status">Sem empresas</p>
        ) : (
          <>
            <section className={`gdCard gdCompareCard`}>
              <h4 className="gdCompareTitle">Comparação (Recebido / Despesas / Lucro)</h4>

              <div className="gdCompareChart">
                <ResponsiveContainer>
                  <BarChart data={companyBars}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(v) => eur(v)} />
                    <Legend />
                    <Bar dataKey="recebido" name="Recebido" fill="#2563eb" />
                    <Bar dataKey="despesas" name="Despesas" fill="#ef4444" />
                    <Bar dataKey="lucro" name="Lucro" fill="#22c55e" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <div className="companyGrid">
              {companies.map((c) => {
                const t = c?.data?.totals || {};
                const recebido = Number(t.revenue_paid_total || 0);
                const despesas = Number(t.expenses_total || 0);
                const lucro = Number(t.profit_total || 0);
                const emitido = Number(t.revenue_issued_total || 0);

                const donut = [
                  { name: "Recebido", value: Math.max(0, recebido) },
                  { name: "Despesas", value: Math.max(0, despesas) },
                ];

                return (
                  <div key={c.company_id} className="gdCard">
                    <div className="companyHead">
                      <h4>{c.name}</h4>
                      <small className="companyMeta">
                        Faturas: <b>{t.invoices_total || 0}</b> (pagas {t.invoices_paid_count || 0})
                      </small>
                    </div>

                    <div className="companyBody">
                      <div className="companyNumbers">
                        <div>
                          Recebido: <b>{eur(recebido)}</b>
                        </div>
                        <div>
                          Emitido: <b>{eur(emitido)}</b>
                        </div>
                        <div>
                          Despesas: <b>{eur(despesas)}</b>
                        </div>
                        <div>
                          Lucro: <b>{eur(lucro)}</b>
                        </div>
                        <div style={{ marginTop: 6 }}>
                          Agendamentos: <b>{t.appointments_total || 0}</b>
                        </div>
                      </div>

                      <div className="companyDonut">
                        <ResponsiveContainer>
                          <PieChart>
                            <Pie
                              data={donut}
                              dataKey="value"
                              nameKey="name"
                              innerRadius={45}
                              outerRadius={65}
                              paddingAngle={4}
                            >
                              {donut.map((_, idx) => (
                                <Cell key={idx} fill={donutColors[idx % donutColors.length]} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(v) => eur(v)} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
