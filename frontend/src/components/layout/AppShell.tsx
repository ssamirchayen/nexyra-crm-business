import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { useApiStatus } from "../../hooks/useApiStatus";
import { CommandPalette } from "./CommandPalette";
import { ConnectionBanner } from "./ConnectionBanner";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const SIDEBAR_STORAGE_KEY = "nexyra-sidebar-collapsed";

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandsOpen, setCommandsOpen] = useState(false);
  const { status, retry } = useApiStatus();

  const closeCommands = useCallback(() => setCommandsOpen(false), []);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandsOpen((current) => !current);
      }
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const toggleSidebar = () => {
    setCollapsed((current) => {
      const next = !current;
      localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  };

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggle={toggleSidebar}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div className="app-shell__main">
        <Topbar
          apiStatus={status}
          onOpenCommands={() => setCommandsOpen(true)}
          onOpenMenu={() => setMobileOpen(true)}
        />
        {status === "offline" && <ConnectionBanner onRetry={() => void retry()} />}
        <main className="page-container"><Outlet /></main>
      </div>
      <CommandPalette open={commandsOpen} onClose={closeCommands} />
    </div>
  );
}
