/**
 * botanical-overlays-archive.js
 *
 * Archived procedural SVG overlay generators, removed from the /lists screen
 * preview in favour of the dedicated /lists/print page (frontend/print.html)
 * which uses real PNG images from frontend/static/print/.
 *
 * These functions are NOT loaded by any page. Kept for reference only.
 *
 * ── _initBotOverlay ────────────────────────────────────────────────────────
 * Injects four botanical corner SVGs (hand-drawn ink paths) into #bot-overlay.
 * Used by the "Botanical" print style. Corners are positioned absolute/fixed
 * at each page corner; TR/BR use CSS scaleX/scale(-1,-1) to mirror TL/BL.
 * Also injects a thin border rule (.bot-border) and a credit line.
 *
 * ── _initHerbOverlay ──────────────────────────────────────────────────────
 * Injects four leaf-cluster corner SVGs and two vertical trail SVGs into
 * #herb-overlay. Used by the "Herbalist" print style. Leaves are generated
 * with parametric bezier curves coloured in four greens. Corner SVGs are
 * CSS-mirrored; trail SVGs sit at mid-page left/right edges.
 *
 * ── _initGoeOverlay ───────────────────────────────────────────────────────
 * Injects two dandelion-metamorphosis SVG strips (header + footer) into
 * #goe-overlay. Used by the "Goethean" print style. Each strip shows the
 * full runcinate leaf developmental sequence (cotyledon → mature runcinate →
 * contracting bract), rendered as a row of 15 forms across the page width.
 * Uses deterministic pseudo-random (sin hash) for organic leaf variation.
 */

(function _initBotOverlay() {
  const ov = document.getElementById('bot-overlay');
  if (!ov) return;
  const p = (sw, d) => `<path stroke-width="${sw}" d="${d}"/>`;
  const paths = [
    p(1.4, 'M 5,9 C 16,6 28,9 42,6 C 52,4 62,7 68,5'),
    p(1.4, 'M 9,5 C 6,16 9,28 6,42 C 4,52 7,62 5,68'),
    p(1.0, 'M 30,7 C 29,13 27,20 26,30'),
    p(0.9, 'M 8,8 C 13,15 17,23 18,33'),
    p(1.1, 'M 20,7 C 18,2 13,0 12,1 C 14,5 18,6 21,8'),
    p(1.0, 'M 46,6 C 44,11 42,15 43,15 C 45,13 47,9 47,7'),
    p(1.0, 'M 62,6 C 61,1 57,0 56,1 C 58,4 61,5 63,7'),
    p(1.1, 'M 7,22 C 2,20 0,15 1,14 C 3,17 6,20 8,24'),
    p(1.0, 'M 6,40 C 11,37 14,35 15,36 C 13,39 10,40 7,43'),
    p(1.0, 'M 5,58 C 0,55 -1,50 0,49 C 2,53 5,56 6,60'),
    p(0.9, 'M 27,20 C 32,18 35,16 36,17 C 33,20 29,21 28,22'),
    p(0.9, 'M 14,20 C 10,17 8,14 9,13 C 11,16 13,19 15,22'),
    p(0.8, 'M 68,5 C 70,3 73,3 74,5 C 73,7 70,7 68,5'),
    p(0.8, 'M 5,68 C 3,70 3,73 5,74 C 7,73 7,70 5,68'),
  ].join('');
  const g = `<g stroke="#2d3a1e" fill="none" stroke-linecap="round">${paths}</g>`;
  const svg = (cls) =>
    `<svg class="bot-corner ${cls}" viewBox="0 0 90 90" overflow="visible" xmlns="http://www.w3.org/2000/svg">${g}</svg>`;
  ov.innerHTML =
    svg('bot-tl') + svg('bot-tr') + svg('bot-bl') + svg('bot-br') +
    '<div class="bot-border"></div>' +
    '<div class="bot-credit-centre">Melvin Jarman · Hofgut LEO</div>' +
    '<span class="bot-pageno"></span>';
})();

(function _initHerbOverlay() {
  const ov = document.getElementById('herb-overlay');
  if (!ov) return;
  const C = ['#3d6e35','#4a7c3f','#5a9a4a','#6ab055'];

  function leaf(l, w) {
    w = w !== undefined ? w : l * 0.22;
    return `M 0,0 C ${(-w).toFixed(1)},${(-l*0.35).toFixed(1)} ${(-w*0.8).toFixed(1)},${(-l*0.7).toFixed(1)} 0,${-l} C ${(w*0.9).toFixed(1)},${(-l*0.7).toFixed(1)} ${(w*0.85).toFixed(1)},${(-l*0.35).toFixed(1)} ${(w*0.1).toFixed(1)},0 Z`;
  }
  function lf(x, y, angle, l, ci, op, w) {
    return `<path d="${leaf(l,w)}" fill="${C[ci]}" opacity="${op}" transform="translate(${x},${y}) rotate(${angle})"/>`;
  }
  function stem(d) { return `<path d="${d}" stroke="#2a5022" stroke-width="0.85" fill="none" opacity="0.55" stroke-linecap="round"/>`; }

  const cornerPaths =
    stem('M 12,12 C 24,8 38,12 52,6') +
    stem('M 10,14 C 8,26 10,42 6,58') +
    stem('M 14,10 C 20,20 26,32 28,46') +
    stem('M 36,8 C 34,18 32,28 30,36') +
    lf(18,14,  30, 44, 0, 0.35) + lf(10,18, -20, 40, 2, 0.32) +
    lf(22, 8,  60, 38, 1, 0.38) + lf( 8,22, -45, 36, 3, 0.30) +
    lf(20,12,  15, 32, 2, 0.48) + lf(14,16, -10, 34, 0, 0.45) +
    lf(30,10,  50, 30, 3, 0.50) + lf( 8,32, -55, 28, 1, 0.44) +
    lf(38, 8,  25, 26, 2, 0.42) + lf(10,44, -35, 30, 0, 0.40) +
    lf(16,14,   5, 22, 3, 0.55) + lf(24,10,  40, 20, 1, 0.52) +
    lf(10,24, -25, 24, 2, 0.50) + lf(34,12,  65, 18, 0, 0.45) +
    lf( 8,40, -60, 20, 3, 0.48);

  const trailPaths =
    stem('M 8,10 C 6,30 8,55 5,80') +
    lf(10,15, -20, 22, 1, 0.28) + lf( 6,35, -40, 18, 3, 0.22) +
    lf(12,55, -10, 20, 0, 0.25) + lf( 5,75, -50, 16, 2, 0.20) +
    lf(14,95, -30, 14, 1, 0.18);

  const mkSvg = (cls, vw, vh, content) =>
    `<svg class="${cls}" viewBox="0 0 ${vw} ${vh}" overflow="visible" xmlns="http://www.w3.org/2000/svg">${content}</svg>`;

  ov.innerHTML =
    mkSvg('herb-corner herb-tl', 110, 110, cornerPaths) +
    mkSvg('herb-corner herb-tr', 110, 110, cornerPaths) +
    mkSvg('herb-corner herb-bl', 110, 110, cornerPaths) +
    mkSvg('herb-corner herb-br', 110, 110, cornerPaths) +
    mkSvg('herb-trail herb-trail-l', 50, 120, trailPaths) +
    mkSvg('herb-trail herb-trail-r', 50, 120, trailPaths) +
    '<div class="herb-credit-l">Melvin Jarman</div>' +
    '<div class="herb-credit-r">Hofgut LEO</div>';
})();

(function _initGoeOverlay() {
  const ov = document.getElementById('goe-overlay');
  if (!ov) return;

  // Same deterministic pseudo-random as the encounters.html dandelion visualiser.
  function rnd(n) { var s = Math.sin(n*12.9898+78.233)*43758.5453; return s-Math.floor(s); }

  // Metamorphosis sequence: [LOBES, span_mm, maxTooth_mm, complexity(0-1), seed]
  // Progression: cotyledon → simple oval → weakly lobed → full runcinate → contracting bracts
  const SEQ = [
    [0,  5, 1.5, 0.00,  0],
    [0,  7, 2.0, 0.00,  5],
    [2,  9, 2.2, 0.22, 10],
    [3, 11, 2.8, 0.34, 15],
    [4, 13, 3.2, 0.46, 20],
    [5, 15, 3.8, 0.57, 25],
    [6, 17, 4.4, 0.66, 30],
    [7, 18, 5.0, 0.75, 35],
    [9, 20, 5.8, 0.86, 40],
    [9, 22, 6.2, 0.96, 45],
    [9, 20, 5.6, 0.88, 50],
    [7, 17, 4.6, 0.68, 55],
    [5, 13, 3.4, 0.43, 60],
    [3, 10, 2.5, 0.23, 65],
    [2,  7, 1.8, 0.09, 70],
  ];

  // Generate SVG path for one leaf form (pointing up from origin, base at (0,0)).
  // Runcinate forms: generate horizontal path then rotate -90° via transform.
  // Oval/cotyledon forms: generated directly vertical.
  function makePath(LOBES, span, maxTooth, complexity, seed) {
    if (LOBES === 0) {
      const hw = maxTooth;
      return `M 0,0 C ${(hw*0.85).toFixed(2)},${(-span*0.18).toFixed(2)} ${(hw*0.95).toFixed(2)},${(-span*0.55).toFixed(2)} 0,${-span} C ${(-hw*0.95).toFixed(2)},${(-span*0.55).toFixed(2)} ${(-hw*0.85).toFixed(2)},${(-span*0.18).toFixed(2)} 0,0 Z`;
    }
    const step = span / LOBES;
    function lobe(t, sd) {
      const jit  = (rnd(t*1.7+sd) - 0.5)*step*0.38;
      const x    = (t/LOBES)*span + jit;
      const grow = 0.30 + 0.70*(t/LOBES);
      const irr  = 0.35 + 0.65*rnd(t*3.3+sd);
      const env  = grow*irr;
      const lean = step*(0.22 + 0.34*rnd(t*5.1+sd));
      const sin  = (0.8 + rnd(t*2.2+sd)*2.8)*(maxTooth*0.18);
      const amp  = env*complexity;
      return { x, len: maxTooth*0.12 + amp*maxTooth*0.88, lean, sin };
    }
    const pts = ['M 0,0'];
    for (let t = 1; t <= LOBES; t++) {
      const u = lobe(t, seed);
      pts.push(`L ${(u.x-step*0.52).toFixed(2)},${(-u.sin).toFixed(2)}`);
      pts.push(`L ${(u.x-u.lean).toFixed(2)},${(-u.len).toFixed(2)}`);
      pts.push(`L ${u.x.toFixed(2)},${(-u.sin*0.45).toFixed(2)}`);
    }
    pts.push(`L ${span},0`);
    for (let b = LOBES; b >= 1; b--) {
      const d = lobe(b, seed+50);
      pts.push(`L ${d.x.toFixed(2)},${(d.sin*0.45).toFixed(2)}`);
      pts.push(`L ${(d.x-d.lean).toFixed(2)},${d.len.toFixed(2)}`);
      pts.push(`L ${(d.x-step*0.52).toFixed(2)},${d.sin.toFixed(2)}`);
    }
    pts.push('Z');
    return pts.join(' ');
  }

  // Build SVG path content for one strip.
  // flipVertical: footer leaves hang downward from a baseline at y=0.
  function makeStrip(forms, opacity, seedAdd, flipVertical) {
    const N = forms.length, margin = 7, totalW = 210, stripH = 25;
    const spacing = (totalW - 2*margin) / (N-1);
    let paths = '';
    forms.forEach(([LOBES, span, maxTooth, complexity, baseSeed], i) => {
      const cx = (margin + i*spacing).toFixed(2);
      const tilt = (rnd(i*7.3+baseSeed) - 0.5)*6; // ±3° organic variation
      const d = makePath(LOBES, span, maxTooth, complexity, baseSeed + seedAdd);
      const isRunc = LOBES > 0;
      const tr = isRunc
        ? `translate(${cx},${stripH}) rotate(${(-90+tilt).toFixed(1)})`
        : `translate(${cx},${stripH}) rotate(${tilt.toFixed(1)})`;
      paths += `<path d="${d}" fill="#3a5a28" opacity="${opacity}" transform="${tr}"/>`;
    });
    // Baseline rule at y=stripH
    paths += `<line x1="5" y1="${stripH}" x2="205" y2="${stripH}" stroke="#3a5a28" stroke-width="0.25" opacity="${(opacity*0.8).toFixed(2)}"/>`;
    // Footer: wrap in vertical flip so leaves hang downward from y=0
    return flipVertical
      ? `<g transform="translate(0,${stripH}) scale(1,-1)">${paths}</g>`
      : paths;
  }

  const mkSvg = (cls, content) =>
    `<svg class="goe-strip ${cls}" viewBox="0 0 210 25" overflow="visible" xmlns="http://www.w3.org/2000/svg">${content}</svg>`;

  ov.innerHTML =
    mkSvg('goe-header', makeStrip(SEQ,                    0.55,   0, false)) +
    mkSvg('goe-footer', makeStrip(SEQ.slice().reverse(),  0.35, 300, true))  +
    '<div class="goe-credit">Melvin Jarman · Hofgut LEO</div>';
})();
