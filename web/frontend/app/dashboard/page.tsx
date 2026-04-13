"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, DashboardData } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  TrendingUp,
  AlertCircle,
  Package,
  DollarSign,
  ShoppingCart,
  RefreshCw,
} from "lucide-react";

const PERIODS = [
  { key: "today", label: "dashboard.period_today" },
  { key: "yesterday", label: "dashboard.period_yesterday" },
  { key: "week", label: "dashboard.period_7d" },
  { key: "month", label: "dashboard.period_30d" },
];

const COLORS = ["#6c63ff", "#22c55e", "#f59e0b", "#3b82f6", "#ef4444", "#a78bfa"];

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

export default function DashboardPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<"today" | "week" | "month" | "year">("today");

  const PERIODS = [
    { key: "today", label: t("dashboard.period_today") },
    { key: "week", label: t("dashboard.period_week") },
    { key: "month", label: t("dashboard.period_month") },
    { key: "year", label: t("dashboard.period_year") },
  ] as const;

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    fetchData();
  }, [period]);

  async function fetchData() {
    setLoading(true);
    setError("");
    try {
      const d = await api.getDashboard(period);
      setData(d);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        {/* Header */}
        <div className="page-header" style={{ marginBottom: 24 }}>
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <LayoutDashboard size={32} style={{ color: "var(--accent)" }} />
              {t("dashboard.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginLeft: 44 }}>
              {t("dashboard.subtitle")}
            </p>
          </div>
          <div className="period-row" style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {/* Period selector */}
            <div className="period-selector" style={{ display: "flex", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
              {PERIODS.map((p) => (
                <button
                  key={p.key}
                  onClick={() => setPeriod(p.key)}
                  style={{
                    padding: "8px 14px",
                    fontSize: 12,
                    fontWeight: 500,
                    border: "none",
                    cursor: "pointer",
                    background: period === p.key ? "var(--accent)" : "transparent",
                    color: period === p.key ? "var(--bg)" : "var(--text-secondary)",
                    transition: "all 0.15s",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t(p.label)}
                </button>
              ))}
            </div>
            <button className="btn btn-ghost refresh-btn" onClick={fetchData} style={{ flexShrink: 0 }}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 10, padding: "12px 16px", color: "var(--red)", marginBottom: 20, display: "flex", gap: 8 }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
            <div className="spinner" />
          </div>
        ) : data ? (
          <>
            {/* KPI Cards */}
            <div className="kpi-grid" style={{ marginBottom: 24 }}>
              <div className="kpi-card">
                <div className="kpi-icon" style={{ background: "rgba(108,99,255,0.15)" }}>
                  <TrendingUp size={20} color="var(--accent)" />
                </div>
                <div className="kpi-label">{t("dashboard.revenue")}</div>
                <div className="kpi-value" style={{ color: "var(--accent)" }}>
                  {fmt(data.total_revenue_today)} TJS
                </div>
              </div>

              <div className="kpi-card">
                <div className="kpi-icon" style={{ background: "rgba(34,197,94,0.15)" }}>
                  <ShoppingCart size={20} color="var(--green)" />
                </div>
                <div className="kpi-label">{t("dashboard.sales")}</div>
                <div className="kpi-value" style={{ color: "var(--green)" }}>
                  {data.total_orders_today}
                </div>
              </div>

              <div
                className="kpi-card"
                onClick={() => router.push("/finance")}
                style={{ cursor: "pointer" }}
              >
                <div className="kpi-icon" style={{ background: "rgba(239,68,68,0.15)" }}>
                  <DollarSign size={20} color="var(--red)" />
                </div>
                <div className="kpi-label">{t("dashboard.total_debt")}</div>
                <div className="kpi-value" style={{ color: "var(--red)" }}>
                  {fmt(data.total_debt)} TJS
                </div>
              </div>

              <div
                className="kpi-card"
                onClick={() => router.push("/suppliers")}
                style={{ cursor: "pointer" }}
              >
                <div className="kpi-icon" style={{ background: "rgba(124,58,237,0.15)" }}>
                  <TrendingUp size={20} color="var(--accent)" />
                </div>
                <div className="kpi-label">{t("dashboard.total_supplier_debt")}</div>
                <div className="kpi-value" style={{ color: "var(--accent)" }}>
                  {fmt(data.total_supplier_debt || 0)} TJS
                </div>
              </div>

              <div className="kpi-card" onClick={() => router.push("/orders?status=active")} style={{ cursor: "pointer" }}>
                <div className="kpi-icon" style={{ background: "rgba(245,158,11,0.15)" }}>
                  <Package size={20} color="var(--yellow)" />
                </div>
                <div className="kpi-label">{t("dashboard.pending_orders")}</div>
                <div className="kpi-value" style={{ color: "var(--yellow)" }}>
                  {data.pending_orders}
                </div>
              </div>
            </div>

            {/* Charts row */}
            <div className="dashboard-charts" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              {/* Revenue by store */}
              <div className="card">
                <h3 style={{ marginBottom: 16 }}>{t("dashboard.revenue_by_store")}</h3>
                {(() => {
                  const activeRevenues = data.store_revenues.filter(r => Number(r.total_revenue) > 0);
                  if (activeRevenues.length > 0) {
                    return (
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={activeRevenues} barSize={32}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                          <XAxis dataKey="store_name" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
                          <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
                          <Tooltip
                            contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8 }}
                            labelStyle={{ color: "var(--text-primary)" }}
                            formatter={(v: any) => [`${fmt(Number(v))} TJS`, t("dashboard.revenue")]}
                          />
                          <Bar dataKey="total_revenue" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    );
                  }
                  return (
                    <div style={{ padding: 30, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                      {t("common.empty")}
                    </div>
                  );
                })()}
              </div>

              {/* Orders by status pie */}
              <div className="card" style={{ flex: 1, minWidth: 280 }}>
                <h3 style={{ marginBottom: 16 }}>{t("dashboard.order_status")}</h3>
                {data.orders_by_status.length > 0 ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                    <ResponsiveContainer width={160} height={180}>
                      <PieChart>
                        <Pie
                          data={data.orders_by_status}
                          dataKey="count"
                          nameKey="status"
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={75}
                        >
                          {data.orders_by_status.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8 }}
                          formatter={(v: any, name: any) => {
                            const statusKey = String(name).toLowerCase();
                            return [v, t(`statuses.${statusKey}`)];
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ flex: 1 }}>
                      {data.orders_by_status.map((s, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: 2, background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                          <span style={{ fontSize: 12, color: "var(--text-secondary)", flex: 1 }}>{t(`statuses.${s.status.toLowerCase()}`) || s.status}</span>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{s.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: 30, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    {t("common.empty")}
                  </div>
                )}
              </div>
            </div>

            {/* Debts section */}
            <div className="dashboard-charts" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              {/* Store debts */}
              <div className="card">
                <h3 style={{ marginBottom: 16 }}>{t("dashboard.debt_by_store")}</h3>
                {data.store_debts.length > 0 ? (
                  <div className="table-wrap">
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left", paddingBottom: 12, fontSize: 12, color: "var(--text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>{t("dashboard.store")}</th>
                        <th style={{ textAlign: "right", paddingBottom: 12, fontSize: 12, color: "var(--text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>{t("dashboard.debt")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.store_debts.map((s) => (
                        <tr key={s.store_id} style={{ borderTop: "1px solid var(--border)" }}>
                          <td style={{ padding: "12px 0", fontWeight: 500 }}>{s.store_name}</td>
                          <td style={{ padding: "12px 0", textAlign: "right", fontWeight: 700, color: Number(s.current_debt) > 0 ? "var(--red)" : "var(--green)" }}>
                            {fmt(Number(s.current_debt))} TJS
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                ) : (
                  <div style={{ padding: 30, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    {t("common.empty")}
                  </div>
                )}
              </div>

              {/* Supplier debts */}
              <div className="card">
                <h3 style={{ marginBottom: 16 }}>{t("dashboard.debt_by_supplier")}</h3>
                {data.supplier_debts && data.supplier_debts.length > 0 ? (
                  <div className="table-wrap">
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left", paddingBottom: 12, fontSize: 12, color: "var(--text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>Оптовик</th>
                        <th style={{ textAlign: "right", paddingBottom: 12, fontSize: 12, color: "var(--text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>{t("dashboard.debt")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.supplier_debts.map((s) => (
                        <tr key={s.supplier_id} style={{ borderTop: "1px solid var(--border)" }}>
                          <td style={{ padding: "12px 0", fontWeight: 500 }}>{s.supplier_name}</td>
                          <td style={{ padding: "12px 0", textAlign: "right", fontWeight: 700, color: "var(--accent)" }}>
                            {fmt(Number(s.current_debt))} TJS
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                ) : (
                  <div style={{ padding: 30, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    {t("common.empty")}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}
