import { UserMe } from "./api";

const TOKEN_KEY = "wh_token";
const USER_KEY = "wh_user";

export function saveAuth(token: string, user: UserMe) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): UserMe | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem(TOKEN_KEY);
}
