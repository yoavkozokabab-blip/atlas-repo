"use client";

import { useEffect } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { sceneProgress } from "../../lib/scene/progress";

/** Fade a panel in over the first `f` of [start,end], hold, fade out over last `f`. */
function bandOpacity(p: number, start: number, end: number, f = 0.06) {
  if (p < start - f || p > end + f) return 0;
  if (p < start) return (p - (start - f)) / f;
  if (p > end) return 1 - (p - end) / f;
  const inN = Math.min(1, (p - start) / f);
  const outN = Math.min(1, (end - p) / f);
  return Math.min(inN, outN);
}

const ACTS: [string, number, number][] = [
  ["scan", 0.08, 0.34],
  ["memory", 0.36, 0.56],
  ["retrieval", 0.58, 0.78],
  ["converge", 0.8, 1.0],
];

export default function ScrollController() {
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    gsap.registerPlugin(ScrollTrigger);

    let lenis: Lenis | null = null;
    const panels = new Map<string, HTMLElement>();
    ACTS.forEach(([name]) => {
      const el = document.querySelector<HTMLElement>(`[data-act="${name}"]`);
      if (el) panels.set(name, el);
    });

    const applyActs = (p: number) => {
      ACTS.forEach(([name, s, e]) => {
        const el = panels.get(name);
        if (!el) return;
        const o = bandOpacity(p, s, e);
        el.style.opacity = String(o);
        el.style.transform = reduce ? "none" : `translateY(${(1 - o) * 18}px)`;
        el.style.pointerEvents = o > 0.6 ? "auto" : "none";
      });
    };

    if (!reduce) {
      lenis = new Lenis({ duration: 1.1, smoothWheel: true });
      (window as unknown as { __lenis?: Lenis }).__lenis = lenis; // QA scroll hook
      lenis.on("scroll", ScrollTrigger.update);
      const raf = (time: number) => lenis!.raf(time * 1000);
      gsap.ticker.add(raf);
      gsap.ticker.lagSmoothing(0);
      // store remover
      (lenis as unknown as { _rafRemover?: () => void })._rafRemover = () =>
        gsap.ticker.remove(raf);
    }

    const st = ScrollTrigger.create({
      trigger: ".narrative",
      start: "top top",
      end: "bottom bottom",
      scrub: true,
      onUpdate: (self) => {
        sceneProgress.p = self.progress;
        applyActs(self.progress);
      },
    });

    // QA hook: jump the narrative to a given progress for deterministic captures.
    (window as unknown as { __atlasNarrative?: (p: number) => void }).__atlasNarrative = (p) => {
      sceneProgress.p = p;
      applyActs(p);
    };

    // reduced motion: set discrete act states without smoothing
    if (reduce) {
      const onScroll = () => {
        const el = document.querySelector<HTMLElement>(".narrative");
        if (!el) return;
        const r = el.getBoundingClientRect();
        const total = r.height - window.innerHeight;
        const p = total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 0;
        sceneProgress.p = p;
        applyActs(p);
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
      (st as unknown as { _cleanup?: () => void })._cleanup = () =>
        window.removeEventListener("scroll", onScroll);
    }

    ScrollTrigger.refresh();

    return () => {
      st.kill();
      (st as unknown as { _cleanup?: () => void })._cleanup?.();
      if (lenis) {
        (lenis as unknown as { _rafRemover?: () => void })._rafRemover?.();
        lenis.destroy();
      }
    };
  }, []);

  return null;
}
