"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { buildRepoGraph } from "../../lib/scene/seededGraph";
import { sceneProgress } from "../../lib/scene/progress";

const C_DORMANT = new THREE.Color("#2C6F66");
const C_ACTIVE = new THREE.Color("#5FD3BE");
const C_BRIGHT = new THREE.Color("#8CF0DC");
const C_DIM = new THREE.Color("#16302C");

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (a: number, b: number, x: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
/** triangular band: 0 outside [a,c], peak 1 at b */
const band = (x: number, a: number, b: number, c: number) =>
  x < a || x > c ? 0 : x < b ? (x - a) / (b - a) : 1 - (x - b) / (c - b);

interface Props {
  nodeCount: number;
  showLabels: boolean;
  reducedMotion: boolean;
}

/** Vanilla Three.js repository constellation. Crystallizes from raw-repo scatter
 *  into the mapped memory state, then idles with parallax + slow drift. */
export default function ConstellationScene({ nodeCount, showLabels, reducedMotion }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current!;
    const graph = buildRepoGraph({ nodeCount, seed: 20260713, radius: 7 });
    const N = graph.nodes.length;

    // ---- renderer / scene / camera ----
    const canvas = document.createElement("canvas");
    canvas.style.cssText = "display:block;width:100%;height:100%";
    host.appendChild(canvas);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0a0c0c, 13, 34);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 60);
    camera.position.set(0, 0.4, 16);

    scene.add(new THREE.AmbientLight(0xffffff, 0.35));
    const hemi = new THREE.HemisphereLight(0xbfeee3, 0x0a0c0c, 0.5);
    scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xdffff5, 0.7);
    dir.position.set(6, 8, 4);
    scene.add(dir);

    // outer group = composition offset (shift graph into the right column on
    // desktop so it never collides with the left-aligned headline); inner spin
    // group = parallax rotation around the graph's own centre.
    const group = new THREE.Group();
    scene.add(group);
    const spin = new THREE.Group();
    group.add(spin);

    // ---- nodes (instanced) ----
    const nodeGeo = new THREE.OctahedronGeometry(1, 0);
    const nodeMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.35,
      metalness: 0.1,
      emissive: C_ACTIVE,
      emissiveIntensity: 0.25,
      toneMapped: false,
    });
    const nodes = new THREE.InstancedMesh(nodeGeo, nodeMat, N);
    nodes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    nodes.frustumCulled = false;
    spin.add(nodes);

    // ---- edges ----
    const edgePos = new Float32Array(graph.edges.length * 2 * 3);
    const edgeCol = new Float32Array(graph.edges.length * 2 * 3);
    graph.edges.forEach((e, i) => {
      const c = e.bridge ? C_ACTIVE : C_DORMANT;
      const a = e.bridge ? 0.6 : 0.3;
      for (let k = 0; k < 2; k++) {
        const o = (i * 2 + k) * 3;
        edgeCol[o] = c.r * a;
        edgeCol[o + 1] = c.g * a;
        edgeCol[o + 2] = c.b * a;
      }
    });
    const edgeGeo = new THREE.BufferGeometry();
    edgeGeo.setAttribute("position", new THREE.BufferAttribute(edgePos, 3));
    edgeGeo.setAttribute("color", new THREE.BufferAttribute(edgeCol, 3));
    const edgeMat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, toneMapped: false });
    const edges = new THREE.LineSegments(edgeGeo, edgeMat);
    edges.frustumCulled = false;
    spin.add(edges);

    // ---- memory core ----
    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.9, 1),
      new THREE.MeshStandardMaterial({
        color: 0x0c1613,
        emissive: C_ACTIVE,
        emissiveIntensity: 0.5,
        roughness: 0.25,
        metalness: 0.4,
        flatShading: true,
        toneMapped: false,
      })
    );
    spin.add(core);
    const coreWire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.92, 1),
      new THREE.MeshBasicMaterial({ color: C_BRIGHT, wireframe: true, transparent: true, opacity: 0.18, toneMapped: false })
    );
    spin.add(coreWire);

    // soft glow sprite behind the core
    const glowTex = makeGlowTexture();
    const glow = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: glowTex, color: C_ACTIVE, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    glow.scale.set(7, 7, 1);
    spin.add(glow);

    // scan plane — sweeps through the graph during the "scan" act
    const scan = new THREE.Mesh(
      new THREE.PlaneGeometry(26, 26),
      new THREE.MeshBasicMaterial({
        color: C_BRIGHT,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      })
    );
    scan.rotation.x = -Math.PI / 2;
    spin.add(scan);

    // retrieval set = the cross-cluster bridge endpoints (hubs) — the "cited"
    // path from the memory core outward. Highlighted during the retrieval act.
    const retrievalSet = new Set<number>();
    graph.edges.forEach((e) => {
      if (e.bridge) {
        retrievalSet.add(e.a);
        retrievalSet.add(e.b);
      }
    });
    graph.nodes.forEach((n) => {
      if (n.label) retrievalSet.add(n.id);
    });

    // ---- scratch ----
    const cur = new Float32Array(N * 3);
    const dummy = new THREE.Object3D();
    const col = new THREE.Color();
    let hovered = -1;

    // ---- labels (DOM overlay, projected) ----
    const labelNodes = showLabels ? graph.nodes.filter((n) => n.label).slice(0, 5) : [];
    const labelEls: HTMLSpanElement[] = labelNodes.map((n) => {
      const el = document.createElement("span");
      el.className = "scene-label";
      el.textContent = n.label!;
      el.style.position = "absolute";
      el.style.left = "0";
      el.style.top = "0";
      el.style.willChange = "transform, opacity";
      el.style.opacity = "0";
      host.appendChild(el);
      return el;
    });

    // narrative factors derived from scroll progress p
    function writeNodes(t: number, p: number) {
      const gather = smooth(0.78, 1.0, p) * 0.82; // converge toward the core
      const retr = band(p, 0.55, 0.68, 0.86); // retrieval highlight strength
      for (let i = 0; i < N; i++) {
        const n = graph.nodes[i];
        const stagger = (i / N) * 0.35;
        const lt = easeOut(clamp01((t - stagger) / (1 - 0.35)));
        let x = n.noise[0] + (n.home[0] - n.noise[0]) * lt;
        let y = n.noise[1] + (n.home[1] - n.noise[1]) * lt;
        let z = n.noise[2] + (n.home[2] - n.noise[2]) * lt;
        if (gather > 0) {
          const g = 1 - gather;
          x *= g; y *= g; z *= g;
        }
        cur[i * 3] = x;
        cur[i * 3 + 1] = y;
        cur[i * 3 + 2] = z;

        const isHover = hovered === i;
        const inRetr = retrievalSet.has(i);
        const base = 0.05 + n.importance * 0.12;
        const s = (isHover ? 1.9 : 1) * (inRetr ? 1 + retr * 0.6 : 1) * base * (0.35 + 0.65 * lt);
        dummy.position.set(x, y, z);
        dummy.scale.setScalar(s);
        dummy.updateMatrix();
        nodes.setMatrixAt(i, dummy.matrix);

        col.copy(C_DORMANT).lerp(C_ACTIVE, n.importance * lt);
        if (retr > 0) {
          if (inRetr) col.lerp(C_BRIGHT, retr);
          else col.lerp(C_DIM, retr * 0.8); // dim the rest so the path reads
        }
        if (isHover) col.copy(C_BRIGHT);
        nodes.setColorAt(i, col);
      }
      nodes.instanceMatrix.needsUpdate = true;
      if (nodes.instanceColor) nodes.instanceColor.needsUpdate = true;

      const arr = edgeGeo.attributes.position.array as Float32Array;
      graph.edges.forEach((e, i) => {
        const oa = i * 2 * 3;
        arr[oa] = cur[e.a * 3]; arr[oa + 1] = cur[e.a * 3 + 1]; arr[oa + 2] = cur[e.a * 3 + 2];
        arr[oa + 3] = cur[e.b * 3]; arr[oa + 4] = cur[e.b * 3 + 1]; arr[oa + 5] = cur[e.b * 3 + 2];
      });
      edgeGeo.attributes.position.needsUpdate = true;
    }

    // ---- sizing ----
    let W = 1, H = 1;
    let landscape = true;
    let offRightX = 0; // hero composition offset (graph in right column)
    let offHeroY = 3.2; // hero vertical offset (mobile lifts graph up)
    // headline box, so labels sit clear of the text (right of, or below it)
    const hero = { right: 0, bottom: 0 };
    const resize = () => {
      const r = host.getBoundingClientRect();
      W = Math.max(1, r.width);
      H = Math.max(1, r.height);
      renderer.setSize(W, H, false);
      camera.aspect = W / H;
      camera.updateProjectionMatrix();
      // Desktop/landscape: shift the constellation into the right column.
      // Mobile: centre horizontally, lift up to frame the headline.
      landscape = W >= 1024 && W / H > 1.1;
      offRightX = landscape ? Math.min(5.5, (W / H) * 3.0) : 0;
      offHeroY = landscape ? -0.9 : 3.2;
      const h1 = document.querySelector(".hero-cine h1");
      if (h1) {
        const b = h1.getBoundingClientRect();
        hero.right = b.right + 28;
        hero.bottom = b.bottom + 8;
      } else {
        hero.right = W * 0.55;
        hero.bottom = H * 0.6;
      }
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    group.position.set(offRightX, offHeroY, 0);

    // ---- pointer (parallax + hover) ----
    const pointer = { x: 0, y: 0 };
    const ndc = new THREE.Vector2(-2, -2);
    const raycaster = new THREE.Raycaster();
    let rayTick = 0;
    const onMove = (e: MouseEvent) => {
      const r = host.getBoundingClientRect();
      pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
      pointer.y = -(((e.clientY - r.top) / r.height) * 2 - 1);
      ndc.set(pointer.x, pointer.y);
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    // ---- loop ----
    const startT = performance.now();
    const introMs = 2200;
    let raf = 0;
    let running = true;
    let last = 0;
    let settled = false;
    let pSmooth = 0;
    let lastP = -1;
    let lastHover = -2;

    const projV = new THREE.Vector3();

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (now - last < 15) return; // ~60fps cap
      last = now;

      const elapsed = now - startT;
      const t = reducedMotion ? 1 : clamp01(elapsed / introMs);

      // scroll progress → drives the narrative (smoothed for calm motion).
      // Under reduced motion we ignore scroll entirely and hold a stable state.
      const pTarget = clamp01(sceneProgress.p);
      pSmooth = pSmooth + (pTarget - pSmooth) * 0.12;
      const p = reducedMotion ? 0 : pSmooth;

      // rewrite instances during the intro, on hover, or whenever progress moves
      if (t < 1 || !settled || hovered !== lastHover || Math.abs(p - lastP) > 0.0004) {
        writeNodes(t, p);
        if (t >= 1) settled = true;
        lastP = p;
        lastHover = hovered;
      }

      // composition: slide graph from the hero (right/offset) to centre as the
      // narrative begins; dolly the camera gently in across the whole story.
      const enter = smooth(0.02, 0.14, p);
      let tgX = landscape ? lerp(offRightX, 0, enter) : 0;
      let tgY = lerp(offHeroY, landscape ? 0.1 : 0.4, enter);
      if (reducedMotion) {
        // stable composition: graph centred-ish, never scroll-linked
        tgX = landscape ? 2.6 : 0;
        tgY = landscape ? -0.3 : 1.4;
      }
      group.position.x += (tgX - group.position.x) * 0.08;
      group.position.y += (tgY - group.position.y) * 0.08;
      const camZ = lerp(16, 12.4, smooth(0, 1, p));
      camera.position.z += (camZ - camera.position.z) * 0.05;

      // scan plane sweeps through the graph during the scan act
      const scanA = band(p, 0.09, 0.2, 0.34);
      scan.visible = scanA > 0.002;
      if (scan.visible) {
        (scan.material as THREE.MeshBasicMaterial).opacity = scanA * 0.2;
        scan.position.y = lerp(6, -6, smooth(0.09, 0.34, p));
      }

      // parallax + drift
      const tX = reducedMotion ? 0 : pointer.y * 0.12 + Math.sin(elapsed * 0.00008) * 0.04;
      const tY = reducedMotion ? 0 : pointer.x * 0.18 + Math.cos(elapsed * 0.00006) * 0.05;
      spin.rotation.x += (tX - spin.rotation.x) * 0.03;
      spin.rotation.y += (tY - spin.rotation.y) * 0.03;

      if (!reducedMotion) {
        const spinRate = 0.0016 + p * 0.004; // core turns a little faster into converge
        core.rotation.y += spinRate;
        core.rotation.x += spinRate * 0.5;
        coreWire.rotation.copy(core.rotation);
        const em = 0.5 + Math.sin(elapsed * 0.0009) * 0.12 + smooth(0.7, 1, p) * 0.5;
        (core.material as THREE.MeshStandardMaterial).emissiveIntensity = em;
        const cs = 1 + smooth(0.78, 1, p) * 0.5; // core grows on converge
        core.scale.setScalar(cs);
        coreWire.scale.setScalar(cs);
        glow.scale.setScalar(7 + smooth(0.7, 1, p) * 4);
      }

      // hover raycast (throttled), only after intro
      if (settled && (rayTick++ & 3) === 0 && ndc.x > -2) {
        raycaster.setFromCamera(ndc, camera);
        const hit = raycaster.intersectObject(nodes);
        const id = hit.length ? (hit[0].instanceId ?? -1) : -1;
        if (id !== hovered) hovered = id;
      }

      // labels — projected to screen, kept out of the left headline column, and
      // de-overlapped so paths never stack on top of each other.
      if (labelEls.length) {
        spin.updateMatrixWorld();
        const placed: { x: number; y: number }[] = [];
        labelNodes.forEach((n, i) => {
          projV.set(n.home[0], n.home[1], n.home[2]);
          spin.localToWorld(projV);
          projV.project(camera);
          const el = labelEls[i];
          const sx = (projV.x * 0.5 + 0.5) * W;
          const sy = (-projV.y * 0.5 + 0.5) * H;
          const clash = placed.some((p) => Math.abs(p.x - sx) < 130 && Math.abs(p.y - sy) < 26);
          // clear of the headline: either right of it, or below it (landscape only)
          const clearOfText = !landscape || sx > hero.right || sy > hero.bottom;
          const ok = projV.z < 1 && clearOfText && sx > 60 && sx < W - 12 && sy > 90 && sy < H - 24 && !clash;
          const narrativeFade = 1 - smooth(0.05, 0.2, p);
          if (ok && narrativeFade > 0.01) {
            placed.push({ x: sx, y: sy });
            el.style.transform = `translate(${sx}px, ${sy}px)`;
            el.style.opacity = String(Math.min(1, easeOut(t)) * 0.85 * narrativeFade);
          } else {
            el.style.opacity = "0";
          }
        });
      }

      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(frame);

    const pause = () => {
      cancelAnimationFrame(raf);
      running = false;
    };
    const resume = () => {
      if (!running) {
        running = true;
        last = 0;
        raf = requestAnimationFrame(frame);
      }
    };
    const onVis = () => {
      if (document.hidden) pause();
      else resume();
    };
    document.addEventListener("visibilitychange", onVis);
    // Debug/QA hook: lets tooling freeze a frame to capture a still screenshot.
    (window as unknown as { __atlasScene?: unknown }).__atlasScene = { pause, resume };

    // ---- cleanup ----
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("mousemove", onMove);
      ro.disconnect();
      labelEls.forEach((el) => el.remove());
      nodeGeo.dispose();
      nodeMat.dispose();
      edgeGeo.dispose();
      edgeMat.dispose();
      core.geometry.dispose();
      (core.material as THREE.Material).dispose();
      coreWire.geometry.dispose();
      (coreWire.material as THREE.Material).dispose();
      glowTex.dispose();
      (glow.material as THREE.Material).dispose();
      scan.geometry.dispose();
      (scan.material as THREE.Material).dispose();
      renderer.dispose();
      canvas.remove();
      const w = window as unknown as { __atlasScene?: unknown };
      if (w.__atlasScene) delete w.__atlasScene;
    };
  }, [nodeCount, showLabels, reducedMotion]);

  return <div ref={hostRef} className="scene-host" aria-hidden="true" />;
}

/** Radial-gradient sprite texture for the core glow. */
function makeGlowTexture() {
  const s = 128;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0, "rgba(255,255,255,0.9)");
  g.addColorStop(0.25, "rgba(140,240,220,0.5)");
  g.addColorStop(1, "rgba(140,240,220,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}
