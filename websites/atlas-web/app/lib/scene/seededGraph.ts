/**
 * seededGraph.ts — deterministic repository-graph generator for the Constellation.
 * Seeded PRNG so every render is reproducible (no per-frame randomness). Produces
 * node "home" positions (clustered = mapped memory) and "noise" positions
 * (scattered = raw repo), plus intra-cluster and labeled bridge edges.
 */

export type NodeKind = "file" | "symbol" | "concept";

export interface GraphNode {
  id: number;
  cluster: number;
  kind: NodeKind;
  home: [number, number, number]; // clustered / resolved
  noise: [number, number, number]; // scattered / raw repo
  importance: number; // 0..1 — drives color + size + label eligibility
  label?: string; // mono file path, only on a few important nodes
}

export interface GraphEdge {
  a: number;
  b: number;
  bridge: boolean; // cross-cluster relationship (brighter)
}

export interface RepoGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusterCenters: [number, number, number][];
  clusterLabels: string[];
}

/** mulberry32 — tiny fast deterministic PRNG. */
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Plausible module/file names — abstract, not claiming to be Atlas's real tree.
const CLUSTER_LABELS = ["core", "api", "auth", "graph", "store", "agent", "ui"];
const FILE_LABELS = [
  "auth/session.ts",
  "api/router.ts",
  "graph/depgraph.py",
  "store/evidence.py",
  "core/scan.py",
  "agent/mcp.py",
  "ui/panel.tsx",
  "core/memory.py",
];

const KINDS: NodeKind[] = ["file", "symbol", "concept"];

export interface GraphOptions {
  nodeCount: number;
  clusters?: number;
  seed?: number;
  /** overall spatial scale */
  radius?: number;
}

export function buildRepoGraph(opts: GraphOptions): RepoGraph {
  const {
    nodeCount,
    clusters = Math.min(7, Math.max(4, Math.round(nodeCount / 40))),
    seed = 20260713,
    radius = 9,
  } = opts;
  const rand = mulberry32(seed);
  const gauss = () => (rand() + rand() + rand() - 1.5) / 1.5; // ~N(0,1)-ish

  // Cluster centers on a loose tilted disc with depth.
  const clusterCenters: [number, number, number][] = [];
  for (let c = 0; c < clusters; c++) {
    const ang = (c / clusters) * Math.PI * 2 + rand() * 0.5;
    const rad = radius * (0.45 + rand() * 0.55);
    clusterCenters.push([
      Math.cos(ang) * rad,
      (rand() - 0.5) * radius * 0.5,
      Math.sin(ang) * rad * 0.7 - rand() * radius * 0.4,
    ]);
  }

  const nodes: GraphNode[] = [];
  for (let i = 0; i < nodeCount; i++) {
    const cluster = i % clusters;
    const center = clusterCenters[cluster];
    const spread = 1.6 + rand() * 1.2;
    const home: [number, number, number] = [
      center[0] + gauss() * spread,
      center[1] + gauss() * spread * 0.8,
      center[2] + gauss() * spread,
    ];
    // Raw-repo scatter: pushed far out in a big shell.
    const nAng = rand() * Math.PI * 2;
    const nR = radius * (1.4 + rand() * 1.6);
    const noise: [number, number, number] = [
      Math.cos(nAng) * nR + gauss() * 3,
      (rand() - 0.5) * radius * 2.4,
      Math.sin(nAng) * nR + gauss() * 3,
    ];
    const importance = Math.pow(rand(), 1.8); // skew low; few important
    const node: GraphNode = {
      id: i,
      cluster,
      kind: KINDS[Math.floor(rand() * KINDS.length)],
      home,
      noise,
      importance,
    };
    nodes.push(node);
  }

  // Labels go on the most-important nodes on the RIGHT of the graph, so once the
  // scene shifts the constellation into the right column they sit clear of the
  // left-aligned headline. Spread vertically so paths don't stack.
  const labelCandidates = nodes
    .filter((n) => n.home[0] > radius * 0.15)
    .sort((a, b) => b.importance - a.importance);
  const usedY: number[] = [];
  let labelIdx = 0;
  for (const n of labelCandidates) {
    if (labelIdx >= FILE_LABELS.length) break;
    if (usedY.some((y) => Math.abs(y - n.home[1]) < 1.1)) continue; // vertical spacing
    n.label = FILE_LABELS[labelIdx++];
    n.importance = Math.max(n.importance, 0.9);
    usedY.push(n.home[1]);
  }

  // Edges: k-nearest within each cluster + a few cross-cluster bridges.
  const edges: GraphEdge[] = [];
  const byCluster: number[][] = Array.from({ length: clusters }, () => []);
  nodes.forEach((n) => byCluster[n.cluster].push(n.id));

  const dist2 = (a: GraphNode, b: GraphNode) => {
    const dx = a.home[0] - b.home[0];
    const dy = a.home[1] - b.home[1];
    const dz = a.home[2] - b.home[2];
    return dx * dx + dy * dy + dz * dz;
  };

  for (const ids of byCluster) {
    for (const id of ids) {
      const near = ids
        .filter((o) => o !== id)
        .map((o) => ({ o, d: dist2(nodes[id], nodes[o]) }))
        .sort((x, y) => x.d - y.d)
        .slice(0, 2);
      for (const { o } of near) {
        if (id < o) edges.push({ a: id, b: o, bridge: false });
      }
    }
  }

  // Bridges: connect the most-important node of each cluster to the next.
  const clusterHub = byCluster.map((ids) =>
    ids.reduce((best, id) => (nodes[id].importance > nodes[best].importance ? id : best), ids[0])
  );
  for (let c = 0; c < clusters; c++) {
    const a = clusterHub[c];
    const b = clusterHub[(c + 1) % clusters];
    if (a !== undefined && b !== undefined && a !== b) {
      edges.push({ a: Math.min(a, b), b: Math.max(a, b), bridge: true });
    }
  }

  return {
    nodes,
    edges,
    clusterCenters,
    clusterLabels: clusterCenters.map((_, i) => CLUSTER_LABELS[i % CLUSTER_LABELS.length]),
  };
}
