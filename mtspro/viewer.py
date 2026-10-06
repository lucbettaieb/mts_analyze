"""Self-contained interactive HTML viewer (piano roll + playback) for a song."""
from __future__ import annotations

import html
import json

from .model import NoteEvent, Song
from .smf import gm_program_for

PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
           "#9a6324", "#469990", "#808000", "#dcbeff", "#7c8cff", "#fabed4", "#aaffc3",
           "#ffe119", "#a9a9a9"]


def song_payload(song: Song) -> dict:
    starts = song.measure_starts()
    cm = song.conductor.measures
    n_meas = len(starts) - 1
    measures = []
    for i in range(n_meas):
        m = cm[min(i, len(cm) - 1)]
        measures.append([starts[i], m.numerator, m.denominator, starts[i + 1] - starts[i],
                         round(m.tempo, 4), m.beat_ticks,
                         (m.marker if i < len(cm) else None)])
    tracks, end = [], 0
    for idx, t in enumerate(song.tracks):
        notes = []
        for mi, mevents in enumerate(t.measures):
            for e in mevents:
                if isinstance(e, NoteEvent):
                    on, off = song.note_span(starts, mi, e)
                    notes += [on, off, e.key, e.velocity]
                    end = max(end, off)
        tracks.append({"tag": t.tag, "name": t.name, "ch": t.channel, "prog": t.program,
                       "gm": gm_program_for(t.name), "color": PALETTE[idx % len(PALETTE)],
                       "notes": notes})
    return {"title": song.title, "ppq": song.ppq, "measures": measures,
            "tracks": tracks, "end": end}


def render(song: Song, source_name: str = "") -> str:
    payload = json.dumps(song_payload(song), separators=(",", ":"))
    title = html.escape(song.title or "Untitled")
    return (_TEMPLATE.replace("__TITLE__", title)
            .replace("__SOURCE__", html.escape(source_name))
            .replace("__DATA__", payload.replace("</", "<\\/")))


def write_file(song: Song, path, source_name: str = "") -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(song, source_name))


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · MTS Viewer</title>
<style>
:root {
  --bg: #f6f5f2; --panel: #ffffff; --ink: #1d1d1f; --muted: #6b6b70; --line: #e2e0db;
  --grid: #ecebe7; --grid-strong: #cfcdc6; --roll: #fbfbf9; --black-key: #f0efeb;
  --accent: #c2410c; --playhead: #dc2626; --marker: #7c3aed;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #121214; --panel: #1b1b1f; --ink: #ececf1; --muted: #9a9aa3; --line: #2c2c33;
    --grid: #1f1f24; --grid-strong: #34343c; --roll: #16161a; --black-key: #1a1a1e;
    --accent: #fb923c; --playhead: #f87171; --marker: #a78bfa;
  }
}
:root[data-theme="dark"] {
  --bg: #121214; --panel: #1b1b1f; --ink: #ececf1; --muted: #9a9aa3; --line: #2c2c33;
  --grid: #1f1f24; --grid-strong: #34343c; --roll: #16161a; --black-key: #1a1a1e;
  --accent: #fb923c; --playhead: #f87171; --marker: #a78bfa;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body { background: var(--bg); color: var(--ink);
  font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
  display: flex; flex-direction: column; }
header { padding: 14px 16px 10px; display: flex; flex-wrap: wrap; gap: 8px 24px; align-items: baseline;
  border-bottom: 1px solid var(--line); background: var(--panel); }
h1 { margin: 0; font-size: 20px; letter-spacing: .02em; }
.sub { color: var(--muted); }
.stats { display: flex; gap: 18px; flex-wrap: wrap; color: var(--muted); }
.stats b { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }
.toolbar { display: flex; gap: 10px; align-items: center; padding: 8px 16px; flex-wrap: wrap;
  border-bottom: 1px solid var(--line); background: var(--panel); }
button { font: inherit; color: var(--ink); background: var(--bg); border: 1px solid var(--line);
  border-radius: 6px; padding: 5px 12px; cursor: pointer; }
button:hover { border-color: var(--accent); }
button.primary { background: var(--accent); color: #fff; border-color: var(--accent); min-width: 72px; }
.pos { font-variant-numeric: tabular-nums; font-family: ui-monospace, Menlo, monospace;
  padding: 4px 10px; border-radius: 6px; background: var(--bg); border: 1px solid var(--line); min-width: 190px; }
label.ctl { display: flex; gap: 6px; align-items: center; color: var(--muted); }
select { font: inherit; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 4px; }
main { flex: 1; display: flex; min-height: 0; }
aside { width: 300px; flex: none; overflow-y: auto; border-right: 1px solid var(--line); background: var(--panel); }
.trk { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; gap: 4px 10px; padding: 7px 12px;
  border-bottom: 1px solid var(--line); align-items: center; }
.trk.off { opacity: .4; }
.sw { width: 10px; height: 28px; border-radius: 3px; }
.tn { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tm { color: var(--muted); font-size: 11.5px; }
.ms { display: flex; gap: 4px; }
.ms button { padding: 1px 7px; font-size: 11px; font-weight: 700; }
.ms button.on.m { background: #64748b; color: #fff; border-color: #64748b; }
.ms button.on.s { background: #ca8a04; color: #fff; border-color: #ca8a04; }
.rollwrap { flex: 1; display: flex; flex-direction: column; min-width: 0; }
#scroller { flex: 1; overflow-x: auto; overflow-y: hidden; position: relative; background: var(--roll); }
#spacer { height: 100%; position: relative; }
#roll { position: sticky; left: 0; top: 0; display: block; cursor: crosshair; }
#tip { position: fixed; pointer-events: none; background: var(--panel); border: 1px solid var(--line);
  border-radius: 6px; padding: 6px 9px; font-size: 12px; display: none; box-shadow: 0 4px 16px rgba(0,0,0,.15); z-index: 5; }
footer { padding: 6px 16px; color: var(--muted); font-size: 11.5px; border-top: 1px solid var(--line); background: var(--panel); }
@media (max-width: 760px) { aside { width: 180px; } .pos { min-width: 0; } }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <span class="sub">Master Tracks Pro song · __SOURCE__</span>
  <div class="stats" id="stats"></div>
</header>
<div class="toolbar">
  <button class="primary" id="play">▶ Play</button>
  <button id="stop">■ Stop</button>
  <span class="pos" id="pos">m 1 · 0:00.0</span>
  <label class="ctl">Zoom <input type="range" id="zoom" min="0.02" max="0.6" step="0.01" value="0.12"></label>
  <label class="ctl">Jump to <select id="markers"></select></label>
  <label class="ctl"><input type="checkbox" id="follow" checked> Follow</label>
  <button id="theme" title="Toggle theme">◐</button>
</div>
<main>
  <aside id="tracks"></aside>
  <div class="rollwrap">
    <div id="scroller"><div id="spacer"><canvas id="roll"></canvas></div></div>
  </div>
</main>
<footer>Playback uses a simple built-in synthesizer for preview only; export to MIDI for proper sound. Click the roll to set the position.</footer>
<div id="tip"></div>
<script>
const S = __DATA__;
const $ = id => document.getElementById(id);
const NN = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const nname = k => NN[k % 12] + (Math.floor(k / 12) - 1);

// ---------- time map ----------
const M = S.measures; // [start, num, den, len, tempo, beatTicks, marker]
const segSec = []; { let s = 0; for (const m of M) { segSec.push(s); s += m[3] * 60 / (m[4] || 120) / S.ppq; } segSec.push(s); }
function measureAt(tick) { let lo = 0, hi = M.length - 1; while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (M[mid][0] <= tick) lo = mid; else hi = mid - 1; } return lo; }
function tickToSec(t) { const i = measureAt(t), m = M[i]; return segSec[i] + (t - m[0]) * 60 / (m[4] || 120) / S.ppq; }
function secToTick(s) { let lo = 0, hi = M.length - 1; while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (segSec[mid] <= s) lo = mid; else hi = mid - 1; }
  const m = M[lo]; return m[0] + (s - segSec[lo]) * (m[4] || 120) * S.ppq / 60; }
const fmt = s => { const t = Math.round(s * 10); return Math.floor(t / 600) + ":" + ((t % 600) / 10).toFixed(1).padStart(4, "0"); };
const endTick = Math.max(S.end, 1), endSec = tickToSec(endTick);

// ---------- stats + tracks ----------
let total = 0, lo = 127, hi = 0;
for (const t of S.tracks) { total += t.notes.length / 4; for (let i = 2; i < t.notes.length; i += 4) { lo = Math.min(lo, t.notes[i]); hi = Math.max(hi, t.notes[i]); } }
if (lo > hi) { lo = 48; hi = 72; }
lo = Math.max(0, lo - 2); hi = Math.min(127, hi + 2);
const meters = [...new Set(M.map(m => m[1] + "/" + m[2]))].join(", ");
$("stats").innerHTML = `<span><b>${S.tracks.length}</b> tracks</span><span><b>${total.toLocaleString()}</b> notes</span>` +
  `<span><b>${fmt(endSec)}</b> duration</span><span><b>${M.length}</b> measures</span><span>meter <b>${meters}</b></span><span><b>${S.ppq}</b> PPQ</span>`;
const state = S.tracks.map(() => ({ mute: false, solo: false }));
const audible = i => { const anySolo = state.some(s => s.solo); return anySolo ? state[i].solo : !state[i].mute; };
function drawTracks() {
  $("tracks").innerHTML = S.tracks.map((t, i) => `<div class="trk ${audible(i) ? "" : "off"}">
    <div class="sw" style="background:${t.color}"></div>
    <div><div class="tn" title="${t.name}">${t.tag.slice(2)} · ${t.name}</div>
    <div class="tm">ch ${t.ch || "–"} · prg ${t.prog || "–"} · ${(t.notes.length / 4).toLocaleString()} notes</div></div>
    <div class="ms"><button class="m ${state[i].mute ? "on" : ""}" data-i="${i}" data-k="mute">M</button>
    <button class="s ${state[i].solo ? "on" : ""}" data-i="${i}" data-k="solo">S</button></div></div>`).join("");
}
$("tracks").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
  const st = state[+b.dataset.i]; st[b.dataset.k] = !st[b.dataset.k]; drawTracks(); draw(); });
drawTracks();
const msel = $("markers");
msel.innerHTML = `<option value="">—</option>` + M.map((m, i) => m[6] ? `<option value="${i}">m${i + 1} · ${m[6]}</option>` : "").join("");
msel.onchange = () => { if (msel.value !== "") { seek(M[+msel.value][0]); centerOn(M[+msel.value][0], true); } };

// ---------- piano roll ----------
const sc = $("scroller"), sp = $("spacer"), cv = $("roll"), ctx = cv.getContext("2d");
const RULER = 34, KEYS = 34;
let pxPerTick = +$("zoom").value, cursorTick = 0;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function layout() {
  sp.style.width = (KEYS + endTick * pxPerTick + 60) + "px";
  const dpr = window.devicePixelRatio || 1;
  cv.width = sc.clientWidth * dpr; cv.height = sc.clientHeight * dpr;
  cv.style.width = sc.clientWidth + "px"; cv.style.height = sc.clientHeight + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); draw();
}
const rowH = () => (sc.clientHeight - RULER) / (hi - lo + 1);
const xOf = t => KEYS + t * pxPerTick - sc.scrollLeft;
const yOf = k => RULER + (hi - k) * rowH();
function draw() {
  const W = sc.clientWidth, H = sc.clientHeight, rh = rowH();
  const t0 = Math.max(0, (sc.scrollLeft - KEYS) / pxPerTick), t1 = t0 + W / pxPerTick;
  ctx.fillStyle = css("--roll"); ctx.fillRect(0, 0, W, H);
  for (let k = lo; k <= hi; k++) if ([1,3,6,8,10].includes(k % 12)) { ctx.fillStyle = css("--black-key"); ctx.fillRect(KEYS, yOf(k), W, rh); }
  // measures & beats
  const mi0 = measureAt(t0);
  ctx.font = "11px -apple-system, sans-serif"; ctx.textBaseline = "middle";
  for (let i = mi0; i < M.length && M[i][0] <= t1; i++) {
    const m = M[i], x = xOf(m[0]);
    if (m[5] * pxPerTick > 5) { ctx.fillStyle = css("--grid"); for (let b = m[5]; b < m[3]; b += m[5]) ctx.fillRect(Math.round(xOf(m[0] + b)), RULER, 1, H); }
    ctx.fillStyle = css("--grid-strong"); ctx.fillRect(Math.round(x), RULER - 8, 1, H);
    const every = Math.max(1, Math.ceil(36 / (m[3] * pxPerTick)));
    if ((i % every) === 0) { ctx.fillStyle = css("--muted"); ctx.fillText(String(i + 1), x + 3, 9); }
    if (i === 0 || M[i - 1][1] !== m[1] || M[i - 1][4] !== m[4]) { ctx.fillStyle = css("--muted"); ctx.fillText(`${m[1]}/${m[2]} ♩=${m[4]}`, x + 3, 9 + (i % every === 0 ? 0 : 0) + 0); }
    if (m[6]) { ctx.fillStyle = css("--marker"); ctx.fillRect(Math.round(x), RULER - 14, 2, H); ctx.font = "600 11px -apple-system, sans-serif";
      ctx.fillText(m[6], x + 5, 23); ctx.font = "11px -apple-system, sans-serif"; }
  }
  // notes
  S.tracks.forEach((t, ti) => {
    const on = audible(ti); ctx.fillStyle = t.color; const n = t.notes;
    for (let i = 0; i < n.length; i += 4) {
      if (n[i + 1] < t0 || n[i] > t1) continue;
      ctx.globalAlpha = (on ? 0.35 + 0.65 * n[i + 3] / 127 : 0.08);
      const x = xOf(n[i]), w = Math.max(2, (n[i + 1] - n[i]) * pxPerTick - 1);
      ctx.fillRect(x, yOf(n[i + 2]) + 0.5, w, Math.max(1.5, rh - 1));
    }
  });
  ctx.globalAlpha = 1;
  // keyboard gutter + ruler bg line
  ctx.fillStyle = css("--panel"); ctx.fillRect(0, RULER, KEYS, H);
  ctx.fillStyle = css("--muted"); ctx.font = "10px -apple-system, sans-serif";
  for (let k = lo; k <= hi; k++) if (k % 12 === 0 && rh * 12 > 14) ctx.fillText(nname(k), 3, yOf(k) + rh / 2);
  ctx.fillStyle = css("--line"); ctx.fillRect(0, RULER - 1, W, 1); ctx.fillRect(KEYS - 1, RULER, 1, H);
  // playhead
  const px = xOf(cursorTick); if (px >= KEYS) { ctx.fillStyle = css("--playhead"); ctx.fillRect(px - 1, 0, 2, H); }
}
sc.addEventListener("scroll", draw);
window.addEventListener("resize", layout);
$("zoom").oninput = () => { const c = (sc.scrollLeft + sc.clientWidth / 2 - KEYS) / pxPerTick; pxPerTick = +$("zoom").value; layout(); centerOn(c, true); };
function centerOn(t, force) { const x = KEYS + t * pxPerTick; if (force || x < sc.scrollLeft + KEYS + 40 || x > sc.scrollLeft + sc.clientWidth * 0.85) sc.scrollLeft = x - sc.clientWidth * (force ? 0.5 : 0.15); }
cv.addEventListener("click", e => { const r = cv.getBoundingClientRect(); const t = Math.max(0, (e.clientX - r.left + sc.scrollLeft - KEYS) / pxPerTick); seek(t); });
cv.addEventListener("mousemove", e => {
  const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, tip = $("tip");
  const t = (x + sc.scrollLeft - KEYS) / pxPerTick, k = hi - Math.floor((y - RULER) / rowH());
  let hit = null;
  for (let ti = S.tracks.length - 1; ti >= 0 && !hit; ti--) { const n = S.tracks[ti].notes;
    for (let i = 0; i < n.length; i += 4) if (n[i + 2] === k && n[i] <= t && n[i + 1] >= t) { hit = [ti, i]; break; } }
  if (!hit) { tip.style.display = "none"; return; }
  const tr = S.tracks[hit[0]], n = tr.notes, i = hit[1], mi = measureAt(n[i]), m = M[mi], off = n[i] - m[0];
  tip.innerHTML = `<b style="color:${tr.color}">■</b> ${tr.name}<br>${nname(n[i + 2])} (${n[i + 2]}) · vel ${n[i + 3]}<br>` +
    `pos ${mi + 1}|${Math.floor(off / m[5]) + 1}|${String(off % m[5]).padStart(3, "0")} · dur ${n[i + 1] - n[i]} ticks · ${fmt(tickToSec(n[i]))}`;
  tip.style.display = "block"; tip.style.left = (e.clientX + 14) + "px"; tip.style.top = (e.clientY + 14) + "px";
});
cv.addEventListener("mouseleave", () => $("tip").style.display = "none");

// ---------- playback (WebAudio preview synth) ----------
let ac = null, master = null, playing = false, startCtx = 0, startSec = 0, timer = null, queue = null, qi = 0, voices = [];
function voiceFor(t) {
  const p = t.gm ?? -1;
  if (p >= 0 && p < 16) return { type: "triangle", a: 0.003, d: 0.6, s: 0.0, r: 0.15, lvl: 0.5 };      // keys / mallets
  if (p >= 16 && p < 24) return { type: "square", a: 0.01, d: 0.1, s: 0.7, r: 0.08, lvl: 0.12 };       // organ
  if (p >= 64 && p < 80) return { type: "sine", a: 0.03, d: 0.1, s: 0.8, r: 0.08, lvl: 0.45, vib: 5 }; // reeds / pipes
  if (p >= 88 && p < 96) return { type: "sawtooth", a: 0.12, d: 0.3, s: 0.6, r: 0.4, lvl: 0.12, lp: 1400 }; // pads
  if (p >= 48 && p < 56) return { type: "sawtooth", a: 0.08, d: 0.2, s: 0.7, r: 0.3, lvl: 0.12, lp: 2200 }; // choir / strings
  if (p >= 104) return { type: "sine", a: 0.002, d: 0.35, s: 0.0, r: 0.1, lvl: 0.6 };                  // ethnic / perc
  return { type: "triangle", a: 0.005, d: 0.3, s: 0.4, r: 0.12, lvl: 0.35 };
}
function buildQueue() { const q = []; S.tracks.forEach((t, ti) => { const n = t.notes; for (let i = 0; i < n.length; i += 4) q.push([tickToSec(n[i]), tickToSec(n[i + 1]), n[i + 2], n[i + 3], ti]); });
  q.sort((a, b) => a[0] - b[0]); return q; }
function playNote(when, dur, key, vel, v) {
  const o = ac.createOscillator(), g = ac.createGain(); o.type = v.type; o.frequency.value = 440 * Math.pow(2, (key - 69) / 12);
  let out = o;
  if (v.lp) { const f = ac.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = v.lp; o.connect(f); out = f; }
  if (v.vib) { const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = v.vib; lg.gain.value = o.frequency.value * 0.004; l.connect(lg); lg.connect(o.frequency); l.start(when); l.stop(when + dur + v.r + 0.05); }
  out.connect(g); g.connect(master);
  const peak = v.lvl * Math.pow(vel / 127, 1.5) * 0.5, end = when + Math.max(dur, 0.03);
  g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(peak, when + v.a);
  g.gain.setTargetAtTime(peak * v.s, when + v.a, v.d / 3);
  g.gain.cancelAndHoldAtTime ? g.gain.cancelAndHoldAtTime(end) : 0;
  g.gain.setTargetAtTime(0, end, v.r / 3);
  o.start(when); o.stop(end + v.r * 2 + 0.05); voices.push(o); o.onended = () => { voices = voices.filter(x => x !== o); };
}
function schedule() {
  const now = ac.currentTime, horizon = now + 0.25;
  while (qi < queue.length) { const q = queue[qi], when = startCtx + (q[0] - startSec); if (when > horizon) break;
    if (when >= now - 0.02 && audible(q[4])) playNote(Math.max(when, now), q[1] - q[0], q[2], q[3], voicesByTrack[q[4]]); qi++; }
  if (qi >= queue.length && now > startCtx + (endSec - startSec) + 1) stop(true);
}
let voicesByTrack = S.tracks.map(voiceFor);
function play() {
  if (!ac) { ac = new (window.AudioContext || window.webkitAudioContext)(); master = ac.createGain(); master.gain.value = 0.5;
    const comp = ac.createDynamicsCompressor(); master.connect(comp); comp.connect(ac.destination); }
  ac.resume(); queue = queue || buildQueue(); startSec = tickToSec(cursorTick); startCtx = ac.currentTime + 0.08;
  qi = 0; while (qi < queue.length && queue[qi][0] < startSec) qi++;
  playing = true; $("play").textContent = "❚❚ Pause"; timer = setInterval(schedule, 25); schedule(); requestAnimationFrame(tick);
}
function stop(reset) { playing = false; clearInterval(timer); voices.forEach(o => { try { o.stop(); } catch (e) {} }); voices = [];
  $("play").textContent = "▶ Play"; if (reset === true) cursorTick = 0; updatePos(); draw(); }
function seek(t) { const was = playing; if (was) stop(); cursorTick = t; updatePos(); draw(); if (was) play(); }
function updatePos() { const mi = measureAt(cursorTick), m = M[mi], off = Math.max(0, Math.floor(cursorTick - m[0]));
  $("pos").textContent = `m ${mi + 1} | ${Math.floor(off / m[5]) + 1} | ${String(off % m[5]).padStart(3, "0")} · ${fmt(tickToSec(cursorTick))}`; }
function tick() { if (!playing) return; const s = startSec + Math.max(0, ac.currentTime - startCtx); cursorTick = Math.min(secToTick(s), endTick);
  if ($("follow").checked) centerOn(cursorTick, false); updatePos(); draw(); requestAnimationFrame(tick); }
$("play").onclick = () => playing ? stop() : play();
$("stop").onclick = () => { stop(true); centerOn(0, true); };
document.addEventListener("keydown", e => { if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "SELECT") { e.preventDefault(); playing ? stop() : play(); } });
$("theme").onclick = () => { const r = document.documentElement, dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const cur = r.dataset.theme || (dark ? "dark" : "light"); r.dataset.theme = cur === "dark" ? "light" : "dark"; draw(); drawTracks(); };
layout();
</script>
</body>
</html>
"""
