"use client";
import React, { useEffect, useState, useCallback, Fragment } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Product, ProductInventoryOut, Store } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { Search, Plus, StoreIcon, ChevronDown, ChevronRight, PackageOpen, FileUp, X, CheckCircle2, ShoppingCart, Trash2 } from "lucide-react";
import * as XLSX from "xlsx";
import { createPortal } from "react-dom";

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

function normalizeSku(raw: unknown): string {
  return String(raw ?? "").trim().toUpperCase();
}

function parseLocalizedNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : NaN;
  const text = String(value ?? "").trim().replace(",", ".");
  if (!text) return NaN;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : NaN;
}

export default function ProductsPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();
  
  const [user, setUser] = useState<any>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const PAGE_SIZE = 50;

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ sku: "", price: "" });
  const [pendingToggleProduct, setPendingToggleProduct] = useState<Product | null>(null);
  const [toggling, setToggling] = useState(false);
  const [pendingDeleteProduct, setPendingDeleteProduct] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [inventoryLoaders, setInventoryLoaders] = useState<Record<number, boolean>>({});
  const [inventoryCache, setInventoryCache] = useState<Record<number, ProductInventoryOut[]>>({});

  const [stores, setStores] = useState<Store[]>([]);
  
  // Modals
  const [receivingProduct, setReceivingProduct] = useState<Product | null>(null);
  const [receiveQty, setReceiveQty] = useState("");

  const [dispatchProduct, setDispatchProduct] = useState<Product | null>(null);
  const [isDispatchModalOpen, setIsDispatchModalOpen] = useState(false);
  const [targetStoreId, setTargetStoreId] = useState<number | string>("");
  const [dispatchQty, setDispatchQty] = useState<string>("1");

  const [isOrderModalOpen, setIsOrderModalOpen] = useState(false);
  const [orderItem, setOrderItem] = useState<any>(null);

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importData, setImportData] = useState<any[]>([]);
  const [importing, setImporting] = useState(false);
  const [importParsing, setImportParsing] = useState(false);
  const [mounted, setMounted] = useState(false);

  const isWarehouse = user?.role === "owner" || user?.role === "warehouse" || user?.role === "admin";
  const isSeller = user?.role === "seller";

  const fetchProducts = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getProducts({
        search,
        page,
        page_size: PAGE_SIZE,
        only_inactive: showInactive,
      });
      setProducts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (e: any) {
      showToast(e.message || "Failed to fetch products", "error");
    } finally {
      setLoading(false);
    }
  }, [search, page, showInactive, showToast]);

  useEffect(() => {
    const usr = getStoredUser();
    setUser(usr);
    if (!isAuthenticated()) { router.push("/login"); return; }
    api.getStores().then(setStores).catch(console.error);
    fetchProducts();
  }, [router, fetchProducts]);

  useEffect(() => {
    setPage(1);
  }, [search]);

  useEffect(() => {
    setMounted(true);
  }, []);

  async function handleToggleActive(p: Product) {
    try {
      setToggling(true);
      await api.updateProduct(p.id, { is_active: !p.is_active });
      setPendingToggleProduct(null);
      await fetchProducts();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setToggling(false);
    }
  }

  async function handleHardDelete(p: Product) {
    try {
      setDeleting(true);
      await api.deleteProduct(p.id);
      setPendingDeleteProduct(null);
      await fetchProducts();
      showToast(t("products.hard_delete_success"), "success");
    } catch (err: any) {
      showToast(err.message || t("products.hard_delete_failed"), "error");
    } finally {
      setDeleting(false);
    }
  }

  async function handleToggleExpand(productId: number) {
    if (expandedRow === productId) {
      setExpandedRow(null);
      return;
    }
    setExpandedRow(productId);

    if (!inventoryCache[productId]) {
      setInventoryLoaders((prev) => ({ ...prev, [productId]: true }));
      try {
        const data = await api.getProductInventory(productId);
        setInventoryCache((prev) => ({ ...prev, [productId]: data }));
      } catch (e: any) {
        console.error("Failed to load inventory for product", e);
      } finally {
        setInventoryLoaders((prev) => ({ ...prev, [productId]: false }));
      }
    }
  }

  async function handleReceiveStock(e: React.FormEvent) {
    e.preventDefault();
    if (!receivingProduct || !receiveQty) return;
    const qty = parseInt(receiveQty, 10);
    if (qty <= 0) return showToast(t("products.invalid_qty"), "error");
    try {
      await api.receiveStock({ product_id: receivingProduct.id, quantity: qty });
      setReceivingProduct(null);
      setReceiveQty("");
      const inv = await api.getProductInventory(receivingProduct.id);
      setInventoryCache((prev) => ({ ...prev, [receivingProduct.id]: inv }));
      showToast(t("products.receive_success", { qty, sku: receivingProduct.sku }));
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  const handleDispatch = async () => {
    const qty = parseInt(dispatchQty);
    if (!dispatchProduct || !targetStoreId || isNaN(qty) || qty <= 0) return;
    try {
      await api.dispatchDisplay({
        product_id: dispatchProduct.id,
        target_store_id: Number(targetStoreId),
        quantity: qty
      });
      const updated = await api.getProductInventory(dispatchProduct.id);
      setInventoryCache((prev) => ({ ...prev, [dispatchProduct.id]: updated }));
      setIsDispatchModalOpen(false);
      setDispatchProduct(null);
      setTargetStoreId("");
      setDispatchQty("1");
      showToast(t("inventory.dispatch_success"), "success");
    } catch (e: any) {
      showToast(e.message, "error");
    }
  };

  async function handleQuickOrder() {
    if (!orderItem || !user?.store_id) return;
    const qty = parseInt(dispatchQty);
    if (isNaN(qty) || qty <= 0) return;
    try {
      await api.createOrder({
        product_id: orderItem.product_id,
        quantity: qty,
        store_id: user.store_id
      });
      showToast(t("products.order_success") || "Заявка создана!", "success");
      setIsOrderModalOpen(false);
      setOrderItem(null);
      setDispatchQty("1");
    } catch (e: any) {
      showToast(e.message, "error");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.createProduct({ sku: form.sku, price: Number(form.price) });
      setForm({ sku: "", price: "" });
      setAdding(false);
      await fetchProducts();
    } catch (e: any) { showToast(e.message, "error"); }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportParsing(true);
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const bstr = evt.target?.result;
        const wb = XLSX.read(bstr, { type: "binary" });
        const wsname = wb.SheetNames[0];
        const ws = wb.Sheets[wsname];
        const data = XLSX.utils.sheet_to_json(ws, { header: 1 }) as any[][];
        const grouped = new Map<string, { sku: string; total: number; priceSum: number; priceCount: number }>();
        const errors: string[] = [];
        for (let i = 0; i < data.length; i++) {
          const row = data[i];
          if (!row || row.length < 6) continue;
          const sku = normalizeSku(row[2]);
          const unitsPerBox = parseLocalizedNumber(row[3]);
          const boxes = parseLocalizedNumber(row[4]);
          const total = parseLocalizedNumber(row[5]);
          const price = parseLocalizedNumber(row[6]);
          const derivedTotal = !Number.isNaN(total) ? total : boxes * unitsPerBox;

          if (!sku) continue;
          if (!Number.isFinite(derivedTotal) || derivedTotal <= 0) {
            errors.push(`row ${i + 1}: invalid quantity for SKU ${sku}`);
            continue;
          }
          if (!Number.isNaN(price) && price < 0) {
            errors.push(`row ${i + 1}: negative price for SKU ${sku}`);
            continue;
          }

          const current = grouped.get(sku) ?? {
            sku,
            total: 0,
            priceSum: 0,
            priceCount: 0,
          };
          current.total += derivedTotal;
          if (!Number.isNaN(price) && price > 0) {
            current.priceSum += price;
            current.priceCount += 1;
          }
          grouped.set(sku, current);
        }

        const parsedItems = Array.from(grouped.values()).map((item) => ({
          sku: item.sku,
          total: Math.round(item.total),
          price: item.priceCount > 0 ? item.priceSum / item.priceCount : 0,
        }));

        if (errors.length) {
          showToast(`Import warnings: ${errors.slice(0, 3).join("; ")}`, "error");
        }
        setImportData(parsedItems);
      } catch (err) { showToast(t("products.import_error"), "error"); }
      finally { setImportParsing(false); }
    };
    reader.readAsBinaryString(file);
  };

  const handleProcessImport = async () => {
    if (importData.length === 0) return;
    setImporting(true);
    try {
      const res = await api.bulkReceiveStock(importData.map(d => ({
        sku: d.sku,
        quantity: Math.round(d.total),
        price: d.price > 0 ? d.price : undefined
      })));
      showToast(t("products.import_success", { processed: res.processed, created: res.created }));
      setImportModalOpen(false);
      setImportData([]);
      await fetchProducts();
    } catch (err: any) { showToast(err.message, "error"); }
    finally { setImporting(false); }
  };

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        <div className="page-header">
          <div>
            <h1 className="page-title">{t("products.title")}</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 2 }}>
              {t("products.found", { count: total })}
            </p>
          </div>
          {isWarehouse && (
            <div style={{ display: "flex", gap: 10 }}>
               <button className="btn btn-ghost" style={{ border: "1px solid var(--border)" }} onClick={() => setImportModalOpen(true)}>
                <FileUp size={15} /> {t("products.import_btn")}
              </button>
              <button className="btn btn-primary" onClick={() => setAdding(!adding)}>
                <Plus size={15} /> {t("products.add")}
              </button>
            </div>
          )}
        </div>

        {adding && isWarehouse && (
          <div className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 14 }}>{t("products.new")}</h3>
            <form onSubmit={handleCreate} style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" }}>
              <div style={{ flex: "1 1 150px" }}>
                <label style={{ display: "block", fontSize: 11, color: "var(--text-muted)", marginBottom: 5 }}>{t("products.col_sku")}</label>
                <input className="input" placeholder={t("products.sku_ph")} value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} required />
              </div>
              <div style={{ flex: "1 1 150px" }}>
                <label style={{ display: "block", fontSize: 11, color: "var(--text-muted)", marginBottom: 5 }}>{t("products.price_tjs")}</label>
                <input className="input" type="number" placeholder="1500" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required style={{ width: "100%" }} />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="submit" className="btn btn-primary">{t("common.save")}</button>
                <button type="button" className="btn btn-ghost" onClick={() => setAdding(false)}>{t("common.cancel")}</button>
              </div>
            </form>
          </div>
        )}

        <div style={{ position: "relative", marginBottom: 16 }}>
          <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input className="input" style={{ paddingLeft: 36, width: "100%" }} placeholder={t("products.search")} value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "var(--text-secondary)", fontSize: 13, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => {
                setShowInactive(e.target.checked);
                setPage(1);
              }}
            />
            {t("products.show_only_inactive")}
          </label>
        </div>

        <div className="card" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
              <div className="spinner" />
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("products.col_sku")}</th>
                    <th style={{ textAlign: "right" }}>{t("products.col_price")}</th>
                    <th style={{ textAlign: "center" }}>{t("common.status")}</th>
                    {isWarehouse && <th style={{ textAlign: "center" }}>{t("common.actions")}</th>}
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <Fragment key={p.id}>
                      <tr 
                        style={{ cursor: "pointer", background: expandedRow === p.id ? "var(--bg-hover)" : "transparent", transition: "background 0.2s", opacity: p.is_active ? 1 : 0.55 }}
                        onClick={() => handleToggleExpand(p.id)}
                      >
                        <td style={{ fontWeight: 700, color: "var(--accent)", fontSize: 13 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            {expandedRow === p.id ? <ChevronDown size={14} color="var(--text-muted)" /> : <ChevronRight size={14} color="var(--text-muted)" />}
                            {p.sku}
                          </div>
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(Number(p.price))} TJS</td>
                        <td style={{ textAlign: "center" }}>
                          <span className={p.is_active ? "badge badge-delivered" : "badge badge-rejected"}>
                            {p.is_active ? t("products.active") : t("products.inactive")}
                          </span>
                        </td>
                        {isWarehouse && (
                          <td style={{ textAlign: "center" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                              {p.is_active && (
                                <button onClick={(e) => { e.stopPropagation(); setReceivingProduct(p); }} className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}>
                                  <PackageOpen size={14} />
                                </button>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPendingToggleProduct(p);
                                }}
                                className={p.is_active ? "btn btn-danger" : "btn btn-primary"}
                                style={{
                                  padding: "4px 12px",
                                  fontSize: 12,
                                  ...(p.is_active ? {} : { background: "var(--green)", color: "#fff" }),
                                }}
                              >
                                {p.is_active ? "X" : t("products.btn_restore")}
                              </button>
                              {!p.is_active && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setPendingDeleteProduct(p);
                                  }}
                                  className="btn btn-danger"
                                  style={{ padding: "4px 10px", fontSize: 12 }}
                                  title={t("products.btn_hard_delete")}
                                >
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </div>
                          </td>
                        )}
                      </tr>
                      {expandedRow === p.id && (
                        <tr style={{ background: "var(--bg-hover)" }}>
                          <td colSpan={isWarehouse ? 4 : 3} style={{ padding: 0 }}>
                            <div style={{ padding: "16px 20px 24px 38px", borderTop: "1px dashed rgba(139,143,168,0.2)" }}>
                              <h4 style={{ fontSize: 12, textTransform: "uppercase", color: "var(--text-secondary)", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
                                <StoreIcon size={14} /> {t("products.availability")}
                              </h4>
                              {inventoryLoaders[p.id] ? (
                                <div className="spinner" style={{ width: 14, height: 14 }} />
                              ) : (
                                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                                  {inventoryCache[p.id]?.map((inv) => (
                                    <div key={inv.store_id} style={{ background: "var(--bg-card)", border: "1px solid var(--border)", padding: "10px 16px", borderRadius: 12, display: "flex", alignItems: "center", gap: 12, minWidth: 200 }}>
                                      <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(108,99,255,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        <StoreIcon size={16} color="var(--accent)" />
                                      </div>
                                      <div>
                                        <div style={{ fontSize: 13, fontWeight: 600 }}>{inv.store_name}</div>
                                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{inv.quantity} шт</div>
                                      </div>
                                      <div style={{ marginLeft: "auto" }}>
                                        {isWarehouse && inv.quantity > 0 && !inv.is_display && stores.find(s => s.id === inv.store_id)?.store_type === "warehouse" && (
                                          <button className="btn-sample-action" onClick={() => { setDispatchProduct(p); setIsDispatchModalOpen(true); }}>
                                            <PackageOpen size={14} />
                                          </button>
                                        )}
                                        {isSeller && inv.quantity > 0 && !inv.is_display && stores.find(s => s.id === inv.store_id)?.store_type === "warehouse" && (
                                          <button className="btn-sample-action" style={{ color: "var(--green)", borderColor: "var(--green)" }} onClick={() => { setOrderItem({ ...inv, product_id: p.id, sku: p.sku }); setIsOrderModalOpen(true); }}>
                                            <ShoppingCart size={14} />
                                          </button>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {!loading && totalPages > 1 && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 24 }}>
            <button className="btn btn-ghost" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>← {t("common.back")}</button>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{page} / {totalPages}</div>
            <button className="btn btn-ghost" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>{t("common.next")} →</button>
          </div>
        )}
      </main>

      {mounted && receivingProduct && createPortal((
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 400 }}>
            <h3 style={{ marginBottom: 8 }}>{t("products.receive_title")}</h3>
            <p style={{ marginBottom: 20, fontSize: 14, color: "var(--text-secondary)" }}>{receivingProduct.sku}</p>
            <form onSubmit={handleReceiveStock}>
              <input type="number" min="1" className="input" style={{ width: "100%", marginBottom: 20 }} value={receiveQty} onChange={e => setReceiveQty(e.target.value)} autoFocus required />
              <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
                <button type="button" className="btn btn-ghost" onClick={() => setReceivingProduct(null)}>{t("common.cancel")}</button>
                <button type="submit" className="btn btn-primary">{t("common.save")}</button>
              </div>
            </form>
          </div>
        </div>
      ), document.body)}

      {mounted && isOrderModalOpen && createPortal((
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 400 }}>
            <h3 style={{ marginBottom: 8, color: "var(--green)", display: "flex", alignItems: "center", gap: 10 }}>
              <ShoppingCart size={22} /> {t("products.action_order") || "Заказать"}
            </h3>
            <p style={{ marginBottom: 20, fontSize: 14, color: "var(--text-secondary)" }}>{orderItem?.sku}</p>
            <input type="number" min="1" max={orderItem?.quantity} className="input" style={{ width: "100%", marginBottom: 20 }} value={dispatchQty} onChange={e => setDispatchQty(e.target.value)} autoFocus required />
            <div style={{ display: "flex", gap: 12 }}>
              <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setIsOrderModalOpen(false)}>{t("common.cancel")}</button>
              <button className="btn btn-primary" style={{ flex: 1, background: "var(--green)" }} onClick={handleQuickOrder}>{t("common.confirm")}</button>
            </div>
          </div>
        </div>
      ), document.body)}

      {mounted && isDispatchModalOpen && createPortal((
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 400 }}>
            <h3 style={{ marginBottom: 8 }}>{t("inventory.dispatch_modal_title")}</h3>
            <p style={{ marginBottom: 20 }}>{dispatchProduct?.sku}</p>
            <div style={{ marginBottom: 16 }}>
              <select className="input" style={{ width: "100%" }} value={targetStoreId} onChange={(e) => setTargetStoreId(e.target.value)}>
                <option value="">---</option>
                {stores.filter(s => s.store_type !== "warehouse").map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <input type="number" className="input" style={{ width: "100%", marginBottom: 24 }} value={dispatchQty} onChange={(e) => setDispatchQty(e.target.value)} min={1} />
            <div style={{ display: "flex", gap: 12 }}>
               <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setIsDispatchModalOpen(false)}>{t("common.cancel")}</button>
               <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleDispatch}>{t("common.confirm")}</button>
            </div>
          </div>
        </div>
      ), document.body)}

      {mounted && importModalOpen && createPortal((
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 850, maxHeight: "90vh", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
              <h3>{t("products.import_title")}</h3>
              <button onClick={() => setImportModalOpen(false)} style={{ background: "transparent", border: "none" }}><X size={24} /></button>
            </div>
            <div style={{ overflowY: "auto", flex: 1 }}>
              {importData.length === 0 ? (
                <div style={{ border: "2px dashed var(--border)", padding: 40, textAlign: "center" }}>
                  <FileUp size={48} color="var(--text-muted)" style={{ marginBottom: 16 }} />
                  <label className="btn btn-primary" style={{ cursor: "pointer" }}>
                    {t("products.import_select_file")}
                    <input type="file" accept=".xlsx, .xls" onChange={handleFileUpload} style={{ display: "none" }} />
                  </label>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("products.col_sku")}</th>
                        <th style={{ textAlign: "center" }}>{t("products.import_col_total")}</th>
                        <th style={{ textAlign: "right" }}>{t("products.import_col_price")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importData.map((d, i) => (
                        <tr key={i}>
                          <td>{d.sku}</td>
                          <td style={{ textAlign: "center" }}>{d.total}</td>
                          <td style={{ textAlign: "right" }}>{fmt(d.price)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 20 }}>
              <button className="btn btn-ghost" onClick={() => setImportModalOpen(false)}>{t("common.cancel")}</button>
              {importData.length > 0 && <button className="btn btn-primary" onClick={handleProcessImport} disabled={importing}>{importing ? "..." : t("products.import_process")}</button>}
            </div>
          </div>
        </div>
      ), document.body)}

      {mounted && pendingToggleProduct && createPortal((
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 420 }}>
            <h3 style={{ marginBottom: 8 }}>
              {pendingToggleProduct.is_active
                ? t("products.toggle_deactivate_title")
                : t("products.toggle_activate_title")}
            </h3>
            <p style={{ marginBottom: 20, fontSize: 14, color: "var(--text-secondary)" }}>
              {pendingToggleProduct.is_active
                ? t("products.toggle_deactivate_confirm", { sku: pendingToggleProduct.sku })
                : t("products.toggle_activate_confirm", { sku: pendingToggleProduct.sku })}
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                className="btn btn-ghost"
                onClick={() => setPendingToggleProduct(null)}
                disabled={toggling}
              >
                {t("common.cancel")}
              </button>
              <button
                className={pendingToggleProduct.is_active ? "btn btn-danger" : "btn btn-success"}
                onClick={() => handleToggleActive(pendingToggleProduct)}
                disabled={toggling}
                style={!pendingToggleProduct.is_active ? { background: "var(--green)", color: "#fff" } : undefined}
              >
                {toggling ? "..." : t("common.confirm")}
              </button>
            </div>
          </div>
        </div>
      ), document.body)}

      {mounted && pendingDeleteProduct && createPortal((
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 460 }}>
            <h3 style={{ marginBottom: 8 }}>{t("products.hard_delete_title")}</h3>
            <p style={{ marginBottom: 20, fontSize: 14, color: "var(--text-secondary)" }}>
              {t("products.hard_delete_confirm", { sku: pendingDeleteProduct.sku })}
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                className="btn btn-ghost"
                onClick={() => setPendingDeleteProduct(null)}
                disabled={deleting}
              >
                {t("common.cancel")}
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleHardDelete(pendingDeleteProduct)}
                disabled={deleting}
              >
                {deleting ? "..." : t("products.btn_hard_delete")}
              </button>
            </div>
          </div>
        </div>
      ), document.body)}
    </div>
  );
}
