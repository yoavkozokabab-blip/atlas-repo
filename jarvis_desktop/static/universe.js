"use strict";

/** Phase 111 — Cinematic 3D repository universe (visualization only). */
const JARVIS_UNIVERSE = (() => {
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
  };

  function nodeColor(n, active, blast) {
    if (blast?.target === n.id) return "#ff2244";
    if (blast?.affected?.has(n.id)) return "#ff8a44";
    if (n.in_cycle) return active ? "#d4b8ff" : "#9a7bff";
    const pct = U.riskPercentiles;
    if (pct?.top1?.has(n.id)) return active ? "#ff9db0" : "#ff5c7a";
    if (pct?.top5?.has(n.id)) return active ? "#ffe08a" : "#ffc24b";
    if (n.is_hub) return active ? "#8af0ff" : "#3ef0ff";
    return active ? "#9eb8ff" : "#5b76c8";
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
    if (typeof THREE === "undefined") return null;
    const group = new THREE.Group();
    group.userData.nodeId = node.id;
    const scale = (node.is_hub ? (node.hub_scale || 2.4) : 1) * Math.sqrt(node.size || 4) * 0.22;
    const geo = node.is_hub
      ? new THREE.IcosahedronGeometry(scale * 1.15, 1)
      : new THREE.SphereGeometry(scale, 16, 12);
    const color = new THREE.Color(nodeColor(node, false, null));
    const mat = new THREE.MeshPhongMaterial({
      color,
      emissive: color.clone().multiplyScalar(U.pulseNodes.has(node.id) ? 0.55 : node.is_hub ? 0.35 : 0.12),
      transparent: true,
      opacity: 0.94,
      shininess: node.is_hub ? 90 : 40,
    });
    const mesh = new THREE.Mesh(geo, mat);
    group.add(mesh);

    if (node.in_cycle) {
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(scale * 1.55, 12, 8),
        new THREE.MeshBasicMaterial({ color: 0x9a7bff, transparent: true, opacity: 0.14, wireframe: true })
      );
      group.add(halo);
    }

    if (node.is_hub) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(scale * 1.8, scale * 0.08, 8, 24),
        new THREE.MeshBasicMaterial({ color: 0x3ef0ff, transparent: true, opacity: 0.45 })
      );
      ring.rotation.x = Math.PI / 2;
      group.add(ring);
    }

    group.userData.mesh = mesh;
    group.userData.baseEmissive = mat.emissive.clone();
    return group;
  }

  function setupScene(fg) {
    if (typeof THREE === "undefined") return;
    const scene = fg.scene();
    scene.fog = new THREE.FogExp2(0x070b14, 0.0028);
    const amb = new THREE.AmbientLight(0x334466, 0.85);
    const key = new THREE.PointLight(0x3ef0ff, 1.2, 900);
    key.position.set(120, 80, 160);
    const fill = new THREE.PointLight(0x9a7bff, 0.7, 700);
    fill.position.set(-140, -60, -80);
    scene.add(amb, key, fill);
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

  function setupGalaxyForces(fg, nodes) {
    try {
      const charge = fg.d3Force("charge");
      if (charge?.strength) charge.strength(-55 - Math.min(140, nodes.length * 0.06));
      const linkForce = fg.d3Force("link");
      if (linkForce?.distance) linkForce.distance(l => 18 + (8 / Math.max(l.opacity || 0.15, 0.12)));
      if (typeof d3 !== "undefined") {
        fg.d3Force("x", d3.forceX(n => n.galaxy_x || 0).strength(0.055));
        fg.d3Force("y", d3.forceY(n => n.galaxy_y || 0).strength(0.055));
        if (d3.forceZ) fg.d3Force("z", d3.forceZ(n => n.galaxy_z || 0).strength(0.04));
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

  function applyHighlight(fg, focusNode, blast) {
    if (!fg) return;
    const show = U.showEdges !== false;
    fg.linkVisibility(() => show);
    const graph = fg.graphData();
    const focus = new Set();
    if (focusNode?.id) {
      focus.add(focusNode.id);
      graph.links.forEach(link => {
        const sid = typeof link.source === "object" ? link.source.id : link.source;
        const tid = typeof link.target === "object" ? link.target.id : link.target;
        if (sid === focusNode.id) focus.add(tid);
        if (tid === focusNode.id) focus.add(sid);
      });
    }
    if (blast?.affected) blast.affected.forEach(id => focus.add(id));
    if (blast?.target) focus.add(blast.target);

    const hasFocus = focus.size > 0 || blast;
    fg.nodeThreeObjectExtend(true);
    fg.nodeColor(n => nodeColor(n, focus.has(n.id), blast))
      .linkColor(l => {
        if (!show) return "rgba(0,0,0,0)";
        const sid = typeof l.source === "object" ? l.source.id : l.source;
        const tid = typeof l.target === "object" ? l.target.id : l.target;
        const active = hasFocus && (focus.has(sid) || focus.has(tid));
        return linkColor(l, active, l.bridge);
      })
      .linkWidth(l => {
        if (!show) return 0;
        const sid = typeof l.source === "object" ? l.source.id : l.source;
        const tid = typeof l.target === "object" ? l.target.id : l.target;
        const active = hasFocus && (focus.has(sid) || focus.has(tid));
        const w = l.weight || 1;
        if (l.bridge) return active ? 1.1 + w * 0.3 : 0.35 + w * 0.12;
        return active ? 0.85 + w * 0.22 : 0.08 + w * 0.05;
      })
      .linkDirectionalParticles(l => {
        if (!show) return 0;
        if (l.bridge) return 4;
        return (l.weight || 1) > 2.5 ? 2 : 0;
      })
      .linkDirectionalParticleWidth(l => (l.bridge ? 1.8 : 1.2))
      .linkDirectionalParticleSpeed(l => 0.004 + (l.weight || 1) * 0.0012)
      .linkDirectionalParticleColor(l => (l.bridge ? "#42f5b0" : "#78a0ff"));
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
    U.riskPercentiles = computePercentiles(nodes);
    const t0 = performance.now();

    const fg = ForceGraph3D()(host)
      .graphData({ nodes: [], links: [] })
      .backgroundColor("rgba(0,0,0,0)")
      .showNavInfo(false)
      .nodeLabel("")
      .nodeThreeObject(n => sphereNodeObject(n))
      .nodeThreeObjectExtend(false)
      .nodeVal(n => (n.is_hub ? (n.hub_scale || 2.2) : 1) * (n.size || 4))
      .nodeOpacity(0.95)
      .linkOpacity(0.72)
      .linkCurvature(0.12)
      .linkDirectionalArrowLength(0)
      .onNodeClick(n => callbacks.onNodeClick?.(n))
      .onNodeHover(n => {
        callbacks.onNodeHover?.(n);
        fg.nodeLabel(node => node && n && node.id === n.id
          ? `${node.label}\n${node.subsystem || ""}\nfan-in ${node.fan_in} · risk ${node.risk_score}${node.is_hub ? " · HUB" : ""}`
          : "");
        applyHighlight(fg, n || callbacks.getSelectedNode?.(), getBlastState());
      })
      .onBackgroundClick(() => {
        callbacks.onBackgroundClick?.();
        applyHighlight(fg, callbacks.getSelectedNode?.(), getBlastState());
      })
      .width(host.clientWidth)
      .height(host.clientHeight);

    U.fg = fg;
    setupScene(fg);
    setupControls(fg);
    setupGalaxyForces(fg, nodes);

    fg.linkDirectionalParticles(l => (l.bridge ? 3 : (l.weight || 1) > 2 ? 1 : 0))
      .linkDirectionalParticleWidth(1.4)
      .linkDirectionalParticleSpeed(0.005);

    applyHighlight(fg, callbacks.getSelectedNode?.(), getBlastState());

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
        const perf = { loadMs: Math.round(performance.now() - t0), nodes: mergedNodes.length, links: mergedLinks.length };
        callbacks.onLoaded?.(perf);
        const dist = 170 + Math.sqrt(mergedNodes.length) * 16;
        fg.cameraPosition({ x: dist * 0.35, y: dist * 0.22, z: dist }, { x: 0, y: 0, z: 0 }, 1200);
        startPulseLoop(fg);
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
    applyHighlight(U.fg, null, getBlastState());
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
      applyHighlight(U.fg, anchor, getBlastState());
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
    U.fg = null;
    U.blastRadiusIds = null;
    U.blastTargetId = null;
  }

  function setShowEdges(show) {
    U.showEdges = show;
    applyHighlight(U.fg, null, getBlastState());
  }

  function refreshHighlight(selectedNode) {
    applyHighlight(U.fg, selectedNode, getBlastState());
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
      const r = n.is_hub ? 5 : 2.2;
      const fill = n.in_cycle ? "#9a7bff" : n.is_hub ? "#3ef0ff" : "#5b76c8";
      svg += `<circle cx="${n.galaxy_x}" cy="${n.galaxy_y}" r="${r}" fill="${fill}"/>`;
      if (n.is_hub) svg += `<text x="${n.galaxy_x + 6}" y="${n.galaxy_y - 6}" fill="#3ef0ff" font-size="8" font-family="Inter,sans-serif">${escapeXml(n.label)}</text>`;
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
    highlightBlastRadius,
    refreshHighlight,
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
    get fg() { return U.fg; },
  };
})();
