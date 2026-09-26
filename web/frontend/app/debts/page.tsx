"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  MessageSquareText,
  NotebookTabs,
  Pencil,
  Plus,
  Search,
  Store as StoreIcon,
  Trash2,
  WalletCards,
  X,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";
import { isAuthenticated } from "@/lib/auth";
import {
  api,
  ManualDebtOverview,
  ManualDebtStoreDetail,
  ManualDebtTransaction,
  ManualDebtTransactionType,
} from "@/lib/api";
import { useToast } from "@/lib/ToastContext";
import styles from "./debts.module.css";

type DialogMode = "charge" | "payment" | "edit";

type DialogState = {
  mode: DialogMode;
  transaction?: ManualDebtTransaction;
} | null;

function money(value: number) {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value)} TJS`;
}

function localToday() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Не удалось выполнить операцию";
}

export default function DebtsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [overview, setOverview] = useState<ManualDebtOverview | null>(null);
  const [detail, setDetail] = useState<ManualDebtStoreDetail | null>(null);
  const [selectedStoreId, setSelectedStoreId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [dialog, setDialog] = useState<DialogState>(null);
  const [amount, setAmount] = useState("");
  const [operationDate, setOperationDate] = useState(localToday);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const loadDetail = useCallback(async (storeId: number) => {
    setDetailLoading(true);
    try {
      setDetail(await api.getManualDebtStore(storeId));
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setDetailLoading(false);
    }
  }, [showToast]);

  const loadOverview = useCallback(async (preferredStoreId?: number | null) => {
    const data = await api.getManualDebts();
    setOverview(data);
    const targetId = preferredStoreId && data.stores.some((item) => item.store_id === preferredStoreId)
      ? preferredStoreId
      : data.stores[0]?.store_id ?? null;
    setSelectedStoreId(targetId);
    if (targetId) await loadDetail(targetId);
    else setDetail(null);
  }, [loadDetail]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    let active = true;
    (async () => {
      try {
        await loadOverview();
      } catch (error) {
        if (active) showToast(errorMessage(error), "error");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [loadOverview, router, showToast]);

  const filteredStores = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("ru");
    return (overview?.stores ?? []).filter((store) =>
      store.store_name.toLocaleLowerCase("ru").includes(query)
    );
  }, [overview, search]);

  function selectStore(storeId: number) {
    setSelectedStoreId(storeId);
    setHistoryOpen(false);
    void loadDetail(storeId);
  }

  function openDialog(mode: DialogMode, transaction?: ManualDebtTransaction) {
    if (mode !== "edit" && !selectedStoreId && !overview?.stores.length) {
      showToast("Сначала добавьте магазин", "error");
      return;
    }
    setDialog({ mode, transaction });
    setAmount(transaction ? String(transaction.amount) : "");
    setOperationDate(transaction?.operation_date ?? localToday());
    setComment(transaction?.comment ?? "");
  }

  function closeDialog() {
    if (!saving) setDialog(null);
  }

  async function submitDialog(event: FormEvent) {
    event.preventDefault();
    if (!dialog) return;
    const parsedAmount = Number(amount.replace(",", "."));
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      showToast("Введите сумму больше нуля", "error");
      return;
    }
    const storeId = dialog.transaction?.store_id ?? selectedStoreId;
    if (!storeId) return;

    setSaving(true);
    try {
      const payload = {
        amount: parsedAmount,
        operation_date: operationDate,
        comment: comment.trim() || null,
      };
      if (dialog.mode === "edit" && dialog.transaction) {
        await api.updateManualDebtTransaction(dialog.transaction.id, payload);
        showToast("Операция обновлена", "success");
      } else if (dialog.mode === "charge") {
        await api.createManualDebtCharge({ store_id: storeId, ...payload });
        showToast("Долг начислен", "success");
      } else {
        await api.createManualDebtPayment({ store_id: storeId, ...payload });
        showToast("Оплата принята", "success");
      }
      setDialog(null);
      await loadOverview(storeId);
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setSaving(false);
    }
  }

  async function deleteTransaction(transaction: ManualDebtTransaction) {
    if (!window.confirm("Удалить эту операцию из истории?")) return;
    try {
      await api.deleteManualDebtTransaction(transaction.id);
      showToast("Операция удалена", "success");
      await loadOverview(transaction.store_id);
    } catch (error) {
      showToast(errorMessage(error), "error");
    }
  }

  const selectedSummary = overview?.stores.find((item) => item.store_id === selectedStoreId);
  const dialogType: ManualDebtTransactionType = dialog?.mode === "edit"
    ? dialog.transaction?.type ?? "charge"
    : dialog?.mode ?? "charge";

  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={`main-layout ${styles.main}`}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>Отдельный учёт</div>
            <h1 className={styles.title}><NotebookTabs size={30} /> Долги магазинов</h1>
            <p className={styles.subtitle}>Ручные начисления и оплаты, отдельно от продаж и инкассации.</p>
          </div>
          <button className="btn btn-primary" onClick={() => openDialog("charge")} disabled={!overview?.stores.length}>
            <Plus size={18} /> Добавить долг
          </button>
        </header>

        {loading ? (
          <div className={styles.loading}>Загрузка долгов…</div>
        ) : (
          <>
            <section className={styles.stats}>
              <article className={styles.statCard}>
                <span className={styles.statIcon}><StoreIcon size={20} /></span>
                <div><p>Магазинов с долгом</p><strong>{overview?.stores_with_debt ?? 0}</strong></div>
              </article>
              <article className={styles.statCard}>
                <span className={`${styles.statIcon} ${styles.orange}`}><WalletCards size={20} /></span>
                <div><p>Общий ручной долг</p><strong>{money(Number(overview?.total_debt ?? 0))}</strong></div>
              </article>
              <article className={styles.statCard}>
                <span className={`${styles.statIcon} ${styles.blue}`}><CircleDollarSign size={20} /></span>
                <div><p>Начислено в этом месяце</p><strong>{money(Number(overview?.charged_this_month ?? 0))}</strong></div>
              </article>
            </section>

            <section className={styles.workspace}>
              <aside className={styles.storePanel}>
                <div className={styles.panelHeading}>
                  <div><strong>Магазины</strong><span>{overview?.stores.length ?? 0}</span></div>
                  <label className={styles.search}>
                    <Search size={16} />
                    <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Найти магазин" />
                  </label>
                </div>
                <div className={styles.storeList}>
                  {filteredStores.map((store) => (
                    <button
                      key={store.store_id}
                      className={`${styles.storeRow} ${selectedStoreId === store.store_id ? styles.activeStore : ""}`}
                      onClick={() => selectStore(store.store_id)}
                    >
                      <span className={styles.storeAvatar}>{store.store_name.slice(0, 1).toUpperCase()}</span>
                      <span className={styles.storeMeta}>
                        <strong>{store.store_name}</strong>
                        <small>{store.last_transaction ? `${formatDate(store.last_transaction.operation_date)} · ${store.last_transaction.type === "charge" ? "начисление" : "оплата"}` : "Операций пока нет"}</small>
                      </span>
                      <span className={styles.storeBalance}>{money(Number(store.balance))}</span>
                      <ChevronRight size={17} className={styles.chevron} />
                    </button>
                  ))}
                  {!filteredStores.length && <div className={styles.empty}>Магазины не найдены</div>}
                </div>
              </aside>

              <div className={styles.detailPanel}>
                {!selectedSummary ? (
                  <div className={styles.emptyDetail}>Выберите магазин, чтобы увидеть ручной долг.</div>
                ) : (
                  <>
                    <div className={styles.detailTop}>
                      <div>
                        <span className={styles.detailLabel}>Магазин</span>
                        <h2>{selectedSummary.store_name}</h2>
                      </div>
                      <div className={styles.balanceBlock}>
                        <span>Текущий ручной долг</span>
                        <strong>{money(Number(detail?.balance ?? selectedSummary.balance))}</strong>
                      </div>
                    </div>

                    <div className={styles.actions}>
                      <button className={styles.chargeButton} onClick={() => openDialog("charge")}>
                        <ArrowUpRight size={19} />
                        <span><strong>Начислить долг</strong><small>Увеличить ручной баланс</small></span>
                      </button>
                      <button
                        className={styles.paymentButton}
                        onClick={() => openDialog("payment")}
                        disabled={Number(detail?.balance ?? 0) <= 0}
                      >
                        <ArrowDownLeft size={19} />
                        <span><strong>Принять оплату</strong><small>Уменьшить ручной баланс</small></span>
                      </button>
                    </div>

                    <div className={styles.historySection}>
                      <button className={styles.historyToggle} onClick={() => setHistoryOpen((value) => !value)}>
                        <span><NotebookTabs size={18} /> История <b>{detail?.transactions.length ?? 0}</b></span>
                        <span className={styles.toggleHint}>{historyOpen ? "Скрыть" : "Показать"} <ChevronDown size={17} className={historyOpen ? styles.rotated : ""} /></span>
                      </button>

                      {detailLoading && <div className={styles.empty}>Загрузка истории…</div>}
                      {historyOpen && !detailLoading && (
                        <div className={styles.historyList}>
                          {detail?.transactions.map((transaction) => (
                            <article className={styles.transaction} key={transaction.id}>
                              <span className={`${styles.transactionIcon} ${transaction.type === "charge" ? styles.chargeIcon : styles.paymentIcon}`}>
                                {transaction.type === "charge" ? <ArrowUpRight size={18} /> : <ArrowDownLeft size={18} />}
                              </span>
                              <div className={styles.transactionBody}>
                                <div className={styles.transactionTitle}>
                                  <strong>{transaction.type === "charge" ? "Начислен долг" : "Принята оплата"}</strong>
                                  <strong className={transaction.type === "charge" ? styles.positiveAmount : styles.negativeAmount}>
                                    {transaction.type === "charge" ? "+" : "−"}{money(Number(transaction.amount))}
                                  </strong>
                                </div>
                                <div className={styles.transactionInfo}>
                                  <span><CalendarDays size={14} /> {formatDate(transaction.operation_date)}</span>
                                  <span><MessageSquareText size={14} /> {transaction.comment || "Без комментария"}</span>
                                  <span>Добавил: {transaction.user_name}</span>
                                </div>
                              </div>
                              <div className={styles.rowActions}>
                                <button aria-label="Редактировать" onClick={() => openDialog("edit", transaction)}><Pencil size={16} /></button>
                                <button aria-label="Удалить" onClick={() => void deleteTransaction(transaction)}><Trash2 size={16} /></button>
                              </div>
                            </article>
                          ))}
                          {!detail?.transactions.length && <div className={styles.empty}>Операций пока нет</div>}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </section>
          </>
        )}
      </main>

      {dialog && (
        <div className="modal-overlay" onMouseDown={closeDialog}>
          <form className={`modal-card ${styles.modal}`} onSubmit={submitDialog} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className={styles.modalKicker}>{dialogType === "charge" ? "Начисление" : "Оплата"}</span>
                <h3>{dialog.mode === "edit" ? "Редактировать операцию" : dialog.mode === "charge" ? "Добавить ручной долг" : "Принять оплату"}</h3>
              </div>
              <button type="button" className={styles.closeButton} onClick={closeDialog} aria-label="Закрыть"><X size={20} /></button>
            </div>
            <div className={styles.modalBody}>
              <label className={styles.field}>
                <span>Магазин</span>
                {dialog.mode === "edit" ? (
                  <input className="input" value={dialog.transaction?.store_name ?? ""} disabled />
                ) : (
                  <select className="input" value={selectedStoreId ?? ""} onChange={(event) => selectStore(Number(event.target.value))} required>
                    {overview?.stores.map((store) => <option key={store.store_id} value={store.store_id}>{store.store_name}</option>)}
                  </select>
                )}
              </label>
              <div className={styles.formGrid}>
                <label className={styles.field}><span>Сумма, TJS</span><input className="input" type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" required autoFocus /></label>
                <label className={styles.field}><span>Дата</span><input className="input" type="date" value={operationDate} onChange={(event) => setOperationDate(event.target.value)} required /></label>
              </div>
              <label className={styles.field}><span>Комментарий</span><textarea className={`input ${styles.textarea}`} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Например: по договорённости с магазином" maxLength={1000} /></label>
              {dialogType === "payment" && detail && <p className={styles.balanceNote}>Доступно к оплате: <strong>{money(Number(detail.balance))}</strong></p>}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-ghost" onClick={closeDialog}>Отмена</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Сохранение…" : "Сохранить"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
