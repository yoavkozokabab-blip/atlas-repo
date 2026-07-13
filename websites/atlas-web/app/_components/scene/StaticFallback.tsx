"use client";

/**
 * Static constellation frame for no-WebGL / low-power / reduced-motion.
 * Pure inline SVG (no canvas, no JS loop) — a resolved memory graph around a
 * core, matching the live scene's language. Deterministic so it never shifts.
 */
export default function StaticFallback() {
  // A small hand-placed graph: clusters of nodes bound to a central core.
  const clusters = [
    { cx: 300, cy: 300, n: 7 },
    { cx: 780, cy: 230, n: 6 },
    { cx: 980, cy: 520, n: 7 },
    { cx: 620, cy: 560, n: 6 },
    { cx: 420, cy: 640, n: 5 },
  ];
  const core = { x: 660, y: 400 };
  let seed = 7;
  const rnd = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  const pts: { x: number; y: number; r: number; hub?: boolean }[] = [];
  const hubs: { x: number; y: number }[] = [];
  clusters.forEach((c) => {
    let hub = { x: c.cx, y: c.cy };
    for (let i = 0; i < c.n; i++) {
      const a = rnd() * Math.PI * 2;
      const d = 22 + rnd() * 70;
      const x = c.cx + Math.cos(a) * d;
      const y = c.cy + Math.sin(a) * d * 0.8;
      const r = 1.4 + rnd() * 2.8;
      const hubbish = i === 0;
      pts.push({ x, y, r: hubbish ? 3.6 : r, hub: hubbish });
      if (hubbish) hub = { x, y };
    }
    hubs.push(hub);
  });

  return (
    <svg
      className="static-scene"
      viewBox="0 0 1320 820"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="coreG" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#8CF0DC" stopOpacity="0.9" />
          <stop offset="45%" stopColor="#5FD3BE" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#2C6F66" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* intra-cluster + node->hub edges */}
      <g stroke="#2C6F66" strokeOpacity="0.35">
        {clusters.map((c, ci) => {
          const cl = pts.filter(
            (p) => Math.hypot(p.x - c.cx, p.y - c.cy) < 130
          );
          const hub = hubs[ci];
          return cl.map((p, i) => (
            <line key={`${ci}-${i}`} x1={hub.x} y1={hub.y} x2={p.x} y2={p.y} />
          ));
        })}
      </g>
      {/* bridges hub->core */}
      <g stroke="#5FD3BE" strokeOpacity="0.5">
        {hubs.map((h, i) => (
          <line key={i} x1={h.x} y1={h.y} x2={core.x} y2={core.y} />
        ))}
      </g>
      {/* core glow */}
      <circle cx={core.x} cy={core.y} r={120} fill="url(#coreG)" />
      <circle cx={core.x} cy={core.y} r={16} fill="#0c1613" stroke="#8CF0DC" strokeOpacity="0.6" />
      {/* nodes */}
      <g>
        {pts.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={p.r}
            fill={p.hub ? "#5FD3BE" : "#2C6F66"}
            fillOpacity={p.hub ? 0.95 : 0.7}
          />
        ))}
      </g>
    </svg>
  );
}
