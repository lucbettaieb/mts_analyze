"""Human-readable analysis of a Master Tracks Pro song."""
from __future__ import annotations

from collections import Counter

from .model import NoteEvent, ShortEvent, Song

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CC_NAMES = {1: "Modulation", 7: "Volume", 10: "Pan", 11: "Expression", 64: "Sustain",
            121: "Reset All Controllers", 123: "All Notes Off"}


def note_name(key: int) -> str:
    return f"{NOTE_NAMES[key % 12]}{key // 12 - 1}"


def tempo_map_seconds(song: Song):
    """Return a function tick -> seconds using the per-measure tempo."""
    starts = song.measure_starts()
    cm = song.conductor.measures
    seg = []  # (start_tick, start_sec, sec_per_tick)
    sec = 0.0
    for i in range(len(starts) - 1):
        bpm = cm[min(i, len(cm) - 1)].tempo or 120.0
        spt = 60.0 / bpm / song.ppq
        seg.append((starts[i], sec, spt))
        sec += (starts[i + 1] - starts[i]) * spt

    def at(tick: int) -> float:
        lo, hi = 0, len(seg) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if seg[mid][0] <= tick:
                lo = mid
            else:
                hi = mid - 1
        s0, sec0, spt = seg[lo]
        return sec0 + (tick - s0) * spt
    return at


def fmt_time(sec: float) -> str:
    tenths = round(sec * 10)
    return f"{tenths // 600}:{(tenths % 600) / 10:04.1f}"


def mbt(song: Song, measure_index: int, tick: int) -> str:
    """Measure|beat|tick position, 1-based like MTS Pro's event list."""
    cm = song.conductor.measures
    bt = cm[min(measure_index, len(cm) - 1)].beat_ticks or song.ppq
    return f"{measure_index + 1:4d}|{tick // bt + 1:2d}|{tick % bt:03d}"


def summarize_track(song, track, starts):
    notes = list(track.notes())
    other = [e for m in track.measures for e in m if isinstance(e, ShortEvent)]
    used = [i for i, m in enumerate(track.measures) if m]
    keys = [n.key for n in notes]
    vels = [n.velocity for n in notes]
    return {
        "notes": len(notes),
        "other": len(other),
        "other_kinds": Counter(
            (f"CC{e.data1} {CC_NAMES.get(e.data1, '')}".strip() if e.kind == "control_change" else e.kind)
            for e in other),
        "range": (min(keys), max(keys)) if keys else None,
        "vel": (min(vels), max(vels), sum(vels) / len(vels)) if vels else None,
        "first": used[0] + 1 if used else None,
        "last": used[-1] + 1 if used else None,
        "rec_channels": sorted({e.channel + 1 for m in track.measures for e in m}),
        "long_notes": sum(1 for n in notes if n.duration_parts[0]),
    }


def report(song: Song, path: str = "") -> str:
    out = []
    w = out.append
    starts = song.measure_starts()
    secs = tempo_map_seconds(song)
    cm = song.conductor.measures

    last_tick = 0
    for t in song.tracks:
        for mi, m in enumerate(t.measures):
            for e in m:
                end = song.note_span(starts, mi, e)[1] if isinstance(e, NoteEvent) else starts[mi] + e.tick
                last_tick = max(last_tick, end)

    w("=" * 78)
    w(f"Master Tracks Pro song: {song.title!r}" + (f"   ({path})" if path else ""))
    w("=" * 78)
    w(f"Resolution        : {song.ppq} PPQ")
    w(f"Song length       : {song.measure_count} measures in conductor; tracks hold "
      f"{max((len(t.measures) for t in song.tracks), default=0)} measures")
    w(f"Music duration    : {fmt_time(secs(last_tick))} (to last note-off, tick {last_tick})")
    w(f"Tracks            : {len(song.tracks)} (+ conductor)")
    w("")

    w("Tempo / meter map")
    w("-" * 78)
    prev = None
    for i, m in enumerate(cm):
        key = (m.tempo, m.numerator, m.denominator, m.measure_ticks, m.beat_ticks)
        if key != prev:
            w(f"  m{i + 1:<4d} @ {fmt_time(secs(starts[i])):>7}  tempo {m.tempo:6.2f}  meter "
              f"{m.numerator}/{m.denominator}  ({m.measure_ticks} ticks, beat = {m.beat_ticks} ticks)")
            prev = key
    w("")
    w("Markers")
    w("-" * 78)
    for i, m in enumerate(cm):
        if m.marker:
            w(f"  m{i + 1:<4d} @ {fmt_time(secs(starts[i])):>7}  {m.marker}")
    w("")

    w("Tracks")
    w("-" * 78)
    w(f"  {'tag':4} {'name':34} {'ch':>2} {'prg':>3} {'notes':>5} {'other':>5}  "
      f"{'range':9} {'meas':9}")
    total_notes = 0
    summaries = {}
    for t in song.tracks:
        s = summarize_track(song, t, starts)
        summaries[t.tag] = s
        total_notes += s["notes"]
        rng = f"{note_name(s['range'][0])}-{note_name(s['range'][1])}" if s["range"] else "-"
        meas = f"{s['first']}-{s['last']}" if s["first"] else "empty"
        w(f"  {t.tag:4} {t.name[:34]:34} {t.channel or '-':>2} {t.program or '-':>3} "
          f"{s['notes']:5d} {s['other']:5d}  {rng:9} {meas:9}")
    w(f"  {'':4} {'TOTAL':34} {'':>2} {'':>3} {total_notes:5d}")
    w("")
    w("Track details")
    w("-" * 78)
    for t in song.tracks:
        s = summaries[t.tag]
        w(f"  {t.tag} {t.name}")
        w(f"     output channel {t.channel or 'as recorded'}, program {t.program or 'none'}"
          f" (MIDI {t.program - 1 if t.program else '-'}), recorded on channel(s) "
          f"{', '.join(map(str, s['rec_channels'])) or '-'}")
        if s["vel"]:
            w(f"     velocity {s['vel'][0]}-{s['vel'][1]} (avg {s['vel'][2]:.0f}); "
              f"{s['long_notes']} notes held across bar lines")
        if s["other_kinds"]:
            w("     other events: " + ", ".join(f"{k} x{v}" for k, v in s["other_kinds"].most_common()))
    w("")

    w("Notes on interpretation")
    w("-" * 78)
    w("  * Tempo is read as quarter notes per minute (16.16 fixed point).")
    w("  * Program numbers address the original 1990s synth patches (E-mu Proteus,")
    w("    Yamaha TX802/TX16W, Roland RD-1000, Alesis effects), not General MIDI.")
    w("    Use `midi --gm` for a version that plays sensibly on a GM synth/soundfont.")
    w("  * Track channels override the recorded event channels on playback, as in MTS Pro.")
    cc123 = sum(s["other_kinds"].get("CC123 All Notes Off", 0) for s in summaries.values())
    if cc123:
        w(f"  * {cc123} 'All Notes Off' (CC123) events are stored in the tracks. They are kept")
        w("    in the faithful export and removed in the --gm listening export.")
    return "\n".join(out)


def dump(song: Song, track_filter=None, measure_range=None) -> str:
    """Event list in the spirit of MTS Pro's Event List window."""
    out = []
    starts = song.measure_starts()
    lo, hi = measure_range or (1, 10 ** 9)
    for t in song.tracks:
        if track_filter and t.tag not in track_filter and t.name not in track_filter:
            continue
        out.append(f"--- {t.tag} {t.name}  (channel {t.channel}, program {t.program})")
        for mi, m in enumerate(t.measures):
            if not (lo <= mi + 1 <= hi):
                continue
            for e in m:
                pos = mbt(song, mi, e.tick)
                if isinstance(e, NoteEvent):
                    mm, bb, tt = e.duration_parts
                    dur = f"{mm}|{bb}|{tt:03d}" if (mm or bb) else f"{tt}"
                    out.append(f"  {pos}  Note   ch{e.channel + 1:<2d} {note_name(e.key):4} "
                               f"({e.key:3d}) vel {e.velocity:3d}/{e.release:3d}  dur {dur}")
                else:
                    label = CC_NAMES.get(e.data1, "") if e.kind == "control_change" else ""
                    out.append(f"  {pos}  {e.kind:15} ch{e.channel + 1:<2d} {e.data1:3d} {e.data2:3d}  {label}")
    out.append("--- Conductor")
    for i, m in enumerate(song.conductor.measures):
        if lo <= i + 1 <= hi:
            out.append(f"  {i + 1:4d}|01|000  tempo {m.tempo:.2f}  meter {m.numerator}/{m.denominator}"
                       + (f"  marker {m.marker!r}" if m.marker else ""))
    return "\n".join(out)
