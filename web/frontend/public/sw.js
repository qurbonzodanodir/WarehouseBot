// WarehouseBot Service Worker v3
// Auto-syncs push subscription with backend on activation

const BACKEND_URL = "/api";

// On activation - claim all clients immediately so SW is active right away
self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});

// On install - skip waiting so new SW takes over immediately without reload
self.addEventListener("install", function (event) {
  self.skipWaiting();
});

// Handle incoming push notifications
self.addEventListener("push", function (event) {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch (e) {
    data = { title: "Уведомление", body: event.data.text(), url: "/" };
  }

  const options = {
    body: data.body || "",
    icon: "/icon-192x192.png",
    badge: "/icon-72x72.png",
    vibrate: [200, 100, 200],
    tag: "warehouse-notification", // replace old notification with new one
    renotify: true,
    requireInteraction: false,
    data: {
      url: data.url || "/orders",
    },
  };

  event.waitUntil(self.registration.showNotification(data.title || "Склад", options));
});

// Handle notification click - open the app
self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  const targetUrl = event.notification.data.url || "/orders";

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then(function (clientList) {
        // If any window is open - focus it
        for (const client of clientList) {
          if ("focus" in client) {
            client.navigate(targetUrl);
            return client.focus();
          }
        }
        // Otherwise open a new window
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});

// Handle push subscription change (when browser auto-rotates keys)
self.addEventListener("pushsubscriptionchange", function (event) {
  event.waitUntil(
    self.registration.pushManager
      .subscribe({
        userVisibleOnly: true,
        applicationServerKey: event.oldSubscription
          ? event.oldSubscription.options.applicationServerKey
          : null,
      })
      .then(function (newSubscription) {
        const subInfo = JSON.parse(JSON.stringify(newSubscription));
        // Re-send new subscription to backend
        return fetch(BACKEND_URL + "/notifications/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            endpoint: subInfo.endpoint,
            keys: {
              p256dh: subInfo.keys.p256dh,
              auth: subInfo.keys.auth,
            },
          }),
        });
      })
  );
});
