"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { isAuthenticated } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import {
  api,
  CashCollectionHistoryItem,
  CashCollectionSummary,
} from "@/lib/api";
import {
  Wallet,
  Building2,
  Receipt,
  AlertCircle,
  CheckCircle2,
  History,
  TrendingDown,
  ChevronDown,
  Check
} from "lucide-react";

export default function FinancePage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [debtors, setDebtors] = useState<CashCollectionSummary[]>([]);
  const [history, setHistory] = useState<CashCollectionHistoryItem[]>([]);

  // Form State
  const [selectedStoreId, setSelectedStoreId] = useState<number | "">("");
  const [amount, setAmount] = useState<string>("");
  const [errorText, setErrorText] = useState("");
  const [successText, setSuccessText] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [debtData, histData] = await Promise.all([
        api.getDebtors(),
        api.getFinanceHistory(30),
      ]);
      setDebtors(debtData);
      setHistory(histData);
    } catch (e: any) {
      showToast(t("common.error") + " : " + e.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const selectedStore = debtors.find((d) => d.store_id === Number(selectedStoreId));
  const totalDebt = debtors.reduce((acc, curr) => acc + Number(curr.current_debt), 0);

  const handleMaxAmount = () => {
    if (selectedStore) {
      setAmount(selectedStore.current_debt.toString());
    }
  };

  const handleCollect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStoreId || !amount) {
      showToast(t("finance.err_req"), "error");
      return;
    }
    const val = parseFloat(amount);
    if (isNaN(val) || val <= 0) {
      showToast(t("finance.err_zero"), "error");
      return;
    }

    try {
      setSubmitting(true);
      await api.collectCash(Number(selectedStoreId), val);
      showToast(t("finance.success_collected", { amount: val }), "success");
      setSelectedStoreId("");
      setAmount("");
      await fetchData(); // Refresh data
    } catch (e: any) {
      showToast(e.message || t("finance.err_collect"), "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        
        {/* Header */}
        <div className="page-header" style={{ marginBottom: "32px" }}>
          <div>
            <h1 className="page-title flex items-center gap-3">
              <Wallet className="w-8 h-8" style={{ color: "var(--accent)" }} />
              {t("finance.title")}
            </h1>
            <p className="text-[14px] mt-1 ml-[44px]" style={{ color: "var(--text-secondary)" }}>
              {t("finance.subtitle")}
            </p>
          </div>
        </div>

        {/* Alerts */}
        {errorText && (
          <div className="flex items-center gap-2 text-red-400 bg-red-500/10 border border-red-500/20 p-4 rounded-xl mb-6">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">{errorText}</span>
          </div>
        )}
        {successText && (
          <div className="flex items-center gap-2 text-green-400 bg-green-500/10 border border-green-500/20 p-4 rounded-xl mb-6 shadow-[0_0_15px_rgba(34,197,94,0.1)]">
            <CheckCircle2 className="w-5 h-5" />
            <span className="font-medium">{successText}</span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center p-20">
            <div className="spinner"></div>
          </div>
        ) : (
          <div className="flex flex-col gap-8">
            
            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="card flex items-center gap-5 transition-all" style={{ borderColor: "var(--border)" }}>
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>
                  <Building2 className="w-7 h-7" />
                </div>
                <div>
                  <div className="text-[13px] font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
                    {t("finance.stores_with_debt")}
                  </div>
                  <div className="text-2xl font-bold font-mono">
                    {debtors.length}
                  </div>
                </div>
              </div>
              <div className="card flex items-center gap-5 transition-all">
                <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center text-red-500">
                  <Receipt className="w-7 h-7" />
                </div>
                <div>
                  <div className="text-[13px] font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
                    {t("finance.total_debt")}
                  </div>
                  <div className="text-2xl font-bold font-mono">
                    {new Intl.NumberFormat("ru-RU").format(totalDebt)} <span className="text-[16px] font-sans" style={{ color: "var(--text-secondary)" }}>TJS</span>
                  </div>
                </div>
              </div>
              <div className="card flex items-center gap-5 transition-all">
                <div className="w-14 h-14 rounded-2xl bg-green-500/10 flex items-center justify-center text-green-500">
                  <Receipt className="w-7 h-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold uppercase tracking-wider" style={{ color: "var(--text-secondary)" }}>{t("finance.collect_action")}</p>
                  <p className="text-3xl font-bold mt-1">{history.length}</p>
                </div>
              </div>
            </div>

            {/* Main Workspace */}
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_2fr] gap-8">
              
              {/* Left Column: Collection Form */}
              <div className="card h-fit sticky top-6 p-0" style={{ borderColor: "var(--accent-muted)" }}>
                <div className="flex items-center gap-3 px-6 py-5 border-b" style={{ borderColor: "var(--border)" }}>
                  <div className="p-2.5 rounded-lg" style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>
                    <Wallet className="w-5 h-5" />
                  </div>
                  <h2 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>{t("finance.collect_action")}</h2>
                </div>

                <div className="p-6">
                  <form onSubmit={handleCollect} className="flex flex-col gap-5">
                    <div className="flex flex-col gap-2">
                      <label className="text-[13px] font-medium" style={{ color: "var(--text-secondary)" }}>
                        {t("finance.select_store")}
                      </label>
                      <select
                        className="input"
                        value={selectedStoreId}
                        onChange={(e) => {
                          setSelectedStoreId(e.target.value ? Number(e.target.value) : "");
                          setAmount("");
                        }}
                      >
                        <option value="" disabled>-- {t("finance.select_store")} --</option>
                        {debtors.map((d) => (
                          <option key={d.store_id} value={d.store_id}>
                            {d.store_name} ({t("finance.debt")}: {d.current_debt} TJS)
                          </option>
                        ))}
                      </select>
                      
                    </div>

                  {selectedStoreId && (
                    <div className="flex flex-col gap-2">
                      <label className="flex justify-between items-center text-[13px] font-medium" style={{ color: "var(--text-secondary)" }}>
                        <span>{t("finance.amount")}</span>
                        <button 
                          type="button"
                          className="hover:underline"
                          style={{ color: "var(--accent)" }}
                          onClick={handleMaxAmount}
                        >
                          {t("finance.max")}
                        </button>
                      </label>
                      <input
                        type="number"
                        className="input font-medium text-lg"
                        placeholder={t("finance.amount_ph")}
                        step="0.01"
                        min="0"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                      />
                      {selectedStore && (
                        <div className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
                          {t("finance.debt")}: <span style={{ color: "var(--text-primary)" }}>{Math.max(0, selectedStore.current_debt - (Number(amount) || 0))} TJS</span>
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    type="submit"
                    className="btn btn-primary w-full py-3 mt-2 text-[15px] font-semibold justify-center"
                    disabled={submitting || !selectedStoreId || !amount}
                  >
                    {submitting ? t("common.loading") : t("finance.btn_collect")}
                  </button>
                  </form>
                </div>
              </div>

              {/* Right Column: Collection History */}
              <div className="card shadow-lg">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2.5 bg-green-500/10 rounded-lg text-green-500">
                    <History className="w-5 h-5" />
                  </div>
                  <h2 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>{t("finance.history_title")}</h2>
                </div>

                {history.length === 0 ? (
                  <div className="empty-state border border-dashed rounded-xl flex flex-col items-center justify-center p-14" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                    <Receipt className="w-12 h-12 mb-4" style={{ color: "var(--border)" }} />
                    <p className="font-medium text-lg" style={{ color: "var(--text-secondary)" }}>{t("finance.history_empty")}</p>
                    <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{t("finance.history_desc")}</p>
                  </div>
                ) : (
                  <div className="table-wrap rounded-xl overflow-hidden border" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                    <table className="w-full text-left">
                      <thead>
                        <tr style={{ background: "var(--bg-hover)" }}>
                          <th className="py-4 px-5 font-semibold text-[11px] uppercase tracking-wider border-b" style={{ color: "var(--text-secondary)", borderColor: "var(--border)" }}>{t("finance.col_date")}</th>
                          <th className="py-4 px-5 font-semibold text-[11px] uppercase tracking-wider border-b" style={{ color: "var(--text-secondary)", borderColor: "var(--border)" }}>{t("finance.col_store")}</th>
                          <th className="py-4 px-5 font-semibold text-[11px] uppercase tracking-wider border-b" style={{ color: "var(--text-secondary)", borderColor: "var(--border)" }}>{t("management.col_name")}</th>
                          <th className="py-4 px-5 text-right font-semibold text-[11px] uppercase tracking-wider border-b" style={{ color: "var(--text-secondary)", borderColor: "var(--border)" }}>{t("finance.col_amount")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.map((h) => {
                          const dt = new Date(h.created_at);
                          return (
                            <tr key={h.id} className="transition-colors group" style={{ borderBottom: "1px solid var(--border)" }}>
                              <td className="py-4 px-5">
                                <div className="flex flex-col">
                                  <span className="font-medium" style={{ color: "var(--text-primary)" }}>{dt.toLocaleDateString('ru-RU')}</span>
                                  <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</span>
                                </div>
                              </td>
                              <td className="py-4 px-5">
                                <div className="flex items-center gap-3">
                                  <div
                                    className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors"
                                    style={{ background: "var(--bg-hover)", color: "var(--text-secondary)" }}
                                  >
                                    {h.store_name.charAt(0).toUpperCase()}
                                  </div>
                                  <span className="font-medium" style={{ color: "var(--text-primary)" }}>{h.store_name}</span>
                                </div>
                              </td>
                              <td className="py-4 px-5 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                                <div className="w-2 h-2 rounded-full bg-green-500"></div>
                                {h.user_name}
                              </td>
                              <td className="py-4 px-5 text-right">
                                <span className="inline-flex items-center px-3 py-1 rounded-full bg-green-500/10 text-green-400 font-bold border border-green-500/20">
                                  + {h.amount.toLocaleString()} <span className="text-xs ml-1 font-normal opacity-70">TJS</span>
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
