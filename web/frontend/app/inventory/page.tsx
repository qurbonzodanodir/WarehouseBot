"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Store, InventoryItem, StoreCatalogCard } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { Package, Search, Store as StoreIcon, DollarSign, Boxes, Warehouse, Database, X } from "lucide-react";
import * as XLSX from "xlsx";

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
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

  const [catalog, setCatalog] = useState<StoreCatalogCard[]>([]);
  const [userRole, setUserRole] = useState<string>("seller");

  const [importData, setImportData] = useState<{sku: string, brand: string}[]>([]);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    const user = getStoredUser();
    if (!isAuthenticated() || !user) { router.push("/login"); return; }
    setUserRole(user.role);
    api.getStores().then((data) => {
      const visibleStores = user.role === "seller"
        ? data.filter((s) => s.id === user.store_id)
        : data;
      setStores(visibleStores);
      // For owner/warehouse default to all stores (null), for seller default to their store
      if (user.role === "seller" && visibleStores.length > 0) {
        setSelectedStore(visibleStores[0].id);
      } else {
        setSelectedStore(null);
      }
    });
  }, [router]);

  useEffect(() => {
    setLoading(true);
    if (!selectedStore) {
      api.getStoreCatalog()
        .then(setCatalog)
        .catch(console.error)
        .finally(() => setLoading(false));
      setItems([]);
    } else {
      api.getInventory(selectedStore)
        .then(setItems)
        .catch(console.error)
        .finally(() => setLoading(false));
      setCatalog([]);
    }
  }, [selectedStore]);

  const handleConfirmImport = async () => {
    if (!selectedStore || importData.length === 0) return;
    setImporting(true);
    try {
      const res = await api.importVitrina(selectedStore, importData);
      showToast(`✅ Загружено успешно! Фирм: ${new Set(importData.map(d=>d.brand)).size}, Артикулов: ${importData.length}. Сохранено новых: ${res.created}, обновлено на витрине: ${res.added_qty}`, "success");
      setIsImportModalOpen(false);
      setImportData([]);
      api.getInventory(selectedStore).then(setItems);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Ошибка сохранения", "error");
    } finally {
      setImporting(false);
    }
  };

  const mergedItems = useMemo(() => {
    const byProduct = new Map<number, InventoryItem>();
    for (const item of items) {
      const existing = byProduct.get(item.product_id);
      if (existing) {
        existing.quantity += item.quantity;
        existing.is_display = false;
      } else {
        byProduct.set(item.product_id, {
          product_id: item.product_id,
          product_sku: item.product_sku,
          quantity: item.quantity,
          is_display: !!item.is_display,
        });
      }
    }
    return Array.from(byProduct.values());
  }, [items]);

  const filtered = mergedItems.filter((i) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return i.product_sku.toLowerCase().includes(q);
  });

  const totalItems = selectedStore ? filtered.reduce((s, i) => s + i.quantity, 0) : catalog.reduce((s, c) => s + c.total_items, 0);

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
              {t("inventory.found", { count: totalItems })}
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
                      const brandsRow = data[0];
                      const brandsMap: Record<number, string> = {};
                      for (let i = 0; i < brandsRow.length; i++) {
                        if (brandsRow[i]) brandsMap[i] = String(brandsRow[i]).trim();
                      }
                      const parsed: {sku: string, brand: string}[] = [];
                      for (let r = 1; r < data.length; r++) {
                        for (let c = 0; c < data[r].length; c++) {
                          if (brandsMap[c] && data[r][c]) {
                            let sku = String(data[r][c]).trim();
                            // Fix Excel removing leading zeros: handle o/oo prefix and pad numeric SKUs
                            if (sku.startsWith('oo') && /^\d+$/.test(sku.slice(2))) {
                              sku = '00' + sku.slice(2);
                            } else if (sku.startsWith('o') && /^\d+$/.test(sku.slice(1))) {
                              sku = '0' + sku.slice(1);
                            } else if (/^\d+$/.test(sku) && sku.length < 5) {
                              sku = sku.padStart(5, '0');
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
                onClick={() => {
                  if (!selectedStore) {
                    showToast("Сначала выберите магазин!", "error");
                    return;
                  }
                  document.getElementById("csv-upload")?.click();
                }}
              >
                <Database size={16} /> Загрузить Excel
              </button>
            </div>
          )}
        </div>


        {/* Store selector */}
        <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
          <div style={{ display: "flex", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
            {userRole !== "seller" && (
              <button
                onClick={() => setSelectedStore(null)}
                style={{
                  padding: "9px 16px",
                  fontSize: 13,
                  fontWeight: 500,
                  border: "none",
                  cursor: "pointer",
                  background: selectedStore === null ? "var(--accent)" : "transparent",
                  color: selectedStore === null ? "#fff" : "var(--text-secondary)",
                  transition: "all 0.15s",
                }}
              >
                {t("orders.all_stores")}
              </button>
            )}
            {stores.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedStore(s.id)}
                style={{
                  padding: "9px 16px",
                  fontSize: 13,
                  fontWeight: 500,
                  border: "none",
                  cursor: "pointer",
                  background: selectedStore === s.id ? "var(--accent)" : "transparent",
                  color: selectedStore === s.id ? "#fff" : "var(--text-secondary)",
                  transition: "all 0.15s",
                }}
              >
                {s.name}
              </button>
            ))}
          </div>

          <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
            <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
            <input
              className="input"
              style={{ paddingLeft: 36 }}
              placeholder={t("inventory.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {selectedStore === null ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 20 }}>
            {loading ? (
              <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "center", padding: 60 }}>
                <div className="spinner" />
              </div>
            ) : catalog.length === 0 ? (
              <div className="card empty-state" style={{ gridColumn: "1 / -1" }}>
                <StoreIcon size={40} style={{ margin: "0 auto 12px", opacity: 0.3 }} />
                {t("management.no_stores")}
              </div>
            ) : (
              catalog.map((store) => (
                <div key={store.id} className="card" style={{ padding: 20, cursor: "pointer", transition: "transform 0.2s" }} onClick={() => setSelectedStore(store.id)}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                    <StoreIcon size={24} style={{ color: "var(--accent)" }} />
                    <div>
                      <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{store.name}</h3>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{store.address || "—"}</div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 16 }}>
                    <div style={{ flex: 1, background: "var(--bg)", padding: "12px 14px", borderRadius: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-secondary)", fontSize: 11, textTransform: "uppercase", marginBottom: 4 }}>
                        <Boxes size={14} /> {t("inventory.goods_label")}
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 700 }}>{fmt(store.total_items)} {t("products.pcs")}</div>
                    </div>
                    <div style={{ flex: 1, background: "var(--bg)", padding: "12px 14px", borderRadius: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-secondary)", fontSize: 11, textTransform: "uppercase", marginBottom: 4 }}>
                        <DollarSign size={14} /> {t("inventory.assets_label")}
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--accent)" }}>{fmt(store.total_value)} TJS</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            {loading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
                <div className="spinner" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="empty-state">
                <Package size={40} style={{ margin: "0 auto 12px", opacity: 0.3 }} />
                {t("inventory.empty")}
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t("inventory.col_sku")}</th>
                      <th style={{ textAlign: "center" }}>{t("inventory.col_qty")}</th>
                      <th style={{ textAlign: "center" }}>{t("inventory.col_status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((item) => (
                      <tr key={item.product_id}>
                        <td data-label={t("inventory.col_sku")} style={{ fontWeight: 700, color: "var(--accent)", fontFamily: "monospace", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                          {item.product_sku}
                          {item.is_display && (
                            <span className="badge badge-pending" style={{ fontSize: 10, padding: "2px 6px" }}>
                              {t("inventory.is_display")}
                            </span>
                          )}
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
              </div>
            )}
          </div>
        )}
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

            <div className="modal-footer" style={{ borderTop: "1px solid var(--border)", paddingTop: 16, marginTop: 16 }}>
              <button className="btn btn-ghost" onClick={() => setIsImportModalOpen(false)} disabled={importing}>Отмена</button>
              <button className="btn btn-primary" onClick={handleConfirmImport} disabled={importing}>
                {importing ? <div className="spinner" style={{width: 16, height: 16}} /> : "Подтвердить и загрузить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
