"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Order } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { CheckCircle2, XCircle, Truck, RefreshCw, Search, ArrowUpRight, ArrowDownLeft } from "lucide-react";

function badgeClass(status: string) {
  const s = status.toLowerCase();
  if (s.includes("pending") && !s.includes("return")) return "badge badge-pending";
  if (s === "dispatched" || s === "display_dispatched") return "badge badge-dispatched";
  if (s === "delivered" || s === "display_delivered") return "badge badge-delivered";
  if (s === "sold") return "badge badge-sold";
  if (s.includes("return")) return "badge badge-return_pending";
  if (s === "rejected") return "badge badge-rejected";
  return "badge";
}

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

export default function OrdersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") || "";
  
  const { t } = useTranslation();
  const { showToast } = useToast();
  
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [search, setSearch] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [user, setUser] = useState<any>(null);
  const [storeFilter, setStoreFilter] = useState<number | "">("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;
  const [stores, setStores] = useState<any[]>([]);

  const STATUSES = [
    { key: "", label: t("orders.status_all") },
    { key: "active", label: t("orders.status_active") || "Активные" },
    { key: "pending", label: t("orders.status_pending") },
    { key: "return_pending", label: t("orders.status_return_pending") },
    { key: "dispatched", label: t("orders.status_dispatched") },
    { key: "delivered", label: t("orders.status_delivered") },
    { key: "sold", label: t("orders.status_sold") },
    { key: "returned", label: t("orders.status_returned") },
    { key: "rejected", label: t("orders.status_rejected") },
  ];

  useEffect(() => {
    const usr = getStoredUser();
    setUser(usr);
    if (!isAuthenticated()) { router.push("/login"); return; }
    
    if (usr && usr.role !== "seller") {
      api.getStores().then(setStores).catch(console.error);
    }
  }, [router]);

  useEffect(() => {
    if (user) {
      setPage(1);
    }
  }, [statusFilter, storeFilter, search]);

  useEffect(() => {
    if (user) {
      fetchOrders();
    }
  }, [user, statusFilter, storeFilter, page]);

  async function fetchOrders() {
    setLoading(true);
    try {
      const data = await api.getOrders({
        status: statusFilter || undefined,
        store_id: storeFilter || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setOrders(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleDispatch(id: number) {
    setActionLoading(id);
    try { await api.dispatchOrder(id); await fetchOrders(); showToast(t("orders.dispatch_success"), "success"); }
    catch (e: any) { showToast(e.message, "error"); }
    finally { setActionLoading(null); }
  }

  async function handleReject(id: number) {
    if (!confirm(t("common.reject_confirm"))) return;
    setActionLoading(id);
    try { await api.rejectOrder(id); await fetchOrders(); showToast(t("orders.reject_success"), "success"); }
    catch (e: any) { showToast(e.message, "error"); }
    finally { setActionLoading(null); }
  }

  async function handleDeliver(id: number) {
    setActionLoading(id);
    try { await api.deliverOrder(id); await fetchOrders(); }
    catch (e: any) { showToast(e.message, "error"); }
    finally { setActionLoading(null); }
  }

  async function handleApproveReturn(id: number) {
    setActionLoading(id);
    try { await api.approveReturn(id); await fetchOrders(); showToast(t("orders.return_approved"), "success"); }
    catch (e: any) { showToast(e.message, "error"); }
    finally { setActionLoading(null); }
  }

  async function handleRejectReturn(id: number) {
     if (!confirm(t("common.reject_confirm"))) return;
     setActionLoading(id);
     try { await api.rejectReturn(id); await fetchOrders(); showToast(t("orders.return_rejected"), "success"); }
     catch (e: any) { showToast(e.message, "error"); }
     finally { setActionLoading(null); }
  }

  const filtered = orders.filter((o) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      o.product.sku.toLowerCase().includes(q) ||
      o.store.name.toLowerCase().includes(q)
    );
  });

  const canManage = user?.role === "warehouse" || user?.role === "owner" || user?.role === "admin";

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        <div className="page-header">
          <div>
            <h1 className="page-title">{t("orders.title")}</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 2 }}>
              {t("orders.found", { count: orders.length })}
            </p>
          </div>
          <button className="btn btn-ghost" onClick={fetchOrders}>
            <RefreshCw size={14} />
            {t("common.refresh")}
          </button>
        </div>

        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
          <div style={{ position: "relative", flex: "1 1 200px", minWidth: 0 }}>
            <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
            <input
              className="input"
              style={{ paddingLeft: 36, width: "100%" }}
              placeholder={t("orders.search_placeholder")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {user && user.role !== "seller" && stores.length > 0 && (
            <select
              className="input"
              style={{ flex: "1 1 140px", minWidth: 0 }}
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">{t("orders.all_stores")}</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="tab-container" style={{ marginBottom: 20, overflowX: "auto" }}>
          <div style={{ display: "flex", gap: 8 }}>
            {STATUSES.map((s) => (
              <button
                key={s.key}
                onClick={() => setStatusFilter(s.key)}
                className={`tab-btn ${statusFilter === s.key ? "active" : ""}`}
                style={{
                    padding: "8px 16px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    border: "1px solid var(--border)",
                    background: statusFilter === s.key ? "var(--accent)" : "var(--bg-card)",
                    color: statusFilter === s.key ? "var(--bg)" : "var(--text-secondary)",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    whiteSpace: "nowrap"
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrap">
            {loading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
                <div className="spinner" />
              </div>
            ) : filtered.length === 0 ? (
              <div style={{ padding: 60, textAlign: "center", color: "var(--text-muted)" }}>{t("orders.no_orders")}</div>
            ) : (
              <table>
                <thead>
                    <tr>
                      <th>ID</th>
                      <th>{t("orders.col_store_product")}</th>
                      <th style={{ textAlign: "right" }}>{t("orders.col_qty")}</th>
                      <th style={{ textAlign: "left" }}>{t("orders.col_total")}</th>
                      <th>{t("common.status")}</th>
                      <th>{t("orders.col_date")}</th>
                      {(canManage || user?.role === "seller") && <th>{t("common.actions")}</th>}
                    </tr>
                </thead>
                <tbody>
                  {filtered.map((order) => {
                    const isReturn = order.status.toLowerCase().includes("return");
                    return (
                      <tr key={order.id} style={{ opacity: order.status.toLowerCase() === "rejected" ? 0.6 : 1 }}>
                        <td data-label="ID" style={{ color: "var(--text-muted)", fontSize: 13 }}>#{order.id}</td>
                        <td data-label={t("orders.col_store_product")}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                             <div style={{ 
                               width: 24, 
                               height: 24, 
                               borderRadius: 6, 
                               background: isReturn ? "rgba(239,68,68,0.1)" : "rgba(34,197,94,0.1)",
                               display: "flex",
                               alignItems: "center",
                               justifyContent: "center"
                             }}>
                                {isReturn ? <ArrowDownLeft size={14} color="var(--red)" /> : <ArrowUpRight size={14} color="var(--green)" />}
                             </div>
                             <div>
                               <div style={{ fontWeight: 600 }}>{order.store.name}</div>
                               <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{order.product.sku}</div>
                             </div>
                          </div>
                        </td>
                        <td data-label={t("orders.col_qty")} style={{ textAlign: "right", fontWeight: 700 }}>{order.quantity} шт</td>
                        <td data-label={t("orders.col_total")} style={{ fontWeight: 600 }}>{fmt(Number(order.total_price))} TJS</td>
                        <td data-label={t("common.status")}>
                          <span className={badgeClass(order.status)}>
                            {t(`statuses.${order.status.toLowerCase()}`) || order.status}
                          </span>
                        </td>
                        <td data-label={t("orders.col_date")} style={{ color: "var(--text-muted)", fontSize: 12 }}>
                          {new Date(order.created_at).toLocaleString("ru-RU", {
                            day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
                          })}
                        </td>
                        {canManage && (
                          <td data-label={t("common.actions")}>
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
                              {order.status === "pending" && (
                                <>
                                  <button className="btn btn-success" style={{ padding: "5px 10px" }} onClick={() => handleDispatch(order.id)} disabled={actionLoading === order.id}>
                                    <Truck size={14} /> {t("orders.action_dispatch")}
                                  </button>
                                  <button className="btn btn-danger" style={{ padding: "5px 10px" }} onClick={() => handleReject(order.id)} disabled={actionLoading === order.id}>
                                    <XCircle size={14} />
                                  </button>
                                </>
                              )}
                              {isReturn && order.status.toLowerCase().includes("pending") && (
                                <>
                                  <button className="btn btn-success" style={{ padding: "5px 10px" }} onClick={() => handleApproveReturn(order.id)} disabled={actionLoading === order.id}>
                                    <CheckCircle2 size={14} /> {t("orders.action_receive")}
                                  </button>
                                  <button className="btn btn-danger" style={{ padding: "5px 10px" }} onClick={() => handleRejectReturn(order.id)} disabled={actionLoading === order.id}>
                                    <XCircle size={14} /> {t("orders.status_rejected")}
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        )}
                        {!canManage && user?.role === "seller" && (
                          <td data-label={t("common.actions")}>
                            {order.status === "dispatched" && (
                              <button className="btn btn-success" style={{ padding: "5px 10px", width: "100%", justifyContent: "center" }} onClick={() => handleDeliver(order.id)} disabled={actionLoading === order.id}>
                                 <CheckCircle2 size={14} /> {t("orders.action_receive")}
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 24, marginBottom: 40 }}>
          <button className="btn btn-ghost" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>← {t("common.back")}</button>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-muted)" }}>{t("common.page")} {page}</div>
          <button className="btn btn-ghost" onClick={() => setPage(p => p + 1)} disabled={orders.length < PAGE_SIZE}>{t("common.next")} →</button>
        </div>
      </main>
    </div>
  );
}
