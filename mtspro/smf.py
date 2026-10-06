"""Standard MIDI File (type 1) export for Master Tracks Pro songs. No dependencies."""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .model import NoteEvent, ShortEvent, Song, Track

# Sort priority for events sharing a tick: note-offs first, then meta, then
# controllers/programs, then note-ons.
_PRI_OFF, _PRI_META, _PRI_CTRL, _PRI_ON = 0, 1, 2, 3

# Keyword -> General MIDI program (0-based). The original program numbers
# address vintage synth patches (Proteus/1, TX802, TX16W, RD-1000), so they
# sound wrong on a GM synth; this table picks a GM stand-in from the track name.
GM_KEYWORDS = [
    (r"piano", 0), (r"celest", 8), (r"glock", 9), (r"vibe", 11), (r"marimba", 12),
    (r"xylo", 13), (r"bell", 14), (r"organ\s*&\s*oboe|choir", 52), (r"organ", 19),
    (r"guitar", 24), (r"bass(?!oon)", 32), (r"string", 48), (r"voice|vocal|aah", 53),
    (r"trumpet", 56), (r"trombone", 57), (r"horn", 60), (r"sax", 65), (r"oboe", 68),
    (r"bassoon", 70), (r"clarinet", 71), (r"piccolo", 72), (r"flute", 73),
    (r"pan\s*flute", 75), (r"milky|pad|dune|warm", 89), (r"balines|gamelan", 114),
    (r"tiki|log|wood", 115), (r"timp", 47), (r"harp", 46),
]


def gm_program_for(name: str) -> Optional[int]:
    low = name.lower()
    if re.search(r"plate|reverb|verb\b|alesis|delay|effect", low) and not re.search(r"flute", low):
        return None  # effects unit, not an instrument
    for pat, prog in GM_KEYWORDS:
        if re.search(pat, low):
            return prog
    return None


@dataclass
class ExportOptions:
    channel_mode: str = "track"      # "track": use track channel; "recorded": keep event channel
    programs: str = "original"       # "original" | "gm" | "none"
    keep_all_notes_off: bool = True  # keep CC123 (All Notes Off) events
    tempo_scale: float = 1.0         # multiply stored tempo (e.g. 0.25 if tempo meant 16th notes)
    gm_overrides: Dict[str, int] = field(default_factory=dict)  # tag -> GM program (0-based)
    avoid_drum_channel: bool = False # move tracks on channel 10 to a free channel


@dataclass
class ExportStats:
    notes: int = 0
    overlaps_trimmed: int = 0
    duplicates_merged: int = 0
    dropped_events: int = 0
    channel_remaps: Dict[str, str] = field(default_factory=dict)
    programs: Dict[str, Optional[int]] = field(default_factory=dict)


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def _meta(kind: int, payload: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(payload)) + payload


def _text(s: str) -> bytes:
    return s.encode("latin-1", "replace")


def _encode_track(events) -> bytes:
    """events: list of (abs_tick, priority, seq, raw_bytes)."""
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    out, last = bytearray(), 0
    for tick, _, _, raw in events:
        out += _vlq(tick - last) + raw
        last = tick
    out += _vlq(0) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(out)) + bytes(out)


def _conductor_events(song: Song, opts: ExportOptions, starts: List[int]):
    ev, seq = [], 0

    def add(tick, raw, pri=_PRI_META):
        nonlocal seq
        ev.append((tick, pri, seq, raw)); seq += 1

    add(0, _meta(0x03, _text(song.title or "Untitled")))
    add(0, _meta(0x01, _text("Converted from Master Tracks Pro by mtspro")))
    prev_tempo = prev_meter = None
    for i, m in enumerate(song.conductor.measures):
        t = starts[i]
        bpm = m.tempo * opts.tempo_scale
        if bpm > 0 and bpm != prev_tempo:
            usec = max(1, min(0xFFFFFF, round(60_000_000 / bpm)))
            add(t, _meta(0x51, usec.to_bytes(3, "big")))
            prev_tempo = bpm
        meter = (m.numerator, m.denominator, m.beat_ticks)
        if meter != prev_meter and m.denominator and (m.denominator & (m.denominator - 1)) == 0:
            dd = m.denominator.bit_length() - 1
            clocks = max(1, round(m.beat_ticks * 24 / song.ppq)) if m.beat_ticks else 24
            add(t, _meta(0x58, bytes([m.numerator, dd, clocks, 8])))
            prev_meter = meter
        if m.marker:
            add(t, _meta(0x06, _text(m.marker)))
    return ev


def _free_channels(song: Song) -> List[int]:
    used = {t.channel for t in song.tracks if t.channel}
    return [c for c in range(1, 17) if c != 10 and c not in used]


def track_events(song: Song, track: Track, starts: List[int], opts: ExportOptions,
                 stats: ExportStats, out_channel: Optional[int]):
    """Absolute-time MIDI events for one track. out_channel is 0-based or None."""
    ev, seq = [], 0

    def add(tick, pri, raw):
        nonlocal seq
        ev.append((tick, pri, seq, raw)); seq += 1

    add(0, _PRI_META, _meta(0x03, _text(track.name or track.tag)))
    if "/" in track.name:
        add(0, _PRI_META, _meta(0x04, _text(track.name.split("/", 1)[1].strip())))

    ch0 = out_channel if out_channel is not None else 0
    prog = None
    if opts.programs == "original" and track.program:
        prog = track.program - 1
    elif opts.programs == "gm":
        prog = opts.gm_overrides.get(track.tag, gm_program_for(track.name))
    stats.programs[track.tag] = prog
    if prog is not None and 0 <= prog <= 127:
        add(0, _PRI_CTRL, bytes([0xC0 | ch0, prog]))

    # Collect notes per (channel, key) to resolve overlaps MIDI cannot express.
    notes = {}
    for mi, events in enumerate(track.measures):
        base = starts[mi]
        for e in events:
            ch = out_channel if out_channel is not None else e.channel
            t = base + e.tick
            if isinstance(e, NoteEvent):
                on, off = song.note_span(starts, mi, e)
                notes.setdefault((ch, e.key), []).append([on, off, e.velocity, e.release])
            elif isinstance(e, ShortEvent):
                if (e.status & 0xF0) == 0xB0 and e.data1 == 123 and not opts.keep_all_notes_off:
                    stats.dropped_events += 1
                    continue
                st = (e.status & 0xF0) | ch
                if (e.status & 0xF0) in (0xC0, 0xD0):
                    raw = bytes([st, e.data1 & 0x7F])
                else:
                    raw = bytes([st, e.data1 & 0x7F, e.data2 & 0x7F])
                add(t, _PRI_CTRL, raw)

    for (ch, key), lst in notes.items():
        lst.sort()
        merged = []
        for n in lst:
            if merged and merged[-1][0] == n[0]:
                prev = merged[-1]          # same key struck twice at the same tick
                prev[1] = max(prev[1], n[1]); prev[2] = max(prev[2], n[2])
                stats.duplicates_merged += 1
                continue
            if merged and merged[-1][1] > n[0]:
                merged[-1][1] = n[0]       # cut previous note where this one starts
                stats.overlaps_trimmed += 1
            merged.append(n)
        for on, off, vel, rel in merged:
            add(on, _PRI_ON, bytes([0x90 | ch, key & 0x7F, max(1, vel & 0x7F)]))
            add(off, _PRI_OFF, bytes([0x80 | ch, key & 0x7F, rel & 0x7F]))
            stats.notes += 1
    return ev


def export(song: Song, opts: Optional[ExportOptions] = None):
    """Return (smf_bytes, ExportStats)."""
    opts = opts or ExportOptions()
    stats = ExportStats()
    starts = song.measure_starts()
    chunks = [_encode_track(_conductor_events(song, opts, starts))]
    free = _free_channels(song)
    for t in song.tracks:
        out_ch = None
        if opts.channel_mode == "track" and t.channel:
            c = t.channel
            if opts.avoid_drum_channel and c == 10:
                if free:
                    c = free.pop(0)
                    stats.channel_remaps[t.tag] = f"10 -> {c}"
            out_ch = c - 1
        chunks.append(_encode_track(track_events(song, t, starts, opts, stats, out_ch)))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), song.ppq)
    return header + b"".join(chunks), stats


def gm_options(**kw) -> ExportOptions:
    """Preset for listening on a General MIDI synth / soundfont."""
    return ExportOptions(programs="gm", keep_all_notes_off=False, avoid_drum_channel=True, **kw)


def write_file(song: Song, path, opts: Optional[ExportOptions] = None) -> ExportStats:
    data, stats = export(song, opts)
    with open(path, "wb") as f:
        f.write(data)
    return stats
