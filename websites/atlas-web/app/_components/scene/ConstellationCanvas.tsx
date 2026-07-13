"use client";

import { Component, type ReactNode } from "react";
import ConstellationScene from "./ConstellationScene";
import StaticFallback from "./StaticFallback";
import { useSceneTier } from "./useSceneTier";

/** Catches any WebGL/runtime error in the scene and shows the static frame. */
class SceneErrorBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    if (process.env.NODE_ENV !== "production") console.warn("Scene fallback:", err);
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export default function ConstellationCanvas() {
  const tier = useSceneTier();

  // Before client detection resolves, or when WebGL is unavailable / low-power,
  // render the static frame — the hero paints instantly, never a blank canvas.
  if (!tier.ready || !tier.webgl) {
    return (
      <div className="scene-root" aria-hidden="true">
        <StaticFallback />
      </div>
    );
  }

  return (
    <div className="scene-root" aria-hidden="true">
      <SceneErrorBoundary fallback={<StaticFallback />}>
        <ConstellationScene
          nodeCount={tier.nodeCount}
          showLabels={tier.showLabels}
          reducedMotion={tier.reducedMotion}
        />
      </SceneErrorBoundary>
    </div>
  );
}
