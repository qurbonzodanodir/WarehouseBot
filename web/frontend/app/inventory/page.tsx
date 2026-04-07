"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Store, InventoryItem, StoreCatalogCard } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { Package, Search, Store as StoreIcon, DollarSign, Boxes } from "lucide-react";

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
  }, []);

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

  const isWarehouse = stores.find(s => s.id === selectedStore)?.store_type === "warehouse";

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        <div className="page-header">
          <div>
            <h1 className="page-title">{t("inventory.title")}</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 2 }}>
              {t("inventory.found", { count: totalItems })}
            </p>
          </div>
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
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: "rgba(108,99,255,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <StoreIcon size={20} color="var(--accent)" />
                    </div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: 15 }}>{store.name}</h3>
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
                        <td style={{ fontWeight: 700, color: "var(--accent)", fontFamily: "monospace", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                          {item.product_sku}
                          {item.is_display && (
                            <span className="badge badge-pending" style={{ fontSize: 10, padding: "2px 6px" }}>
                              {t("inventory.is_display")}
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: "center", fontWeight: 700, fontSize: 16 }}>
                          {item.quantity}
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <span className={item.quantity > 10 ? "badge badge-delivered" : item.quantity > 0 ? "badge badge-pending" : "badge badge-rejected"}>
                            {item.quantity > 10 ? t("inventory.status_in_stock") : item.quantity > 0 ? t("inventory.status_low") : t("inventory.status_no")}
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
    </div>
  );
}
