"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, DashboardData } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  TrendingUp,
  AlertCircle,
  Package,
  Wallet,
  ShoppingCart,
  RefreshCw,
  LayoutDashboard,
  Store as StoreIcon,
  Truck,
  ArrowRight,
} from "lucide-react";

const PIE_COLORS = ["#6c63ff", "#22c55e", "#f59e0b", "#3b82f6", "#ef4444", "#a78bfa"];

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
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

  async function loadData(showSpinner = true) {
    if (showSpinner) setLoading(true);
    setError("");
    try {
      const d = await api.getDashboard(period);
      setData(d);
    } catch (e) {
      setError(getErrorMessage(e, t("common.error")));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const topStores = useMemo(() => {
    if (!data) return [];
    return [...data.store_revenues]
      .filter(r => Number(r.total_revenue) > 0)
      .sort((a, b) => Number(b.total_revenue) - Number(a.total_revenue));
  }, [data]);
  const maxStoreRevenue = topStores[0]?.total_revenue || 0;

  const debtStores = useMemo(() => {
    if (!data) return [];
    return [...data.store_debts]
      .filter(s => Number(s.current_debt) > 0)
      .sort((a, b) => Number(b.current_debt) - Number(a.current_debt));
  }, [data]);
  const maxStoreDebt = debtStores[0]?.current_debt || 0;

  const supplierDebtsList = useMemo(() => {
    if (!data?.supplier_debts) return [];
    return [...data.supplier_debts]
      .filter(s => Number(s.current_debt) > 0)
      .sort((a, b) => Number(b.current_debt) - Number(a.current_debt));
  }, [data]);
  const maxSupplierDebt = supplierDebtsList[0]?.current_debt || 0;

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        {/* Hero header */}
        <div className="dash-header">
          <div className="dash-title-block">
            <div className="dash-icon-wrap">
              <LayoutDashboard size={22} />
            </div>
            <div>
              <h1 className="page-title" style={{ margin: 0 }}>{t("dashboard.title")}</h1>
              <p className="dash-subtitle">{t("dashboard.subtitle")}</p>
            </div>
          </div>
          <div className="dash-controls">
            <div className="period-pills">
              {PERIODS.map((p) => (
                <button
                  key={p.key}
                  onClick={() => setPeriod(p.key)}
                  className={`period-pill ${period === p.key ? "active" : ""}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button className="icon-btn" onClick={() => void loadData(false)} title="Refresh">
              <RefreshCw size={15} />
            </button>
          </div>
        </div>

        {error && (
          <div className="dash-error">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
            <div className="spinner" />
          </div>
        ) : data ? (
          <>
            {/* Hero KPI grid */}
            <div className="dash-kpi-grid">
              <KpiCard accent="#6c63ff" icon={<TrendingUp size={18} />} label={t("dashboard.revenue")} value={fmt(data.total_revenue_today)} suffix="TJS" />
              <KpiCard accent="#22c55e" icon={<ShoppingCart size={18} />} label={t("dashboard.sales")} value={String(data.total_orders_today)} />
              <KpiCard accent="#ef4444" icon={<Wallet size={18} />} label={t("dashboard.total_debt")} value={fmt(data.total_debt)} suffix="TJS" onClick={() => router.push("/finance")} />
              <KpiCard accent="#3b82f6" icon={<Truck size={18} />} label={t("dashboard.total_supplier_debt")} value={fmt(data.total_supplier_debt || 0)} suffix="TJS" onClick={() => router.push("/suppliers")} />
              <KpiCard accent="#f59e0b" icon={<Package size={18} />} label={t("dashboard.pending_orders")} value={String(data.pending_orders)} onClick={() => router.push("/orders?status=active")} />
            </div>

            {/* Charts row */}
            <div className="dash-charts">
              <div className="dash-card">
                <div className="dash-card-head">
                  <h3>{t("dashboard.revenue_by_store")}</h3>
                </div>
                {topStores.length > 0 ? (
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={topStores}>
                      <defs>
                        <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#6c63ff" stopOpacity={0.6} />
                          <stop offset="100%" stopColor="#6c63ff" stopOpacity={0.05} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                      <XAxis dataKey="store_name" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
                      <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12 }}
                        labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
                        formatter={(value) => [`${fmt(Number(value ?? 0))} TJS`, t("dashboard.revenue")]}
                      />
                      <Area type="monotone" dataKey="total_revenue" stroke="#6c63ff" strokeWidth={2} fill="url(#revGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState />
                )}
              </div>

              <div className="dash-card">
                <div className="dash-card-head">
                  <h3>{t("dashboard.order_status")}</h3>
                </div>
                {data.orders_by_status.length > 0 ? (
                  <div className="pie-row">
                    <ResponsiveContainer width={170} height={200}>
                      <PieChart>
                        <Pie data={data.orders_by_status} dataKey="count" nameKey="status" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2}>
                          {data.orders_by_status.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="var(--bg-card)" strokeWidth={2} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12 }}
                          formatter={(value, name) => [String(value ?? ""), t(`statuses.${String(name ?? "").toLowerCase()}`)]}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="pie-legend">
                      {data.orders_by_status.map((s, i) => (
                        <div key={i} className="pie-legend-row">
                          <span className="pie-legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                          <span className="pie-legend-label">{t(`statuses.${s.status.toLowerCase()}`) || s.status}</span>
                          <span className="pie-legend-value">{s.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <EmptyState />
                )}
              </div>
            </div>

            {/* Lists row */}
            <div className="dash-charts">
              <div className="dash-card">
                <div className="dash-card-head">
                  <h3><StoreIcon size={16} /> {t("dashboard.revenue_by_store")}</h3>
                </div>
                {topStores.length > 0 ? (
                  <div className="rank-list">
                    {topStores.slice(0, 8).map((s, i) => (
                      <div key={i} className="rank-row">
                        <div className="rank-num">{i + 1}</div>
                        <div className="rank-body">
                          <div className="rank-line">
                            <span className="rank-name">{s.store_name}</span>
                            <span className="rank-value" style={{ color: "var(--accent)" }}>{fmt(Number(s.total_revenue))} TJS</span>
                          </div>
                          <div className="rank-bar">
                            <div className="rank-bar-fill" style={{
                              width: `${maxStoreRevenue ? (Number(s.total_revenue) / Number(maxStoreRevenue) * 100) : 0}%`,
                              background: "linear-gradient(90deg, #6c63ff, #a78bfa)",
                            }} />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState />
                )}
              </div>

              <div className="dash-card">
                <div className="dash-card-head">
                  <h3><Wallet size={16} /> {t("dashboard.debt_by_store")}</h3>
                  <button className="link-btn" onClick={() => router.push("/finance")}>
                    Все <ArrowRight size={12} />
                  </button>
                </div>
                {debtStores.length > 0 ? (
                  <div className="rank-list">
                    {debtStores.slice(0, 8).map((s, i) => (
                      <div key={s.store_id} className="rank-row">
                        <div className="rank-num" style={{ background: "rgba(239,68,68,0.12)", color: "var(--red)" }}>{i + 1}</div>
                        <div className="rank-body">
                          <div className="rank-line">
                            <span className="rank-name">{s.store_name}</span>
                            <span className="rank-value" style={{ color: "var(--red)" }}>{fmt(Number(s.current_debt))} TJS</span>
                          </div>
                          <div className="rank-bar">
                            <div className="rank-bar-fill" style={{
                              width: `${maxStoreDebt ? (Number(s.current_debt) / Number(maxStoreDebt) * 100) : 0}%`,
                              background: "linear-gradient(90deg, #ef4444, #f59e0b)",
                            }} />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState text={t("common.empty")} ok />
                )}
              </div>
            </div>

            {/* Supplier debts */}
            {supplierDebtsList.length > 0 && (
              <div className="dash-card" style={{ marginBottom: 24 }}>
                <div className="dash-card-head">
                  <h3><Truck size={16} /> {t("dashboard.debt_by_supplier")}</h3>
                  <button className="link-btn" onClick={() => router.push("/suppliers")}>
                    Все <ArrowRight size={12} />
                  </button>
                </div>
                <div className="rank-list">
                  {supplierDebtsList.slice(0, 6).map((s, i) => (
                    <div key={s.supplier_id} className="rank-row">
                      <div className="rank-num" style={{ background: "rgba(59,130,246,0.12)", color: "var(--blue)" }}>{i + 1}</div>
                      <div className="rank-body">
                        <div className="rank-line">
                          <span className="rank-name">{s.supplier_name}</span>
                          <span className="rank-value" style={{ color: "var(--blue)" }}>{fmt(Number(s.current_debt))} TJS</span>
                        </div>
                        <div className="rank-bar">
                          <div className="rank-bar-fill" style={{
                            width: `${maxSupplierDebt ? (Number(s.current_debt) / Number(maxSupplierDebt) * 100) : 0}%`,
                            background: "linear-gradient(90deg, #3b82f6, #6c63ff)",
                          }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : null}
      </main>
    </div>
  );
}

function KpiCard({ accent, icon, label, value, suffix, onClick }: {
  accent: string; icon: React.ReactNode; label: string; value: string; suffix?: string; onClick?: () => void;
}) {
  return (
    <div className={`dash-kpi ${onClick ? "clickable" : ""}`} onClick={onClick} style={{ "--kpi-accent": accent } as React.CSSProperties}>
      <div className="dash-kpi-strip" />
      <div className="dash-kpi-head">
        <div className="dash-kpi-icon">{icon}</div>
        <div className="dash-kpi-label">{label}</div>
      </div>
      <div className="dash-kpi-value">
        {value}
        {suffix && <span className="dash-kpi-suffix">{suffix}</span>}
      </div>
    </div>
  );
}

function EmptyState({ text, ok }: { text?: string; ok?: boolean } = {}) {
  return (
    <div className="dash-empty">
      <div className="dash-empty-icon" style={{ color: ok ? "var(--green)" : "var(--text-muted)" }}>
        {ok ? "✓" : "○"}
      </div>
      <div className="dash-empty-text">{text || "Нет данных"}</div>
    </div>
  );
}
