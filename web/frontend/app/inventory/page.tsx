"use client";
import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Store, InventoryItem, StoreCatalogCard } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { Package, Search, Store as StoreIcon, DollarSign, Boxes, Warehouse, Database, X } from "lucide-react";
import * as XLSX from "xlsx";

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU").format(n);
}

type VitrinaImportItem = {
  sku: string;
  brand: string;
  price?: number;
  store_price?: number | null;
};

function parseImportNumber(value: unknown): number | undefined {
  if (typeof value === "number") return Number.isFinite(value) ? value : undefined;
  const text = String(value ?? "").trim().replace(/\s/g, "").replace(",", ".");
  if (!text) return undefined;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizeVitrinaSku(raw: unknown): string {
  let sku = String(raw ?? "").trim();
  const starMatch = sku.match(/^(\*+)/);
  if (starMatch) {
    sku = "0".repeat(starMatch[1].length) + sku.slice(starMatch[1].length);
  }
  const replaced = sku.replace(/[oO]/g, "0");
  if (/^\d+$/.test(replaced)) {
    sku = replaced;
  }
  return sku.trim().toUpperCase();
}

function isPriceHeader(value: unknown): boolean {
  const text = String(value ?? "").trim().toLowerCase();
  return text === "цена" || text === "нарх";
}

function isStorePriceHeader(value: unknown): boolean {
  const text = String(value ?? "").trim().toLowerCase();
  return text.includes("магаз") || text.includes("мағоза");
}

export default function InventoryPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStore, setSelectedStore] = useState<number | null>(null);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(50);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  const [catalog, setCatalog] = useState<StoreCatalogCard[]>([]);
  const [userRole, setUserRole] = useState<string>("seller");

  const [importData, setImportData] = useState<VitrinaImportItem[]>([]);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [bulkStorePrice, setBulkStorePrice] = useState<string>("");
  const [bulkPrice, setBulkPrice] = useState<string>("");

  useEffect(() => {
    const user = getStoredUser();
    if (!user) {
      router.replace("/login");
      return;
    }
    setUserRole(user.role);
    
    api.getStores().then(setStores).catch(console.error);
  }, [router]);

  // Debounce search (300ms)
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset to page 1 when search or store changes
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearch, selectedStore]);

  useEffect(() => {
    setLoading(true);
    if (!selectedStore) {
      api.getStoreCatalog()
        .then(setCatalog)
        .catch(console.error)
        .finally(() => setLoading(false));
      setItems([]);
      setTotalItems(0);
      setTotalPages(0);
    } else {
      api.getInventory(selectedStore, currentPage, pageSize, debouncedSearch)
        .then((data) => {
          setItems(data.items);
          setTotalItems(data.total);
          setTotalPages(data.total_pages);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
      setCatalog([]);
    }
  }, [selectedStore, currentPage, pageSize, debouncedSearch]);

  const handleConfirmImport = async () => {
    if (!selectedStore || importData.length === 0) return;
    setImporting(true);
    try {
      const res = await api.importVitrina(selectedStore, importData);
      showToast(`✅ Загружено успешно! Фирм: ${new Set(importData.map(d=>d.brand)).size}, Артикулов: ${importData.length}. Сохранено новых: ${res.created}, обновлено на витрине: ${res.added_qty}`, "success");
      setIsImportModalOpen(false);
      setImportData([]);
      setBulkPrice("");
      setBulkStorePrice("");
      api.getInventory(selectedStore, currentPage, pageSize).then((data) => {
        setItems(data.items);
        setTotalItems(data.total);
        setTotalPages(data.total_pages);
      });
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Ошибка сохранения", "error");
    } finally {
      setImporting(false);
    }
  };

  // Backend handles search filtering now; `items` is already filtered & paginated
  const filtered = items;

  const totalQuantity = selectedStore ? totalItems : catalog.reduce((s, c) => s + c.total_items, 0);

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        <div className="page-header">
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Warehouse size={32} style={{ color: "var(--accent)" }} />
              {t("inventory.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginLeft: 44 }}>
              {t("inventory.found", { count: totalQuantity })}
            </p>
          </div>
          {userRole !== "seller" && (
            <div style={{ display: "flex", gap: 10 }}>
              <input 
                type="file" 
                id="csv-upload" 
                hidden 
                accept=".csv, .xlsx, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (!selectedStore) {
                    showToast("Сначала выберите магазин (витрину)!", "error");
                    e.target.value = "";
                    return;
                  }
                  const reader = new FileReader();
                  reader.onload = (evt) => {
                    try {
                      const bstr = evt.target?.result;
                      const wb = XLSX.read(bstr, { type: "binary" });
                      const wsname = wb.SheetNames[0];
                      const ws = wb.Sheets[wsname];
                      const data = XLSX.utils.sheet_to_json(ws, { header: 1 }) as any[][];
                      if (data.length < 2) {
                        showToast("Файл пустой или неверный формат", "error");
                        return;
                      }
                      const headers = data[0];
                      const groups: { brand: string; skuCol: number; priceCol?: number; storePriceCol?: number }[] = [];
                      for (let c = 0; c < headers.length; c++) {
                        const header = String(headers[c] ?? "").trim();
                        if (!header || isPriceHeader(header) || isStorePriceHeader(header)) continue;
                        const priceCol = isPriceHeader(headers[c + 1]) ? c + 1 : undefined;
                        const storePriceCol = isStorePriceHeader(headers[c + 2]) ? c + 2 : undefined;
                        groups.push({ brand: header, skuCol: c, priceCol, storePriceCol });
                      }

                      const parsed: VitrinaImportItem[] = [];
                      for (let r = 1; r < data.length; r++) {
                        const row = data[r] || [];
                        for (const group of groups) {
                          const sku = normalizeVitrinaSku(row[group.skuCol]);
                          if (!sku || sku.toLowerCase().includes("пример") || sku.toLowerCase() === "sku") continue;
                          const price = group.priceCol !== undefined ? parseImportNumber(row[group.priceCol]) : undefined;
                          const storePrice = group.storePriceCol !== undefined ? parseImportNumber(row[group.storePriceCol]) : undefined;
                          parsed.push({
                            sku,
                            brand: group.brand,
                            price,
                            store_price: storePrice ?? null,
                          });
                        }
                      }
                      if (parsed.length === 0) {
                        showToast("Не найдено товаров. Проверьте формат: Фирма | Цена | Цена для магазина", "error");
                        return;
                      }
                      setImportData(parsed);
                      setIsImportModalOpen(true);
                    } catch (err) {
                      showToast("Ошибка чтения файла", "error");
                    }
                  };
                  reader.readAsBinaryString(file);
                  e.target.value = "";
                }}
              />
              <button 
                className="btn"
                style={{ background: "var(--bg-card)", color: "var(--text-primary)", border: "1px solid var(--border)", height: "fit-content", padding: "10px 16px" }}
                onClick={() => document.getElementById('csv-upload')?.click()}
              >
                <Database size={18} style={{ marginRight: 8 }} />
                Загрузить Excel
              </button>
            </div>
          )}
        </div>

        <div className="page-filters" style={{ flexDirection: "column", alignItems: "stretch", gap: 12 }}>
          {/* Back to all stores button (only when a store is selected) */}
          {selectedStore && (
            <button
              type="button"
              onClick={() => setSelectedStore(null)}
              style={{
                padding: "8px 14px",
                borderRadius: 999,
                border: "1px solid var(--border)",
                background: "transparent",
                color: "var(--text-primary)",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.15s",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                width: "fit-content",
              }}
            >
              <Boxes size={14} /> ← {t("inventory.all_stores")}
            </button>
          )}

          {/* Search input (only when a store is selected) */}
          {selectedStore && (
            <div style={{ position: "relative", maxWidth: 480, width: "100%" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", pointerEvents: "none" }} />
              <input
                type="text"
                className="input"
                placeholder={t("inventory.search_placeholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 36, paddingRight: search ? 34 : undefined, width: "100%" }}
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  title="Очистить"
                  style={{
                    position: "absolute",
                    right: 8,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--text-secondary)",
                    padding: 4,
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          )}
        </div>

        <div className="page-content">
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
              <div className="spinner" />
            </div>
          ) : !selectedStore ? (
            // Store cards view for "All stores" - compact grid
            <div className="store-card-grid">
              {catalog.map((store) => (
                <div 
                  key={store.id}
                  className="card store-card"
                  onClick={() => {
                    setSelectedStore(store.id);
                    setCurrentPage(1);
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <StoreIcon size={16} style={{ color: "var(--accent)" }} />
                    <span style={{ fontSize: 14, fontWeight: 600 }}>
                      {store.name}
                    </span>
                  </div>
                  
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>Товаров</div>
                      <div style={{ fontSize: 20, fontWeight: 700 }}>{fmt(store.total_items)}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>Стоимость</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--accent)" }}>{fmt(store.total_value)} TJS</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <Package size={40} style={{ margin: "0 auto 12px", opacity: 0.3 }} />
              {t("inventory.empty")}
            </div>
          ) : (
            // Items table for specific store
            <div className="table-wrap">
              <React.Fragment>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: "35px", textAlign: "center" }}>№</th>
                    <th style={{ minWidth: "70px" }}>{t("inventory.col_sku")}</th>
                    <th>Фирма</th>
                    <th style={{ textAlign: "center" }}>{t("inventory.col_qty")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item, index) => (
                    <tr key={item.product_id}>
                      <td data-label="№" style={{ textAlign: "center", fontWeight: 600, color: "var(--text-secondary)" }}>
                        {index + 1}
                      </td>
                      <td data-label={t("inventory.col_sku")} style={{ fontWeight: 700, color: "var(--accent)", fontFamily: "monospace", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                        {item.product_sku}
                        {item.is_display && (
                          <span className="badge badge-pending" style={{ fontSize: 10, padding: "2px 6px" }}>
                            {t("inventory.is_display")}
                          </span>
                        )}
                      </td>
                      <td data-label="Фирма" style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                        {item.product_brand || "—"}
                      </td>
                      <td data-label={t("inventory.col_qty")} style={{ textAlign: "center", fontWeight: 700 }}>
                        {item.quantity} шт
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </React.Fragment>
              
              {totalPages > 1 && (
                <div style={{ 
                  display: "flex", 
                  justifyContent: "center", 
                  alignItems: "center", 
                  gap: 8, 
                  marginTop: 20,
                  padding: "16px 0",
                  borderTop: "1px solid var(--border)"
                }}>
                  <button 
                    className="btn btn-ghost" 
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                    style={{ padding: "6px 12px", fontSize: 12 }}
                  >
                    ⟪
                  </button>
                  <button 
                    className="btn btn-ghost" 
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    style={{ padding: "6px 12px", fontSize: 12 }}
                  >
                    ⟨
                  </button>
                  
                  <span style={{ 
                    padding: "0 16px", 
                    fontSize: 13, 
                    color: "var(--text-primary)",
                    fontWeight: 500
                  }}>
                    {currentPage} / {totalPages}
                  </span>
                  
                  <button 
                    className="btn btn-ghost" 
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages}
                    style={{ padding: "6px 12px", fontSize: 12 }}
                  >
                    ⟩
                  </button>
                  <button 
                    className="btn btn-ghost" 
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                    style={{ padding: "6px 12px", fontSize: 12 }}
                  >
                    ⟫
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {isImportModalOpen && (
        <div className="modal-overlay" style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.5)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setIsImportModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: 600, width: "100%", maxHeight: "90vh", display: "flex", flexDirection: "column", background: "var(--bg-card)" }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Database size={20} /> Предпросмотр: Витрина
              </h3>
              <button className="btn-close" onClick={() => setIsImportModalOpen(false)}>
                <X size={20} />
              </button>
            </div>
            
            <div style={{ padding: "0 24px", color: "var(--text-secondary)", fontSize: 14 }}>
              Будет загружено: <strong style={{color:"var(--text-primary)"}}>{importData.length}</strong> артикулов по 1 шт на выбранную витрину. Цены товара тоже обновятся.
            </div>

            <div style={{ padding: "12px 24px 0", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
                  Цена склада — применить ко всем
                </label>
                <input
                  type="number"
                  className="input"
                  placeholder="0"
                  value={bulkPrice}
                  onChange={(e) => setBulkPrice(e.target.value)}
                  style={{ width: "100%", height: 36 }}
                />
              </div>
              <button
                className="btn btn-ghost"
                style={{ height: 36 }}
                onClick={() => {
                  const v = parseFloat(bulkPrice);
                  if (!isFinite(v) || v < 0) { showToast("Введите корректную цену", "error"); return; }
                  setImportData(prev => prev.map(r => ({ ...r, price: v })));
                }}
              >
                Применить
              </button>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
                  Цена магазина — применить ко всем
                </label>
                <input
                  type="number"
                  className="input"
                  placeholder="0"
                  value={bulkStorePrice}
                  onChange={(e) => setBulkStorePrice(e.target.value)}
                  style={{ width: "100%", height: 36 }}
                />
              </div>
              <button
                className="btn btn-ghost"
                style={{ height: 36 }}
                onClick={() => {
                  const v = parseFloat(bulkStorePrice);
                  if (!isFinite(v) || v < 0) { showToast("Введите корректную цену", "error"); return; }
                  setImportData(prev => prev.map(r => ({ ...r, store_price: v })));
                }}
              >
                Применить
              </button>
            </div>

            <div className="modal-body" style={{ flex: 1, overflowY: "auto", marginTop: 12 }}>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Бренд (Колонка)</th>
                      <th>Артикул</th>
                      <th style={{ textAlign: "right" }}>Цена склада</th>
                      <th style={{ textAlign: "right" }}>Цена магазина</th>
                      <th style={{ textAlign: "center" }}>Кол-во</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importData.slice(0, 100).map((row, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{row.brand}</td>
                        <td style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--accent)" }}>{row.sku}</td>
                        <td style={{ textAlign: "right" }}>
                          <input
                            type="number"
                            className="input"
                            value={row.price ?? ""}
                            placeholder="0"
                            onChange={(e) => {
                              const raw = e.target.value;
                              const v = raw === "" ? undefined : parseFloat(raw);
                              setImportData(prev => prev.map((r, i) => i === idx ? { ...r, price: v === undefined || isNaN(v) ? undefined : v } : r));
                            }}
                            style={{ width: 100, height: 30, textAlign: "right", fontWeight: 600 }}
                          />
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <input
                            type="number"
                            className="input"
                            value={row.store_price ?? ""}
                            placeholder="0"
                            onChange={(e) => {
                              const raw = e.target.value;
                              const v = raw === "" ? null : parseFloat(raw);
                              setImportData(prev => prev.map((r, i) => i === idx ? { ...r, store_price: v === null || isNaN(v as number) ? null : (v as number) } : r));
                            }}
                            style={{ width: 100, height: 30, textAlign: "right", fontWeight: 600 }}
                          />
                        </td>
                        <td style={{ textAlign: "center", fontWeight: 700 }}>1 шт</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {importData.length > 100 && (
                  <div style={{ padding: 16, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    ... и еще {importData.length - 100} товаров. Используйте поля выше для массового задания цен.
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: 8, padding: "16px 24px", borderTop: "1px solid var(--border)" }}>
              <button className="btn btn-ghost" onClick={() => setIsImportModalOpen(false)}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={handleConfirmImport} disabled={importing}>
                {importing ? "Загрузка..." : "Подтвердить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
