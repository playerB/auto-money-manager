"use client";

import Link from "next/link";

type NavKey = "home" | "upload";

const I = {
  home: "M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1Z",
  insights: "M4 20V10M10 20V4M16 20v-6M22 20H2",
  upload: "M12 15V3M8 7l4-4 4 4M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4",
  category: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z",
};

function Icon({ d }: { d: string }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

export function Sidebar({
  active,
  onToggle,
  onNavigate,
}: {
  active: NavKey;
  onToggle?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div
          className="brand-logo"
          onClick={onToggle}
          title="Toggle sidebar"
          role="button"
        >
          💸
        </div>
        <div className="brand-text">
          <div className="brand-name">Money Manager</div>
          <div className="brand-sub">Personal</div>
        </div>
        <button className="collapse-btn" onClick={onToggle} aria-label="Collapse sidebar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M9 4v16" />
          </svg>
        </button>
      </div>

      <nav className="nav">
        <Link className="nav-item" data-active={active === "home"} href="/" onClick={onNavigate}>
          <Icon d={I.home} />
          <span className="nav-label">Home</span>
        </Link>
        <button type="button" className="nav-item" data-disabled="true">
          <Icon d={I.insights} />
          <span className="nav-label">Insights</span>
        </button>
        <Link className="nav-item" data-active={active === "upload"} href="/statements" onClick={onNavigate}>
          <Icon d={I.upload} />
          <span className="nav-label">Upload</span>
        </Link>
        <button type="button" className="nav-item" data-disabled="true">
          <Icon d={I.category} />
          <span className="nav-label">Category</span>
        </button>
      </nav>

      <div className="sidebar-spacer" />

      <div className="sidebar-foot">
        <button type="button" className="nav-item" data-disabled="true">
          <Icon d={I.settings} />
          <span className="nav-label">Settings</span>
        </button>
        <div className="profile">
          <div className="avatar">S</div>
          <div className="profile-text">
            <div className="profile-name">Supawish</div>
            <div className="profile-email">supawish.kanok@gmail.com</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
