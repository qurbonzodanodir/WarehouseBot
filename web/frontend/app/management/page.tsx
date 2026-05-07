"use client";
import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, Store, Employee, Invite, Brand, UserMe } from "@/lib/api";
import { isAuthenticated, getStoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n/LanguageContext";
import { useToast } from "@/lib/ToastContext";
import { Users, StoreIcon, Plus, UserPlus, Search, MapPin, Shield, UserCircle2, ArrowRight, Copy, Trash2, Clock, Key, RotateCcw, RefreshCw } from "lucide-react";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export default function ManagementPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<number | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loadingStores, setLoadingStores] = useState(true);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [storeSearch, setStoreSearch] = useState("");

  const [storeFormOpen, setStoreFormOpen] = useState(false);
  const [editingStoreId, setEditingStoreId] = useState<number | null>(null);
  const [storeForm, setStoreForm] = useState({ name: "", address: "" });

  const [empFormOpen, setEmpFormOpen] = useState(false);
  const [editingEmployeeId, setEditingEmployeeId] = useState<number | null>(null);
  const [empForm, setEmpForm] = useState({ name: "", role: "seller" });

  const [invites, setInvites] = useState<Invite[]>([]);
  const [loadingInvites, setLoadingInvites] = useState(false);
  const [inviteFormOpen, setInviteFormOpen] = useState(false);
  const [newInviteRole, setNewInviteRole] = useState("seller");
  const [showInactiveEmployees, setShowInactiveEmployees] = useState(false);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandForm, setBrandForm] = useState("");
  const [editingBrandId, setEditingBrandId] = useState<number | null>(null);
  const [showAllStores, setShowAllStores] = useState(false);

  const [user, setUser] = useState<UserMe | null>(null);
  const [mounted, setMounted] = useState(false);
  const isOwner = user?.role === "owner";
  const selectedStore = stores.find(s => s.id === selectedStoreId) ?? null;
  const isSelectedWarehouse = selectedStore?.store_type === "warehouse";
  const allowedRole = isSelectedWarehouse ? "warehouse" : "seller";
  const allowedRoleOptions = isSelectedWarehouse
    ? [{ value: "warehouse", label: t("sidebar.warehouse") }]
    : [{ value: "seller", label: t("sidebar.seller") }];


  const fetchStores = useCallback(async () => {
    setLoadingStores(true);
    try {
      const data = await api.getStores();
      setStores(data);
      if (data.length > 0 && !selectedStoreId) {
        setSelectedStoreId(data[0].id);
      }
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setLoadingStores(false);
    }
  }, [selectedStoreId, showToast, t]);

  const fetchEmployees = useCallback(async (storeId: number) => {
    setLoadingEmployees(true);
    try {
      const data = await api.getStoreEmployees(storeId, showInactiveEmployees);
      setEmployees(data);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setLoadingEmployees(false);
    }
  }, [showInactiveEmployees, showToast, t]);

  const fetchInvites = useCallback(async (storeId: number) => {
    setLoadingInvites(true);
    try {
      const data = await api.getInvites(storeId);
      setInvites(data);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    } finally {
      setLoadingInvites(false);
    }
  }, [showToast, t]);

  const fetchBrands = useCallback(async () => {
    try {
      const data = await api.getBrands();
      setBrands(data);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }, [showToast, t]);

  useEffect(() => {
    setMounted(true);
    const storedUser = getStoredUser();
    setUser(storedUser);
    
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    if (storedUser && storedUser.role !== "owner") {
      router.push("/dashboard");
      return;
    }
    void fetchStores();
    void fetchBrands();
  }, [router, fetchBrands, fetchStores]);

  useEffect(() => {
    if (selectedStoreId) {
      fetchEmployees(selectedStoreId);
      fetchInvites(selectedStoreId);
      setEmpForm((prev) => ({ ...prev, role: allowedRole }));
      setNewInviteRole(allowedRole);
    } else {
      setEmployees([]);
      setInvites([]);
    }
  }, [selectedStoreId, showInactiveEmployees, fetchEmployees, fetchInvites, allowedRole]);

  async function handleCreateInvite() {
    if (!selectedStoreId) return;
    try {
      await api.createInvite({ store_id: selectedStoreId, role: newInviteRole });
      showToast(t("management.toast_invite_created"), "success");
      setInviteFormOpen(false);
      fetchInvites(selectedStoreId);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleDeleteInvite(code: string) {
    if (!confirm(t("management.confirm_delete_invite"))) return;
    try {
      await api.deleteInvite(code);
      showToast(t("management.toast_invite_deleted"), "success");
      if (selectedStoreId) fetchInvites(selectedStoreId);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    showToast(t("management.toast_copied"), "success");
  };

  function openStoreForm(store?: Store) {
    if (store) {
      setEditingStoreId(store.id);
      setStoreForm({ name: store.name, address: store.address || "" });
    } else {
      setEditingStoreId(null);
      setStoreForm({ name: "", address: "" });
    }
    setStoreFormOpen(true);
  }

  function openEmpForm(emp?: Employee) {
    if (emp) {
      setEditingEmployeeId(emp.id);
      setEmpForm({ name: emp.name, role: emp.role === allowedRole ? emp.role : allowedRole });
    } else {
      setEditingEmployeeId(null);
      setEmpForm({ name: "", role: allowedRole });
    }
    setEmpFormOpen(true);
  }

  async function handleSubmitStore(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingStoreId) {
        await api.updateStore(editingStoreId, storeForm);
      } else {
        await api.createStore(storeForm);
      }
      setStoreFormOpen(false);
      setStoreForm({ name: "", address: "" });
      await fetchStores();
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleSubmitEmployee(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedStoreId && !editingEmployeeId) return;
    try {
      if (editingEmployeeId) {
        await api.updateEmployee(editingEmployeeId, { name: empForm.name, role: empForm.role });
      } else {
        await api.createEmployee(selectedStoreId!, { name: empForm.name, role: empForm.role });
      }
      setEmpFormOpen(false);
      setEmpForm({ name: "", role: "seller" });
      if (selectedStoreId) await fetchEmployees(selectedStoreId);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleDeleteEmployee(empId: number) {
    if (!confirm("Вы уверены, что хотите удалить этого сотрудника?")) return;
    try {
      await api.deleteEmployee(empId);
      showToast("Сотрудник успешно удален", "success");
      if (selectedStoreId) await fetchEmployees(selectedStoreId);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleRestoreEmployee(empId: number) {
    try {
      await api.restoreEmployee(empId);
      showToast("Сотрудник восстановлен", "success");
      if (selectedStoreId) await fetchEmployees(selectedStoreId);
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleSubmitBrand(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingBrandId) {
        await api.updateBrand(editingBrandId, { name: brandForm });
      } else {
        await api.createBrand({ name: brandForm });
      }
      setBrandForm("");
      setEditingBrandId(null);
      await fetchBrands();
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  async function handleDeleteBrand(id: number) {
    if (!confirm(t("management.brand_delete_confirm"))) return;
    try {
      await api.deleteBrand(id);
      showToast(t("management.brand_deleted"), "success");
      await fetchBrands();
    } catch (error) {
      showToast(getErrorMessage(error, t("common.error")), "error");
    }
  }

  function roleBadge(role: string) {
    const map: Record<string, string> = {
      owner: t("sidebar.owner"),
      warehouse: t("sidebar.warehouse"),
      seller: t("sidebar.seller"),
      admin: t("sidebar.admin"),
    };
    return map[role] || role;
  }

  if (!user || !isOwner) return null;

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <main className="main-layout">
        {/* Header */}
        <div className="page-header" style={{ marginBottom: 32 }}>
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Users size={32} style={{ color: "var(--accent)" }} />
              {t("management.title")}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, marginLeft: 44 }}>
              {t("management.subtitle")}
            </p>
          </div>
          <button 
            className="btn btn-primary" 
            style={{ padding: "10px 20px", borderRadius: 12, display: "flex", gap: 8, alignItems: "center", boxShadow: "0 4px 12px rgba(108, 99, 255, 0.2)" }} 
            onClick={() => openStoreForm()}
          >
            <Plus size={16} /> <span style={{ fontWeight: 600 }}>{t("management.add_store")}</span>
          </button>
        </div>

        {/* Global Add/Edit Store Form */}
        {storeFormOpen && (
          <div style={{ background: "var(--bg-card)", padding: 24, borderRadius: 16, marginBottom: 24, border: "1px solid var(--border)", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
            <h3 style={{ marginBottom: 16, fontSize: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <StoreIcon size={18} color="var(--accent)"/> 
              {editingStoreId ? t("management.edit_store") : t("management.store_form_title")}
            </h3>
            <form onSubmit={handleSubmitStore} style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}>
              <div style={{ flex: "1 1 250px" }}>
                <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>{t("management.store_name")}</label>
                <input className="input" style={{ width: "100%", padding: "12px 16px", borderRadius: 10 }} placeholder={t("management.store_name_ph")} value={storeForm.name} onChange={(e) => setStoreForm({ ...storeForm, name: e.target.value })} required />
              </div>
              <div style={{ flex: "2 1 350px" }}>
                <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>{t("management.store_address")}</label>
                <input className="input" style={{ width: "100%", padding: "12px 16px", borderRadius: 10 }} placeholder={t("management.store_address_ph")} value={storeForm.address} onChange={(e) => setStoreForm({ ...storeForm, address: e.target.value })} required />
              </div>
              <div style={{ display: "flex", gap: 12 }}>
                <button type="button" className="btn btn-ghost" style={{ padding: "12px 20px", borderRadius: 10 }} onClick={() => setStoreFormOpen(false)}>{t("common.cancel")}</button>
                <button type="submit" className="btn btn-primary" style={{ padding: "12px 24px", borderRadius: 10 }}>{t("common.save")}</button>
              </div>
            </form>
          </div>
        )}

        {/* Main Content Split */}
        <div className="mobile-stack management-split" style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
          
          {/* LEFT: Stores Panel */}
          <div className="mobile-full management-stores-panel" style={{ 
            flex: "0 0 340px", 
            background: "var(--bg-card)", 
            borderRadius: 16, 
            border: "1px solid var(--border)", 
            display: "flex", 
            flexDirection: "column",
            height: "calc(100vh - 160px)",
            minHeight: "400px", /* For mobile fallback */
            overflow: "hidden",
            boxShadow: "0 2px 10px rgba(0,0,0,0.02)"
          }}>
            {/* Panel Header */}
            <div style={{ padding: "20px 20px 16px 20px", borderBottom: "1px solid var(--border)", background: "var(--bg-card)", zIndex: 10 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                  <StoreIcon size={16} /> {t("management.stores_title")}
                </h3>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", background: "var(--bg-hover)", padding: "4px 10px", borderRadius: 20 }}>
                  {stores.length}
                </div>
              </div>
              <div style={{ position: "relative" }}>
                <Search size={16} strokeWidth={2.5} style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                <input
                  className="input"
                  style={{ width: "100%", padding: "10px 16px 10px 40px", borderRadius: 10, fontSize: 13, backgroundColor: "var(--bg-hover)", border: "none" }}
                  placeholder={t("management.search_store_ph")}
                  value={storeSearch}
                  onChange={(e) => setStoreSearch(e.target.value)}
                />
              </div>
            </div>

            {/* Panel List */}
            <div style={{ overflowY: "auto", flex: 1, padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              {loadingStores ? (
                <div style={{ display: "flex", justifyContent: "center", padding: 40 }}><div className="spinner" /></div>
              ) : stores.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)", fontSize: 13 }}>{t("management.no_stores")}</div>
              ) : (
                <>
                  {(() => {
                    const filteredStores = stores.filter(s => s.name.toLowerCase().includes(storeSearch.toLowerCase()));
                    const displayStores = showAllStores ? filteredStores : filteredStores.slice(0, 3);
                    const hasMore = filteredStores.length > 3;
                    return (
                      <>
                        {displayStores.map((s) => {
                          const isActive = selectedStoreId === s.id;
                          return (
                            <div
                              key={s.id}
                              className="management-store-item"
                              onClick={() => setSelectedStoreId(s.id)}
                              style={{
                                padding: "16px",
                                borderRadius: 12,
                                cursor: "pointer",
                                background: isActive ? "var(--accent)" : "transparent",
                                border: isActive ? "1px solid var(--accent)" : "1px solid transparent",
                                transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                                color: isActive ? "#fff" : "var(--text-primary)",
                              }}
                              onMouseEnter={(e) => {
                                if (!isActive) e.currentTarget.style.background = "var(--bg-hover)";
                              }}
                              onMouseLeave={(e) => {
                                if (!isActive) e.currentTarget.style.background = "transparent";
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                <div style={{ fontWeight: 600, fontSize: 14 }}>{s.name} <span style={{ opacity: 0.6, fontSize: 12, fontWeight: 400 }}>(ID: {s.id})</span></div>
                                {isActive && <ArrowRight size={16} color="rgba(255,255,255,0.7)" />}
                              </div>
                              <div style={{ 
                                display: "flex", alignItems: "center", gap: 6, fontSize: 12, marginTop: 8,
                                color: isActive ? "rgba(255,255,255,0.8)" : "var(--text-muted)"
                              }}>
                                <MapPin size={12} />
                                {s.address || t("management.no_address")}
                              </div>
                            </div>
                          );
                        })}
                        {hasMore && !showAllStores && (
                          <button
                            onClick={() => setShowAllStores(true)}
                            style={{
                              padding: "12px",
                              borderRadius: 12,
                              border: "1px dashed var(--border)",
                              background: "transparent",
                              color: "var(--text-muted)",
                              fontSize: 13,
                              cursor: "pointer",
                              textAlign: "center",
                              width: "100%",
                            }}
                          >
                            ... и ещё {filteredStores.length - 3} магазинов
                          </button>
                        )}
                      </>
                    );
                  })()}
                </>
              )}
            </div>
          </div>

          {/* RIGHT: Employees Panel */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 24 }}>
            {!selectedStoreId ? (
              <div style={{ 
                background: "var(--bg-card)", borderRadius: 16, border: "1px dashed var(--border)", 
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 400, padding: 40, color: "var(--text-muted)", textAlign: "center"
              }}>
                <div style={{ width: 64, height: 64, borderRadius: "50%", background: "var(--bg-hover)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
                  <StoreIcon size={32} opacity={0.5} />
                </div>
                <h3 style={{ fontSize: 16, color: "var(--text-secondary)", maxWidth: 300, lineHeight: 1.5 }}>{t("management.emp_select_store")}</h3>
              </div>
            ) : (
              <>
                <div style={{ background: "var(--bg-card)", borderRadius: 16, border: "1px solid var(--border)", padding: "24px 32px", boxShadow: "0 2px 10px rgba(0,0,0,0.02)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>{t("management.brands_title")}</h3>
                      <p style={{ margin: "6px 0 0 0", color: "var(--text-muted)", fontSize: 13 }}>{t("management.brands_subtitle")}</p>
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)" }}>{brands.length}</div>
                  </div>
                  <form onSubmit={handleSubmitBrand} style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
                    <input
                      className="input"
                      style={{ flex: "1 1 280px" }}
                      placeholder={t("management.brand_name_ph")}
                      value={brandForm}
                      onChange={(e) => setBrandForm(e.target.value)}
                      required
                    />
                    <div style={{ display: "flex", gap: 8 }}>
                      {editingBrandId && (
                        <button type="button" className="btn btn-ghost" onClick={() => { setEditingBrandId(null); setBrandForm(""); }}>
                          {t("common.cancel")}
                        </button>
                      )}
                      <button type="submit" className="btn btn-primary">
                        {editingBrandId ? t("management.brand_save") : t("management.brand_add")}
                      </button>
                    </div>
                  </form>
                  <div className="management-brand-list" style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                    {brands.map((brand) => (
                      <div key={brand.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", border: "1px solid var(--border)", borderRadius: 999, background: "var(--bg-hover)" }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{brand.name}</span>
                        <button type="button" className="btn btn-ghost" style={{ padding: "2px 6px" }} onClick={() => { setEditingBrandId(brand.id); setBrandForm(brand.name); }}>
                          {t("management.btn_edit_emp")}
                        </button>
                        <button type="button" className="btn btn-ghost" style={{ padding: "2px 6px", color: "var(--red)" }} onClick={() => handleDeleteBrand(brand.id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ 
                  background: "var(--bg-card)", borderRadius: 16, border: "1px solid var(--border)", padding: "24px 32px",
                  display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "space-between", alignItems: "center", boxShadow: "0 2px 10px rgba(0,0,0,0.02)"
                }}>
                  <div>
                    <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, display: "flex", alignItems: "center", gap: 10 }}>
                       {selectedStore?.name}
                    </h2>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 13, marginTop: 6 }}>
                      <MapPin size={14} /> {selectedStore?.address || t("management.no_address")}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="btn btn-primary"
                      style={{ padding: "8px 12px", borderRadius: 10, display: "flex", alignItems: "center", gap: 6 }}
                      onClick={() => openEmpForm()}
                    >
                      <UserPlus size={14} />
                      {t("management.add_emp")}
                    </button>
                    <button className="btn btn-ghost" style={{ padding: "6px", color: "var(--text-muted)", background: "transparent" }} onClick={() => openStoreForm(selectedStore ?? undefined)} title={t("management.edit_store_btn_title")}>
                      <StoreIcon size={16} />
                    </button>
                  </div>
                </div>

                {empFormOpen && (
                  <div style={{ background: "var(--bg-card)", borderRadius: 16, border: "1px solid var(--accent)", padding: 24, boxShadow: "0 8px 30px rgba(108,99,255,0.12)", marginBottom: 24 }}>
                    <h4 style={{ margin: "0 0 16px 0", display: "flex", alignItems: "center", gap: 8, color: "var(--accent)" }}>
                      <Shield size={16} /> {editingEmployeeId ? t("management.edit_emp") : t("management.add_emp_title")}
                    </h4>
                    <form onSubmit={handleSubmitEmployee} style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}>
                      <div style={{ flex: "1 1 100%" }}>
                        <label style={{ display: "block", fontSize: 12, color: "var(--text-secondary)", marginBottom: 6 }}>{t("management.emp_name")}</label>
                        <input className="input" style={{ width: "100%", borderRadius: 8 }} placeholder={t("management.emp_name_ph")} value={empForm.name} onChange={(e) => setEmpForm({ ...empForm, name: e.target.value })} required />
                      </div>
                      <div style={{ flex: "1 1 100%" }}>
                        <label style={{ display: "block", fontSize: 12, color: "var(--text-secondary)", marginBottom: 6 }}>{t("management.emp_role")}</label>
                        <select className="input" style={{ width: "100%", borderRadius: 8 }} value={empForm.role} onChange={(e) => setEmpForm({ ...empForm, role: e.target.value })}>
                          {allowedRoleOptions.map((role) => (
                            <option key={role.value} value={role.value}>{role.label}</option>
                          ))}
                        </select>
                      </div>
                      <div style={{ flex: "1 1 100%", display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 8 }}>
                        <button type="button" className="btn btn-ghost" style={{ borderRadius: 8 }} onClick={() => setEmpFormOpen(false)}>{t("common.cancel")}</button>
                        <button type="submit" className="btn btn-primary" style={{ borderRadius: 8 }}>{t("common.save")}</button>
                      </div>
                    </form>
                  </div>
                )}

                <div style={{ background: "var(--bg-card)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden" }}>
                  <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)", background: "var(--bg-hover)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                      <Users size={16} /> {t("management.emp_list_title")}
                    </h3>
                    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                      <button className="btn btn-ghost" style={{ padding: "4px 8px" }} onClick={() => fetchEmployees(selectedStoreId!)} title="Обновить список"><RefreshCw size={14} /></button>
                      <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", fontSize: 13, color: showInactiveEmployees ? "var(--red)" : "var(--text-secondary)", fontWeight: showInactiveEmployees ? 600 : 400 }}>
                        <input type="checkbox" checked={showInactiveEmployees} onChange={(e) => setShowInactiveEmployees(e.target.checked)} />
                        {"Только удаленные"}
                      </label>
                    </div>
                  </div>
                  {loadingEmployees ? (
                    <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><div className="spinner" /></div>
                  ) : employees.length === 0 ? (
                    <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)", fontSize: 14 }}>
                      <UserCircle2 size={40} opacity={0.3} style={{ marginBottom: 16, margin: "0 auto" }} />
                      {showInactiveEmployees ? "Удаленных сотрудников нет" : t("management.emp_no_emps")}
                    </div>
                  ) : (
                    <div className="table-wrap management-emp-table" style={{ margin: 0, border: "none" }}>
                      <table style={{ margin: 0 }}>
                        <thead style={{ background: "transparent" }}>
                          <tr>
                            <th style={{ paddingLeft: 24 }}>ID</th>
                            <th>{t("management.col_name")}</th>
                            <th>{t("management.col_role")}</th>
                            <th style={{ paddingRight: 24, textAlign: "right" }}>{t("management.col_actions")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {employees.map((emp) => (
                            <tr key={emp.id} style={{ transition: "background 0.2s", opacity: emp.is_active ? 1 : 0.6 }} onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-hover)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                              <td style={{ paddingLeft: 24, fontSize: 12, color: "var(--text-muted)" }}>#{emp.id}</td>
                              <td data-label={t("management.col_name")}>
                                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                  <div className="emp-avatar" style={{ width: 36, height: 36, borderRadius: "50%", background: "var(--accent-muted)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14 }}>
                                    {emp.name.charAt(0).toUpperCase()}
                                  </div>
                                  <div style={{ display: "flex", flexDirection: "column" }}>
                                    <span style={{ fontWeight: 600, fontSize: 14 }}>{emp.name}</span>
                                    {emp.telegram_id ? (
                                      <span style={{ fontSize: 11, color: "var(--green)", fontWeight: 500, display: "flex", alignItems: "center", gap: 4 }}>
                                        <div style={{width: 6, height: 6, borderRadius: "50%", background: "var(--green)"}} /> {t("management.tg_linked")}
                                      </span>
                                    ) : (
                                      <span style={{ fontSize: 11, color: "var(--orange)", fontWeight: 500, display: "flex", alignItems: "center", gap: 4 }}>
                                        <div style={{width: 6, height: 6, borderRadius: "50%", background: "var(--orange)"}} /> {t("management.tg_unlinked")}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </td>
                              <td data-label={t("management.col_role")}>
                                <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600, background: "rgba(108,99,255,0.1)", color: "var(--accent)" }}>
                                  <Shield size={12} /> {roleBadge(emp.role)}
                                </span>
                              </td>
                              <td data-label={t("management.col_actions")} style={{ paddingRight: 24, textAlign: "right" }}>
                                <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                                  {emp.is_active ? (
                                    <>
                                      <button className="btn btn-ghost" style={{ padding: "6px 10px", fontSize: 13, background: "var(--bg-hover)", flex: 1, justifyContent: "center" }} onClick={() => openEmpForm(emp)}>
                                        {t("management.btn_edit_emp")}
                                      </button>
                                      <button className="btn btn-ghost" style={{ padding: "6px 10px", color: "var(--red)", background: "rgba(255,0,0,0.05)" }} onClick={() => handleDeleteEmployee(emp.id)} title="Delete employee">
                                        <Trash2 size={14} />
                                      </button>
                                    </>
                                  ) : (
                                    <button className="btn btn-ghost" style={{ padding: "6px 12px", fontSize: 13, color: "var(--green)", background: "rgba(0,255,0,0.05)", display: "flex", gap: 6, alignItems: "center" }} onClick={() => handleRestoreEmployee(emp.id)}>
                                      <RotateCcw size={14} /> {"Восстановить"}
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Invite Codes Section */}
                <div style={{ background: "var(--bg-card)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden", marginTop: 24 }}>
                  <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)", display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                      <Key size={16} /> {t("management.invites_title")}
                    </h3>
                    <button 
                      className="btn btn-ghost" 
                      style={{ padding: "6px 12px", fontSize: 13, border: "1px solid var(--border)" }}
                      onClick={() => setInviteFormOpen(!inviteFormOpen)}
                    >
                      {inviteFormOpen ? t("common.cancel") : t("management.btn_create_invite")}
                    </button>
                  </div>
                  
                  {inviteFormOpen && (
                    <div style={{ padding: 20, background: "var(--bg-hover)", borderBottom: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "center" }}>
                      <div style={{ flex: 1 }}>
                        <select 
                          className="input" 
                          style={{ width: "100%", borderRadius: 8, height: 40 }}
                          value={newInviteRole}
                          onChange={(e) => setNewInviteRole(e.target.value)}
                        >
                          {allowedRoleOptions.map((role) => (
                            <option key={role.value} value={role.value}>{role.label}</option>
                          ))}
                        </select>
                      </div>
                      <button className="btn btn-primary" style={{ padding: "0 20px", height: 40, borderRadius: 8 }} onClick={handleCreateInvite}>
                        {t("management.btn_generate")}
                      </button>
                    </div>
                  )}

                  <div style={{ padding: 12 }}>
                    {loadingInvites ? (
                      <div style={{ textAlign: "center", padding: 20 }}><div className="spinner" /></div>
                    ) : invites.length === 0 ? (
                      <div style={{ textAlign: "center", padding: 24, color: "var(--text-muted)", fontSize: 13 }}>
                        {t("management.no_invites")}
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {invites.map(inv => (
                          <div key={inv.code} style={{ 
                            display: "flex", alignItems: "center", justifyContent: "space-between", 
                            padding: "12px 16px", borderRadius: 12, border: "1px solid var(--border)",
                            background: "var(--bg-card)"
                          }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                              <div 
                                onClick={() => copyToClipboard(inv.code)}
                                style={{ 
                                  cursor: "pointer", fontWeight: 800, fontSize: 16, letterSpacing: 2, color: "var(--accent)", 
                                  background: "var(--bg-hover)", padding: "4px 12px", borderRadius: 8, border: "1px dashed var(--accent)"
                                }}
                                title={t("management.click_to_copy")}
                              >
                                {inv.code}
                              </div>
                              <div style={{ display: "flex", flexDirection: "column" }}>
                                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>{roleBadge(inv.role)}</span>
                                <span style={{ fontSize: 10, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                                  <Clock size={10} /> 
                                  {t("management.expires_prefix")} {new Date(inv.expires_at).toLocaleDateString()} {new Date(inv.expires_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                </span>
                              </div>
                            </div>
                            <div style={{ display: "flex", gap: 8 }}>
                              <button 
                                onClick={() => copyToClipboard(inv.code)}
                                style={{ padding: 8, borderRadius: 8, background: "var(--bg-hover)", border: "none", cursor: "pointer", color: "var(--text-secondary)" }}
                              >
                                <Copy size={14} />
                              </button>
                              <button 
                                onClick={() => handleDeleteInvite(inv.code)}
                                style={{ padding: 8, borderRadius: 8, background: "rgba(255,0,0,0.05)", border: "none", cursor: "pointer", color: "var(--red)" }}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
