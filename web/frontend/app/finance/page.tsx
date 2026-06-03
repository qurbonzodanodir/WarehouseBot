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
} from "lucide-react";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

async function requestFinanceData() {
  const [debtData, histData] = await Promise.all([
    api.getDebtors(),
    api.getFinanceHistory(30),
  ]);
  return { debtData, histData };
}

export default function FinancePage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [debtors, setDebtors] = useState<CashCollectionSummary[]>([]);
  const [history, setHistory] = useState<CashCollectionHistoryItem[]>([]);

  // Form State
  const [fullStoreId, setFullStoreId] = useState<number | "">("");
  const [partialStoreId, setPartialStoreId] = useState<number | "">("");
  const [partialAmount, setPartialAmount] = useState<string>("");
  const errorText = "";
  const successText = "";

  async function fetchData() {
    try {
      setLoading(true);
      const { debtData, histData } = await requestFinanceData();
      setDebtors(debtData);
      setHistory(histData);
    } catch (error) {
      showToast(`${t("common.error")} : ${getErrorMessage(error, t("common.error"))}`, "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    let isActive = true;

    async function loadFinance() {
      try {
        setLoading(true);
        const { debtData, histData } = await requestFinanceData();
        if (isActive) {
          setDebtors(debtData);
          setHistory(histData);
        }
      } catch (error) {
        if (isActive) {
          showToast(`${t("common.error")} : ${getErrorMessage(error, t("common.error"))}`, "error");
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    void loadFinance();

    return () => {
      isActive = false;
    };
  }, [router, showToast, t]);

  const totalDebt = debtors.reduce((acc, curr) => acc + Number(curr.current_debt), 0);
  const selectedFullStore = debtors.find((d) => d.store_id === Number(fullStoreId));
  const selectedPartialStore = debtors.find((d) => d.store_id === Number(partialStoreId));

  const handleFullCollect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullStoreId) {
      showToast(t("finance.err_req"), "error");
      return;
    }
    const store = debtors.find((d) => d.store_id === Number(fullStoreId));
    if (!store) return;
    const val = Number(store.current_debt);
    if (val <= 0) {
      showToast(t("finance.err_zero"), "error");
      return;
    }

    try {
      setSubmitting(true);
      await api.collectCash(Number(fullStoreId), val);
      showToast(t("finance.success_collected", { amount: val }), "success");
      setFullStoreId("");
      await fetchData(); // Refresh data
    } catch (error) {
      showToast(getErrorMessage(error, t("finance.err_collect")), "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePartialCollect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!partialStoreId || !partialAmount) {
      showToast(t("finance.err_req"), "error");
      return;
    }
    const val = parseFloat(partialAmount);
    if (isNaN(val) || val <= 0) {
      showToast(t("finance.err_zero"), "error");
      return;
    }
    const store = debtors.find((d) => d.store_id === Number(partialStoreId));
    if (store && val > Number(store.current_debt)) {
      showToast("Сумма не может превышать текущий долг магазина.", "error");
      return;
    }

    try {
      setSubmitting(true);
      await api.collectCash(Number(partialStoreId), val);
      showToast(t("finance.success_collected", { amount: val }), "success");
      setPartialStoreId("");
      setPartialAmount("");
      await fetchData(); // Refresh data
    } catch (error) {
      showToast(getErrorMessage(error, t("finance.err_collect")), "error");
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
              {/* Left Column: Collection Form */}
              <div className="flex flex-col gap-6 sticky top-6 h-fit">
                
                {/* Card 1: Полное списание */}
                <div className="card p-0" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center gap-3 px-6 py-5 border-b" style={{ borderColor: "var(--border)" }}>
                    <div className="p-2.5 rounded-lg" style={{ background: "rgba(34, 197, 94, 0.1)", color: "var(--green)" }}>
                      <CheckCircle2 className="w-5 h-5" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                        {t("finance.full_collect_title")}
                      </h2>
                      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                        {t("finance.full_collect_desc")}
                      </p>
                    </div>
                  </div>

                  <div className="p-6">
                    <form onSubmit={handleFullCollect} className="flex flex-col gap-4">
                      <div className="flex flex-col gap-2">
                        <label className="text-[12px] font-medium" style={{ color: "var(--text-secondary)" }}>
                          {t("finance.select_store")}
                        </label>
                        <select
                          className="input"
                          value={fullStoreId}
                          onChange={(e) => setFullStoreId(e.target.value ? Number(e.target.value) : "")}
                        >
                          <option value="" disabled>-- {t("finance.select_store")} --</option>
                          {debtors.map((d) => (
                            <option key={d.store_id} value={d.store_id}>
                              {d.store_name} ({d.current_debt} TJS)
                            </option>
                          ))}
                        </select>
                      </div>

                      <button
                        type="submit"
                        className="btn btn-success w-full py-2.5 mt-2 text-[14px] font-semibold justify-center gap-2"
                        disabled={submitting || !fullStoreId}
                      >
                        {submitting ? (
                          <div className="spinner" style={{ width: 16, height: 16 }} />
                        ) : selectedFullStore ? (
                          <>
                            {t("finance.full_collect_btn")}: {selectedFullStore.current_debt.toLocaleString()} TJS
                          </>
                        ) : (
                          t("finance.select_store")
                        )}
                      </button>
                    </form>
                  </div>
                </div>

                {/* Card 2: Частичное списание */}
                <div className="card p-0" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center gap-3 px-6 py-5 border-b" style={{ borderColor: "var(--border)" }}>
                    <div className="p-2.5 rounded-lg" style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>
                      <Receipt className="w-5 h-5" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                        {t("finance.partial_collect_title")}
                      </h2>
                      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                        {t("finance.partial_collect_desc")}
                      </p>
                    </div>
                  </div>

                  <div className="p-6">
                    <form onSubmit={handlePartialCollect} className="flex flex-col gap-4">
                      <div className="flex flex-col gap-2">
                        <label className="text-[12px] font-medium" style={{ color: "var(--text-secondary)" }}>
                          {t("finance.select_store")}
                        </label>
                        <select
                          className="input"
                          value={partialStoreId}
                          onChange={(e) => {
                            setPartialStoreId(e.target.value ? Number(e.target.value) : "");
                            setPartialAmount("");
                          }}
                        >
                          <option value="" disabled>-- {t("finance.select_store")} --</option>
                          {debtors.map((d) => (
                            <option key={d.store_id} value={d.store_id}>
                              {d.store_name} ({d.current_debt} TJS)
                            </option>
                          ))}
                        </select>
                      </div>

                      {partialStoreId && selectedPartialStore && (
                        <div className="flex flex-col gap-3 p-3 rounded-lg border" style={{ borderColor: "var(--border)", background: "var(--bg-hover)" }}>
                          <div className="flex justify-between text-xs">
                            <span style={{ color: "var(--text-secondary)" }}>{t("finance.debt")}:</span>
                            <span className="font-bold" style={{ color: "var(--text-primary)" }}>
                              {selectedPartialStore.current_debt.toLocaleString()} TJS
                            </span>
                          </div>

                          <div className="flex flex-col gap-1.5">
                            <label className="text-[11px] font-medium" style={{ color: "var(--text-secondary)" }}>
                              {t("finance.amount")}
                            </label>
                            <div className="relative">
                              <input
                                type="number"
                                className="input w-full font-semibold"
                                style={{ paddingRight: 60 }}
                                placeholder={t("finance.amount_ph")}
                                step="0.01"
                                min="0.01"
                                max={selectedPartialStore.current_debt}
                                value={partialAmount}
                                onChange={(e) => setPartialAmount(e.target.value)}
                              />
                              <button
                                type="button"
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-bold px-2 py-1 rounded hover:opacity-85"
                                style={{ background: "var(--accent-muted)", color: "var(--accent)" }}
                                onClick={() => setPartialAmount(selectedPartialStore.current_debt.toString())}
                              >
                                {t("finance.max")}
                              </button>
                            </div>
                          </div>

                          {partialAmount && (
                            <div className="flex justify-between text-xs pt-1 border-t" style={{ borderColor: "var(--border)" }}>
                              <span style={{ color: "var(--text-muted)" }}>Остаток долга:</span>
                              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                                {Math.max(0, Number(selectedPartialStore.current_debt) - (Number(partialAmount) || 0)).toLocaleString()} TJS
                              </span>
                            </div>
                          )}
                        </div>
                      )}

                      <button
                        type="submit"
                        className="btn btn-primary w-full py-2.5 mt-1 text-[14px] font-semibold justify-center gap-2"
                        disabled={submitting || !partialStoreId || !partialAmount}
                      >
                        {submitting ? (
                          <div className="spinner" style={{ width: 16, height: 16 }} />
                        ) : (
                          t("finance.partial_collect_btn")
                        )}
                      </button>
                    </form>
                  </div>
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
