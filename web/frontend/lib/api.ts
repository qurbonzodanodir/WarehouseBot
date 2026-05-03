
import { clearAuth, notifyAuthExpired } from "./auth";

const getApiBase = () => {
  const explicitBase = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (explicitBase) {
    return explicitBase.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return "/api";
  }
  return "http://backend:8000/api";
};

type ApiErrorItem = {
  msg?: string;
};

type ApiErrorPayload = {
  detail?: unknown;
  message?: unknown;
};

let isRefreshing = false;
let refreshSubscribers: Array<(ok: boolean) => void> = [];

function subscribeTokenRefresh(cb: (ok: boolean) => void) {
  refreshSubscribers.push(cb);
}

function onRefreshed(ok: boolean) {
  refreshSubscribers.forEach(cb => cb(ok));
  refreshSubscribers = [];
}

function handleAuthExpired() {
  clearAuth();
  notifyAuthExpired();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  const normalizedPayload: ApiErrorPayload | null = isRecord(payload)
    ? payload as ApiErrorPayload
    : null;
  const detail = normalizedPayload?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item): string => {
        if (typeof item === "string") return item;
        if (isRecord(item) && typeof (item as ApiErrorItem).msg === "string") {
          return (item as ApiErrorItem).msg ?? "";
        }
        return "";
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (isRecord(detail)) {
    if (typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }
    const firstEntry = Object.values(detail).find(v => typeof v === "string" && v.trim());
    if (typeof firstEntry === "string") {
      return firstEntry;
    }
  }

  if (
    normalizedPayload &&
    typeof normalizedPayload.message === "string" &&
    normalizedPayload.message.trim()
  ) {
    return normalizedPayload.message;
  }

  return fallback;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retried = false
): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/")) {
      if (!retried) {
        if (!isRefreshing) {
          isRefreshing = true;
          try {
            const refreshRes = await fetch(`${getApiBase()}/auth/refresh`, {
              method: "POST",
              credentials: "include",
              headers: { "Content-Type": "application/json" },
            });

            if (!refreshRes.ok) {
              throw new Error("Session expired");
            }

            const data = await refreshRes.json();
            if (typeof window !== "undefined" && data.user) {
              localStorage.setItem("wh_user", JSON.stringify(data.user));
            }
            isRefreshing = false;
            onRefreshed(true);
          } catch (e) {
            isRefreshing = false;
            handleAuthExpired();
            onRefreshed(false);
            throw e;
          }
        }
        return new Promise((resolve, reject) => {
          subscribeTokenRefresh((ok) => {
            if (!ok) {
              reject(new Error("Session expired"));
              return;
            }
            void request<T>(path, options, true).then(resolve).catch(reject);
          });
        });
      }
      
      handleAuthExpired();
    }
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(extractErrorMessage(error, "Request failed"));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentLength = res.headers.get("content-length");
  if (contentLength === "0") {
    return undefined as T;
  }

  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ user: UserMe }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  getMe: () => request<UserMe>("/auth/me"),

  // Analytics
  getDashboard: (period = "today") =>
    request<DashboardData>(`/analytics/dashboard?period=${period}`),

  // Orders
  getOrders: (params?: { store_id?: number; status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.store_id) qs.set("store_id", String(params.store_id));
    if (params?.status) qs.set("status", params.status);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    return request<Order[]>(`/orders?${qs}`);
  },
  dispatchOrder: (id: number) =>
    request<Order>(`/orders/${id}/dispatch`, { method: "PUT" }),
  rejectOrder: (id: number) =>
    request<Order>(`/orders/${id}/reject`, { method: "PUT" }),
  deliverOrder: (id: number) =>
    request<Order>(`/orders/${id}/deliver`, { method: "PUT" }),
  approveReturn: (id: number) =>
    request<Order>(`/orders/${id}/approve_return`, { method: "PUT" }),
  rejectReturn: (id: number) =>
    request<Order>(`/orders/${id}/reject_return`, { method: "PUT" }),
  createOrder: (data: { product_id: number; quantity: number; store_id?: number }) =>
    request<Order>("/orders", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Products
  getProducts: (params?: { search?: string; include_inactive?: boolean; only_inactive?: boolean; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.include_inactive) qs.set("include_inactive", "true");
    if (params?.only_inactive) qs.set("only_inactive", "true");
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const q = qs.toString();
    return request<PaginatedResponse<Product>>(`/products${q ? `?${q}` : ""}`);
  },
  getProductOptions: (params?: { search?: string; productIds?: number[]; include_inactive?: boolean; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.productIds?.length) qs.set("product_ids", params.productIds.join(","));
    if (params?.include_inactive) qs.set("include_inactive", "true");
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<ProductPicker[]>(`/products/options${q ? `?${q}` : ""}`);
  },
  getProductInventory: (id: number) =>
    request<ProductInventoryOut[]>(`/products/${id}/inventory`),
  getBrands: () => request<Brand[]>("/products/brands"),
  getBrandStats: () => request<BrandStat[]>("/products/brands/stats"),
  createBrand: (data: { name: string }) =>
    request<Brand>("/products/brands", { method: "POST", body: JSON.stringify(data) }),
  updateBrand: (id: number, data: { name: string }) =>
    request<Brand>(`/products/brands/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteBrand: (id: number) =>
    request(`/products/brands/${id}`, { method: "DELETE" }),
  createProduct: (data: { sku: string; price: number; brand: string }) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(data) }),
  updateProduct: (id: number, data: Partial<Product>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteProduct: (id: number) =>
    request(`/products/${id}`, { method: "DELETE" }),

  // Inventory
  getInventory: (store_id: number, page: number = 1, pageSize: number = 50) =>
    request<{
      items: InventoryItem[];
      total: number;
      page: number;
      page_size: number;
      total_pages: number;
    }>(`/inventory/${store_id}?page=${page}&page_size=${pageSize}`),
  getAllInventory: () => request<Record<string, StoreInventory>>("/inventory"),
  receiveStock: (data: { product_id: number; quantity: number }) =>
    request<{success: boolean; product_id: number; new_quantity: number}>("/inventory/receive", { method: "POST", body: JSON.stringify(data) }),
  bulkReceiveStock: (data: { items: { sku: string; quantity: number; price?: number; brand?: string }[], replace_quantity?: boolean }) =>
    request<{success: boolean; processed: number; created: number}>("/inventory/bulk-receive", { method: "POST", body: JSON.stringify(data) }),
  importVitrina: (store_id: number, items: { sku: string; brand: string }[]) =>
    request<{success: boolean; store: string; created: number; updated: number; added_qty: number}>("/inventory/import-vitrina", {
      method: "POST",
      body: JSON.stringify({ store_id, items })
    }),

  clearInventory: () =>
    request<{message: string}>("/inventory/clear-all", {
      method: "DELETE"
    }),

  // Stores
  getStores: () => request<Store[]>("/stores"),
  getStoreCatalog: () => request<StoreCatalogCard[]>("/stores/catalog"),
  createStore: (data: { name: string; address: string }) =>
    request<Store>("/stores", { method: "POST", body: JSON.stringify(data) }),
  updateStore: (id: number, data: { name?: string; address?: string }) =>
    request<Store>(`/stores/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  getStoreEmployees: (store_id: number, include_inactive = false) =>
    request<Employee[]>(`/stores/${store_id}/employees?include_inactive=${include_inactive}&_t=${Date.now()}`),
  updateEmployee: (id: number, data: Partial<Employee>) =>
    request<Employee>(`/stores/employees/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteEmployee: (id: number) =>
    request<{status: string; message: string}>(`/stores/employees/${id}`, { method: "DELETE" }),
  restoreEmployee: (id: number) =>
    request<{status: string; message: string}>(`/stores/employees/${id}/restore`, { method: "POST" }),
  createEmployee: (store_id: number, data: { name: string; role: string }) =>
    request<Employee>(`/stores/${store_id}/employees`, { method: "POST", body: JSON.stringify(data) }),

  // Finance
  getDebtors(): Promise<CashCollectionSummary[]> {
    return request<CashCollectionSummary[]>("/finance/debtors");
  },

  getFinanceHistory(limit: number = 50): Promise<CashCollectionHistoryItem[]> {
    return request<CashCollectionHistoryItem[]>(`/finance/history?limit=${limit}`);
  },

  collectCash(storeId: number, amount: number): Promise<CashCollectionHistoryItem> {
    return request<CashCollectionHistoryItem>("/finance/collect", {
      method: "POST",
      body: JSON.stringify({ store_id: storeId, amount: amount }),
    });
  },

  // Invites
  getInvites: (store_id: number) =>
    request<Invite[]>(`/invites/${store_id}`),
  createInvite: (data: { store_id: number; role: string }) =>
    request<Invite>("/invites", { method: "POST", body: JSON.stringify(data) }),
  deleteInvite: (code: string) =>
    request(`/invites/${code}`, { method: "DELETE" }),

  // Samples
  dispatchDisplay: (data: { product_id: number; target_store_id: number; quantity: number }) =>
    request<{ success: boolean; order_id: number }>("/inventory/dispatch-display", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Suppliers
  getSuppliers: () => request<Supplier[]>("/suppliers"),
  createSupplier: (data: { name: string; contact_info?: string; address?: string; notes?: string }) =>
    request<Supplier>("/suppliers", { method: "POST", body: JSON.stringify(data) }),
  getSupplierDetail: (id: number) => request<SupplierDetail>(`/suppliers/${id}`),
  addSupplierInvoice: (id: number, data: { items: { product_id: number; quantity: number }[]; notes?: string | null }) =>
    request<SupplierInvoiceItem>(`/suppliers/${id}/invoices`, { method: "POST", body: JSON.stringify(data) }),
  addSupplierPayment: (id: number, data: { amount: number; notes?: string | null }) =>
    request<SupplierPaymentItem>(`/suppliers/${id}/payments`, { method: "POST", body: JSON.stringify(data) }),
  addSupplierReturn: (id: number, data: { items: { product_id: number; quantity: number }[]; notes?: string | null }) =>
    request<SupplierReturnItem>(`/suppliers/${id}/returns`, { method: "POST", body: JSON.stringify(data) }),
};

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}


export interface UserMe {
  id: number;
  telegram_id: number | null;
  email: string | null;
  name: string;
  role: "seller" | "warehouse" | "owner" | "admin";
  store_id: number | null;
  store_name: string | null;
}

export interface DashboardData {
  total_orders_today: number;
  total_revenue_today: number;
  total_debt: number;
  total_supplier_debt: number;
  pending_orders: number;
  store_debts: { store_id: number; store_name: string; current_debt: number }[];
  supplier_debts: { supplier_id: number; supplier_name: string; current_debt: number }[];
  store_revenues: { store_name: string; total_revenue: number }[];
  orders_by_status: { status: string; count: number }[];
}

export interface Order {
  id: number;
  batch_id: string | null;
  store_id: number;
  store: { id: number; name: string };
  product_id: number;
  product: { id: number; sku: string; price: number };
  quantity: number;
  price_per_item: number;
  total_price: number;
  status: string;
  created_at: string;
}

export interface Product {
  id: number;
  sku: string;
  brand: string;
  price: number;
  is_active: boolean;
}

export interface ProductPicker {
  id: number;
  sku: string;
  brand: string;
  price: number;
}

export interface Brand {
  id: number;
  name: string;
}

export interface BrandStat {
  id: number;
  name: string;
  product_count: number;
}

export interface ProductCreate {
  sku: string;
  price: number;
}

export interface ProductUpdate {
  price?: number;
  is_active?: boolean;
}

export interface InventoryItem {
  product_id: number;
  product_sku: string;
  quantity: number;
  is_display?: boolean;
}

export interface StoreInventory {
  items: { product_id: number; sku: string; quantity: number; is_display?: boolean }[];
}

export interface StoreCatalogCard {
  id: number;
  name: string;
  address: string;
  total_items: number;
  total_value: number;
}

export interface ProductInventoryOut {
  store_id: number;
  store_name: string;
  quantity: number;
  is_display: boolean;
}

export interface Store {
  id: number;
  name: string;
  address: string;
  store_type: string;
  current_debt: number;
  is_active: boolean;
  total_items?: number;
}

export interface Employee {
  id: number;
  telegram_id: number;
  email?: string;
  name: string;
  role: string;
  is_active: boolean;
}

export interface CashCollectionHistoryItem {
  id: number;
  store_id: number;
  store_name: string;
  user_id: number;
  user_name: string;
  amount: number;
  created_at: string;
}

export interface CashCollectionSummary {
  store_id: number;
  store_name: string;
  current_debt: number;
}

export interface Invite {
  code: string;
  role: string;
  store_id: number;
  expires_at: string;
  is_used: boolean;
  created_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  contact_info: string | null;
  address: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  current_debt: number;
}

export interface SupplierInvoiceLineItem {
  product_id: number;
  sku: string;
  quantity: number;
  price_per_unit: number;
  line_total: number;
}

export interface SupplierInvoiceItem {
  id: number;
  supplier_id: number;
  total_amount: number;
  notes: string | null;
  created_at: string;
  user_name: string | null;
  items?: SupplierInvoiceLineItem[];
}

export interface SupplierPaymentItem {
  id: number;
  supplier_id: number;
  amount: number;
  notes: string | null;
  created_at: string;
  user_name: string | null;
}

export interface SupplierReturnItem {
  id: number;
  supplier_id: number;
  total_amount: number;
  notes: string | null;
  created_at: string;
  user_name: string | null;
  items?: SupplierInvoiceLineItem[]; // Reuse line item interface
}

export interface SupplierDetail extends Supplier {
  total_invoiced: number;
  total_paid: number;
  total_returned: number;
  invoices: SupplierInvoiceItem[];
  payments: SupplierPaymentItem[];
  returns: SupplierReturnItem[];
}
