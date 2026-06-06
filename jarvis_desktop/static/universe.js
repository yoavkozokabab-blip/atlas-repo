"use strict";

/** Phase 111/116B/121F — Cinematic 3D repository universe (visualization only). */
const ATLAS_UNIVERSE = (() => {
  const LARGE_GRAPH_THRESHOLD = 1000;
  const HOVER_NEIGHBOR_CAP = 100;
  const SELECT_NEIGHBOR_CAP = 250;
  const MODULE_VISUAL_MIN = 5.5;
  const MODULE_VISUAL_MAX = 28;
  /** Phase 121F — force native ForceGraph spheres for module view (custom meshes were invisible in UI). */
  const MODULE_FORCE_VISIBLE = true;
  const MODULE_FORCE_MIN_RADIUS = 5;
  const MODULE_FORCE_MAX_RADIUS = 16;
  const MODULE_NODE_REL_SIZE = 7;
  const MODULE_MIN_RADIUS = 1.85;
  const MODULE_MAX_RADIUS = 22;
  const SUBSYSTEM_MIN_RADIUS = 4;
  const SUBSYSTEM_MAX_RADIUS = 28;
  const SCENE_SCALE_DIVISOR = 82;

  const U = {
    fg: null,
    host: null,
    data: null,
    riskPercentiles: null,
    showEdges: true,
    tourActive: false,
    driftEnabled: true,
    screenshotMode: false,
    blastRadiusIds: null,
    blastTargetId: null,
    pulseNodes: new Set(),
    hubLabels: [],
    animFrame: null,
    driftFrame: null,
    lastInteraction: Date.now(),
    accessorsInstalled: false,
    largeGraph: false,
    adj: { neighbors: new Map(), meta: new Map(), linkKeys: new Map() },
    highlightState: { hoverId: null, selectedId: null, focus: new Set() },
    hoverRaf: null,
    lastHoverId: null,
    perfEnabled: false,
    subsystemView: false,
    sceneNodeScale: 1,
    forceVisibleModule: false,
    nodeSizing: null,
    renderDiagnostics: null,
  };

  function shouldForceVisibleModuleNodes(data, nodes) {
    if (!MODULE_FORCE_VISIBLE) return false;
    const view = (data?.view || "").toLowerCase();
    if (view && view !== "module") return false;
    if (nodes.some(isSubsystemNode)) return false;
    return true;
  }

  /**
   * Phase 123 — bounds-aware node sizing.
   *
   * The previous bug: node display radius was capped at ~16 units while the
   * galaxy coordinates spread nodes across hundreds of units. Fit to those
   * bounds, the spheres became sub-pixel dots so only the edge lines were
   * visible. Here we scale every node's radius to a fraction of the graph's
   * spatial spread, so nodes are ALWAYS clearly larger than the edges, and
   * important (high fan-in / hub) modules are visibly larger than leaves.
   */
  function computeSpatialBounds(nodes) {
    let maxR = 1;
    for (const n of nodes || []) {
      const x = n.galaxy_x ?? n.x ?? 0;
      const y = n.galaxy_y ?? n.y ?? 0;
      const z = n.galaxy_z ?? n.z ?? 0;
      maxR = Math.max(maxR, Math.hypot(x, y, z));
    }
    return maxR;
  }

  function nodeImportance(node) {
    // 0..1 importance from coupling + risk + provided visual size.
    const fi = node.fan_in || 0;
    const fo = node.fan_out || 0;
    const coupling = Math.log1p(fi * 1.6 + fo);
    const couplingNorm = Math.min(1, coupling / Math.log1p(60));
    const riskNorm = Math.min(1, (node.risk_score || 0) / 80);
    let imp = 0.55 * couplingNorm + 0.45 * riskNorm;
    if (node.is_hub) imp = Math.max(imp, 0.7);
    return Math.max(0, Math.min(1, imp));
  }

  function buildNodeSizing(nodes, subsystemView) {
    const bounds = computeSpatialBounds(nodes);
    // Largest node ~1/9 of the spread; smallest ~1/34, with absolute floors so
    // tiny/empty graphs still render visible spheres.
    const minR = Math.max(subsystemView ? 7 : 5, bounds / (subsystemView ? 22 : 34));
    const maxR = Math.max(minR + 4, bounds / (subsystemView ? 7 : 9));
    U.nodeSizing = { bounds, minR, maxR, subsystemView };
    return U.nodeSizing;
  }

  function nativeDisplayRadius(node) {
    const s = U.nodeSizing || { minR: 5, maxR: 16 };
    const imp = subsystemNodeImportance(node);
    const r = s.minR + (s.maxR - s.minR) * imp;
    return Number.isFinite(r) && r > 0 ? r : s.minR;
  }

  function subsystemNodeImportance(node) {
    if (isSubsystemNode(node)) {
      const mc = node.module_count || node.visual_size || node.size || 1;
      return Math.max(0.25, Math.min(1, Math.log1p(mc) / Math.log1p(60)));
    }
    return nodeImportance(node);
  }

  /** nodeVal so that built-in sphere display radius == nativeDisplayRadius (relSize=1). */
  function nativeNodeVal(node) {
    const r = nativeDisplayRadius(node);
    return Math.max(0.001, Math.pow(r, 3));
  }

  // ----------------------------------------------------------------------
  // Phase 124 — explicit OPAQUE node spheres.
  //
  // ForceGraph3D's built-in node spheres rendered as near-invisible dots in
  // practice (lit material + fog + camera distance washed them out, leaving a
  // spiderweb of edges). We bypass that entirely: each node is an OPAQUE,
  // UNLIT MeshBasicMaterial sphere with `fog:false`, so its colour is constant
  // and bright at any distance and never fades into the background. This is the
  // bulletproof path — a human sees actual balls.
  // ----------------------------------------------------------------------
  function baseNodeColorHex(node) {
    if (node.in_cycle) return 0x9a7bff;             // purple — cycle member
    const pct = U.riskPercentiles;
    if (pct?.top1?.has(node.id)) return 0xff5c7a;   // red/pink — highest risk
    if (pct?.top5?.has(node.id)) return 0xffc24b;   // amber — elevated risk
    if (node.is_hub) return 0x3ef0ff;               // cyan — hub
    if (isSubsystemNode(node)) return 0x5b9eff;     // blue — subsystem
    return 0x6f93ff;                                // bright blue — normal module
  }

  function makeNodeMesh(node) {
    if (typeof THREE === "undefined" || !node?.id) return null;
    const r = nativeDisplayRadius(node);
    const color = baseNodeColorHex(node);
    const geo = new THREE.SphereGeometry(r, 18, 14);
    const mat = new THREE.MeshBasicMaterial({
      color,
      transparent: false,
      opacity: 1,
      fog: false,        // never fade into the background
      depthWrite: true,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.nodeId = node.id;
    mesh.userData.baseColor = color;
    mesh.renderOrder = 2;
    node.__nodeMesh = mesh;
    return mesh;
  }

  function _dimColor(hex) {
    if (typeof THREE === "undefined") return hex;
    return new THREE.Color(hex).multiplyScalar(0.32).getHex();
  }

  /** Recolour/scale custom node meshes for hover, selection, focus-dim and blast. */
  function refreshNodeMeshColors() {
    if (!U.fg || typeof THREE === "undefined") return;
    const focus = U.highlightState.focus;
    const hasFocus = focus.size > 0;
    const hoverId = U.highlightState.hoverId;
    const selId = U.highlightState.selectedId;
    const blastTarget = U.blastTargetId;
    const blastSet = U.blastRadiusIds ? new Set(U.blastRadiusIds) : null;
    const graph = U.fg.graphData();
    for (const n of graph.nodes || []) {
      const mesh = n.__nodeMesh || n.__threeObj;
      if (!mesh || !mesh.material) continue;
      const base = mesh.userData.baseColor ?? baseNodeColorHex(n);
      let col = base;
      let scale = 1;
      if (blastSet && blastSet.has(n.id)) col = 0xff8a44;
      if (blastTarget === n.id) { col = 0xff2244; scale = 1.5; }
      if (selId === n.id) { col = 0xffffff; scale = 1.6; }
      else if (hoverId === n.id) { col = 0xbdf2ff; scale = 1.32; }
      else if (hasFocus && !focus.has(n.id)) { col = _dimColor(base); }
      mesh.material.color.set(col);
      mesh.scale.setScalar(scale);
    }
  }

  /** nodeVal for built-in spheres: display radius ≈ cbrt(val) * nodeRelSize */
  function moduleForceVal(node) {
    const visual = moduleVisualSize(node);
    const hub = node.is_hub ? 1.22 : 1;
    const desired = Math.max(
      MODULE_FORCE_MIN_RADIUS,
      4.2 + Math.sqrt(visual) * 0.75 * hub
    );
    const capped = Math.min(MODULE_FORCE_MAX_RADIUS, desired);
    const rel = MODULE_NODE_REL_SIZE;
    const val = Math.pow(capped / rel, 3);
    return Number.isFinite(val) && val > 0 ? val : Math.pow(MODULE_FORCE_MIN_RADIUS / rel, 3);
  }

  function moduleForceDisplayRadius(nodeVal) {
    const v = Number(nodeVal);
    if (!Number.isFinite(v) || v <= 0) return MODULE_FORCE_MIN_RADIUS;
    return Math.cbrt(v) * MODULE_NODE_REL_SIZE;
  }

  function isSubsystemNode(node) {
    return node?.graph_view === "subsystem" || String(node?.id || "").startsWith("subsystem:");
  }

  function moduleVisualSize(node) {
    const fi = node.fan_in || 0;
    const fo = node.fan_out || 0;
    const raw = node.visual_size || node.size || (6 + Math.log1p(fi + fo + 1) * 2.85);
    return Math.max(MODULE_VISUAL_MIN, Math.min(MODULE_VISUAL_MAX, raw));
  }

  function computeSceneNodeScale(nodes, subsystemView) {
    if (subsystemView || !(nodes || []).length) return 1;
    let maxR = 48;
    for (const n of nodes) {
      const x = n.galaxy_x ?? n.x ?? 0;
      const y = n.galaxy_y ?? n.y ?? 0;
      const z = n.galaxy_z ?? n.z ?? 0;
      maxR = Math.max(maxR, Math.hypot(x, y, z));
    }
    return Math.max(1.15, Math.min(6.5, maxR / SCENE_SCALE_DIVISOR));
  }

  function moduleNodeScale(node) {
    const visual = moduleVisualSize(node);
    const hubMul = node.is_hub ? Math.min(2.6, 1.05 + Math.sqrt(visual) * 0.14) : 1.0;
    const scene = U.sceneNodeScale || 1;
    const radius = scene * hubMul * (0.95 + Math.sqrt(visual) * 0.42);
    const safe = Number.isFinite(radius) ? radius : MODULE_MIN_RADIUS;
    return Math.max(MODULE_MIN_RADIUS, Math.min(MODULE_MAX_RADIUS, safe));
  }

  function subsystemNodeScale(node) {
    const hubScale = Math.min(3.2, Math.max(1.15, node.hub_scale || 1.35));
    const visual = Math.min(18, node.visual_size || node.size || 8);
    const scene = Math.max(1, (U.sceneNodeScale || 1) * 0.9);
    const radius = scene * hubScale * (0.72 + Math.sqrt(visual) * 0.38);
    const safe = Number.isFinite(radius) ? radius : SUBSYSTEM_MIN_RADIUS;
    return Math.max(SUBSYSTEM_MIN_RADIUS, Math.min(SUBSYSTEM_MAX_RADIUS, safe));
  }

  function graphSpatialRadius(nodes) {
    let maxR = 40;
    for (const n of nodes || []) {
      const x = n.x ?? n.galaxy_x ?? 0;
      const y = n.y ?? n.galaxy_y ?? 0;
      const z = n.z ?? n.galaxy_z ?? 0;
      const nodeR = U.nodeSizing ? nativeDisplayRadius(n)
        : (isSubsystemNode(n) ? subsystemNodeScale(n) : moduleNodeScale(n));
      maxR = Math.max(maxR, Math.hypot(x, y, z) + nodeR * 1.5);
    }
    return maxR;
  }

  function enablePerfLogging(on) {
    U.perfEnabled = !!on;
  }

  function linkEndpoints(link) {
    const sid = typeof link.source === "object" ? link.source.id : link.source;
    const tid = typeof link.target === "object" ? link.target.id : link.target;
    return [sid, tid];
  }

  function buildAdjacencyMaps(nodes, links) {
    const neighbors = new Map();
    const meta = new Map();
    const linkKeys = new Map();
    const ensure = (id) => {
      if (!neighbors.has(id)) neighbors.set(id, new Set());
      return neighbors.get(id);
    };
    nodes.forEach((n) => {
      ensure(n.id);
      meta.set(n.id, {
        label: n.label,
        subsystem: n.subsystem,
        fan_in: n.fan_in,
        risk_score: n.risk_score,
        is_hub: n.is_hub,
        tooltip: `${n.label}\n${n.subsystem || ""}\nfan-in ${n.fan_in} · risk ${n.risk_score}${n.is_hub ? " · HUB" : ""}`,
      });
    });
    links.forEach((link, idx) => {
      const [sid, tid] = linkEndpoints(link);
      if (!sid || !tid) return;
      ensure(sid).add(tid);
      ensure(tid).add(sid);
      linkKeys.set(`${sid}\0${tid}`, idx);
    });
    return { neighbors, meta, linkKeys };
  }

  function neighborFocus(nodeId, cap) {
    const focus = new Set();
    if (!nodeId) return focus;
    focus.add(nodeId);
    const neigh = U.adj.neighbors.get(nodeId);
    if (!neigh) return focus;
    let n = 0;
    for (const id of neigh) {
      if (n >= cap) break;
      focus.add(id);
      n += 1;
    }
    return focus;
  }

  function rebuildFocusSet() {
    const cap = U.largeGraph ? HOVER_NEIGHBOR_CAP : Number.POSITIVE_INFINITY;
    const selCap = U.largeGraph ? SELECT_NEIGHBOR_CAP : Number.POSITIVE_INFINITY;
    const focus = new Set();
    if (U.highlightState.selectedId) {
      neighborFocus(U.highlightState.selectedId, selCap).forEach((id) => focus.add(id));
    }
    if (U.highlightState.hoverId && U.highlightState.hoverId !== U.highlightState.selectedId) {
      neighborFocus(U.highlightState.hoverId, cap).forEach((id) => focus.add(id));
    }
    if (U.blastTargetId) focus.add(U.blastTargetId);
    (U.blastRadiusIds || []).forEach((id) => focus.add(id));
    U.highlightState.focus = focus;
  }

  function getBlastForNode(n) {
    if (!U.blastTargetId && !(U.blastRadiusIds || []).length) return null;
    return {
      target: U.blastTargetId,
      affected: new Set(U.blastRadiusIds || []),
    };
  }

  function logHoverPerf(ms, label) {
    if (!U.perfEnabled) return;
    if (ms > 50) console.warn(`[Atlas graph] ${label} ${ms.toFixed(1)}ms (>50ms)`);
    else if (ms > 16) console.debug(`[Atlas graph] ${label} ${ms.toFixed(1)}ms`);
  }

  function syncHighlightVisuals(fg) {
    if (!fg) return;
    rebuildFocusSet();
    const hoverId = U.highlightState.hoverId;
    if (hoverId && U.adj.meta.has(hoverId)) {
      const m = U.adj.meta.get(hoverId);
      fg.nodeLabel(`${m.label}\n${m.subsystem || ""}\nfan-in ${m.fan_in} · risk ${m.risk_score}${m.is_hub ? " · HUB" : ""}`);
    } else {
      fg.nodeLabel("");
    }
    refreshNodeMeshColors();
    if (typeof fg.refresh === "function") fg.refresh();
  }

  function installGraphAccessors(fg) {
    if (!fg || U.accessorsInstalled) return;
    U.accessorsInstalled = true;
    const showEdges = () => U.showEdges !== false;

    fg.linkVisibility(() => showEdges());
    fg.nodeColor((n) => {
      const blast = getBlastForNode(n);
      const active = U.highlightState.focus.has(n.id);
      return nodeColor(n, active, blast);
    });
    fg.linkColor((l) => {
      if (!showEdges()) return "rgba(0,0,0,0)";
      const [sid, tid] = linkEndpoints(l);
      const active = U.highlightState.focus.size > 0
        && (U.highlightState.focus.has(sid) || U.highlightState.focus.has(tid));
      return linkColor(l, active, l.bridge);
    });
    fg.linkWidth((l) => {
      if (!showEdges()) return 0;
      const [sid, tid] = linkEndpoints(l);
      const active = U.highlightState.focus.size > 0
        && (U.highlightState.focus.has(sid) || U.highlightState.focus.has(tid));
      const w = l.weight || 1;
      if (l.bridge) return active ? 1.4 + w * 0.35 : 0.2 + w * 0.08;
      return active ? 1.05 + w * 0.28 : 0.06 + w * 0.04;
    });
    fg.nodeOpacity((n) => {
      if (!n) return 0;
      if (U.forceVisibleModule) {
        if (U.highlightState.focus.size === 0) return 1.0;
        return U.highlightState.focus.has(n.id) ? 1.0 : 0.55;
      }
      if (U.highlightState.focus.size === 0) {
        return isSubsystemNode(n) ? 0.92 : 1.0;
      }
      return U.highlightState.focus.has(n.id) ? 1.0 : 0.22;
    });
    fg.linkOpacity((l) => {
      if (!showEdges()) return 0;
      const [sid, tid] = linkEndpoints(l);
      const active = U.highlightState.focus.size > 0
        && (U.highlightState.focus.has(sid) || U.highlightState.focus.has(tid));
      const base = l.bridge ? 0.5 : (l.opacity || 0.18);
      if (U.highlightState.focus.size === 0) return base;
      return active ? Math.min(0.95, base + 0.4) : 0.04;
    });
    fg.linkDirectionalParticles((l) => {
      if (!showEdges()) return 0;
      const [sid, tid] = linkEndpoints(l);
      const active = U.highlightState.focus.size > 0
        && (U.highlightState.focus.has(sid) || U.highlightState.focus.has(tid));
      const pulseCtx = U.highlightState.selectedId || U.highlightState.hoverId
        || U.pulseNodes.has(sid) || U.pulseNodes.has(tid);
      if (active && pulseCtx) return l.bridge ? 4 : 3;
      if (U.largeGraph) return 0;
      if (l.bridge) return 4;
      return (l.weight || 1) > 2.5 ? 2 : 0;
    });
    fg.linkDirectionalParticleWidth((l) => (l.bridge ? 1.8 : 1.2));
    fg.linkDirectionalParticleSpeed((l) => 0.004 + (l.weight || 1) * 0.0012);
    fg.linkDirectionalParticleColor((l) => (l.bridge ? "#42f5b0" : "#78a0ff"));
  }

  function scheduleHoverUpdate(fg, node, callbacks) {
    const id = node?.id ?? null;
    if (id === U.lastHoverId) return;
    U.lastHoverId = id;
    callbacks?.onNodeHover?.(node);
    if (U.hoverRaf) cancelAnimationFrame(U.hoverRaf);
    U.hoverRaf = requestAnimationFrame(() => {
      U.hoverRaf = null;
      const t0 = performance.now();
      U.highlightState.hoverId = id;
      syncHighlightVisuals(fg);
      logHoverPerf(performance.now() - t0, "hover");
    });
  }

  function applySelectionHighlight(fg, selectedNode) {
    if (!fg) return;
    const t0 = performance.now();
    U.highlightState.selectedId = selectedNode?.id || null;
    syncHighlightVisuals(fg);
    logHoverPerf(performance.now() - t0, "select");
  }

  function nodeColor(n, active, blast) {
    const dim = U.highlightState.focus.size > 0 && !active;
    if (blast?.target === n.id) return "#ff2244";
    if (blast?.affected?.has(n.id)) return "#ff8a44";
    if (n.in_cycle) return active ? "#d4b8ff" : dim ? "#4a3868" : "#9a7bff";
    const pct = U.riskPercentiles;
    if (pct?.top1?.has(n.id)) return active ? "#ff9db0" : dim ? "#6a3040" : "#ff5c7a";
    if (pct?.top5?.has(n.id)) return active ? "#ffe08a" : dim ? "#6a5528" : "#ffc24b";
    if (n.is_hub) return active ? "#8af0ff" : dim ? "#1a4850" : "#3ef0ff";
    if (isSubsystemNode(n)) return active ? "#7ec8ff" : dim ? "#2a3d58" : "#5b9eff";
    return active ? "#9eb8ff" : dim ? "#2a3558" : "#5b76c8";
  }

  function linkColor(link, active, bridge) {
    const base = bridge ? 0.55 : (link.opacity || 0.18);
    const opacity = active ? Math.min(0.98, base + 0.35) : base;
    const hue = bridge ? "180,255,220" : "120,160,255";
    return `rgba(${hue},${opacity})`;
  }

  function computePercentiles(nodes) {
    const ranked = [...nodes].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    const count = ranked.length || 1;
    const top1 = Math.max(1, Math.ceil(count * 0.01));
    const top5 = Math.max(1, Math.ceil(count * 0.05));
    U.pulseNodes = new Set(ranked.slice(0, top1).map(n => n.id));
    return {
      top1: new Set(ranked.slice(0, top1).map(n => n.id)),
      top5: new Set(ranked.slice(0, top5).map(n => n.id)),
    };
  }

  function sphereNodeObject(node) {
    if (U.forceVisibleModule) return null;
    if (typeof THREE === "undefined") return null;
    if (!node?.id) return null;
    const group = new THREE.Group();
    group.userData.nodeId = node.id;
    const subsystem = isSubsystemNode(node);
    const scale = subsystem ? subsystemNodeScale(node) : moduleNodeScale(node);
    if (!Number.isFinite(scale) || scale <= 0) return null;
    const geo = subsystem || node.is_hub
      ? new THREE.IcosahedronGeometry(subsystem ? scale : scale * 1.15, subsystem ? 0 : 1)
      : new THREE.SphereGeometry(scale, 16, 12);
    const color = new THREE.Color(nodeColor(node, false, null));
    const topRisk = subsystem && (node.risk_rank <= 3 || U.riskPercentiles?.top5?.has(node.id));
    const selected = U.highlightState.selectedId === node.id;
    const emissiveScale = U.pulseNodes.has(node.id) ? 0.65
      : selected ? 0.52
      : topRisk ? 0.38
      : subsystem ? 0.22
      : node.is_hub ? 0.48
      : 0.28;
    const mat = new THREE.MeshPhongMaterial({
      color,
      emissive: color.clone().multiplyScalar(emissiveScale),
      transparent: false,
      opacity: 1,
      shininess: subsystem ? 65 : node.is_hub ? 100 : 52,
      depthWrite: true,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.renderOrder = 2;
    group.add(mesh);

    if (node.in_cycle) {
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(scale * 1.55, 12, 8),
        new THREE.MeshBasicMaterial({ color: 0x9a7bff, transparent: true, opacity: 0.14, wireframe: true })
      );
      group.add(halo);
    }

    if (subsystem && topRisk) {
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(scale * 1.12, 0)),
        new THREE.LineBasicMaterial({ color: 0xff5c7a, transparent: true, opacity: 0.9 })
      );
      group.add(outline);
    } else if (node.is_hub && !subsystem) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(scale * 2.0, scale * 0.1, 8, 28),
        new THREE.MeshBasicMaterial({ color: 0x3ef0ff, transparent: true, opacity: 0.55 })
      );
      ring.rotation.x = Math.PI / 2;
      group.add(ring);
    }

    const glow = new THREE.Mesh(
      new THREE.SphereGeometry(scale * 1.22, 10, 8),
      new THREE.MeshBasicMaterial({
        color: color.getHex(),
        transparent: true,
        opacity: subsystem ? 0.12 : node.is_hub ? 0.18 : 0.1,
        depthWrite: false,
      })
    );
    glow.renderOrder = 1;
    group.add(glow);

    group.userData.mesh = mesh;
    group.userData.glow = glow;
    group.userData.baseEmissive = mat.emissive.clone();
    return group;
  }

  function measureNodeDisplayRadius(threeObj) {
    if (!threeObj) return 0;
    let r = 0;
    if (threeObj.geometry?.parameters?.radius != null) {
      r = threeObj.geometry.parameters.radius;
    }
    const sx = threeObj.scale?.x ?? 1;
    const sy = threeObj.scale?.y ?? 1;
    const sz = threeObj.scale?.z ?? 1;
    const scale = Math.max(sx, sy, sz);
    if (threeObj.type === "Group" && threeObj.children?.length) {
      for (const child of threeObj.children) {
        const cr = measureNodeDisplayRadius(child);
        if (cr > r) r = cr;
      }
      return r;
    }
    return r * scale;
  }

  function auditRenderedMeshes(fg, graphNodes) {
    const nodes = graphNodes || fg?.graphData()?.nodes || [];
    let meshCount = 0;
    let minR = Infinity;
    let maxR = 0;
    const missing = [];
    for (const n of nodes) {
      const obj = n.__threeObj;
      if (!obj) {
        missing.push(n.id);
        continue;
      }
      meshCount += 1;
      const r = measureNodeDisplayRadius(obj);
      if (Number.isFinite(r) && r > 0) {
        minR = Math.min(minR, r);
        maxR = Math.max(maxR, r);
      }
    }
    if (!Number.isFinite(minR)) minR = 0;
    const diag = {
      nodes: nodes.length,
      meshes: meshCount,
      minRadius: Math.round(minR * 100) / 100,
      maxRadius: Math.round(maxR * 100) / 100,
      forceVisibleModule: !!U.forceVisibleModule,
      missingMeshes: missing.length,
    };
    U.renderDiagnostics = diag;
    console.info("[Atlas graph] render audit", diag);
    if (meshCount !== nodes.length) {
      console.warn(
        `[Atlas graph] rendered_node_meshes (${meshCount}) !== graph.nodes.length (${nodes.length})`
      );
    }
    if (U.forceVisibleModule && meshCount > 0 && minR < MODULE_FORCE_MIN_RADIUS - 0.5) {
      console.warn(`[Atlas graph] node_radius_min ${minR} < ${MODULE_FORCE_MIN_RADIUS}`);
    }
    return diag;
  }

  function setupScene(fg) {
    if (typeof THREE === "undefined") return;
    const scene = fg.scene();
    // Phase 124 — very light fog so edges recede slightly but nodes (fog:false)
    // and the scene never wash out. Heavy fog previously hid the graph.
    scene.fog = new THREE.FogExp2(0x070b14, 0.00035);
    const amb = new THREE.AmbientLight(0x446688, 1.05);
    const key = new THREE.PointLight(0x3ef0ff, 1.45, 12000);
    key.position.set(120, 80, 160);
    const fill = new THREE.PointLight(0x9a7bff, 0.85, 12000);
    fill.position.set(-140, -60, -80);
    scene.add(amb, key, fill);
    try {
      const cam = fg.camera();
      if (cam) {
        cam.near = 0.8;
        cam.far = 25000;
        cam.updateProjectionMatrix?.();
      }
    } catch (e) { /* optional */ }
  }

  function setupControls(fg) {
    try {
      const controls = fg.controls();
      if (!controls) return;
      controls.enableDamping = true;
      controls.dampingFactor = 0.09;
      controls.rotateSpeed = 0.45;
      const mark = () => { U.lastInteraction = Date.now(); U.driftEnabled = false; };
      controls.addEventListener?.("start", mark);
      controls.addEventListener?.("change", mark);
      controls.addEventListener?.("end", () => {
        U.lastInteraction = Date.now();
        setTimeout(() => { if (!U.tourActive) U.driftEnabled = true; }, 4000);
      });
    } catch (e) { /* optional */ }
  }

  function setupGalaxyForces(fg, nodes, options) {
    options = options || {};
    const subsystem = !!options.subsystemView;
    try {
      const charge = fg.d3Force("charge");
      if (charge?.strength) {
        charge.strength(subsystem
          ? -180 - Math.min(280, nodes.length * 6)
          : -85 - Math.min(200, nodes.length * 0.09));
      }
      const linkForce = fg.d3Force("link");
      if (linkForce?.distance) {
        linkForce.distance(l => subsystem
          ? 38 + Math.min(24, (l.edge_count || 1) * 2.5)
          : 18 + (8 / Math.max(l.opacity || 0.15, 0.12)));
      }
      if (typeof d3 !== "undefined") {
        const pull = subsystem ? 0.12 : 0.055;
        fg.d3Force("x", d3.forceX(n => n.galaxy_x || 0).strength(pull));
        fg.d3Force("y", d3.forceY(n => n.galaxy_y || 0).strength(pull));
        if (d3.forceZ) fg.d3Force("z", d3.forceZ(n => n.galaxy_z || 0).strength(subsystem ? 0.08 : 0.04));
        if (d3.forceCollide) {
          if (subsystem) {
            fg.d3Force("collide", d3.forceCollide(n => nativeDisplayRadius(n) * 1.12)
              .strength(0.85).iterations(2));
          } else if (nodes.length <= 1500) {
            fg.d3Force("collide", d3.forceCollide(n => nativeDisplayRadius(n) * 1.1)
              .strength(0.3).iterations(1));
          } else {
            fg.d3Force("collide", null);
          }
        }
      }
    } catch (e) { /* force hooks vary by build */ }
    nodes.forEach(n => {
      if (n.galaxy_x != null) {
        n.x = n.galaxy_x;
        n.y = n.galaxy_y;
        n.z = n.galaxy_z;
      }
    });
  }

  function startPulseLoop(fg) {
    stopPulseLoop();
    const tick = () => {
      if (!U.fg) return;
      const t = Date.now() * 0.003;
      const graph = fg.graphData();
      (graph.nodes || []).forEach(node => {
        const obj = node.__threeObj;
        if (!obj?.userData?.mesh) return;
        const mesh = obj.userData.mesh;
        if (U.pulseNodes.has(node.id)) {
          const pulse = 0.35 + Math.sin(t * 2.2) * 0.25;
          mesh.material.emissive.copy(obj.userData.baseEmissive).multiplyScalar(1 + pulse);
        }
      });
      U.animFrame = requestAnimationFrame(tick);
    };
    U.animFrame = requestAnimationFrame(tick);
  }

  function stopPulseLoop() {
    if (U.animFrame) cancelAnimationFrame(U.animFrame);
    U.animFrame = null;
  }

  function startCameraDrift(fg) {
    stopCameraDrift();
    const drift = () => {
      if (!U.fg || U.tourActive || !U.driftEnabled) {
        U.driftFrame = requestAnimationFrame(drift);
        return;
      }
      if (Date.now() - U.lastInteraction < 5000) {
        U.driftFrame = requestAnimationFrame(drift);
        return;
      }
      const t = Date.now() * 0.00004;
      const dist = 180 + Math.sqrt((U.data?.nodes?.length || 100)) * 12;
      fg.cameraPosition({
        x: dist * Math.sin(t),
        y: 40 + Math.sin(t * 0.6) * 18,
        z: dist * Math.cos(t),
      }, { x: 0, y: 0, z: 0 }, 0);
      U.driftFrame = requestAnimationFrame(drift);
    };
    U.driftFrame = requestAnimationFrame(drift);
  }

  function stopCameraDrift() {
    if (U.driftFrame) cancelAnimationFrame(U.driftFrame);
    U.driftFrame = null;
  }

  /** Legacy entry — mutates highlight state then refresh (no accessor re-bind). */
  function applyHighlight(fg, focusNode, blast) {
    if (!fg) return;
    if (blast?.affected) {
      U.blastRadiusIds = [...blast.affected];
      U.blastTargetId = blast.target || null;
    }
    if (focusNode?.id) {
      U.highlightState.selectedId = focusNode.id;
    }
    syncHighlightVisuals(fg);
  }

  function fitGraphCamera(fg, nodes) {
    if (!fg || !nodes?.length) return;
    const subsystem = U.subsystemView;
    const bounds = graphSpatialRadius(nodes);
    // Phase 124 — tighter fit so node spheres are clearly visible at default zoom
    // (previous multiplier pushed the camera back until nodes looked like dots).
    const dist = Math.max(
      subsystem ? 80 : 95,
      bounds * 1.35 + Math.sqrt(nodes.length) * (subsystem ? 10 : 6)
    );
    const lookY = subsystem ? 0 : bounds * 0.04;
    fg.cameraPosition(
      { x: dist * 0.38, y: dist * 0.26 + lookY, z: dist * 0.92 },
      { x: 0, y: lookY, z: 0 },
      subsystem ? 700 : 1100
    );
  }

  function resetGraphView() {
    if (!U.fg) return;
    const graph = U.fg.graphData();
    fitGraphCamera(U.fg, graph.nodes || []);
  }

  function buildGraph(host, data, callbacks) {
    callbacks = callbacks || {};
    destroyGraph();
    U.host = host;
    U.data = data;
    if (!data?.ok || !(data.nodes || []).length) {
      host.innerHTML = '<div style="display:grid;place-items:center;height:100%;color:var(--muted)">No graph data.</div>';
      return null;
    }
    if (typeof ForceGraph3D === "undefined") {
      host.innerHTML = `<div style="padding:24px;color:var(--muted)">3D graph library unavailable offline.</div>`;
      return null;
    }

    host.innerHTML = "";
    const nodes = data.nodes.map(n => ({ ...n }));
    const links = data.links.map(l => ({ ...l }));
    U.subsystemView = data.view === "subsystem" || data.graph_view === "subsystem"
      || nodes.some(n => isSubsystemNode(n));
    U.sceneNodeScale = computeSceneNodeScale(nodes, U.subsystemView);
    // Phase 123 — native ForceGraph spheres for ALL views, sized to the spatial
    // spread so nodes are reliably visible (visibility > custom-mesh beauty).
    U.forceVisibleModule = true;
    buildNodeSizing(nodes, U.subsystemView);
    U.riskPercentiles = computePercentiles(nodes);
    const t0 = performance.now();

    const fg = ForceGraph3D()(host)
      .graphData({ nodes: [], links: [] })
      .backgroundColor("rgba(0,0,0,0)")
      .showNavInfo(false)
      .nodeLabel(n => (U.subsystemView && n ? `${n.label || n.id} · ${n.module_count ?? 0}` : ""))
      .linkCurvature(0.12)
      .linkDirectionalArrowLength(0)
      .onNodeClick(n => callbacks.onNodeClick?.(n))
      .onNodeHover(n => scheduleHoverUpdate(fg, n, callbacks))
      .onBackgroundClick(() => {
        callbacks.onBackgroundClick?.();
        U.lastHoverId = null;
        U.highlightState.hoverId = null;
        scheduleHoverUpdate(fg, null, callbacks);
      })
      .width(host.clientWidth)
      .height(host.clientHeight);

    // Phase 124 — explicit opaque spheres (bulletproof visibility). nodeVal still
    // feeds the force layout / spacing; the visible body is our MeshBasicMaterial.
    fg.nodeThreeObject(n => makeNodeMesh(n))
      .nodeThreeObjectExtend(false)
      .nodeVal(n => nativeNodeVal(n));

    U.fg = fg;
    setupScene(fg);
    setupControls(fg);
    setupGalaxyForces(fg, nodes, { subsystemView: U.subsystemView });

    installGraphAccessors(fg);

    const chunkSize = nodes.length > 1000 ? 160 : nodes.length;
    let loaded = 0;
    function loadChunk() {
      const slice = nodes.slice(loaded, loaded + chunkSize);
      loaded += slice.length;
      const current = fg.graphData();
      const mergedNodes = [...(current.nodes || []), ...slice];
      const ids = new Set(mergedNodes.map(n => n.id));
      const mergedLinks = links.filter(l => ids.has(l.source) && ids.has(l.target));
      fg.graphData({ nodes: mergedNodes, links: mergedLinks });
      if (loaded < nodes.length) {
        requestAnimationFrame(loadChunk);
      } else {
        U.adj = buildAdjacencyMaps(mergedNodes, mergedLinks);
        U.largeGraph = mergedNodes.length > LARGE_GRAPH_THRESHOLD;
        U.highlightState = { hoverId: null, selectedId: null, focus: new Set() };
        installGraphAccessors(fg);
        syncHighlightVisuals(fg);
        const renderDiagnostics = auditRenderedMeshes(fg, mergedNodes);
        const perf = {
          loadMs: Math.round(performance.now() - t0),
          nodes: mergedNodes.length,
          links: mergedLinks.length,
          largeGraph: U.largeGraph,
          adjacencyBuilt: U.adj.neighbors.size,
          forceVisibleModule: U.forceVisibleModule,
          renderDiagnostics,
        };
        callbacks.onLoaded?.(perf);
        fitGraphCamera(fg, mergedNodes);
        if (!U.largeGraph && !U.forceVisibleModule) startPulseLoop(fg);
        startCameraDrift(fg);
      }
    }
    requestAnimationFrame(loadChunk);

    if (!U._resizeBound) {
      U._resizeBound = true;
      window.addEventListener("resize", () => {
        if (!U.fg || !U.host) return;
        U.fg.width(U.host.clientWidth).height(U.host.clientHeight);
      });
    }
    return fg;
  }

  function getBlastState() {
    if (!U.blastRadiusIds && !U.blastTargetId) return null;
    return {
      target: U.blastTargetId,
      affected: new Set(U.blastRadiusIds || []),
    };
  }

  function highlightBlastRadius(highlight) {
    if (!highlight) {
      U.blastRadiusIds = null;
      U.blastTargetId = null;
    } else {
      U.blastTargetId = highlight.target_node_id || null;
      const ids = new Set(highlight.affected_node_ids || highlight.node_ids || []);
      if (U.blastTargetId) ids.delete(U.blastTargetId);
      U.blastRadiusIds = [...ids];
    }
    syncHighlightVisuals(U.fg);
    if (U.blastTargetId && U.fg) {
      const graph = U.fg.graphData();
      const target = (graph.nodes || []).find(n => n.id === U.blastTargetId);
      if (target) flyToNode(target, 900);
    }
  }

  function flyToNode(node, ms) {
    if (!U.fg || !node) return;
    const dist = 55 + (node.is_hub ? 25 : 12);
    const x = (node.x ?? node.galaxy_x ?? 0) + dist * 0.4;
    const y = (node.y ?? node.galaxy_y ?? 0) + dist * 0.15;
    const z = (node.z ?? node.galaxy_z ?? 0) + dist;
    const lx = node.x ?? node.galaxy_x ?? 0;
    const ly = node.y ?? node.galaxy_y ?? 0;
    const lz = node.z ?? node.galaxy_z ?? 0;
    U.fg.cameraPosition({ x, y, z }, { x: lx, y: ly, z: lz }, ms || 1400);
  }

  function startTour(stops, onStep) {
    if (!U.fg || !stops?.length) return;
    U.tourActive = true;
    U.driftEnabled = false;
    let index = 0;

    function runStep() {
      if (index >= stops.length) {
        U.tourActive = false;
        U.driftEnabled = true;
        onStep?.({ done: true });
        return;
      }
      const stop = stops[index];
      onStep?.({ stop, index, total: stops.length });
      const graph = U.fg.graphData();
      const anchor = (graph.nodes || []).find(n => n.id === stop.anchor_node_id)
        || (graph.nodes || []).find(n => (stop.focus_node_ids || []).includes(n.id));
      if (anchor) flyToNode(anchor, 1600);
      const focusIds = new Set(stop.focus_node_ids || []);
      U.blastTargetId = stop.anchor_node_id;
      U.blastRadiusIds = [...focusIds].filter(id => id !== U.blastTargetId);
      syncHighlightVisuals(U.fg);
      index += 1;
      setTimeout(runStep, 6500);
    }
    runStep();
  }

  function stopTour() {
    U.tourActive = false;
    U.driftEnabled = true;
  }

  function destroyGraph() {
    stopPulseLoop();
    stopCameraDrift();
    stopTour();
    if (U.hoverRaf) cancelAnimationFrame(U.hoverRaf);
    U.hoverRaf = null;
    U.lastHoverId = null;
    U.fg = null;
    U.subsystemView = false;
    U.sceneNodeScale = 1;
    U.forceVisibleModule = false;
    U.nodeSizing = null;
    U.renderDiagnostics = null;
    U.blastRadiusIds = null;
    U.blastTargetId = null;
    U.accessorsInstalled = false;
    U.adj = { neighbors: new Map(), meta: new Map(), linkKeys: new Map() };
    U.highlightState = { hoverId: null, selectedId: null, focus: new Set() };
  }

  function setShowEdges(show) {
    U.showEdges = show;
    syncHighlightVisuals(U.fg);
  }

  function refreshHighlight(selectedNode) {
    applySelectionHighlight(U.fg, selectedNode);
  }

  function exportPNG(scale) {
    if (!U.fg) return null;
    try {
      const renderer = U.fg.renderer();
      const canvas = renderer.domElement;
      const prev = { w: canvas.width, h: canvas.height };
      const factor = scale || 2;
      U.fg.width(U.host.clientWidth * factor).height(U.host.clientHeight * factor);
      renderer.render(U.fg.scene(), U.fg.camera());
      const url = canvas.toDataURL("image/png");
      U.fg.width(U.host.clientWidth).height(U.host.clientHeight);
      return url;
    } catch (e) {
      return null;
    }
  }

  function exportSVG() {
    const nodes = U.data?.nodes || [];
    const links = U.data?.links || [];
    if (!nodes.length) return null;
    const xs = nodes.map(n => n.galaxy_x || 0);
    const ys = nodes.map(n => n.galaxy_y || 0);
    const minX = Math.min(...xs) - 40;
    const maxX = Math.max(...xs) + 40;
    const minY = Math.min(...ys) - 40;
    const maxY = Math.max(...ys) + 40;
    const w = maxX - minX;
    const h = maxY - minY;
    const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${w} ${h}" width="${Math.round(w * 2)}" height="${Math.round(h * 2)}">`;
    svg += `<rect x="${minX}" y="${minY}" width="${w}" height="${h}" fill="#070b14"/>`;
    links.forEach(l => {
      const s = byId[l.source] || byId[l.source?.id];
      const t = byId[l.target] || byId[l.target?.id];
      if (!s || !t) return;
      const stroke = l.bridge ? "#42f5b0" : "#5b76c8";
      const op = l.bridge ? 0.55 : (l.opacity || 0.2);
      svg += `<line x1="${s.galaxy_x}" y1="${s.galaxy_y}" x2="${t.galaxy_x}" y2="${t.galaxy_y}" stroke="${stroke}" stroke-opacity="${op}" stroke-width="${l.bridge ? 1.2 : 0.6}"/>`;
    });
    nodes.forEach(n => {
      const subsystem = isSubsystemNode(n);
      const r = subsystem
        ? Math.min(8, 2.5 + Math.sqrt(Math.min(n.visual_size || n.size || 6, 14)))
        : (n.is_hub ? 5 : 2.2);
      const fill = n.in_cycle ? "#9a7bff" : subsystem ? "#5b9eff" : n.is_hub ? "#3ef0ff" : "#5b76c8";
      svg += `<circle cx="${n.galaxy_x}" cy="${n.galaxy_y}" r="${r}" fill="${fill}"/>`;
      if (subsystem || n.is_hub) {
        svg += `<text x="${n.galaxy_x + 6}" y="${n.galaxy_y - 6}" fill="#9eb8ff" font-size="8" font-family="Inter,sans-serif">${escapeXml(n.label)}</text>`;
      }
    });
    svg += "</svg>";
    return svg;
  }

  function escapeXml(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  }

  function downloadDataUrl(url, filename) {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
  }

  function downloadText(text, filename, mime) {
    const blob = new Blob([text], { type: mime || "text/plain" });
    const url = URL.createObjectURL(blob);
    downloadDataUrl(url, filename);
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function toggleScreenshotMode(on) {
    U.screenshotMode = !!on;
    document.body.classList.toggle("screenshot-mode", U.screenshotMode);
  }

  function animateCounter(el, target, duration) {
    if (!el) return;
    const start = parseFloat(el.textContent) || 0;
    const end = Number(target) || 0;
    const t0 = performance.now();
    const dur = duration || 900;
    function frame(now) {
      const p = Math.min(1, (now - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = start + (end - start) * eased;
      el.textContent = Number.isInteger(end) ? Math.round(val) : val.toFixed(1);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function renderTimeline(container, timeline) {
    if (!container) return;
    if (!timeline?.ok) {
      container.innerHTML = `<span class="muted tiny">Timeline unavailable — scan a repository first.</span>`;
      return;
    }
    const snaps = timeline.snapshots || [];
    const latest = timeline.latest || snaps[snaps.length - 1] || {};
    const bars = snaps.map((s, i) => {
      const h = 20 + Math.min(60, (s.module_count || 0) / 8);
      return `<div class="tl-bar" style="height:${h}px" title="modules ${s.module_count} · edges ${s.dependency_count}"><span>${s.module_count}</span></div>`;
    }).join("");
    container.innerHTML = `
      <div class="tl-head">
        <span class="tl-title">Architecture timeline</span>
        <span class="muted tiny">${timeline.history_available ? "history" : "baseline snapshot"}</span>
      </div>
      <div class="tl-metrics">
        <span>modules <b>${latest.module_count ?? "—"}</b></span>
        <span>edges <b>${latest.dependency_count ?? "—"}</b></span>
        <span>risk <b>${latest.risk_score ?? "—"}</b></span>
        <span>cycles <b>${latest.cycle_count ?? "—"}</b></span>
      </div>
      <div class="tl-chart">${bars || '<span class="muted tiny">No snapshots yet</span>'}</div>`;
  }

  return {
    buildGraph,
    destroyGraph,
    fitGraphCamera,
    resetGraphView,
    highlightBlastRadius,
    refreshHighlight,
    applySelectionHighlight,
    buildAdjacencyMaps,
    scheduleHoverUpdate,
    enablePerfLogging,
    LARGE_GRAPH_THRESHOLD,
    HOVER_NEIGHBOR_CAP,
    setShowEdges,
    startTour,
    stopTour,
    flyToNode,
    exportPNG,
    exportSVG,
    downloadDataUrl,
    downloadText,
    toggleScreenshotMode,
    animateCounter,
    renderTimeline,
    getRenderDiagnostics() {
      return U.renderDiagnostics;
    },
    MODULE_FORCE_VISIBLE,
    MODULE_FORCE_MIN_RADIUS,
    get fg() { return U.fg; },
  };
})();
window.ATLAS_UNIVERSE = ATLAS_UNIVERSE;
