"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import AtlasMark from "../AtlasMark";
import { GITHUB_URL } from "../../_config";

const LINKS = [
  ["Product", "/features"],
  ["How it works", "/how-it-works"],
  ["Integrations", "/integrations"],
  ["Docs", "/docs"],
  ["Pricing", "/pricing"],
] as const;

export default function CineNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const burgerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    if (!open) return;

    // move focus into the panel, trap Tab within it, Escape closes
    const trigger = burgerRef.current;
    const panel = panelRef.current;
    const focusables = panel
      ? Array.from(
          panel.querySelectorAll<HTMLElement>(
            'a[href], button, [tabindex]:not([tabindex="-1"])'
          )
        )
      : [];
    focusables[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      } else if (e.key === "Tab" && focusables.length) {
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKey);
      trigger?.focus(); // return focus to the trigger
    };
  }, [open]);

  return (
    <>
      <header className={`cnav${scrolled ? " scrolled" : ""}`}>
        <div className="cnav-inner">
          <Link className="cbrand" href="/" aria-label="Atlas home">
            <AtlasMark size={26} className="mark" />
            Atlas
          </Link>
          <nav className="cnav-links" aria-label="Primary">
            {LINKS.map(([label, href]) => (
              <Link key={href} href={href}>
                {label}
              </Link>
            ))}
          </nav>
          <div className="cnav-right">
            <a className="cnav-ghost" href={GITHUB_URL} target="_blank" rel="noreferrer">
              GitHub
            </a>
            <Link className="btn-mag" href="/download" data-evt="download_click">
              Download <span className="arw" aria-hidden>→</span>
            </Link>
            <button
              ref={burgerRef}
              className="cnav-burger"
              aria-label="Open menu"
              aria-expanded={open}
              onClick={() => setOpen(true)}
            >
              <svg width="18" height="12" viewBox="0 0 18 12" fill="none" aria-hidden>
                <path d="M0 1h18M0 6h18M0 11h18" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {open && (
        <div ref={panelRef} className="mobile-panel" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="mobile-panel-top">
            <Link className="cbrand" href="/" onClick={() => setOpen(false)}>
              <AtlasMark size={26} className="mark" /> Atlas
            </Link>
            <button className="cnav-burger" aria-label="Close menu" onClick={() => setOpen(false)}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path d="M1 1l14 14M15 1L1 15" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </button>
          </div>
          <nav className="mobile-links" aria-label="Mobile">
            {LINKS.map(([label, href]) => (
              <Link key={href} href={href} onClick={() => setOpen(false)}>
                {label}
              </Link>
            ))}
            <a href={GITHUB_URL} target="_blank" rel="noreferrer" onClick={() => setOpen(false)}>
              GitHub
            </a>
          </nav>
          <div className="mobile-panel-foot">
            <Link className="btn-mag" href="/download" onClick={() => setOpen(false)}>
              Download Atlas <span className="arw" aria-hidden>→</span>
            </Link>
            <span className="mono muted">v1.0.0 · Windows · No signup</span>
          </div>
        </div>
      )}
    </>
  );
}
