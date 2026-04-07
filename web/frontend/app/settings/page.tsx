"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { isAuthenticated } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useTheme } from "next-themes";
import { Sun, Moon, Globe, Palette, ChevronRight, Monitor } from "lucide-react";

export default function SettingsPage() {
  const router = useRouter();
  const { t, lang, setLang } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!isAuthenticated()) { router.push("/login"); return; }
  }, []);

  if (!mounted) return null;

  const isDark = theme === "dark";

  const themeOptions = [
    {
      id: "light",
      icon: <Sun size={22} />,
      label: "settings.themes.light",
      desc: "settings.themes.light_desc",
    },
    {
      id: "dark",
      icon: <Moon size={22} />,
      label: "settings.themes.dark",
      desc: "settings.themes.dark_desc",
    },
    {
      id: "system",
      icon: <Monitor size={22} />,
      label: "settings.themes.system",
      desc: "settings.themes.system_desc",
    },
  ];

  const langOptions = [
    { id: "ru", flag: "🇷🇺", label: "Русский", native: "Русский" },
    { id: "tj", flag: "🇹🇯", label: "Тоҷикӣ", native: "Тоҷикӣ" },
  ];

  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main className="main-layout">
        <div className="page-header">
          <div>
            <h1 className="page-title">{t("settings.title")}</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 2 }}>
              {t("settings.subtitle")}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 640 }}>

          {/* Theme section */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{
              padding: "16px 20px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: "var(--accent-muted)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Palette size={18} color="var(--accent)" />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{t("settings.theme")}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 1 }}>
                  {t("settings.theme_select")}
                </div>
              </div>
            </div>

            <div style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {themeOptions.map((opt) => {
                  const active = theme === opt.id;
                  return (
                    <button
                      key={opt.id}
                      onClick={() => setTheme(opt.id)}
                      style={{
                        flex: "1 1 140px",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 10,
                        padding: "18px 12px",
                        borderRadius: 12,
                        border: active ? "2px solid var(--accent)" : "2px solid var(--border)",
                        background: active ? "var(--accent-muted)" : "var(--bg)",
                        cursor: "pointer",
                        transition: "all 0.2s",
                        color: active ? "var(--accent)" : "var(--text-secondary)",
                      }}
                    >
                      <div style={{
                        width: 48, height: 48,
                        borderRadius: 12,
                        background: active ? "rgba(108,99,255,0.15)" : "var(--bg-hover)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        transition: "background 0.2s",
                      }}>
                        {opt.icon}
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontWeight: active ? 700 : 500, fontSize: 13 }}>
                          {t(opt.label)}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 3 }}>
                          {t(opt.desc)}
                        </div>
                      </div>
                      {active && (
                        <div style={{
                          width: 8, height: 8, borderRadius: "50%",
                          background: "var(--accent)",
                        }} />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Language section */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{
              padding: "16px 20px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: "var(--accent-muted)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Globe size={18} color="var(--accent)" />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{t("settings.language")}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 1 }}>
                  {t("settings.lang_desc")}
                </div>
              </div>
            </div>

            <div style={{ padding: "12px 20px" }}>
              {langOptions.map((opt, i) => {
                const active = lang === opt.id;
                return (
                  <div
                    key={opt.id}
                    onClick={() => setLang(opt.id as "ru" | "tj")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: "14px 0",
                      borderBottom: i < langOptions.length - 1 ? "1px solid var(--border)" : "none",
                      cursor: "pointer",
                      transition: "opacity 0.2s",
                    }}
                  >
                    <span style={{ fontSize: 26 }}>{opt.flag}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: active ? 700 : 500, fontSize: 14, color: active ? "var(--text-primary)" : "var(--text-secondary)" }}>
                        {opt.label}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                        {opt.native}
                      </div>
                    </div>
                    <div style={{
                      width: 22, height: 22, borderRadius: "50%",
                      border: `2px solid ${active ? "var(--accent)" : "var(--border)"}`,
                      background: active ? "var(--accent)" : "transparent",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      transition: "all 0.2s",
                      flexShrink: 0,
                    }}>
                      {active && (
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#fff" }} />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Info */}
          <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", marginTop: 12 }}>
            {t("settings.auto_save")}
          </p>
        </div>
      </main>
    </div>
  );
}
