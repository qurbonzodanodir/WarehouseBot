"use client";
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { api, Supplier, SupplierDetail, Product } from "@/lib/api";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { createPortal } from "react-dom";
import {
  TruckIcon, Plus, AlertCircle, ChevronRight, ChevronDown,
  Receipt, Wallet, X, History, ArrowDownCircle, ArrowUpCircle,
  Search, Trash2, ShoppingCart
} from "lucide-react";

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

interface CartItem {
  product: Product;
  quantity: number;
}

export default function SuppliersPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();

  const [user, setUser] = useState<any>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, SupplierDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<number, boolean>>({});

  // Add supplier modal
  const [addSupplierOpen, setAddSupplierOpen] = useState(false);
  const [supplierForm, setSupplierForm] = useState({ name: "", contact_info: "", address: "", notes: "" });
  const [savingSupplier, setSavingSupplier] = useState(false);

  // Invoice (shipment) modal — product cart
  const [invoiceModal, setInvoiceModal] = useState<Supplier | null>(null);
  const [invoiceNotes, setInvoiceNotes] = useState("");
  const [savingInvoice, setSavingInvoice] = useState(false);
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [productSearch, setProductSearch] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);

  // Payment modal
  const [paymentModal, setPaymentModal] = useState<Supplier | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentNotes, setPaymentNotes] = useState("");
  const [savingPayment, setSavingPayment] = useState(false);

  const fetchSuppliers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getSuppliers();
      setSuppliers(data);
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    const usr = getStoredUser();
    setUser(usr);
    if (!isAuthenticated()) { router.push("/login"); return; }
    fetchSuppliers();
    setMounted(true);
  }, [router, fetchSuppliers]);

  const handleExpand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (!detailCache[id]) {
      setDetailLoading(prev => ({ ...prev, [id]: true }));
      try {
        const detail = await api.getSupplierDetail(id);
        setDetailCache(prev => ({ ...prev, [id]: detail }));
      } catch (e: any) {
        showToast(e.message, "error");
      } finally {
        setDetailLoading(prev => ({ ...prev, [id]: false }));
      }
    }
  };

  const handleCreateSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supplierForm.name.trim()) return;
    setSavingSupplier(true);
    try {
      await api.createSupplier(supplierForm);
      setAddSupplierOpen(false);
      setSupplierForm({ name: "", contact_info: "", address: "", notes: "" });
      await fetchSuppliers();
      showToast(t("suppliers.created_success"), "success");
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setSavingSupplier(false);
    }
  };

  const openInvoiceModal = async (s: Supplier) => {
    setInvoiceModal(s);
    setCart([]);
    setInvoiceNotes("");
    setProductSearch("");
    if (allProducts.length === 0) {
      try {
        const resp = await api.getProducts({ page_size: 1000 });
        setAllProducts(resp.items ?? []);
      } catch (e: any) {
        showToast(e.message, "error");
      }
    }
  };

  const addToCart = (product: Product) => {
    setCart(prev => {
      const existing = prev.find(c => c.product.id === product.id);
      if (existing) {
        return prev.map(c => c.product.id === product.id ? { ...c, quantity: c.quantity + 1 } : c);
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const updateCartQty = (productId: number, qty: number) => {
    if (qty <= 0) {
      setCart(prev => prev.filter(c => c.product.id !== productId));
    } else {
      setCart(prev => prev.map(c => c.product.id === productId ? { ...c, quantity: qty } : c));
    }
  };

  const cartTotal = cart.reduce((acc, c) => acc + Number(c.product.price) * c.quantity, 0);

  const handleAddInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invoiceModal || cart.length === 0) return;
    setSavingInvoice(true);
    try {
      await api.addSupplierInvoice(invoiceModal.id, {
        items: cart.map(c => ({ product_id: c.product.id, quantity: c.quantity })),
        notes: invoiceNotes || null,
      });
      setInvoiceModal(null);
      setCart([]);
      setInvoiceNotes("");
      setDetailCache(prev => { const n = { ...prev }; delete n[invoiceModal.id]; return n; });
      await fetchSuppliers();
      showToast(t("suppliers.invoice_added"), "success");
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setSavingInvoice(false);
    }
  };

  const filteredProducts = useMemo(() =>
    allProducts.filter(p =>
      p.sku.toLowerCase().includes(productSearch.toLowerCase())
    ),
  [allProducts, productSearch]);


  const handleAddPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentModal) return;
    const amount = parseFloat(paymentAmount);
    if (isNaN(amount) || amount <= 0) { showToast(t("finance.err_zero"), "error"); return; }
    setSavingPayment(true);
    try {
      await api.addSupplierPayment(paymentModal.id, { amount, notes: paymentNotes || null });
      setPaymentModal(null);
      setPaymentAmount(""); setPaymentNotes("");
      setDetailCache(prev => { const n = { ...prev }; delete n[paymentModal.id]; return n; });
      await fetchSuppliers();
      showToast(t("suppliers.payment_success"), "success");
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setSavingPayment(false);
    }
  };

  const totalDebt = suppliers.reduce((acc, s) => acc + Number(s.current_debt), 0);

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        {/* Header */}
        <div className="page-header" style={{ marginBottom: 32 }}>
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <TruckIcon size={28} style={{ color: "var(--accent)" }} />
              {t("suppliers.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 14, marginTop: 4 }}>
              {t("suppliers.subtitle")}
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => setAddSupplierOpen(true)}>
            <Plus size={15} /> {t("suppliers.add_btn")}
          </button>
        </div>

        {/* KPIs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 28 }}>
          <div className="card" style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: "var(--accent-muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <TruckIcon size={22} style={{ color: "var(--accent)" }} />
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 2 }}>{t("suppliers.total_suppliers")}</div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{suppliers.length}</div>
            </div>
          </div>
          <div className="card" style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: "rgba(239,68,68,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <AlertCircle size={22} style={{ color: "#ef4444" }} />
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 2 }}>{t("suppliers.total_debt")}</div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{fmt(totalDebt)} <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>TJS</span></div>
            </div>
          </div>
        </div>

        {/* Suppliers Table */}
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><div className="spinner" /></div>
        ) : suppliers.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 60 }}>
            <TruckIcon size={48} style={{ color: "var(--text-muted)", margin: "0 auto 16px" }} />
            <p style={{ color: "var(--text-secondary)", fontSize: 16 }}>{t("suppliers.empty")}</p>
          </div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("suppliers.col_name")}</th>
                    <th>{t("suppliers.col_contact")}</th>
                    <th style={{ textAlign: "right" }}>{t("suppliers.col_debt")}</th>
                    <th style={{ textAlign: "center" }}>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map(s => (
                    <React.Fragment key={s.id}>
                      <tr
                        style={{ cursor: "pointer", background: expandedId === s.id ? "var(--bg-hover)" : "transparent" }}
                        onClick={() => handleExpand(s.id)}
                      >
                        <td data-label={t("suppliers.col_name")}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            {expandedId === s.id ? <ChevronDown size={14} color="var(--text-muted)" /> : <ChevronRight size={14} color="var(--text-muted)" />}
                            <span style={{ fontWeight: 600 }}>{s.name}</span>
                          </div>
                        </td>
                        <td data-label={t("suppliers.col_contact")} style={{ color: "var(--text-secondary)", fontSize: 13 }}>{s.contact_info || "—"}</td>
                        <td data-label={t("suppliers.col_debt")} style={{ textAlign: "right" }}>
                          <span style={{ fontWeight: 700, color: Number(s.current_debt) > 0 ? "#ef4444" : "var(--text-secondary)" }}>
                            {fmt(Number(s.current_debt))} TJS
                          </span>
                        </td>
                        <td data-label={t("common.actions")} style={{ textAlign: "center" }}>
                          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }} onClick={e => e.stopPropagation()}>
                            <button
                              className="btn btn-danger"
                              style={{ padding: "4px 10px", fontSize: 12, display: "flex", gap: 4, alignItems: "center" }}
                              onClick={() => { openInvoiceModal(s); }}
                            >
                              <ArrowDownCircle size={13} /> {t("suppliers.btn_invoice")}
                            </button>
                            {Number(s.current_debt) > 0 && (
                              <button
                                className="btn btn-primary"
                                style={{ padding: "4px 10px", fontSize: 12, background: "var(--green)", display: "flex", gap: 4, alignItems: "center" }}
                                onClick={() => { setPaymentModal(s); setPaymentAmount(""); setPaymentNotes(""); }}
                              >
                                <ArrowUpCircle size={13} /> {t("suppliers.btn_pay")}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Expanded Detail Row */}
                      {expandedId === s.id && (
                        <tr className="expanded-row-mobile" style={{ background: "var(--bg-hover)" }}>
                          <td colSpan={4} style={{ padding: 0, display: "block" }}>
                            <div style={{ padding: "16px", borderTop: "1px dashed rgba(139,143,168,0.2)" }}>
                              {detailLoading[s.id] ? (
                                <div className="spinner" style={{ width: 16, height: 16 }} />
                              ) : detailCache[s.id] ? (
                                <div className="kpi-grid" style={{ gap: 24 }}>
                                  {/* Invoices */}
                                  <div>
                                    <h4 style={{ fontSize: 12, textTransform: "uppercase", color: "var(--text-secondary)", marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                                      <Receipt size={13} /> {t("suppliers.invoices_title")}
                                    </h4>
                                    {detailCache[s.id].invoices.length === 0 ? (
                                      <p style={{ color: "var(--text-muted)", fontSize: 13 }}>{t("suppliers.no_invoices")}</p>
                                    ) : detailCache[s.id].invoices.slice(0, 5).map(inv => {
                                      const totalQty = inv.items?.reduce((acc, curr) => acc + curr.quantity, 0) || 0;
                                      return (
                                        <div key={inv.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)", fontSize: 13, alignItems: "center" }}>
                                          <span style={{ color: "var(--text-secondary)" }}>{new Date(inv.created_at).toLocaleDateString("ru-RU")}</span>
                                          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                                            <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{totalQty > 0 ? `${totalQty} шт.` : "0 шт."}</span>
                                            <span style={{ color: "#ef4444", fontWeight: 600, minWidth: 80, textAlign: "right" }}>+{fmt(Number(inv.total_amount))} TJS</span>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                  {/* Payments */}
                                  <div>
                                    <h4 style={{ fontSize: 12, textTransform: "uppercase", color: "var(--text-secondary)", marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                                      <Wallet size={13} /> {t("suppliers.payments_title")}
                                    </h4>
                                    {detailCache[s.id].payments.length === 0 ? (
                                      <p style={{ color: "var(--text-muted)", fontSize: 13 }}>{t("suppliers.no_payments")}</p>
                                    ) : detailCache[s.id].payments.slice(0, 5).map(pay => (
                                      <div key={pay.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                                        <span style={{ color: "var(--text-secondary)" }}>{new Date(pay.created_at).toLocaleDateString("ru-RU")}</span>
                                        <span style={{ color: "var(--green)", fontWeight: 600 }}>−{fmt(Number(pay.amount))} TJS</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Add Supplier Modal */}
      {mounted && addSupplierOpen && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 480 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
              <h3>{t("suppliers.add_title")}</h3>
              <button onClick={() => setAddSupplierOpen(false)} style={{ background: "transparent", border: "none" }}><X size={22} /></button>
            </div>
            <form onSubmit={handleCreateSupplier} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("suppliers.col_name")} *</label>
                <input className="input" style={{ width: "100%" }} value={supplierForm.name} onChange={e => setSupplierForm({ ...supplierForm, name: e.target.value })} required autoFocus />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("suppliers.col_contact")}</label>
                <input className="input" style={{ width: "100%" }} value={supplierForm.contact_info} onChange={e => setSupplierForm({ ...supplierForm, contact_info: e.target.value })} placeholder="+992..." />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("suppliers.col_address")}</label>
                <input className="input" style={{ width: "100%" }} value={supplierForm.address} onChange={e => setSupplierForm({ ...supplierForm, address: e.target.value })} />
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
                <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setAddSupplierOpen(false)}>{t("common.cancel")}</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={savingSupplier}>{savingSupplier ? "..." : t("common.save")}</button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}

      {/* Invoice Modal — Product Cart */}
      {mounted && invoiceModal && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 780, width: "95vw", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <h3 style={{ color: "#ef4444", display: "flex", alignItems: "center", gap: 8, margin: 0 }}>
                  <ArrowDownCircle size={20} /> {t("suppliers.invoice_title")}
                </h3>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{invoiceModal.name}</p>
              </div>
              <button onClick={() => setInvoiceModal(null)} style={{ background: "transparent", border: "none" }}><X size={22} /></button>
            </div>

            {/* Body: 2 columns */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, flex: 1, minHeight: 0, overflow: "hidden" }}>
              {/* LEFT: Product search */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, overflow: "hidden" }}>
                <div style={{ position: "relative" }}>
                  <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                  <input
                    className="input"
                    style={{ width: "100%", paddingLeft: 32, fontSize: 13 }}
                    placeholder="Поиск по SKU..."
                    value={productSearch}
                    onChange={e => setProductSearch(e.target.value)}
                    autoFocus
                  />
                </div>
                <div style={{ flex: 1, overflowY: "auto", borderRadius: 8, border: "1px solid var(--border)" }}>
                  {filteredProducts.length === 0 ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>Товары не найдены</div>
                  ) : filteredProducts.map(p => {
                    const inCart = cart.find(c => c.product.id === p.id);
                    return (
                      <div
                        key={p.id}
                        onClick={() => addToCart(p)}
                        style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "10px 14px", cursor: "pointer",
                          background: inCart ? "rgba(124,58,237,0.08)" : "transparent",
                          borderBottom: "1px solid var(--border)",
                          transition: "background 0.15s"
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{p.sku}</div>
                          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmt(Number(p.price))} TJS / шт.</div>
                        </div>
                        {inCart ? (
                          <span style={{ fontSize: 11, background: "var(--accent)", color: "#fff", borderRadius: 20, padding: "2px 8px" }}>{inCart.quantity} шт.</span>
                        ) : (
                          <Plus size={16} color="var(--text-muted)" />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* RIGHT: Cart */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, overflow: "hidden" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ShoppingCart size={16} style={{ color: "var(--accent)" }} />
                  <span style={{ fontWeight: 600, fontSize: 13 }}>Корзина ({cart.length})</span>
                </div>
                <div style={{ flex: 1, overflowY: "auto", borderRadius: 8, border: "1px solid var(--border)" }}>
                  {cart.length === 0 ? (
                    <div style={{ padding: 30, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>Выберите товары слева</div>
                  ) : cart.map(c => (
                    <div key={c.product.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderBottom: "1px solid var(--border)" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{c.product.sku}</div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmt(Number(c.product.price))} × {c.quantity} = <strong>{fmt(Number(c.product.price) * c.quantity)}</strong> TJS</div>
                      </div>
                      <input
                        type="number" min="1"
                        style={{ width: 60, padding: "4px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 13, textAlign: "center" }}
                        value={c.quantity}
                        onChange={e => updateCartQty(c.product.id, parseInt(e.target.value) || 0)}
                      />
                      <button onClick={() => updateCartQty(c.product.id, 0)} style={{ background: "transparent", border: "none", cursor: "pointer", color: "#ef4444" }}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                </div>
                {/* Total */}
                <div style={{ padding: "12px 14px", background: "var(--bg-hover)", borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Итого:</span>
                  <span style={{ fontSize: 18, fontWeight: 700, color: "#ef4444" }}>{fmt(cartTotal)} TJS</span>
                </div>
              </div>
            </div>

            {/* Footer */}
            <form onSubmit={handleAddInvoice} style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder={t("suppliers.notes_ph")}
                value={invoiceNotes}
                onChange={e => setInvoiceNotes(e.target.value)}
              />
              <button type="button" className="btn btn-ghost" onClick={() => setInvoiceModal(null)}>{t("common.cancel")}</button>
              <button
                type="submit"
                className="btn btn-danger"
                disabled={savingInvoice || cart.length === 0}
              >
                {savingInvoice ? "..." : `Отгрузить — ${fmt(cartTotal)} TJS`}
              </button>
            </form>
          </div>
        </div>,
        document.body
      )}

      {/* Payment Modal (debt decreases) */}
      {mounted && paymentModal && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 420 }}>
            <h3 style={{ marginBottom: 4, color: "var(--green)", display: "flex", alignItems: "center", gap: 8 }}>
              <ArrowUpCircle size={20} /> {t("suppliers.payment_title")}
            </h3>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>{paymentModal.name}</p>
            <p style={{ fontSize: 13, color: "#ef4444", marginBottom: 20 }}>
              {t("suppliers.current_debt")}: <strong>{fmt(Number(paymentModal.current_debt))} TJS</strong>
            </p>
            <form onSubmit={handleAddPayment} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("finance.amount")} (TJS) *</label>
                <input type="number" min="0" step="0.01" max={Number(paymentModal.current_debt)} className="input" style={{ width: "100%" }} value={paymentAmount} onChange={e => setPaymentAmount(e.target.value)} autoFocus required />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("suppliers.notes")}</label>
                <input className="input" style={{ width: "100%" }} value={paymentNotes} onChange={e => setPaymentNotes(e.target.value)} placeholder={t("suppliers.notes_ph")} />
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setPaymentModal(null)}>{t("common.cancel")}</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: "var(--green)" }} disabled={savingPayment}>{savingPayment ? "..." : t("suppliers.btn_pay")}</button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
