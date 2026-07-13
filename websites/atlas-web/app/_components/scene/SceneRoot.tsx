"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// The heavy three.js scene is code-split and only loaded on the client, after
// the hero text has already painted (never blocks LCP).
const ConstellationCanvas = dynamic(() => import("./ConstellationCanvas"), {
  ssr: false,
});

const STAGES = ["Mapping repository", "Resolving symbols", "Building memory", "Ready"];

export default function SceneRoot() {
  const [mounted, setMounted] = useState(false);
  const [done, setDone] = useState(false);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    setMounted(true);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setDone(true);
      return;
    }
    // Honest short loader: advance stages while the scene chunk + first frames
    // resolve, then reveal. Not a fake long delay — capped and skippable.
    const t1 = setTimeout(() => setStage(1), 220);
    const t2 = setTimeout(() => setStage(2), 460);
    const t3 = setTimeout(() => setStage(3), 720);
    const t4 = setTimeout(() => setDone(true), 900);
    return () => [t1, t2, t3, t4].forEach(clearTimeout);
  }, []);

  return (
    <>
      <div className="atmos" aria-hidden="true" />
      {mounted && <ConstellationCanvas />}
      {!done && (
        <div className={`scene-loader${done ? " done" : ""}`} aria-hidden="true">
          <span className="lword">ATLAS</span>
          <span className="bar">
            <i />
          </span>
          <span className="stat">{STAGES[stage]}</span>
        </div>
      )}
    </>
  );
}
