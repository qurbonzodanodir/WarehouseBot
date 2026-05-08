"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Order, Store, UserMe, Product } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { CheckCircle2, XCircle, Truck, RefreshCw, Search, ArrowUpRight, ArrowDownLeft, ShoppingCart, ChevronLeft, ChevronRight, Plus, Trash2, Package } from "lucide-react";

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

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

async function requestOrders(
  statusFilter: string,
  storeFilter: number | "",
  page: number,
  pageSize: number,
) {
  return api.getOrders({
    status: statusFilter || undefined,
    store_id: storeFilter || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });
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
  const [user] = useState<UserMe | null>(() => getStoredUser());
  const [storeFilter, setStoreFilter] = useState<number | "">("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;
  const [stores, setStores] = useState<Store[]>([]);

  // Warehouse dispatch modal state
  const [dispatchModalOpen, setDispatchModalOpen] = useState(false);
  const [dispatchStoreId, setDispatchStoreId] = useState<number | null>(null);
  const [dispatchItems, setDispatchItems] = useState<{ product_id: number; quantity: number }[]>([]);
  const [dispatchLoading, setDispatchLoading] = useState(false);
  const [availableProducts, setAvailableProducts] = useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [itemQuantity, setItemQuantity] = useState("1");
  const [productSearch, setProductSearch] = useState("");

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

  async function refreshOrders() {
    setLoading(true);
    try {
      const data = await requestOrders(statusFilter, storeFilter, page, PAGE_SIZE);
      setOrders(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    
    if (user && user.role !== "seller") {
      api.getStores().then(setStores).catch((error) => {
        console.error(error);
      });
    }
  }, [router, user]);

  useEffect(() => {
    if (user) {
      setPage(1);
    }
  }, [user, statusFilter, storeFilter, search]);

  useEffect(() => {
    if (!user) return;

    let isActive = true;

    async function loadOrders() {
      setLoading(true);
      try {
        const data = await requestOrders(statusFilter, storeFilter, page, PAGE_SIZE);
        if (isActive) {
          setOrders(data);
        }
      } catch (error) {
        if (isActive) {
          console.error(error);
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    void loadOrders();

    return () => {
      isActive = false;
    };
  }, [user, statusFilter, storeFilter, page]);

  async function handleDispatch(id: number) {
    setActionLoading(id);
    try { await api.dispatchOrder(id); await refreshOrders(); showToast(t("orders.dispatch_success"), "success"); }
    catch (error) { showToast(getErrorMessage(error, t("common.error")), "error"); }
    finally { setActionLoading(null); }
  }

  async function handleReject(id: number) {
    if (!confirm(t("common.reject_confirm"))) return;
    setActionLoading(id);
    try { await api.rejectOrder(id); await refreshOrders(); showToast(t("orders.reject_success"), "success"); }
    catch (error) { showToast(getErrorMessage(error, t("common.error")), "error"); }
    finally { setActionLoading(null); }
  }

  async function handleDeliver(id: number) {
    setActionLoading(id);
    try { await api.deliverOrder(id); await refreshOrders(); }
    catch (error) { showToast(getErrorMessage(error, t("common.error")), "error"); }
    finally { setActionLoading(null); }
  }

  async function handleApproveReturn(id: number) {
    setActionLoading(id);
    try { await api.approveReturn(id); await refreshOrders(); showToast(t("orders.return_approved"), "success"); }
    catch (error) { showToast(getErrorMessage(error, t("common.error")), "error"); }
    finally { setActionLoading(null); }
  }

  async function handleRejectReturn(id: number) {
     if (!confirm(t("common.reject_confirm"))) return;
     setActionLoading(id);
     try { await api.rejectReturn(id); await refreshOrders(); showToast(t("orders.return_rejected"), "success"); }
     catch (error) { showToast(getErrorMessage(error, t("common.error")), "error"); }
     finally { setActionLoading(null); }
  }

  // Warehouse dispatch handlers
  async function openDispatchModal() {
    setDispatchModalOpen(true);
    setDispatchStoreId(null);
    setDispatchItems([]);
    setSelectedProductId(null);
    setItemQuantity("1");
    try {
      const products = await api.getProducts({ include_inactive: false, page_size: 1000 });
      setAvailableProducts(products.items || []);
    } catch (error) {
      console.error(error);
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  function closeDispatchModal() {
    setDispatchModalOpen(false);
    setDispatchStoreId(null);
    setDispatchItems([]);
    setSelectedProductId(null);
    setItemQuantity("1");
    setProductSearch("");
  }

  function addDispatchItem() {
    if (!selectedProductId || !itemQuantity) return;
    const qty = parseInt(itemQuantity, 10);
    if (qty <= 0) return;

    const existing = dispatchItems.find((item) => item.product_id === selectedProductId);
    if (existing) {
      setDispatchItems(dispatchItems.map((item) =>
        item.product_id === selectedProductId ? { ...item, quantity: item.quantity + qty } : item
      ));
    } else {
      setDispatchItems([...dispatchItems, { product_id: selectedProductId, quantity: qty }]);
    }
    setSelectedProductId(null);
    setItemQuantity("1");
  }

  function removeDispatchItem(product_id: number) {
    setDispatchItems(dispatchItems.filter((item) => item.product_id !== product_id));
  }

  async function handleDispatchSubmit() {
    if (!dispatchStoreId || dispatchItems.length === 0) {
      showToast("Выберите магазин и добавьте товары", "error");
      return;
    }
    setDispatchLoading(true);
    try {
      await api.dispatchFromWarehouse({
        store_id: dispatchStoreId,
        items: dispatchItems,
      });
      showToast("Заказ отправлен в магазин", "success");
      closeDispatchModal();
      await refreshOrders();
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setDispatchLoading(false);
    }
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
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <ShoppingCart size={32} style={{ color: "var(--accent)" }} />
              {t("orders.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginLeft: 44 }}>
              {t("orders.found", { count: orders.length })}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {canManage && (
              <button className="btn btn-primary" onClick={openDispatchModal}>
                <Package size={14} />
                Отправить в магазин
              </button>
            )}
            <button className="btn btn-ghost" onClick={() => void refreshOrders()}>
              <RefreshCw size={14} />
              {t("common.refresh")}
            </button>
          </div>
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
          <button className="btn btn-ghost" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <ChevronLeft size={16} /> {t("common.back")}
          </button>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-muted)" }}>{t("common.page")} {page}</div>
          <button className="btn btn-ghost" onClick={() => setPage(p => p + 1)} disabled={orders.length < PAGE_SIZE} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {t("common.next")} <ChevronRight size={16} />
          </button>
        </div>
      </main>

      {/* Warehouse Dispatch Modal */}
      {dispatchModalOpen && (
        <div className="modal-overlay orders-dispatch-overlay">
          <div className="modal-card orders-dispatch-modal">
            <div className="modal-header">
              <h3>Отправить в магазин</h3>
              <button className="btn btn-ghost" onClick={closeDispatchModal} style={{ padding: 4 }}>
                <XCircle size={18} />
              </button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>Магазин</label>
                <select
                  className="input"
                  value={dispatchStoreId ?? ""}
                  onChange={(e) => setDispatchStoreId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">— выбрать —</option>
                  {stores
                    .filter(s => s.store_type !== "warehouse")
                    .map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>Товар</label>
                <input
                  className="input"
                  placeholder="Поиск по SKU или бренду"
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                />
                <select
                  className="input"
                  style={{ marginTop: 8 }}
                  value={selectedProductId ?? ""}
                  onChange={(e) => setSelectedProductId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">— выбрать —</option>
                  {availableProducts
                    .filter(p => {
                      const q = productSearch.toLowerCase();
                      return !q || p.sku.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q);
                    })
                    .slice(0, 100)
                    .map(p => (
                      <option key={p.id} value={p.id}>{p.sku} - {p.brand}</option>
                    ))}
                </select>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                <div style={{ flex: 1 }}>
                  <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>Кол-во</label>
                  <input
                    className="input"
                    type="number"
                    min="1"
                    value={itemQuantity}
                    onChange={(e) => setItemQuantity(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary orders-dispatch-add" onClick={addDispatchItem}>
                  <Plus size={14} />
                </button>
              </div>

              {dispatchItems.length > 0 && (
                <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>
                    Товары для отправки ({dispatchItems.length})
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {dispatchItems.map((item) => {
                      const product = availableProducts.find(p => p.id === item.product_id);
                      if (!product) return null;
                      return (
                        <div key={item.product_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
                          <div>
                            <span style={{ fontWeight: 600 }}>{product.sku}</span>
                            <span style={{ color: "var(--text-muted)", marginLeft: 8 }}>{product.brand}</span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                            <span style={{ fontWeight: 600 }}>{item.quantity} шт</span>
                            <button
                              className="btn btn-ghost"
                              onClick={() => removeDispatchItem(item.product_id)}
                              style={{ padding: 4, color: "var(--red)" }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer" style={{ justifyContent: "flex-end", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-ghost" onClick={closeDispatchModal}>Отмена</button>
              <button
                className="btn btn-primary"
                onClick={handleDispatchSubmit}
                disabled={dispatchLoading || !dispatchStoreId || dispatchItems.length === 0}
              >
                {dispatchLoading ? "Отправка..." : "Отправить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
