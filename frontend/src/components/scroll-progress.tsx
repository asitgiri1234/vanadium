"use client";

import { useEffect, useState } from "react";

/**
 * Top-of-page scroll progress bar (SaveMeTokens-style).
 * Width tracks scroll position — grows down, shrinks up.
 */
export function ScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const update = () => {
      const scrollTop = window.scrollY;
      const maxScroll =
        document.documentElement.scrollHeight - window.innerHeight;
      setProgress(maxScroll > 0 ? (scrollTop / maxScroll) * 100 : 0);
    };

    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update, { passive: true });
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  return (
    <div
      className="pointer-events-none fixed left-0 right-0 top-0 z-[100] h-[2px] bg-border/30"
      aria-hidden
    >
      <div
        className="gradient-bg h-full shadow-glow-cyan transition-[width] duration-100 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
