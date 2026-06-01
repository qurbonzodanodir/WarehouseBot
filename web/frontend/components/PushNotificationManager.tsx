"use client";

import { useEffect, useState } from "react";
import { getStoredUser } from "@/lib/auth";
import { api, UserMe } from "@/lib/api";
import { Bell, BellOff, Loader2 } from "lucide-react";

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, "+")
    .replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function PushNotificationManager() {
  const [user, setUser] = useState<UserMe | null>(null);
  const [isSupported, setIsSupported] = useState(false);
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
    if ("serviceWorker" in navigator && "PushManager" in window) {
      setIsSupported(true);
      registerServiceWorker();
    }
  }, []);

  const registerServiceWorker = async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js", {
        scope: "/",
        updateViaCache: "none",
      });
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        // Sync existing subscription with backend just in case
        try {
          const subscriptionInfo = JSON.parse(JSON.stringify(sub));
          await api.subscribeToPush(subscriptionInfo);
        } catch (syncErr) {
          console.error("Failed to sync existing push subscription:", syncErr);
        }
      }
      setSubscription(sub);
    } catch (err) {
      console.error("Service Worker registration failed:", err);
    }
  };

  const subscribeToPush = async () => {
    setLoading(true);
    setError(null);
    try {
      const registration = await navigator.serviceWorker.ready;

      // 1. Get VAPID public key from backend
      const vapidRes = await api.getVapidPublicKey();
      const vapidPublicKey = vapidRes.publicKey;
      
      if (!vapidPublicKey) {
        throw new Error("VAPID public key not found");
      }

      const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);

      // 2. Subscribe
      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedVapidKey,
      });

      // 3. Send to backend
      const subscriptionInfo = JSON.parse(JSON.stringify(sub));
      await api.subscribeToPush(subscriptionInfo);

      setSubscription(sub);
    } catch (err: any) {
      console.error("Failed to subscribe to push notifications", err);
      setError(err.message || "Ошибка подписки на уведомления");
    } finally {
      setLoading(false);
    }
  };

  if (!isSupported || !user) {
    return null; // Don't show if not supported or not logged in
  }

  // Only WAREHOUSE, ADMIN, OWNER need this
  if (!["admin", "owner", "warehouse"].includes(user.role)) {
    return null;
  }

  if (subscription) {
    return (
      <button
        className="flex items-center gap-2 px-3 py-2 text-sm text-green-600 bg-green-50 rounded-md"
        disabled
        title="Уведомления включены"
      >
        <Bell size={16} />
        <span className="hidden sm:inline">Уведомления включены</span>
      </button>
    );
  }

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={subscribeToPush}
        disabled={loading}
        className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
      >
        {loading ? <Loader2 size={16} className="animate-spin" /> : <BellOff size={16} />}
        <span className="hidden sm:inline">Включить уведомления</span>
      </button>
      {error && <span className="text-xs text-red-500 mt-1">{error}</span>}
    </div>
  );
}
