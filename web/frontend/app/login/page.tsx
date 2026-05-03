"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(email, password);

      // Seller не имеет доступа к веб-панели
      if (res.user.role === "seller") {
        setError(t("login.err_no_access"));
        return;
      }

      saveAuth(res.user);

      // Warehouse → сразу на заказы, Admin/Owner → дашборд
      if (res.user.role === "warehouse") {
        router.push("/orders");
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t("login.err_auth");
      setError(message || t("login.err_auth"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg)",
        padding: 20,
      }}
    >
      {/* Background glow */}
      <div
        style={{
          position: "fixed",
          top: "20%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 600,
          height: 300,
          background: "radial-gradient(ellipse, var(--accent-muted) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div className="card" style={{ width: "100%", maxWidth: 420, position: "relative" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <h1 style={{ fontSize: "1.5rem", marginBottom: 6 }}>Yasham</h1>
          <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>
            {t("login.subtitle")}
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label
              style={{
                display: "block",
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {t("login.email")}
            </label>
            <input
              className="input"
              type="email"
              placeholder={t("login.email_ph")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label
              style={{
                display: "block",
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {t("login.password")}
            </label>
            <input
              className="input"
              type="password"
              placeholder={t("login.password_ph")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <div
              style={{
                background: "var(--red-muted)",
                border: "1px solid var(--red-muted)",
                borderRadius: 8,
                padding: "10px 14px",
                color: "var(--red)",
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center", padding: "12px 16px", marginTop: 4 }}
          >
            {loading ? (
              <>
                <Loader2 size={16} style={{ animation: "spin 0.7s linear infinite" }} />
                {t("login.loading")}
              </>
            ) : (
              t("login.btn")
            )}
          </button>
        </form>

        <p
          style={{
            textAlign: "center",
            color: "var(--text-muted)",
            fontSize: 11,
            marginTop: 24,
          }}
        >
          {t("login.hint")}
        </p>
      </div>
    </div>
  );
}
