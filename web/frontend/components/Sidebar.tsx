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
  BoxIcon,
  Menu,
  X,
} from "lucide-react";
import { clearAuth, getStoredUser } from "@/lib/auth";
import { UserMe } from "@/lib/api";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";

const ownerNav = [
  { href: "/dashboard", icon: LayoutDashboard, label: "sidebar.dashboard" },
  { href: "/orders", icon: ShoppingCart, label: "sidebar.orders" },
  { href: "/inventory", icon: Warehouse, label: "sidebar.inventory" },
  { href: "/products", icon: Package, label: "sidebar.products" },
  { href: "/finance", icon: DollarSign, label: "sidebar.finance" },
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

function roleBadge(role: string, t: any) {
  const map: Record<string, string> = {
    owner: t("sidebar.owner"),
    warehouse: t("sidebar.warehouse"),
    seller: t("sidebar.seller"),
    admin: t("sidebar.admin"),
  };
  return map[role] || role;
}

export default function Sidebar() {
  const { t, lang, setLang } = useTranslation();
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserMe | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  // Close sidebar on navigation (path changes)
  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  useEffect(() => {
    setUser(getStoredUser());
  }, []);

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  const nav = getNav(user?.role || "seller");

  return (
    <>
      {/* Mobile Header */}
      <div className="mobile-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <BoxIcon size={18} color="#fff" />
          </div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>Warehouse</div>
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
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  background: "var(--accent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <BoxIcon size={20} color="#fff" />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>Warehouse</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>ERP System</div>
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
