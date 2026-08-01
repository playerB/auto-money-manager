"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";

// App frame: collapsible sidebar on desktop (icon rail), off-canvas drawer on
// mobile (opened by the header burger). Header content is supplied per page.
export function AppShell({
  active,
  headerLeft,
  headerRight,
  children,
}: {
  active: "home" | "upload";
  headerLeft?: ReactNode;
  headerRight?: ReactNode;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("amm-sidebar") === "collapsed");
    } catch {
      /* ignore */
    }
  }, []);

  function toggleCollapse() {
    setCollapsed((c) => {
      const n = !c;
      try {
        localStorage.setItem("amm-sidebar", n ? "collapsed" : "open");
      } catch {
        /* ignore */
      }
      return n;
    });
  }

  return (
    <div className="app" data-collapsed={collapsed} data-mobile-open={mobileOpen}>
      <Sidebar
        active={active}
        onToggle={toggleCollapse}
        onNavigate={() => setMobileOpen(false)}
      />
      <div className="scrim" onClick={() => setMobileOpen(false)} />

      <main className="main">
        <header className="main-header">
          <div className="header-left">
            <button
              className="burger"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </button>
            {headerLeft}
          </div>
          <div className="header-actions">{headerRight}</div>
        </header>
        {children}
      </main>
    </div>
  );
}
