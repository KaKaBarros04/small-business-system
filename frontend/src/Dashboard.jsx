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

import "./Dashboard.css";

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

export default function Dashboard() {
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
      const res = await api.getDashboardSummary(y, m);
      setData(res);
    } catch (e) {
      setError(e?.message || "Erro ao carregar dashboard");
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

  const totals = data?.totals || {};
  const expensesByCategory = data?.expenses_by_category || [];
  const revenueByMonth = data?.revenue_by_month || [];

  const profitSeries = useMemo(() => {
    return revenueByMonth
      .slice()
      .sort((a, b) => a.year - b.year || a.month - b.month)
      .map((x) => ({
        label: labelFromYM(x.year, x.month),
        profit: Number(x.profit || 0),
      }));
  }, [revenueByMonth]);

  const vatSeries = useMemo(() => {
    return revenueByMonth
      .slice()
      .sort((a, b) => a.year - b.year || a.month - b.month)
      .map((x) => ({
        label: labelFromYM(x.year, x.month),
        vat_paid: Number(x.vat_paid || 0),
        vat_issued: Number(x.vat_issued || 0),
      }));
  }, [revenueByMonth]);

  const profit = Number(totals.profit_total || 0);
  const expenses = Number(totals.expenses_total || 0);
  const donutProfit = Math.max(0, profit);
  const donutData = [
    { name: "Lucro", value: donutProfit },
    { name: "Despesas", value: Math.max(0, expenses) },
  ];
  const donutColors = ["#22c55e", "#ef4444"];

  const expensesCatSeries = useMemo(() => {
    return (expensesByCategory || [])
      .map((x) => ({
        category: x?.category ?? x?.name ?? x?.label ?? "Sem categoria",
        amount: Number(x?.amount ?? x?.total ?? x?.value ?? 0),
      }))
      .filter((x) => Number.isFinite(x.amount) && x.amount > 0)
      .sort((a, b) => b.amount - a.amount)
      .slice(0, 12);
  }, [expensesByCategory]);

  return (
    <div className="dash">
      {/* Header / filtros */}
      <div className="dashHeader">
        <div className="dashTitle">
          <h2>Dashboard</h2>
          <p>Resumo financeiro e operacional do período selecionado.</p>
        </div>

        <div className="dashFilters">
          <div className="field">
            <label>Modo</label>
            <select className="select" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="month">Mês</option>
              <option value="year">Ano</option>
            </select>
          </div>

          {mode === "year" ? (
            <div className="field">
              <label>Ano</label>
              <input
                className="input"
                type="number"
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                min={1900}
                max={3000}
                step={1}
              />
            </div>
          ) : (
            <div className="field">
              <label>Mês</label>
              <input
                className="input"
                type="month"
                value={selectedKey}
                onChange={(e) => setSelectedKey(e.target.value)}
              />
            </div>
          )}

          {loading && <span className="msg">A carregar...</span>}
          {error && <span className="msg error">{error}</span>}
        </div>
      </div>

      {/* Totais */}
      <div className="dashGrid">
        <div className="kpi">
          <div className="kpiTop">
            <div className="kpiLabel">Recebido</div>
            <div className="kpiIcon" aria-hidden="true">💶</div>
          </div>
          <div className="kpiValue">{eur(totals.revenue_paid_total)}</div>
          <div className="kpiSub">Pagos: {totals.invoices_paid_count || 0}</div>
        </div>

        <div className="kpi">
          <div className="kpiTop">
            <div className="kpiLabel">Emitido</div>
            <div className="kpiIcon" aria-hidden="true">🧾</div>
          </div>
          <div className="kpiValue">{eur(totals.revenue_issued_total)}</div>
          <div className="kpiSub">Faturas: {totals.invoices_total || 0}</div>
        </div>

        <div className="kpi">
          <div className="kpiTop">
            <div className="kpiLabel">Despesas</div>
            <div className="kpiIcon" aria-hidden="true">💸</div>
          </div>
          <div className="kpiValue">{eur(totals.expenses_total)}</div>
          <div className="kpiSub">&nbsp;</div>
        </div>

        <div className="kpi">
          <div className="kpiTop">
            <div className="kpiLabel">Lucro</div>
            <div className="kpiIcon" aria-hidden="true">📈</div>
          </div>
          <div className="kpiValue">{eur(totals.profit_total)}</div>
          <div className={`kpiSub ${profit < 0 ? "kpiWarn" : ""}`}>
            {profit < 0 ? "⚠️ lucro negativo" : "\u00A0"}
          </div>
        </div>

        <div className="kpi">
          <div className="kpiTop">
            <div className="kpiLabel">IVA</div>
            <div className="kpiIcon" aria-hidden="true">🏛️</div>
          </div>
          <div className="kpiValue">
             {eur((totals.vat_issued_total || 0) + (totals.vat_paid_total || 0))}
          </div>
        </div>
      </div>

      {/* Gráficos */}
      <div className="chartsGrid">
        <section className="card chartCard">
          <div className="chartHead">
            <h3>Lucro por mês</h3>
            <span className="hint">Tendência</span>
          </div>
          <div className="chartBox">
            <ResponsiveContainer>
              <LineChart data={profitSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(v) => eur(v)} />
                <Line type="monotone" dataKey="profit" strokeWidth={3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="card chartCard">
          <div className="chartHead">
            <h3>Lucro vs Despesas</h3>
            <span className="hint">Distribuição</span>
          </div>
          <div className="chartBox">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={donutData} dataKey="value" nameKey="name" innerRadius={70} outerRadius={105} paddingAngle={4}>
                  {donutData.map((_, idx) => (
                    <Cell key={idx} fill={donutColors[idx % donutColors.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => eur(v)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="card chartCard">
          <div className="chartHead">
            <h3>IVA por mês</h3>
            <span className="hint">Pago vs Emitido</span>
          </div>
          <div className="chartBox">
            <ResponsiveContainer>
              <LineChart data={vatSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(v) => eur(v)} />
                <Legend />
                <Line type="monotone" dataKey="vat_paid" name="IVA pago" strokeWidth={3} dot={false} />
                <Line
                  type="monotone"
                  dataKey="vat_issued"
                  name="IVA emitido"
                  strokeWidth={3}
                  dot={false}
                  strokeDasharray="6 4"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      

      {/* Despesas por categoria */}
      <div>
        <div className="sectionTitle">
          <h3>Despesas por categoria</h3>
          <p>Top 12 categorias por valor</p>
        </div>

        {expensesCatSeries.length === 0 ? (
          <p className="status">Sem dados</p>
        ) : (
          <div className="card" style={{ padding: 14 }}>
            <div style={{ width: "100%", height: 320 }}>
              <ResponsiveContainer>
                <BarChart data={expensesCatSeries} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" interval={0} angle={-25} textAnchor="end" height={70} />
                  <YAxis tickFormatter={(v) => eur(v)} />
                  <Tooltip formatter={(v) => eur(v)} />
                  <Bar dataKey="amount" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
