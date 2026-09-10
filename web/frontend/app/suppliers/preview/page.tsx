"use client";

/**
 * PREVIEW ONLY — standalone mock, no auth/API/Sidebar.
 * Open: http://localhost:3000/suppliers/preview
 */
import React, { useMemo, useState } from "react";

type Side = "receivable" | "payable";

type TimelineItem = {
  id: string;
  date: string;
  label: string;
  qty?: string;
  amount: number;
};

const MOCK = [
  {
    id: 2,
    name: "Бахром",
    contact: "—",
    receivable: 0,
    payable: 0,
    receivableTimeline: [
      { id: "r1", date: "16.06.2026", label: "Отдали товар", qty: "1 шт.", amount: 115 },
      { id: "r2", date: "16.06.2026", label: "Отдали товар", qty: "1 шт.", amount: 115 },
      { id: "r3", date: "16.06.2026", label: "Отдали товар", qty: "1 шт.", amount: 115 },
      { id: "r4", date: "15.06.2026", label: "Оплата от партнёра", amount: -230 },
      { id: "r5", date: "15.06.2026", label: "Оплата от партнёра", amount: -115 },
      { id: "r6", date: "10.09.2026", label: "Закрытие долга", amount: -1955 },
    ] as TimelineItem[],
    payableTimeline: [
      { id: "p1", date: "16.06.2026", label: "Приняли товар", qty: "2 шт.", amount: 228 },
      { id: "p2", date: "16.06.2026", label: "Наша оплата", amount: -228 },
    ] as TimelineItem[],
  },
  {
    id: 1,
    name: "Ширин",
    contact: "—",
    receivable: 0,
    payable: 0,
    receivableTimeline: [
      { id: "s1", date: "12.06.2026", label: "Отдали товар", qty: "3 шт.", amount: 345 },
      { id: "s2", date: "10.09.2026", label: "Закрытие долга", amount: -345 },
    ] as TimelineItem[],
    payableTimeline: [] as TimelineItem[],
  },
];

function fmt(n: number) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n);
}

const css = {
  page: {
    minHeight: "100vh",
    background: "#0f1117",
    color: "#e8eaf0",
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    padding: "24px clamp(16px, 3vw, 40px) 48px",
  } as React.CSSProperties,
  banner: {
    marginBottom: 18,
    padding: "12px 14px",
    borderRadius: 12,
    border: "1px dashed #3a4054",
    background: "#171a22",
    color: "#a8b0c4",
    fontSize: 13,
  } as React.CSSProperties,
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 16,
    marginBottom: 22,
    flexWrap: "wrap",
  } as React.CSSProperties,
  title: { margin: 0, fontSize: 28, fontWeight: 750, letterSpacing: "-0.02em" } as React.CSSProperties,
  subtitle: { margin: "6px 0 0", color: "#8b93a7", fontSize: 14, maxWidth: 560 } as React.CSSProperties,
  primaryBtn: {
    border: "none",
    borderRadius: 12,
    background: "#5b8def",
    color: "#fff",
    padding: "11px 16px",
    fontWeight: 650,
    fontSize: 14,
    cursor: "pointer",
  } as React.CSSProperties,
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 12,
    marginBottom: 18,
  } as React.CSSProperties,
  kpi: {
    background: "#171a22",
    border: "1px solid #2a2f3d",
    borderRadius: 14,
    padding: "16px 18px",
  } as React.CSSProperties,
  layout: {
    display: "grid",
    gridTemplateColumns: "minmax(240px, 320px) 1fr",
    gap: 14,
    alignItems: "start",
  } as React.CSSProperties,
  card: {
    background: "#171a22",
    border: "1px solid #2a2f3d",
    borderRadius: 16,
    overflow: "hidden",
  } as React.CSSProperties,
  muted: { color: "#8b93a7", fontSize: 12 } as React.CSSProperties,
  ghostBtn: {
    border: "1px solid #2a2f3d",
    borderRadius: 10,
    background: "transparent",
    color: "#e8eaf0",
    height: 38,
    padding: "0 12px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  } as React.CSSProperties,
};

export default function PartnersPreviewPage() {
  const [selectedId, setSelectedId] = useState(2);
  const [side, setSide] = useState<Side>("receivable");
  const selected = useMemo(() => MOCK.find((p) => p.id === selectedId) || MOCK[0], [selectedId]);

  const actions =
    side === "receivable"
      ? ["Отдать товар", "Принять оплату", "Принять возврат"]
      : ["Принять товар", "Оплатить", "Вернуть товар"];

  const timeline = side === "receivable" ? selected.receivableTimeline : selected.payableTimeline;

  return (
    <div style={css.page}>
      <div style={css.banner}>
        <strong style={{ color: "#fff" }}>PREVIEW</strong>
        {" — новый дизайн Партнёров. Прод не изменён. Если ок — перенесём на /suppliers."}
      </div>

      <div style={css.header}>
        <div>
          <h1 style={css.title}>Партнёры</h1>
          <p style={css.subtitle}>
            Контрагенты, которым мы отдаём товар и у которых можем принимать товар.
          </p>
        </div>
        <button type="button" style={css.primaryBtn}>
          + Добавить партнёра
        </button>
      </div>

      <div style={css.kpiGrid} className="preview-kpi">
        {[
          ["Всего партнёров", "2"],
          ["Нам должны", "0 TJS"],
          ["Мы должны", "0 TJS"],
        ].map(([label, value]) => (
          <div key={label} style={css.kpi}>
            <div style={css.muted}>{label}</div>
            <div style={{ marginTop: 6, fontSize: 22, fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={css.layout} className="preview-layout">
        <section style={css.card}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #2a2f3d", fontWeight: 700, fontSize: 13 }}>
            Список партнёров
          </div>
          {MOCK.map((p) => {
            const active = p.id === selected.id;
            const net = p.receivable - p.payable;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedId(p.id)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  border: "none",
                  borderBottom: "1px solid #2a2f3d",
                  background: active ? "#1d2230" : "transparent",
                  color: "#e8eaf0",
                  padding: "14px 16px",
                  cursor: "pointer",
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: "rgba(91,141,239,0.15)",
                    color: "#5b8def",
                    display: "grid",
                    placeItems: "center",
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {p.name[0]}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{p.name}</div>
                  <div style={{ ...css.muted, marginTop: 2 }}>
                    Баланс {net >= 0 ? "+" : "−"}
                    {fmt(Math.abs(net))} TJS
                  </div>
                </div>
                <span style={{ color: "#8b93a7" }}>{active ? "▾" : "›"}</span>
              </button>
            );
          })}
        </section>

        <section style={{ ...css.card, minHeight: 520 }}>
          <div
            style={{
              padding: "18px 20px",
              borderBottom: "1px solid #2a2f3d",
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div>
              <h2 style={{ margin: 0, fontSize: 20 }}>{selected.name}</h2>
              <div style={{ ...css.muted, marginTop: 4, fontSize: 13 }}>Контакт: {selected.contact}</div>
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <div style={{ padding: "8px 12px", borderRadius: 10, background: "#1d2230", minWidth: 120 }}>
                <div style={css.muted}>Нам должны</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#3ecf8e" }}>{fmt(selected.receivable)} TJS</div>
              </div>
              <div style={{ padding: "8px 12px", borderRadius: 10, background: "#1d2230", minWidth: 120 }}>
                <div style={css.muted}>Мы должны</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#f07178" }}>{fmt(selected.payable)} TJS</div>
              </div>
            </div>
          </div>

          <div style={{ padding: "14px 16px 0" }}>
            <div style={{ display: "inline-flex", gap: 4, padding: 4, borderRadius: 12, background: "#1d2230" }}>
              {(
                [
                  ["receivable", "Он должен нам"],
                  ["payable", "Мы должны ему"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSide(key)}
                  style={{
                    border: "none",
                    borderRadius: 9,
                    padding: "8px 14px",
                    fontSize: 13,
                    fontWeight: 650,
                    cursor: "pointer",
                    background: side === key ? "#171a22" : "transparent",
                    color: side === key ? "#e8eaf0" : "#8b93a7",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {actions.map((label) => (
                <button key={label} type="button" style={css.ghostBtn}>
                  {label}
                </button>
              ))}
            </div>

            <div style={{ border: "1px solid #2a2f3d", borderRadius: 14, background: "#12151c", padding: "8px 14px 10px" }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "#8b93a7",
                  textTransform: "uppercase",
                  letterSpacing: 0.4,
                  padding: "8px 4px 10px",
                }}
              >
                История операций
              </div>
              {timeline.length === 0 ? (
                <div style={{ padding: "28px 8px", textAlign: "center", color: "#8b93a7", fontSize: 13 }}>
                  Пока нет операций
                </div>
              ) : (
                timeline.map((item, idx) => (
                  <div
                    key={item.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "88px 1fr auto",
                      gap: 12,
                      alignItems: "center",
                      padding: "12px 4px",
                      borderBottom: idx === timeline.length - 1 ? "none" : "1px solid #2a2f3d",
                    }}
                  >
                    <span style={{ fontSize: 12, color: "#8b93a7" }}>{item.date}</span>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 650 }}>{item.label}</div>
                      {item.qty ? <div style={{ fontSize: 12, color: "#8b93a7", marginTop: 2 }}>{item.qty}</div> : null}
                    </div>
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: item.amount > 0 ? "#3ecf8e" : "#a8b0c4",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.amount > 0 ? "+" : ""}
                      {fmt(item.amount)} TJS
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .preview-layout { grid-template-columns: 1fr !important; }
          .preview-kpi { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
