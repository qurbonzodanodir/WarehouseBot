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

  const [importData, setImportData] = useState<{sku: string, brand: string}[]>([]);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);

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
              <button 
                className="btn"
                style={{ 
                  background: "#dc3545", 
                  color: "white", 
                  border: "none", 
                  height: "fit-content", 
                  padding: "10px 16px" 
                }}
                onClick={() => {
                  if (confirm("⚠️ ВНИМАНИЕ! Это удалит ВСЕ товары из ВСЕХ магазинов! Восстановить будет невозможно. Продолжить?")) {
                    api.clearInventory().then(() => {
                      showToast("✅ Все товары удалены. Теперь можно загружать новые данные из Excel", "success");
                      // Refresh data
                      if (selectedStore) {
                        api.getInventory(selectedStore, currentPage, pageSize).then((data) => {
                          setItems(data.items);
                          setTotalItems(data.total);
                          setTotalPages(data.total_pages);
                        });
                      } else {
                        api.getStoreCatalog().then(setCatalog);
                      }
                    }).catch((error) => {
                      showToast(error instanceof Error ? error.message : "Ошибка при удалении товаров", "error");
                    });
                  }
                }}
              >
                <Database size={18} style={{ marginRight: 8 }} />
                Удалить все товары
              </button>
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
                      const brandsRow = data[0];
                      const brandsMap: Record<number, string> = {};
                      for (let i = 0; i < brandsRow.length; i++) {
                        if (brandsRow[i]) {
                          let brandName = String(brandsRow[i]).trim();
                          // Fix Excel removing leading zeros in brand headers (e.g. "o53" → "053")
                          const replacedBrand = brandName.replace(/[oO]/g, '0');
                          if (/^\d+$/.test(replacedBrand)) {
                            brandName = replacedBrand;
                          }
                          brandsMap[i] = brandName;
                        }
                      }
                      const parsed: {sku: string, brand: string}[] = [];
                      for (let r = 1; r < data.length; r++) {
                        for (let c = 0; c < data[r].length; c++) {
                          if (brandsMap[c] && data[r][c]) {
                            let sku = String(data[r][c]).trim();
                            // Only replace o/O with 0 if the whole SKU becomes numeric
                            // (keeps SKU length as-is; does NOT add leading zeros)
                            const replaced = sku.replace(/[oO]/g, '0');
                            if (/^\d+$/.test(replaced)) {
                              sku = replaced;
                            }
                            if (sku && !sku.toLowerCase().includes("пример") && sku.toLowerCase() !== "sku") {
                              parsed.push({ sku, brand: brandsMap[c] });
                            }
                          }
                        }
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
          {/* Store pill-chips */}
          <div className="store-chips-scroll" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button
              type="button"
              onClick={() => setSelectedStore(null)}
              style={{
                padding: "8px 14px",
                borderRadius: 999,
                border: selectedStore === null ? "1px solid var(--accent)" : "1px solid var(--border)",
                background: selectedStore === null ? "var(--accent)" : "transparent",
                color: selectedStore === null ? "#fff" : "var(--text-primary)",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.15s",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Boxes size={14} /> {t("inventory.all_stores")}
            </button>
            {stores.map((store) => {
              const active = selectedStore === store.id;
              return (
                <button
                  key={store.id}
                  type="button"
                  onClick={() => setSelectedStore(store.id)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 999,
                    border: active ? "1px solid var(--accent)" : "1px solid var(--border)",
                    background: active ? "var(--accent)" : "transparent",
                    color: active ? "#fff" : "var(--text-primary)",
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: "pointer",
                    transition: "all 0.15s",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <StoreIcon size={14} />
                  <span style={{ maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {store.name}
                  </span>
                  {store.total_items && store.total_items > 0 ? (
                    <span
                      style={{
                        padding: "2px 7px",
                        borderRadius: 999,
                        background: active ? "rgba(255,255,255,0.25)" : "var(--bg-card)",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {fmt(store.total_items)}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>

          {/* Search input (only when a store is selected) */}
          {selectedStore && (
            <div className="input-group" style={{ maxWidth: 480, position: "relative" }}>
              <Search size={18} style={{ color: "var(--text-secondary)" }} />
              <input
                type="text"
                className="input"
                placeholder={t("inventory.search_placeholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingRight: search ? 34 : undefined }}
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
            // Store cards view for "All stores"
            <div className="store-card-grid">
              {catalog.map((store) => (
                <div 
                  key={store.id}
                  className="card store-card"
                  style={{ cursor: "pointer" }}
                  onClick={() => {
                    setSelectedStore(store.id);
                    setCurrentPage(1);
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <StoreIcon size={18} style={{ color: "var(--accent)" }} />
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
                      {store.name}
                    </h3>
                  </div>
                  
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 2 }}>
                        Товаров
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>
                        {fmt(store.total_items)}
                      </div>
                    </div>
                    
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 2 }}>
                        Стоимость
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: "var(--accent)" }}>
                        {fmt(store.total_value)} TJS
                      </div>
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
                    <th style={{ width: "50px" }}>№</th>
                    <th>{t("inventory.col_sku")}</th>
                    <th>Фирма</th>
                    <th style={{ textAlign: "center" }}>{t("inventory.col_qty")}</th>
                    <th style={{ textAlign: "center" }}>{t("inventory.col_status")}</th>
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
                      <td data-label={t("inventory.col_status")} style={{ textAlign: "center" }}>
                        <span className={`badge ${item.quantity > 5 ? 'badge-delivered' : 'badge-pending'}`}>
                          {item.quantity > 5 ? t("inventory.status_in_stock") : t("inventory.status_low")}
                        </span>
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
        <div className="modal-overlay" onClick={() => setIsImportModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: 600, width: "100%", maxHeight: "90vh", display: "flex", flexDirection: "column" }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Database size={20} /> Предпросмотр: Витрина
              </h3>
              <button className="btn-close" onClick={() => setIsImportModalOpen(false)}>
                <X size={20} />
              </button>
            </div>
            
            <div style={{ padding: "0 24px", color: "var(--text-secondary)", fontSize: 14 }}>
              Будет загружено: <strong style={{color:"var(--text-primary)"}}>{importData.length}</strong> артикулов по 1 шт на выбранную витрину.
            </div>

            <div className="modal-body" style={{ flex: 1, overflowY: "auto", marginTop: 12 }}>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Бренд (Колонка)</th>
                      <th>Артикул</th>
                      <th style={{ textAlign: "center" }}>Кол-во</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importData.slice(0, 100).map((row, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{row.brand}</td>
                        <td style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--accent)" }}>{row.sku}</td>
                        <td style={{ textAlign: "center", fontWeight: 700 }}>1 шт</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {importData.length > 100 && (
                  <div style={{ padding: 16, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    ... и еще {importData.length - 100} товаров.
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
