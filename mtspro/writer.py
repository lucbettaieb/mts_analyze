"""Serialize a Song back to Master Tracks Pro binary format (byte-exact round trip)."""
from __future__ import annotations

import struct

from .model import ConductorMeasure, NoteEvent, Song


def _chunk(tag: str, header: bytes, length: int) -> bytes:
    return tag.encode("latin-1") + struct.pack(">I", length) + header


def _conductor_record(m: ConductorMeasure) -> bytes:
    body = struct.pack(">HHHHBB", m.tempo_int, m.tempo_frac, m.beat_ticks,
                       m.measure_ticks, m.numerator, m.denominator)
    body += m.reserved + bytes([m.beat_mask, m.flags])
    if m.name_raw is not None:
        body += m.name_raw
    return struct.pack(">H", len(body)) + body


def _measure_block(events) -> bytes:
    body = bytearray()
    for e in events:
        body += struct.pack(">HB", e.tick, e.status)
        if isinstance(e, NoteEvent):
            body += bytes([e.key, e.velocity, e.release]) + struct.pack(">I", e.duration)
        else:
            body += bytes([e.data1, e.data2, e.pad])
    body += b"\xff\xff"
    return struct.pack(">H", len(body)) + bytes(body)


def serialize(song: Song) -> bytes:
    lens = song.tag_lengths
    out = bytearray()
    out += _chunk("SCOR", song.header_raw, lens.get("SCOR", 8 + len(song.header_raw)))
    out += _chunk("TK00", song.conductor.header_raw, lens.get("TK00", 8 + len(song.conductor.header_raw)))
    for m in song.conductor.measures:
        out += _conductor_record(m)
    for t in song.tracks:
        out += _chunk(t.tag, t.header_raw, lens.get(t.tag, 8 + len(t.header_raw)))
        for events in t.measures:
            out += _measure_block(events)
    return bytes(out)


def write_file(song: Song, path) -> None:
    with open(path, "wb") as f:
        f.write(serialize(song))
