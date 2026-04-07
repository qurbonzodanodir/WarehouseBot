"use client";

import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => setMounted(true), []);

  if (!mounted) return null;

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      title={isDark ? "Switch to light" : "Switch to dark"}
      style={{
        background: "transparent",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "5px 8px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--text-muted)",
        transition: "all 0.2s",
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
        (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)";
        (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
      }}
    >
      {isDark ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
}
