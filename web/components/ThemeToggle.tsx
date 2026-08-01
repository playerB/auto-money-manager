"use client";

import { useEffect, useState } from "react";

// Segmented theme control: ☀ Light / 🌙 Dark, active side highlighted.
export function ThemeToggle() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    setDark(document.documentElement.getAttribute("data-theme") !== "light");
  }, []);

  function set(next: "light" | "dark") {
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("amm-theme", next);
    } catch {
      /* ignore */
    }
    setDark(next === "dark");
  }

  return (
    <div className="segtoggle" role="group" aria-label="Theme">
      <button type="button" data-active={!dark} onClick={() => set("light")}>
        ☀ Light
      </button>
      <button type="button" data-active={dark} onClick={() => set("dark")}>
        🌙 Dark
      </button>
    </div>
  );
}
