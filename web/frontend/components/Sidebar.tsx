"use client";
import Link from "next/link";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Warehouse,
  DollarSign,
  Settings,
  Users,
  LogOut,
  Menu,
  X,
  Truck,
} from "lucide-react";
import { clearAuth, getStoredUser, onAuthExpired } from "@/lib/auth";
import { api, UserMe } from "@/lib/api";
import { useEffect, useState } from "react";

const ownerNav = [
  { href: "/dashboard", icon: LayoutDashboard, label: "sidebar.dashboard" },
  { href: "/orders", icon: ShoppingCart, label: "sidebar.orders" },
  { href: "/inventory", icon: Warehouse, label: "sidebar.inventory" },
  { href: "/products", icon: Package, label: "sidebar.products" },
  { href: "/finance", icon: DollarSign, label: "sidebar.finance" },
  { href: "/suppliers", icon: Truck, label: "sidebar.suppliers" },
  { href: "/management", icon: Users, label: "sidebar.management" },
  { href: "/settings", icon: Settings, label: "sidebar.settings" },
];

const warehouseNav = [
  { href: "/orders", icon: ShoppingCart, label: "sidebar.requests" },
  { href: "/inventory", icon: Warehouse, label: "sidebar.inventory" },
  { href: "/products", icon: Package, label: "sidebar.products" },
  { href: "/settings", icon: Settings, label: "sidebar.settings" },
];

function getNav(role: string) {
  if (role === "owner" || role === "admin") return ownerNav;
  if (role === "warehouse") return warehouseNav;
  return []; // seller не имеет доступа к веб-панели
}

type Translator = ReturnType<typeof useTranslation>["t"];

function roleBadge(role: string, t: Translator) {
  const map: Record<string, string> = {
    owner: t("sidebar.owner"),
    warehouse: t("sidebar.warehouse"),
    seller: t("sidebar.seller"),
    admin: t("sidebar.admin"),
  };
  return map[role] || role;
}

export default function Sidebar() {
  const { t } = useTranslation();
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserMe | null>(() => getStoredUser());
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;

    api.getMe()
      .then((freshUser) => {
        if (!isMounted) return;
        localStorage.setItem("wh_user", JSON.stringify(freshUser));
        setUser(freshUser);
      })
      .catch(() => {
        return;
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    return onAuthExpired(() => {
      clearAuth();
      router.push("/login");
    });
  }, [router]);

  async function handleLogout() {
    setIsOpen(false);
    try {
      await api.logout();
    } catch {
      // If the session is already gone, local cleanup is still enough.
    }
    clearAuth();
    router.push("/login");
  }

  function handleNavClick() {
    setIsOpen(false);
  }

  function handleRefreshClick() {
    setIsOpen(false);
    router.refresh();
  }

  const nav = getNav(user?.role || "seller");

  return (
    <>
      {/* Mobile Header */}
      <div className="mobile-header">
        <div 
          style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
          onClick={handleRefreshClick}
          title="Обновить страницу"
        >
          <div style={{ fontWeight: 700, fontSize: 18 }}>Yasham</div>
        </div>
        <button onClick={() => setIsOpen(true)} className="mobile-menu-btn" aria-label="Open menu">
          <Menu size={26} />
        </button>
      </div>

      {/* Backdrop Overlay */}
      <div 
        className={`sidebar-overlay ${isOpen ? "open" : ""}`} 
        onClick={() => setIsOpen(false)} 
      />

      {/* Sidebar Drawer */}
      <aside className={`sidebar ${isOpen ? "open" : ""}`}>
        {/* Logo */}
        <div className="sidebar-logo">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
            <div 
              style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
              onClick={handleRefreshClick}
              title="Обновить страницу"
            >
              <div>
                <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-0.5px" }}>Yasham</div>
              </div>
            </div>
            
            <button 
              className="sidebar-close-btn" 
              onClick={() => setIsOpen(false)}
            >
              <X size={20} />
            </button>
          </div>
        </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        <div className="nav-section-title">{t('sidebar.navigation')}</div>
        {nav.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${active ? "active" : ""}`}
              onClick={handleNavClick}
            >
              <Icon className="icon" />
              {t(item.label)}
            </Link>
          );
        })}
      </nav>

      {/* User info */}
      <div
        style={{
          padding: "16px",
          borderTop: "1px solid var(--border)",
          marginTop: "auto",
        }}
      >
        {user && (
          <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{user.name}</div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--text-muted)",
                  marginTop: 2,
                }}
              >
                {roleBadge(user.role, t)}
                {user.store_name ? ` · ${user.store_name}` : ""}
              </div>
            </div>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="btn btn-ghost"
          style={{ width: "100%", justifyContent: "center" }}
        >
          <LogOut size={16} />
          {t('sidebar.logout')}
        </button>
      </div>  
    </aside>
    </>
  );
}
