"use client";

import { useEffect, useState } from "react";

export interface SceneTier {
  ready: boolean; // resolved on client (avoids SSR mismatch)
  webgl: boolean; // render the live canvas at all
  nodeCount: number;
  showLabels: boolean;
  bloom: boolean;
  dpr: [number, number];
  reducedMotion: boolean;
}

const SSR_TIER: SceneTier = {
  ready: false,
  webgl: false,
  nodeCount: 0,
  showLabels: false,
  bloom: false,
  dpr: [1, 2],
  reducedMotion: false,
};

function detectWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (c.getContext("webgl") || c.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

/** Picks a quality tier once on mount from viewport, memory, save-data, motion. */
export function useSceneTier(): SceneTier {
  const [tier, setTier] = useState<SceneTier>(SSR_TIER);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const w = window.innerWidth;
    // @ts-expect-error non-standard but widely supported
    const mem: number = navigator.deviceMemory || 4;
    // @ts-expect-error non-standard
    const saveData: boolean = navigator.connection?.saveData || false;
    const webgl = detectWebGL();

    // Reserve the static frame for genuinely constrained devices — normal phones
    // (360–414px) still get the simplified live scene.
    const lowPower = w < 340 || mem < 4 || saveData;

    let nodeCount = 260;
    let showLabels = true;
    let bloom = true;
    let dpr: [number, number] = [1, 2];

    if (w < 768) {
      nodeCount = 70;
      showLabels = false;
      bloom = false;
      dpr = [1, 2];
    } else if (w < 1024) {
      nodeCount = 160;
      showLabels = false;
      bloom = false;
    } else if (w < 1440) {
      nodeCount = 220;
    }

    // Live canvas only when it will look good and perform; otherwise static frame.
    const useWebgl = webgl && !lowPower;

    setTier({
      ready: true,
      webgl: useWebgl,
      nodeCount,
      showLabels: showLabels && !reduce,
      bloom: bloom && !reduce,
      dpr,
      reducedMotion: reduce,
    });
  }, []);

  return tier;
}
