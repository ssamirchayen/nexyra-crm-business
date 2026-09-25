import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";

export type ApiStatus = "checking" | "online" | "offline";

export function useApiStatus() {
  const [status, setStatus] = useState<ApiStatus>("checking");

  const check = useCallback(async () => {
    if (!navigator.onLine) {
      setStatus("offline");
      return;
    }

    setStatus((current) => (current === "online" ? current : "checking"));

    try {
      await api.get<unknown>("/health");
      setStatus("online");
    } catch {
      setStatus("offline");
    }
  }, []);

  useEffect(() => {
    void check();

    const handleOnline = () => void check();
    const handleOffline = () => setStatus("offline");
    const timer = window.setInterval(() => void check(), 30_000);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [check]);

  return { status, retry: check };
}
