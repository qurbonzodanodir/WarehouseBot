"use client";
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { isAuthenticated } from "@/lib/auth";
import { api, ProductPicker, Supplier, SupplierDetail } from "@/lib/api";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { createPortal } from "react-dom";
import {
  Truck, Plus, AlertCircle, ChevronRight, ChevronDown,
  Receipt, Wallet, X, History, ArrowDownCircle, ArrowUpCircle,
  Search, Trash2, ShoppingCart
} from "lucide-react";

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

interface CartItem {
  product: ProductPicker;
  quantity: number;
}

export default function SuppliersPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();

  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});
  const [openRecvHistory, setOpenRecvHistory] = useState(false);
  const [openPayHistory, setOpenPayHistory] = useState(false);
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
  const [productOptions, setProductOptions] = useState<ProductPicker[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productSearch, setProductSearch] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);

  // Payment modal
  const [paymentModal, setPaymentModal] = useState<Supplier | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentNotes, setPaymentNotes] = useState("");
  const [savingPayment, setSavingPayment] = useState(false);

  // Return modal
  const [returnModal, setReturnModal] = useState<Supplier | null>(null);
  const [returnNotes, setReturnNotes] = useState("");
  const [savingReturn, setSavingReturn] = useState(false);

  // Partner goods received / payable side
  const [receiptModal, setReceiptModal] = useState<Supplier | null>(null);
  const [receiptNotes, setReceiptNotes] = useState("");
  const [savingReceipt, setSavingReceipt] = useState(false);
  const [payoutModal, setPayoutModal] = useState<Supplier | null>(null);
  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutNotes, setPayoutNotes] = useState("");
  const [savingPayout, setSavingPayout] = useState(false);
  const [outgoingReturnModal, setOutgoingReturnModal] = useState<Supplier | null>(null);
  const [outgoingReturnNotes, setOutgoingReturnNotes] = useState("");
  const [savingOutgoingReturn, setSavingOutgoingReturn] = useState(false);

  const fetchSuppliers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getSuppliers();
      setSuppliers(data);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    void fetchSuppliers();
    setMounted(true);
  }, [router, fetchSuppliers]);

  useEffect(() => {
    setOpenRecvHistory(false);
    setOpenPayHistory(false);
  }, [expandedId]);

  const handleExpand = async (id: number) => {
    setExpandedId(id);
    if (!detailCache[id]) {
      setDetailLoading(prev => ({ ...prev, [id]: true }));
      try {
        const detail = await api.getSupplierDetail(id);
        setDetailCache(prev => ({ ...prev, [id]: detail }));
      } catch (error) {
        showToast(getErrorMessage(error, t("common.error")), "error");
      } finally {
        setDetailLoading(prev => ({ ...prev, [id]: false }));
      }
    }
  };

  useEffect(() => {
    if (expandedId == null && suppliers.length > 0) {
      void handleExpand(suppliers[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suppliers, expandedId]);

  useEffect(() => {
    if (expandedId != null && !detailCache[expandedId] && !detailLoading[expandedId]) {
      void handleExpand(expandedId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandedId, detailCache, detailLoading]);

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
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingSupplier(false);
    }
  };

  const openInvoiceModal = (s: Supplier) => {
    setInvoiceModal(s);
    setCart([]);
    setInvoiceNotes("");
    setProductSearch("");
  };

  const openReturnModal = async (s: Supplier) => {
    setReturnModal(s);
    setCart([]);
    setReturnNotes("");
    setProductSearch("");
    
    // Ensure we have details to filter products by previous shipments
    if (!detailCache[s.id]) {
      setDetailLoading(prev => ({ ...prev, [s.id]: true }));
      try {
        const detail = await api.getSupplierDetail(s.id);
        setDetailCache(prev => ({ ...prev, [s.id]: detail }));
      } catch (error) {
        showToast(getErrorMessage(error, t("common.error")), "error");
      } finally {
        setDetailLoading(prev => ({ ...prev, [s.id]: false }));
      }
    }

  };

  const openReceiptModal = (s: Supplier) => {
    setReceiptModal(s);
    setCart([]);
    setReceiptNotes("");
    setProductSearch("");
  };

  const openOutgoingReturnModal = async (s: Supplier) => {
    setOutgoingReturnModal(s);
    setCart([]);
    setOutgoingReturnNotes("");
    setProductSearch("");

    if (!detailCache[s.id]) {
      setDetailLoading(prev => ({ ...prev, [s.id]: true }));
      try {
        const detail = await api.getSupplierDetail(s.id);
        setDetailCache(prev => ({ ...prev, [s.id]: detail }));
      } catch (error) {
        showToast(getErrorMessage(error, t("common.error")), "error");
      } finally {
        setDetailLoading(prev => ({ ...prev, [s.id]: false }));
      }
    }
  };

  const addToCart = (product: ProductPicker) => {
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
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingInvoice(false);
    }
  };

  const filteredProducts = useMemo(() => {
    let list = productOptions;
    
    // If it's a return, show ONLY products that were previously sent to this supplier
    if (returnModal && detailCache[returnModal.id]) {
      const detail = detailCache[returnModal.id];
      const invoicedProductIds = new Set<number>();
      detail.invoices.forEach(inv => {
        inv.items?.forEach(item => {
          invoicedProductIds.add(item.product_id);
        });
      });
      list = list.filter(p => invoicedProductIds.has(p.id));
    }

    if (outgoingReturnModal && detailCache[outgoingReturnModal.id]) {
      const detail = detailCache[outgoingReturnModal.id];
      const receivedProductIds = new Set<number>();
      detail.receipts?.forEach(receipt => {
        receipt.items?.forEach(item => {
          receivedProductIds.add(item.product_id);
        });
      });
      list = list.filter(p => receivedProductIds.has(p.id));
    }

    return list.filter(p =>
      p.sku.toLowerCase().includes(productSearch.toLowerCase())
    );
  }, [detailCache, outgoingReturnModal, productOptions, productSearch, returnModal]);

  // Max returnable quantity per product (total invoiced - total already returned)
  const returnableQtyMap = useMemo<Record<number, number>>(() => {
    if (!returnModal || !detailCache[returnModal.id]) return {};
    const detail = detailCache[returnModal.id];
    const map: Record<number, number> = {};
    // Sum up all invoiced quantities
    detail.invoices.forEach(inv => {
      inv.items?.forEach(item => {
        map[item.product_id] = (map[item.product_id] || 0) + item.quantity;
      });
    });
    // Subtract already returned quantities
    detail.returns?.forEach(ret => {
      ret.items?.forEach(item => {
        map[item.product_id] = (map[item.product_id] || 0) - item.quantity;
      });
    });
    // Remove entries where nothing left to return
    return Object.fromEntries(Object.entries(map).filter(([, qty]) => qty > 0));
  }, [returnModal, detailCache]);

  const returnableToPartnerQtyMap = useMemo<Record<number, number>>(() => {
    if (!outgoingReturnModal || !detailCache[outgoingReturnModal.id]) return {};
    const detail = detailCache[outgoingReturnModal.id];
    const map: Record<number, number> = {};
    detail.receipts?.forEach(receipt => {
      receipt.items?.forEach(item => {
        map[item.product_id] = (map[item.product_id] || 0) + item.quantity;
      });
    });
    detail.outgoing_returns?.forEach(ret => {
      ret.items?.forEach(item => {
        map[item.product_id] = (map[item.product_id] || 0) - item.quantity;
      });
    });
    return Object.fromEntries(Object.entries(map).filter(([, qty]) => qty > 0));
  }, [outgoingReturnModal, detailCache]);

  useEffect(() => {
    const activeModal = invoiceModal ?? returnModal ?? receiptModal ?? outgoingReturnModal;
    if (!activeModal) {
      setProductOptions([]);
      return;
    }
    if (returnModal && !detailCache[returnModal.id]) {
      setProductOptions([]);
      return;
    }
    if (outgoingReturnModal && !detailCache[outgoingReturnModal.id]) {
      setProductOptions([]);
      return;
    }

    let isActive = true;
    const productIds = returnModal
      ? Object.keys(returnableQtyMap).map(Number)
      : outgoingReturnModal
        ? Object.keys(returnableToPartnerQtyMap).map(Number)
        : undefined;
    if (returnModal && productIds && productIds.length === 0) {
      setProductOptions([]);
      return;
    }
    if (outgoingReturnModal && productIds && productIds.length === 0) {
      setProductOptions([]);
      return;
    }

    setProductsLoading(true);
    api.getProductOptions({
      search: productSearch,
      productIds,
      limit: 50,
    })
      .then((items) => {
        if (isActive) {
          setProductOptions(items);
        }
      })
      .catch((error) => {
        if (isActive) {
          showToast(getErrorMessage(error, t("common.error")), "error");
        }
      })
      .finally(() => {
        if (isActive) {
          setProductsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [detailCache, invoiceModal, outgoingReturnModal, productSearch, receiptModal, returnModal, returnableQtyMap, returnableToPartnerQtyMap, showToast, t]);

  // Override addToCart for return: don't exceed max
  const addToReturnCart = (product: ProductPicker) => {
    const max = returnableQtyMap[product.id] ?? 0;
    if (max <= 0) return;
    setCart(prev => {
      const existing = prev.find(c => c.product.id === product.id);
      if (existing) {
        const newQty = Math.min(existing.quantity + 1, max);
        return prev.map(c => c.product.id === product.id ? { ...c, quantity: newQty } : c);
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const updateReturnCartQty = (productId: number, qty: number) => {
    const max = returnableQtyMap[productId] ?? 0;
    const clamped = Math.min(Math.max(qty, 0), max);
    if (clamped <= 0) {
      setCart(prev => prev.filter(c => c.product.id !== productId));
    } else {
      setCart(prev => prev.map(c => c.product.id === productId ? { ...c, quantity: clamped } : c));
    }
  };

  const addToOutgoingReturnCart = (product: ProductPicker) => {
    const max = returnableToPartnerQtyMap[product.id] ?? 0;
    if (max <= 0) return;
    setCart(prev => {
      const existing = prev.find(c => c.product.id === product.id);
      if (existing) {
        const newQty = Math.min(existing.quantity + 1, max);
        return prev.map(c => c.product.id === product.id ? { ...c, quantity: newQty } : c);
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const updateOutgoingReturnCartQty = (productId: number, qty: number) => {
    const max = returnableToPartnerQtyMap[productId] ?? 0;
    const clamped = Math.min(Math.max(qty, 0), max);
    if (clamped <= 0) {
      setCart(prev => prev.filter(c => c.product.id !== productId));
    } else {
      setCart(prev => prev.map(c => c.product.id === productId ? { ...c, quantity: clamped } : c));
    }
  };


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
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingPayment(false);
    }
  };

  const handleCreateReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!returnModal || cart.length === 0) return;
    setSavingReturn(true);
    try {
      await api.addSupplierReturn(returnModal.id, {
        items: cart.map(c => ({ product_id: c.product.id, quantity: c.quantity })),
        notes: returnNotes || null,
      });
      setReturnModal(null);
      setCart([]);
      setReturnNotes("");
      setDetailCache(prev => { const n = { ...prev }; delete n[returnModal.id]; return n; });
      await fetchSuppliers();
      showToast(t("suppliers.return_success"), "success");
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingReturn(false);
    }
  };

  const handleAddReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!receiptModal || cart.length === 0) return;
    setSavingReceipt(true);
    try {
      await api.addSupplierReceipt(receiptModal.id, {
        items: cart.map(c => ({ product_id: c.product.id, quantity: c.quantity })),
        notes: receiptNotes || null,
      });
      setReceiptModal(null);
      setCart([]);
      setReceiptNotes("");
      setDetailCache(prev => { const n = { ...prev }; delete n[receiptModal.id]; return n; });
      await fetchSuppliers();
      showToast(t("suppliers.receipt_success"), "success");
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingReceipt(false);
    }
  };

  const handleAddPayout = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!payoutModal) return;
    const amount = parseFloat(payoutAmount);
    if (isNaN(amount) || amount <= 0) { showToast(t("finance.err_zero"), "error"); return; }
    setSavingPayout(true);
    try {
      await api.addSupplierPayout(payoutModal.id, { amount, notes: payoutNotes || null });
      setPayoutModal(null);
      setPayoutAmount("");
      setPayoutNotes("");
      setDetailCache(prev => { const n = { ...prev }; delete n[payoutModal.id]; return n; });
      await fetchSuppliers();
      showToast(t("suppliers.payout_success"), "success");
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingPayout(false);
    }
  };

  const handleCreateOutgoingReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!outgoingReturnModal || cart.length === 0) return;
    setSavingOutgoingReturn(true);
    try {
      await api.addSupplierOutgoingReturn(outgoingReturnModal.id, {
        items: cart.map(c => ({ product_id: c.product.id, quantity: c.quantity })),
        notes: outgoingReturnNotes || null,
      });
      setOutgoingReturnModal(null);
      setCart([]);
      setOutgoingReturnNotes("");
      setDetailCache(prev => { const n = { ...prev }; delete n[outgoingReturnModal.id]; return n; });
      await fetchSuppliers();
      showToast(t("suppliers.return_to_partner_success"), "success");
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setSavingOutgoingReturn(false);
    }
  };

  const totalDebt = suppliers.reduce((acc, s) => acc + Number(s.current_debt), 0);
  const totalPayable = suppliers.reduce((acc, s) => acc + Number(s.payable_debt || 0), 0);
  const netBalance = suppliers.reduce((acc, s) => acc + Number(s.net_balance || 0), 0);
  const selectedSupplier = suppliers.find((s) => s.id === expandedId) || null;
  const selectedDetail = expandedId ? detailCache[expandedId] : null;

  const toggleHistory = (key: string) => {
    setExpandedHistory(prev => ({ ...prev, [key]: !prev[key] }));
  };
  const renderLineItems = (items?: { sku: string; quantity: number; price_per_unit: number; line_total: number }[]) => {
    if (!items || items.length === 0) return null;
    return (
      <div className="partner-history-items">
        {items.map((item, index) => (
          <div key={`${item.sku}-${index}`} className="partner-history-item">
            <div>
              <div style={{ fontWeight: 650 }}>{item.sku}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
                {item.quantity} шт. × {fmt(Number(item.price_per_unit))} TJS
              </div>
            </div>
            <strong>{fmt(Number(item.line_total))} TJS</strong>
          </div>
        ))}
      </div>
    );
  };

  type TimelineRow = {
    key: string;
    date: string;
    label: string;
    badge: string;
    qty?: string;
    amount: number;
    tone: "give" | "take";
    items?: { sku: string; quantity: number; price_per_unit: number; line_total: number }[];
  };

  const buildReceivableTimeline = (detail: SupplierDetail): TimelineRow[] => {
    const rows: (TimelineRow & { ts: number })[] = [];
    for (const inv of detail.invoices || []) {
      const totalQty = inv.items?.reduce((acc, curr) => acc + curr.quantity, 0) || 0;
      rows.push({
        key: `invoice-${inv.id}`,
        date: new Date(inv.created_at).toLocaleDateString("ru-RU"),
        label: t("suppliers.invoices_title"),
        qty: `${totalQty} шт.`,
        amount: Number(inv.total_amount),
        badge: "Отдали товар",
        tone: "give",
        items: inv.items,
        ts: new Date(inv.created_at).getTime(),
      });
    }
    for (const pay of detail.payments || []) {
      const note = (pay.notes || "").toLowerCase();
      const badge = note.includes("закрыт") ? "Закрытие долга" : "Оплата от партнёра";
      rows.push({
        key: `payment-${pay.id}`,
        date: new Date(pay.created_at).toLocaleDateString("ru-RU"),
        label: t("suppliers.payments_title"),
        amount: -Number(pay.amount),
        badge,
        tone: "take",
        ts: new Date(pay.created_at).getTime(),
      });
    }
    for (const ret of detail.returns || []) {
      const totalQty = ret.items?.reduce((acc, curr) => acc + curr.quantity, 0) || 0;
      rows.push({
        key: `return-${ret.id}`,
        date: new Date(ret.created_at).toLocaleDateString("ru-RU"),
        label: t("suppliers.returns_title"),
        qty: `${totalQty} шт.`,
        amount: -Number(ret.total_amount),
        badge: "Возврат нам",
        tone: "take",
        items: ret.items,
        ts: new Date(ret.created_at).getTime(),
      });
    }
    return rows.sort((a, b) => b.ts - a.ts);
  };

  const buildPayableTimeline = (detail: SupplierDetail): TimelineRow[] => {
    const rows: (TimelineRow & { ts: number })[] = [];
    for (const receipt of detail.receipts || []) {
      const totalQty = receipt.items?.reduce((acc, curr) => acc + curr.quantity, 0) || 0;
      rows.push({
        key: `receipt-${receipt.id}`,
        date: new Date(receipt.created_at).toLocaleDateString("ru-RU"),
        label: t("suppliers.receipts_title"),
        qty: `${totalQty} шт.`,
        amount: Number(receipt.total_amount),
        badge: "Приняли товар",
        tone: "take",
        items: receipt.items,
        ts: new Date(receipt.created_at).getTime(),
      });
    }
    for (const payout of detail.payouts || []) {
      rows.push({
        key: `payout-${payout.id}`,
        date: new Date(payout.created_at).toLocaleDateString("ru-RU"),
        label: t("suppliers.payouts_title"),
        amount: -Number(payout.amount),
        badge: "Наша оплата",
        tone: "give",
        ts: new Date(payout.created_at).getTime(),
      });
    }
    for (const ret of detail.outgoing_returns || []) {
      const totalQty = ret.items?.reduce((acc, curr) => acc + curr.quantity, 0) || 0;
      rows.push({
        key: `outgoing-return-${ret.id}`,
        date: new Date(ret.created_at).toLocaleDateString("ru-RU"),
        label: t("suppliers.outgoing_returns_title"),
        qty: `${totalQty} шт.`,
        amount: -Number(ret.total_amount),
        badge: "Вернули партнёру",
        tone: "give",
        items: ret.items,
        ts: new Date(ret.created_at).getTime(),
      });
    }
    return rows.sort((a, b) => b.ts - a.ts);
  };

  const renderTimeline = (rows: TimelineRow[]) => {
    if (rows.length === 0) {
      return <p className="partner-history-empty" style={{ padding: "18px 8px", textAlign: "center" }}>{t("common.empty")}</p>;
    }
    return (
      <div className="partner-timeline">
        {rows.map((row) => {
          const open = !!expandedHistory[row.key];
          return (
            <div key={row.key} className="partner-tl-item">
              <button
                type="button"
                className={`partner-tl-main${row.items ? "" : " is-static"}`}
                onClick={() => row.items && toggleHistory(row.key)}
              >
                <span className="partner-tl-date">{row.date}</span>
                <div className="partner-tl-mid">
                  <div className="partner-tl-title">{row.badge}</div>
                  {row.qty ? <div className="partner-tl-sub">{row.qty}</div> : null}
                </div>
                <div className={`partner-tl-amount ${row.tone}`}>
                  {row.amount > 0 ? "+" : "−"}{fmt(Math.abs(row.amount))} TJS
                </div>
              </button>
              {open && renderLineItems(row.items)}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        {/* Header */}
        <div className="page-header" style={{ marginBottom: 32 }}>
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Truck size={32} style={{ color: "var(--accent)" }} />
              {t("suppliers.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginLeft: 44 }}>
              {t("suppliers.subtitle")}
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => setAddSupplierOpen(true)}>
            <Plus size={15} /> {t("suppliers.add_btn")}
          </button>
        </div>

        {/* KPIs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 28 }}>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <Truck size={24} style={{ color: "var(--accent)" }} />
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>{t("suppliers.total_suppliers")}</div>
            </div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{suppliers.length}</div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <AlertCircle size={24} style={{ color: "var(--green)" }} />
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>{t("suppliers.total_debt")}</div>
            </div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{fmt(totalDebt)} <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>TJS</span></div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <Wallet size={24} style={{ color: "var(--red)" }} />
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>{t("suppliers.total_payable")}</div>
            </div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{fmt(totalPayable)} <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>TJS</span></div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <History size={24} style={{ color: "var(--accent)" }} />
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>{t("suppliers.net_balance")}</div>
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: netBalance >= 0 ? "var(--green)" : "var(--red)" }}>{fmt(Math.abs(netBalance))} <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>TJS</span></div>
          </div>
        </div>

        {/* Partners split layout */}
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><div className="spinner" /></div>
        ) : suppliers.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 60 }}>
            <Truck size={48} style={{ color: "var(--text-muted)", margin: "0 auto 16px" }} />
            <p style={{ color: "var(--text-secondary)", fontSize: 16 }}>{t("suppliers.empty")}</p>
          </div>
        ) : (
          <div className="mobile-stack" style={{ display: "grid", gridTemplateColumns: "minmax(240px, 300px) 1fr", gap: 14, alignItems: "start" }}>
            <section className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)", fontSize: 13, fontWeight: 700 }}>
                {t("suppliers.col_name")}
              </div>
              {suppliers.map((s) => {
                const active = expandedId === s.id;
                const net = Number(s.net_balance || 0);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => void handleExpand(s.id)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      background: active ? "var(--bg-hover)" : "transparent",
                      color: "var(--text-primary)",
                      padding: "14px 16px",
                      cursor: "pointer",
                      display: "flex",
                      gap: 12,
                      alignItems: "center",
                    }}
                  >
                    <div style={{
                      width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                      background: "var(--accent-muted)", color: "var(--accent)",
                      display: "grid", placeItems: "center", fontWeight: 700,
                    }}>
                      {s.name.charAt(0).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>{s.name}</div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                        {net >= 0 ? "+" : "−"}{fmt(Math.abs(net))} TJS
                      </div>
                    </div>
                    {active ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
                  </button>
                );
              })}
            </section>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {selectedSupplier && (
                <div className="card" style={{ padding: "16px 18px", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>{t("suppliers.col_name")}</div>
                    <h2 style={{ margin: 0, fontSize: 22 }}>{selectedSupplier.name}</h2>
                    <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>
                      {t("suppliers.col_contact")}: {selectedSupplier.contact_info || "—"}
                    </div>
                  </div>
                </div>
              )}

              {expandedId != null && detailLoading[expandedId] ? (
                <div className="card" style={{ padding: 40, display: "flex", justifyContent: "center" }}><div className="spinner" /></div>
              ) : selectedSupplier && selectedDetail ? (
                <>
                  <section className="partner-detail-panel">
                    <div className="partner-detail-header">
                      <div>
                        <h3 className="partner-detail-title">{t("suppliers.current_debt")}</h3>
                        <div className="partner-detail-subtitle">{t("suppliers.btn_invoice")} · {t("suppliers.btn_pay")} · {t("suppliers.btn_return")}</div>
                      </div>
                      <div className="partner-detail-amount" style={{ color: "var(--green)" }}>
                        {fmt(Number(selectedDetail.receivable_debt || 0))} TJS
                      </div>
                    </div>
                    <div className="partner-detail-body">
                      <div className="partner-actions">
                        <button className="partner-action-btn" onClick={() => openInvoiceModal(selectedSupplier)}>
                          <ArrowDownCircle size={14} /> {t("suppliers.btn_invoice")}
                        </button>
                        <button className="partner-action-btn" disabled={Number(selectedSupplier.current_debt) <= 0} onClick={() => { setPaymentModal(selectedSupplier); setPaymentAmount(""); setPaymentNotes(""); }}>
                          <ArrowUpCircle size={14} /> {t("suppliers.btn_pay")}
                        </button>
                        <button className="partner-action-btn" onClick={() => openReturnModal(selectedSupplier)}>
                          <History size={14} /> {t("suppliers.btn_return")}
                        </button>
                      </div>
                      <button
                        type="button"
                        className="partner-action-btn"
                        style={{ width: "100%", justifyContent: "space-between", marginTop: 4 }}
                        onClick={() => setOpenRecvHistory((v) => !v)}
                      >
                        <span>История</span>
                        <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>
                          {buildReceivableTimeline(selectedDetail).length} записей · {openRecvHistory ? "скрыть ▴" : "показать ▾"}
                        </span>
                      </button>
                      {openRecvHistory && (
                        <div className="partner-history-box" style={{ marginTop: 10 }}>
                          {renderTimeline(buildReceivableTimeline(selectedDetail))}
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="partner-detail-panel">
                    <div className="partner-detail-header">
                      <div>
                        <h3 className="partner-detail-title">{t("suppliers.current_payable")}</h3>
                        <div className="partner-detail-subtitle">{t("suppliers.btn_receipt")} · {t("suppliers.btn_payout")} · {t("suppliers.btn_return_to_partner")}</div>
                      </div>
                      <div className="partner-detail-amount" style={{ color: "var(--red)" }}>
                        {fmt(Number(selectedDetail.payable_debt || 0))} TJS
                      </div>
                    </div>
                    <div className="partner-detail-body">
                      <div className="partner-actions">
                        <button className="partner-action-btn" onClick={() => openReceiptModal(selectedSupplier)}>
                          <ArrowUpCircle size={14} /> {t("suppliers.btn_receipt")}
                        </button>
                        <button className="partner-action-btn" disabled={Number(selectedSupplier.payable_debt || 0) <= 0} onClick={() => { setPayoutModal(selectedSupplier); setPayoutAmount(""); setPayoutNotes(""); }}>
                          <Wallet size={14} /> {t("suppliers.btn_payout")}
                        </button>
                        <button className="partner-action-btn" onClick={() => openOutgoingReturnModal(selectedSupplier)}>
                          <History size={14} /> {t("suppliers.btn_return_to_partner")}
                        </button>
                      </div>
                      <button
                        type="button"
                        className="partner-action-btn"
                        style={{ width: "100%", justifyContent: "space-between", marginTop: 4 }}
                        onClick={() => setOpenPayHistory((v) => !v)}
                      >
                        <span>История</span>
                        <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>
                          {buildPayableTimeline(selectedDetail).length} записей · {openPayHistory ? "скрыть ▴" : "показать ▾"}
                        </span>
                      </button>
                      {openPayHistory && (
                        <div className="partner-history-box" style={{ marginTop: 10 }}>
                          {renderTimeline(buildPayableTimeline(selectedDetail))}
                        </div>
                      )}
                    </div>
                  </section>
                </>
              ) : null}
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
            <div className="modal-grid-split">
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
                  {productsLoading ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                      {t("common.loading")}
                    </div>
                  ) : filteredProducts.length === 0 ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                      {productSearch ? t("common.no_results") : t("common.empty")}
                    </div>
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

      {/* Receipt Modal — goods received from partner */}
      {mounted && receiptModal && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 780, width: "95vw", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <h3 style={{ color: "#3b82f6", display: "flex", alignItems: "center", gap: 8, margin: 0 }}>
                  <ArrowUpCircle size={20} /> {t("suppliers.receipt_title")}
                </h3>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{receiptModal.name}</p>
              </div>
              <button onClick={() => setReceiptModal(null)} style={{ background: "transparent", border: "none" }}><X size={22} /></button>
            </div>

            <div className="modal-grid-split">
              <div style={{ display: "flex", flexDirection: "column", gap: 10, overflow: "hidden" }}>
                <div style={{ position: "relative" }}>
                  <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                  <input className="input" style={{ width: "100%", paddingLeft: 32, fontSize: 13 }} placeholder="Поиск по SKU..." value={productSearch} onChange={e => setProductSearch(e.target.value)} autoFocus />
                </div>
                <div style={{ flex: 1, overflowY: "auto", borderRadius: 8, border: "1px solid var(--border)" }}>
                  {productsLoading ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>{t("common.loading")}</div>
                  ) : filteredProducts.length === 0 ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>{productSearch ? t("common.no_results") : t("common.empty")}</div>
                  ) : filteredProducts.map(p => {
                    const inCart = cart.find(c => c.product.id === p.id);
                    return (
                      <div key={p.id} onClick={() => addToCart(p)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", cursor: "pointer", background: inCart ? "rgba(59,130,246,0.08)" : "transparent", borderBottom: "1px solid var(--border)" }}>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{p.sku}</div>
                          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmt(Number(p.price))} TJS / шт.</div>
                        </div>
                        {inCart ? <span style={{ fontSize: 11, background: "#3b82f6", color: "#fff", borderRadius: 20, padding: "2px 8px" }}>{inCart.quantity} шт.</span> : <Plus size={16} color="var(--text-muted)" />}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10, overflow: "hidden" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ShoppingCart size={16} style={{ color: "#3b82f6" }} />
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
                      <input type="number" min="1" style={{ width: 60, padding: "4px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 13, textAlign: "center" }} value={c.quantity} onChange={e => updateCartQty(c.product.id, parseInt(e.target.value) || 0)} />
                      <button onClick={() => updateCartQty(c.product.id, 0)} style={{ background: "transparent", border: "none", cursor: "pointer", color: "#ef4444" }}><Trash2 size={15} /></button>
                    </div>
                  ))}
                </div>
                <div style={{ padding: "12px 14px", background: "var(--bg-hover)", borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Итого:</span>
                  <span style={{ fontSize: 18, fontWeight: 700, color: "#3b82f6" }}>{fmt(cartTotal)} TJS</span>
                </div>
              </div>
            </div>

            <form onSubmit={handleAddReceipt} style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
              <input className="input" style={{ flex: 1 }} placeholder={t("suppliers.notes_ph")} value={receiptNotes} onChange={e => setReceiptNotes(e.target.value)} />
              <button type="button" className="btn btn-ghost" onClick={() => setReceiptModal(null)}>{t("common.cancel")}</button>
              <button type="submit" className="btn btn-primary" disabled={savingReceipt || cart.length === 0}>{savingReceipt ? "..." : `${t("suppliers.btn_receipt")} — ${fmt(cartTotal)} TJS`}</button>
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
            <p style={{ fontSize: 13, color: "var(--green)", marginBottom: 20 }}>
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
      {/* Payout Modal (our debt decreases) */}
      {mounted && payoutModal && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 420 }}>
            <h3 style={{ marginBottom: 4, color: "var(--red)", display: "flex", alignItems: "center", gap: 8 }}>
              <Wallet size={20} /> {t("suppliers.payout_title")}
            </h3>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>{payoutModal.name}</p>
            <p style={{ fontSize: 13, color: "var(--red)", marginBottom: 20 }}>
              {t("suppliers.current_payable")}: <strong>{fmt(Number(payoutModal.payable_debt || 0))} TJS</strong>
            </p>
            <form onSubmit={handleAddPayout} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("finance.amount")} (TJS) *</label>
                <input type="number" min="0" step="0.01" max={Number(payoutModal.payable_debt || 0)} className="input" style={{ width: "100%" }} value={payoutAmount} onChange={e => setPayoutAmount(e.target.value)} autoFocus required />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 5 }}>{t("suppliers.notes")}</label>
                <input className="input" style={{ width: "100%" }} value={payoutNotes} onChange={e => setPayoutNotes(e.target.value)} placeholder={t("suppliers.notes_ph")} />
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setPayoutModal(null)}>{t("common.cancel")}</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: "var(--green)" }} disabled={savingPayout}>{savingPayout ? "..." : t("suppliers.btn_payout")}</button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
      {/* Return Modal — Product Cart (Reusing styles from Invoice Modal) */}
      {mounted && returnModal && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 780, width: "95vw", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <h3 style={{ color: "var(--orange)", display: "flex", alignItems: "center", gap: 8, margin: 0 }}>
                  <History size={20} /> {t("suppliers.return_title")}
                </h3>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{returnModal.name}</p>
              </div>
              <button onClick={() => setReturnModal(null)} style={{ background: "transparent", border: "none" }}><X size={22} /></button>
            </div>

            {/* Body */}
            <div className="modal-grid-split">
              {/* Product List */}
              <div style={{ display: "flex", flexDirection: "column", background: "var(--bg)", borderRadius: 12, border: "1px solid var(--border)" }}>
                <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ position: "relative" }}>
                    <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                    <input
                      className="input"
                      style={{ paddingLeft: 32, fontSize: 13 }}
                      placeholder={t("products.search")}
                      value={productSearch}
                      onChange={e => setProductSearch(e.target.value)}
                    />
                  </div>
                </div>
                <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
                  {productsLoading ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                      {t("common.loading")}
                    </div>
                  ) : filteredProducts.length === 0 ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                      {productSearch ? t("common.no_results") : t("suppliers.no_send_products")}
                    </div>
                  ) : filteredProducts.filter(p => (returnableQtyMap[p.id] ?? 0) > 0).map(p => {
                    const maxQty = returnableQtyMap[p.id] ?? 0;
                    return (
                      <div
                        key={p.id}
                        onClick={() => addToReturnCart(p)}
                        style={{ padding: "8px 12px", borderRadius: 8, cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4, background: "var(--bg-card)", border: "1px solid var(--border)" }}
                      >
                        <div>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{p.sku}</span>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 8 }}>макс. {maxQty} шт.</span>
                        </div>
                        <Plus size={14} color="var(--accent)" />
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Cart */}
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
                  {cart.length === 0 ? (
                    <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                      <ShoppingCart size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                      <p style={{ fontSize: 13, color: "var(--text-muted)" }}>{t("suppliers.no_send_products")}</p>
                    </div>
                  ) : (
                    cart.map(c => {
                      const max = returnableQtyMap[c.product.id] ?? 0;
                      return (
                        <div key={c.product.id} style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--bg-card)", padding: 10, borderRadius: 10, marginBottom: 8, border: "1px solid var(--border)" }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{c.product.sku}</div>
                            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{fmt(c.product.price)} TJS · макс. {max} шт.</div>
                          </div>
                          <input
                            type="number"
                            className="input"
                            min={1}
                            max={max}
                            style={{ width: 60, padding: "4px 8px", textAlign: "center" }}
                            value={c.quantity}
                            onChange={e => updateReturnCartQty(c.product.id, parseInt(e.target.value) || 0)}
                          />
                          <button onClick={() => updateReturnCartQty(c.product.id, 0)} style={{ border: "none", background: "transparent", color: "var(--red)" }}>
                            <Trash2 size={16} />
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16 }}>
                  <textarea
                    className="input"
                    style={{ width: "100%", height: 60, marginBottom: 12, resize: "none" }}
                    placeholder={t("suppliers.notes_ph")}
                    value={returnNotes}
                    onChange={e => setReturnNotes(e.target.value)}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>{t("common.total")}:</span>
                    <span style={{ fontSize: 18, fontWeight: 700, color: "#d97706" }}>{fmt(cartTotal)} TJS</span>
                  </div>
                  <button
                    style={{
                      width: "100%",
                      height: 44,
                      background: cart.length === 0 || savingReturn ? "rgba(217,119,6,0.4)" : "#d97706",
                      color: "#fff",
                      border: "none",
                      borderRadius: 10,
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: cart.length === 0 || savingReturn ? "not-allowed" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                    }}
                    disabled={cart.length === 0 || savingReturn}
                    onClick={handleCreateReturn}
                  >
                    <History size={16} />
                    {savingReturn ? "..." : t("suppliers.btn_return")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
      {/* Return to Partner Modal */}
      {mounted && outgoingReturnModal && createPortal(
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 780, width: "95vw", maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <h3 style={{ color: "#8b5cf6", display: "flex", alignItems: "center", gap: 8, margin: 0 }}>
                  <History size={20} /> {t("suppliers.return_to_partner_title")}
                </h3>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{outgoingReturnModal.name}</p>
              </div>
              <button onClick={() => setOutgoingReturnModal(null)} style={{ background: "transparent", border: "none" }}><X size={22} /></button>
            </div>

            <div className="modal-grid-split">
              <div style={{ display: "flex", flexDirection: "column", background: "var(--bg)", borderRadius: 12, border: "1px solid var(--border)" }}>
                <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ position: "relative" }}>
                    <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                    <input className="input" style={{ paddingLeft: 32, fontSize: 13 }} placeholder={t("products.search")} value={productSearch} onChange={e => setProductSearch(e.target.value)} />
                  </div>
                </div>
                <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
                  {productsLoading ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>{t("common.loading")}</div>
                  ) : filteredProducts.length === 0 ? (
                    <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>{productSearch ? t("common.no_results") : t("suppliers.no_received_products")}</div>
                  ) : filteredProducts.filter(p => (returnableToPartnerQtyMap[p.id] ?? 0) > 0).map(p => {
                    const maxQty = returnableToPartnerQtyMap[p.id] ?? 0;
                    return (
                      <div key={p.id} onClick={() => addToOutgoingReturnCart(p)} style={{ padding: "8px 12px", borderRadius: 8, cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4, background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                        <div>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{p.sku}</span>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 8 }}>макс. {maxQty} шт.</span>
                        </div>
                        <Plus size={14} color="#8b5cf6" />
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
                  {cart.length === 0 ? (
                    <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                      <ShoppingCart size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                      <p style={{ fontSize: 13, color: "var(--text-muted)" }}>{t("suppliers.no_received_products")}</p>
                    </div>
                  ) : cart.map(c => {
                    const max = returnableToPartnerQtyMap[c.product.id] ?? 0;
                    return (
                      <div key={c.product.id} style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--bg-card)", padding: 10, borderRadius: 10, marginBottom: 8, border: "1px solid var(--border)" }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{c.product.sku}</div>
                          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{fmt(c.product.price)} TJS · макс. {max} шт.</div>
                        </div>
                        <input type="number" className="input" min={1} max={max} style={{ width: 60, padding: "4px 8px", textAlign: "center" }} value={c.quantity} onChange={e => updateOutgoingReturnCartQty(c.product.id, parseInt(e.target.value) || 0)} />
                        <button onClick={() => updateOutgoingReturnCartQty(c.product.id, 0)} style={{ border: "none", background: "transparent", color: "var(--red)" }}><Trash2 size={16} /></button>
                      </div>
                    );
                  })}
                </div>
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16 }}>
                  <textarea className="input" style={{ width: "100%", height: 60, marginBottom: 12, resize: "none" }} placeholder={t("suppliers.notes_ph")} value={outgoingReturnNotes} onChange={e => setOutgoingReturnNotes(e.target.value)} />
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>{t("common.total")}:</span>
                    <span style={{ fontSize: 18, fontWeight: 700, color: "#8b5cf6" }}>{fmt(cartTotal)} TJS</span>
                  </div>
                  <button style={{ width: "100%", height: 44, background: cart.length === 0 || savingOutgoingReturn ? "rgba(139,92,246,0.4)" : "#8b5cf6", color: "#fff", border: "none", borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: cart.length === 0 || savingOutgoingReturn ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }} disabled={cart.length === 0 || savingOutgoingReturn} onClick={handleCreateOutgoingReturn}>
                    <History size={16} />
                    {savingOutgoingReturn ? "..." : t("suppliers.btn_return_to_partner")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
