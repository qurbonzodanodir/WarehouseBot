import type { UserMe } from "./api";

const USER_KEY = "wh_user";
const AUTH_EXPIRED_EVENT = "wh:auth-expired";

export function saveAuth(user: UserMe) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): UserMe | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserMe;
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem(USER_KEY);
}

export function notifyAuthExpired() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}

export function onAuthExpired(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(AUTH_EXPIRED_EVENT, listener);
  return () => {
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
  };
}
