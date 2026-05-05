"use client";
import React, { useEffect, useState, useCallback, Fragment } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Brand, BrandStat, Product, ProductInventoryOut, Store, UserMe } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { Search, Plus, StoreIcon, ChevronDown, ChevronRight, ChevronLeft, PackageOpen, Package, FileUp, X, ShoppingCart, Trash2 } from "lucide-react";
import * as XLSX from "xlsx";
import { createPortal } from "react-dom";

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

function normalizeSku(raw: unknown): string {
  return String(raw ?? "").trim().toUpperCase();
}

function normalizeBrandName(brand: string | undefined): string {
  const normalized = String(brand || "").trim();
  if (normalized) return normalized.toUpperCase();
  return "UNKNOWN";
}

function parseLocalizedNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : NaN;
  const text = String(value ?? "").trim().replace(",", ".");
  if (!text) return NaN;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : NaN;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

interface OrderModalItem {
  product_id: number;
  sku: string;
  quantity: number;
}

interface ImportItem {
  sku: string;
  total: number;
  price: number;
  brand: string;
}

export default function ProductsPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();
  
  const [user] = useState<UserMe | null>(() => getStoredUser());
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [brandOptions, setBrandOptions] = useState<{ name: string; count: number }[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [selectedBrand, setSelectedBrand] = useState<string>("");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const PAGE_SIZE = 50;

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ sku: "", brand: "", price: "" });
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
  const [orderItem, setOrderItem] = useState<OrderModalItem | null>(null);

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importFillBrand, setImportFillBrand] = useState(""); // global fill-all brand
  const [importReplaceQty, setImportReplaceQty] = useState(true);
  const [importData, setImportData] = useState<ImportItem[]>([]);
  const [importing, setImporting] = useState(false);
  const [mounted, setMounted] = useState(false);

  const isWarehouse = user?.role === "owner" || user?.role === "warehouse" || user?.role === "admin";
  const isSeller = user?.role === "seller";
  const visibleBrands = React.useMemo(
    () => brandOptions.filter((b) => b.name !== "UNKNOWN"),
    [brandOptions]
  );
  // Backend now filters by brand, so filteredProducts === products
  const filteredProducts = products;

  const fetchProducts = useCallback(async (overrides?: { search?: string; page?: number; showInactive?: boolean; brand?: string | null }) => {
    const searchValue = overrides?.search ?? search;
    const pageValue = overrides?.page ?? page;
    const showInactiveValue = overrides?.showInactive ?? showInactive;
    const brandValue = overrides?.brand !== undefined ? overrides.brand : selectedBrand;
    try {
      setLoading(true);
      const data = await api.getProducts({
        search: searchValue,
        brand: brandValue || undefined,
        page: pageValue,
        page_size: PAGE_SIZE,
        only_inactive: showInactiveValue,
      });
      setProducts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      showToast(getErrorMessage(error, "Failed to fetch products"), "error");
    } finally {
      setLoading(false);
    }
  }, [search, page, showInactive, selectedBrand, showToast]);

  const fetchBrandOptions = useCallback(async () => {
    try {
      const [catalog, stats] = await Promise.all([
        api.getBrands(),
        api.getBrandStats(),
      ]);
      setBrands(catalog);
      const counts = new Map<string, number>(
        stats.map((item: BrandStat) => [item.name.toUpperCase(), item.product_count])
      );
      const list = catalog
        .map((brand) => ({ name: brand.name, count: counts.get(brand.name.toUpperCase()) || 0 }))
        .sort((a, b) => a.name.localeCompare(b.name));
      setBrandOptions(list);
    } catch (e) {
      showToast(getErrorMessage(e, t("common.error")), "error");
    }
  }, [showToast, t]);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    api.getStores().then(setStores).catch((error) => {
      showToast(getErrorMessage(error, t("common.error")), "error");
    });
    void fetchProducts();
    void fetchBrandOptions();
  }, [router, fetchProducts, fetchBrandOptions, showToast, t]);

  useEffect(() => {
    setPage(1);
  }, [search, selectedBrand]);

  useEffect(() => {
    setMounted(true);
  }, []);

  async function handleToggleActive(p: Product) {
    try {
      setToggling(true);
      await api.updateProduct(p.id, { is_active: !p.is_active });
      setPendingToggleProduct(null);
      await fetchProducts();
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
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
    } catch (error) {
      showToast(getErrorMessage(error, t("products.hard_delete_failed")), "error");
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
      } catch (error) {
        console.error("Failed to load inventory for product", error);
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
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
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
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
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
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.createProduct({ sku: form.sku, brand: form.brand, price: Number(form.price) });
      setForm({ sku: "", brand: "", price: "" });
      setAdding(false);
      setSearch("");
      setSelectedBrand("");
      setShowInactive(false);
      setPage(1);
      await fetchProducts({ search: "", page: 1, showInactive: false });
      await fetchBrandOptions();
    } catch (error) { 
      const message = getErrorMessage(error, t("common.error"));
      if (message === "Product with this SKU already exists") {
        showToast(t("products.sku_exists") || "Товар с таким артикулом (SKU) уже существует", "error");
      } else {
        showToast(message, "error"); 
      }
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const bstr = evt.target?.result;
        const wb = XLSX.read(bstr, { type: "binary" });
        const wsname = wb.SheetNames[0];
        const ws = wb.Sheets[wsname];
        const data = XLSX.utils.sheet_to_json(ws, { header: 1 }) as unknown[][];
        const grouped = new Map<string, { sku: string; total: number; priceSum: number; priceCount: number }>();
        const errors: string[] = [];
        
        for (let i = 0; i < data.length; i++) {
          const row = data[i];
          if (!row || row.length < 6) continue;
          
          const skuRaw = String(row[2] || "").trim();
          const sku = normalizeSku(skuRaw);
          
          if (!sku) continue;

          // Skip header or footer rows
          const upperSku = sku.toUpperCase();
          if (upperSku.includes("НОМГУИ") || upperSku.includes("ЧАМЪ") || upperSku.includes("АРТИКУЛ")) {
            continue;
          }

          const unitsPerBox = parseLocalizedNumber(row[3]);
          const boxes = parseLocalizedNumber(row[4]);
          const total = parseLocalizedNumber(row[5]);
          const price = parseLocalizedNumber(row[6]);
          
          // Determine quantity
          const derivedTotal = !Number.isNaN(total) ? total : (Number.isNaN(boxes) || Number.isNaN(unitsPerBox) ? NaN : boxes * unitsPerBox);

          // Silent skip for rows that don't look like products (e.g. empty rows or extra text)
          if (Number.isNaN(derivedTotal)) {
            continue;
          }

          if (derivedTotal <= 0) {
            errors.push(`row ${i + 1}: invalid quantity (${derivedTotal}) for SKU ${sku}`);
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
          brand: "",
        }));

        if (errors.length) {
          showToast(`Import warnings: ${errors.slice(0, 3).join("; ")}`, "error");
        }
        setImportData(parsedItems);
      } catch {
        showToast(t("products.import_error"), "error");
      }
    };
    reader.readAsBinaryString(file);
  };

  const handleProcessImport = async () => {
    if (importData.length === 0) return;
    setImporting(true);
    try {
      const res = await api.bulkReceiveStock({
        items: importData.map(d => ({
          sku: d.sku,
          quantity: Math.round(d.total),
          price: d.price > 0 ? d.price : undefined,
          brand: d.brand || undefined,
        })),
        replace_quantity: importReplaceQty,
      });
      showToast(t("products.import_success", { processed: res.processed, created: res.created }));
      setImportModalOpen(false);
      setImportData([]);
      setImportFillBrand("");
      setImportReplaceQty(true);
      setSelectedBrand("");
      setSearch("");
      setPage(1);
      await fetchBrandOptions();
      await fetchProducts({ page: 1, search: "", showInactive: false });
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
    finally { setImporting(false); }
  };

  // Fill all rows with selected brand
  const handleFillAllBrand = (brandName: string) => {
    setImportFillBrand(brandName);
    setImportData(prev => prev.map(d => ({ ...d, brand: brandName })));
  };

  const handleItemBrandChange = (idx: number, brandName: string) => {
    setImportData(prev => prev.map((d, i) => i === idx ? { ...d, brand: brandName } : d));
  };

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        <div className="page-header">
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Package size={32} style={{ color: "var(--accent)" }} />
              {t("products.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginLeft: 44 }}>
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
              <div style={{ flex: "1 1 160px" }}>
                <label style={{ display: "block", fontSize: 11, color: "var(--text-muted)", marginBottom: 5 }}>{t("products.col_brand")}</label>
                <select className="input" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} required style={{ width: "100%" }}>
                  <option value="">{t("products.brand_select")}</option>
                  {brands.map((brand) => (
                    <option key={brand.id} value={brand.name}>
                      {brand.name}
                    </option>
                  ))}
                </select>
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
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: 12,
              background: "var(--bg-card)",
              padding: 10,
            }}
          >
            <label
              style={{
                display: "block",
                fontSize: 11,
                color: "var(--text-muted)",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: 0.4,
              }}
            >
              {t("products.col_brand")}
            </label>
            <select
              className="input"
              style={{
                width: "100%",
                fontSize: 13,
                height: 38,
                borderRadius: 10,
                background: "var(--bg-elevated)",
              }}
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value)}
            >
              <option value="">{t("products.brand_all")}</option>
              {visibleBrands.map((brand) => (
                <option key={brand.name} value={normalizeBrandName(brand.name)}>
                  {brand.name}
                </option>
              ))}
            </select>
          </div>
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
                    <th style={{ width: "35px", textAlign: "center", color: "var(--text-muted)" }}>#</th>
                    <th style={{ width: "80px" }}>{t("products.col_sku")}</th>
                    <th style={{ width: "auto" }}>{t("products.col_brand")}</th>
                    <th style={{ width: "80px", textAlign: "right" }}>{t("products.col_price")}</th>
                    <th style={{ width: "60px", textAlign: "center" }}>{t("common.status")}</th>
                    {isWarehouse && <th style={{ width: "80px", textAlign: "center" }}>{t("common.actions")}</th>}
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map((p, idx) => (
                    <Fragment key={p.id}>
                      <tr 
                        style={{ cursor: "pointer", background: expandedRow === p.id ? "var(--bg-hover)" : "transparent", transition: "background 0.2s", opacity: p.is_active ? 1 : 0.55 }}
                        onClick={() => handleToggleExpand(p.id)}
                      >
                        <td style={{ textAlign: "center", fontSize: 12, color: "var(--text-muted)", fontWeight: 500 }}>
                          {(page - 1) * 50 + idx + 1}
                        </td>
                        <td data-label={t("products.col_sku")} style={{ fontWeight: 700, color: "var(--accent)", fontSize: 13 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            {expandedRow === p.id ? <ChevronDown size={14} color="var(--text-muted)" /> : <ChevronRight size={14} color="var(--text-muted)" />}
                            {p.sku}
                          </div>
                        </td>
                        <td data-label={t("products.col_brand")} style={{ fontSize: 12, fontWeight: 600 }}>
                          {normalizeBrandName(p.brand) === "UNKNOWN" ? "-" : normalizeBrandName(p.brand)}
                        </td>
                        <td data-label={t("products.col_price")} style={{ textAlign: "right", fontWeight: 600 }}>{fmt(Number(p.price))} TJS</td>
                        <td data-label={t("common.status")} style={{ textAlign: "center" }}>
                          <span className={p.is_active ? "badge badge-delivered" : "badge badge-rejected"}>
                            {p.is_active ? t("products.active") : t("products.inactive")}
                          </span>
                        </td>
                        {isWarehouse && (
                          <td data-label={t("common.actions")} style={{ textAlign: "center" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                              {p.is_active && (
                                <button onClick={(e) => { e.stopPropagation(); setReceivingProduct(p); }} className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12, display: "flex", gap: "4px", alignItems: "center" }}>
                                  <PackageOpen size={13} style={{ opacity: 0.8 }} /> {t("products.btn_receive") || "Добавить"}
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

                            </div>
                          </td>
                        )}
                      </tr>
                      {expandedRow === p.id && (
                        <tr style={{ background: "var(--bg-hover)" }}>
                          <td colSpan={isWarehouse ? 5 : 4} style={{ padding: 0 }}>
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
                  {filteredProducts.length === 0 && (
                    <tr>
                      <td colSpan={isWarehouse ? 5 : 4} style={{ textAlign: "center", color: "var(--text-secondary)", padding: "22px 12px" }}>
                        {t("common.no_results")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {!loading && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 24, marginBottom: 40 }}>
            <button
              className="btn btn-ghost"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <ChevronLeft size={16} /> {t("common.back")}
            </button>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{page} / {Math.max(totalPages, 1)}</div>
            <button
              className="btn btn-ghost"
              onClick={() => setPage(p => Math.min(Math.max(totalPages, 1), p + 1))}
              disabled={page >= Math.max(totalPages, 1)}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              {t("common.next")} <ChevronRight size={16} />
            </button>
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
          <div className="modal-card" style={{ maxWidth: 960, maxHeight: "90vh", display: "flex", flexDirection: "column" }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>{t("products.import_title")}</h3>
              <button onClick={() => { setImportModalOpen(false); setImportData([]); setImportFillBrand(""); setImportReplaceQty(true); }} style={{ background: "transparent", border: "none", cursor: "pointer" }}><X size={24} /></button>
            </div>

            {/* Controls bar (shown only after file loaded) */}
            {importData.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, padding: "10px 14px", background: "var(--bg-secondary)", borderRadius: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>{t("products.import_fill_all")}</span>
                <select
                  className="input"
                  style={{ padding: "4px 10px", fontSize: 13, height: "auto", minWidth: 160 }}
                  value={importFillBrand}
                  onChange={e => handleFillAllBrand(e.target.value)}
                >
                  <option value="">{t("products.import_select_placeholder")}</option>
                  {brands.map(b => <option key={b.id} value={b.name}>{b.name}</option>)}
                </select>
                <div style={{ width: 1, height: 20, background: "var(--border)", margin: "0 4px" }} />
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer",
                  color: importReplaceQty ? "var(--accent)" : "var(--text-secondary)",
                  padding: "4px 10px", borderRadius: 8, border: "1px solid var(--border)",
                  background: importReplaceQty ? "var(--accent-muted, rgba(99,102,241,.1))" : "transparent" }}>
                  <input type="checkbox" checked={importReplaceQty} onChange={e => setImportReplaceQty(e.target.checked)} style={{ margin: 0 }} />
                  {t("products.import_replace_qty")}
                </label>
                <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-muted)" }}>
                  {importData.filter(d => !d.brand).length > 0
                    ? t("products.import_warn_no_brand", { count: importData.filter(d => !d.brand).length })
                    : t("products.import_all_brands_ok")}
                </span>
              </div>
            )}

            {/* Body */}
            <div style={{ overflowY: "auto", flex: 1 }}>
              {importData.length === 0 ? (
                <div style={{ border: "2px dashed var(--border)", padding: 40, textAlign: "center", borderRadius: 10 }}>
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
                        <th style={{ minWidth: 160 }}>{t("products.col_brand")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importData.map((d, i) => (
                        <tr key={i} style={{ background: !d.brand ? "rgba(239,68,68,.04)" : undefined }}>
                          <td style={{ fontWeight: 500 }}>{d.sku}</td>
                          <td style={{ textAlign: "center" }}>{d.total}</td>
                          <td style={{ textAlign: "right" }}>{fmt(d.price)}</td>
                          <td>
                            <select
                              className="input"
                              style={{ padding: "3px 8px", fontSize: 12, height: "auto", width: "100%",
                                borderColor: !d.brand ? "var(--red, #ef4444)" : undefined }}
                              value={d.brand}
                              onChange={e => handleItemBrandChange(i, e.target.value)}
                            >
                              <option value="">{t("products.import_brand_placeholder")}</option>
                              {brands.map(b => <option key={b.id} value={b.name}>{b.name}</option>)}
                            </select>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Footer */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 16 }}>
              <button className="btn btn-ghost" onClick={() => { setImportModalOpen(false); setImportData([]); setImportFillBrand(""); }}>{t("common.cancel")}</button>
              {importData.length > 0 && (
                <button
                  className="btn btn-primary"
                  onClick={handleProcessImport}
                  disabled={importing || importData.some(d => !d.brand)}
                  title={importData.some(d => !d.brand) ? t("products.import_btn_warn") : undefined}
                  style={{ opacity: importData.some(d => !d.brand) ? 0.6 : 1, cursor: importData.some(d => !d.brand) ? "not-allowed" : "pointer" }}
                >
                  {importing ? "..." : t("products.import_process")}
                </button>
              )}
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
