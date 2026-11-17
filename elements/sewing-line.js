/**
 * Sewing line: five sewing machines on one line table. Each machine is a bed,
 * a pillar, an arm that overhangs the bed, a head with its needle, a
 * handwheel and a thread cone. The station under the pointer slides out of
 * the line toward the viewer with its needle down; its neighbours follow less
 * and later, staggered outwards. Station numbers are dots on the table edge.
 * The slider is the stagger, in ms.
 */
const {
  Cam, circ, clamp, facing, fit, hull, lerp, open, poly, prism, proj, r2, ringAt, rings, run, seg, unproj,
  tdone, tset, tval, tween, disposer, flatDot, mk, place, pointer, put, reflect, register, solid,
} = HL;

const N = 5, G = 38, BZ = 12, DX = 20;
const REST_JOG = [2, -1.5, 3, 0, -2.5], REST_NDL = [0.3, 0.8, 0.1, 0.6, 0.4], FALL = [1, 0.3, 0.08];
const BX0 = -6, BX1 = 92, BY0 = -8, BY1 = (N - 1) * G + 28, MARK = 2;

/** A ring moved so its centre sits at (cx, cy). */
const at = (ring, cx, cy) => ring.map((q) => ({ ...q, u: q.u + cx, v: q.v + cy }));

/** Station i's paths with the machine slid by dx along x and the needle down by n (0 up, 1 down). */
function machine(P, front, i, dx, n) {
  const yb = i * G, Z = BZ, x = (v) => v + dx;
  const block = (x0, y0, x1, y1, r, b, z0, z1) => {
    const [ring, inner] = rings(x(x0), yb + y0, x(x1), yb + y1, r, b);
    return prism(P, front, ring, inner, Z + z0, Z + z1);
  };
  // the thread cone tapers, so its two rings are written by hand (rule 09)
  const foot = at(circ(4.2, 16), x(40), yb + 11), top = at(circ(1.7, 16), x(40), yb + 11), inner = at(circ(1, 16), x(40), yb + 11);
  const cone = {
    sil: poly(hull(ringAt(P, foot, Z + 35).concat(ringAt(P, top, Z + 47)))),
    crease: open(ringAt(P, run(inner, front), Z + 47)),
  };
  // the handwheel stands in the plane of the arm's end, a disc and its thickness
  const disc = (px, r) => {
    const pts = [];
    for (let k = 0; k < 20; k++) { const t = (k / 20) * Math.PI * 2; pts.push(P(x(px), yb + 11 + r * Math.cos(t), Z + 29 + r * Math.sin(t))); }
    return poly(pts);
  };
  const L = lerp(2.5, 8, n);
  return {
    bed: block(4, 2, 60, 20, 4, 1.4, 0, 6),
    head: block(10, 6.5, 22, 15.5, 2.5, 1.2, 14, 34),
    needle: seg(P(x(16), yb + 11, Z + 14), P(x(16), yb + 11, Z + 14 - L)),
    pillar: block(46, 6.5, 56, 15.5, 2.5, 1.2, 6, 30),
    arm: block(13, 5.5, 57, 16.5, 3.5, 1.4, 26, 35),
    cone,
    wheelBack: disc(57.4, 6),
    wheel: disc(59, 6),
    hub: disc(59, 2),
  };
}

function mount({ stage, svg, read }, value) {
  const bag = disposer();
  let stag = value;

  // fitted to the line with the nearest machine pulled all the way out
  const C = Cam(45, 0.5, 1.62);
  fit(C, [[BX0, BY0, 0], [BX1, BY1, -6], [BX1, BY0, 0], [BX0, BY1, 0], [BX0, BY0, BZ + 47], [60 + DX, BY1, BZ + 47]], 200, 166);
  const P = proj(C), front = facing(C);

  const g = mk("g", {}, svg);
  const [bo, bi] = rings(BX0, BY0, BX1, BY1, 6, 2);
  reflect(svg, g, P, front, bo, 0, 14);
  put(solid(g), prism(P, front, bo, bi, 0, BZ));

  // station numbers: station k carries k dots along the table's near edge
  const dots = [];
  for (let i = 0; i < N; i++) {
    const row = [];
    for (let k = 0; k <= i; k++) {
      const el = flatDot(g, C, 1.3, "dot " + (i === MARK ? "" : "off"));
      place(el, P(86, i * G + 11 + (k - i / 2) * 3.6, BZ));
      row.push(el);
    }
    dots.push(row);
  }

  const st = [];
  for (let i = 0; i < N; i++) {
    const grp = mk("g", {}, g);
    const bed = solid(grp), head = solid(grp);
    const needle = mk("path", { class: "nf" }, grp);
    const pillar = solid(grp), arm = solid(grp), cone = solid(grp);
    const wheelBack = mk("path", { class: "lo" }, grp), wheel = mk("path", { class: "sil" }, grp), hub = mk("path", { class: "nf lo" }, grp);
    st.push({ bed, head, needle, pillar, arm, cone, wheelBack, wheel, hub, s: tween(REST_JOG[i]), n: tween(REST_NDL[i]), last: "" });
  }

  function draw(i, dx, n) {
    const o = st[i], key = r2(dx) + "|" + r2(n);
    if (key === o.last) return;
    o.last = key;
    const m = machine(P, front, i, dx, n);
    for (const k of ["bed", "head", "pillar", "arm", "cone"]) put(o[k], m[k]);
    for (const k of ["needle", "wheelBack", "wheel", "hub"]) o[k].setAttribute("d", m[k]);
  }

  const B = register(stage, (_dt, now) => {
    let moving = false;
    st.forEach((o, i) => { draw(i, tval(o.s, now), tval(o.n, now)); if (!tdone(o.s, now) || !tdone(o.n, now)) moving = true; });
    return moving;
  });
  bag.add(B.unregister);

  // hit test on a fixed plane at the machines' mid height: nothing that moves is tested (rule 01)
  function hit([sx, sy]) {
    const [wx, wy] = unproj(C, sx, sy, BZ + 20);
    if (wx < BX0 - 4 || wx > BX1 + 4) return -1;
    const k = (wy - 11) / G;
    return k < -0.6 || k > N - 0.4 ? -1 : clamp(Math.round(k), 0, N - 1);
  }

  let act = -1;
  function setActive(a) {
    if (a === act) return;
    const now = performance.now(), from = a >= 0 ? a : act;
    act = a;
    st.forEach((o, i) => {
      const d = Math.abs(i - from), delay = d * stag;
      const f = a < 0 ? 0 : FALL[d] || 0;
      tset(o.s, lerp(REST_JOG[i], DX, f), now, delay);
      tset(o.n, a < 0 ? REST_NDL[i] : i === a ? 1 : 0, now, delay);
      const on = i === a;
      for (const k of ["bed", "head", "pillar", "arm", "cone"]) o[k].sil.classList.toggle("hi", on);
      o.needle.classList.toggle("hi", on);
      dots[i].forEach((el) => el.setAttribute("class", "dot" + ((a < 0 ? i === MARK : on) ? "" : " off")));
    });
    read.textContent = a < 0 ? "rest" : "station " + (a + 1);
    B.wake();
  }

  bag.add(pointer(stage, { move: (p) => setActive(hit(p)), leave: () => setActive(-1) }));
  bag.add(() => svg.replaceChildren());

  return { set: (v) => { stag = v; }, destroy: bag.dispose };
}

hairline({
  name: "sewing-line",
  means: "Five sewing machines on a line table: the station under the pointer slides out, needle down, and its neighbours follow.",
  rules: [1, 2, 3, 10],
  range: [0, 45, 90],
  tour: [[227, 110], [97, 176], [184, 132], null],
  mount,
});
