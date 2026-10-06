"""Lossless, human-readable JSON representation of a Master Tracks Pro song.

Every byte of the original file is represented: decoded fields are written
alongside the raw hex of headers whose meaning is only partly known, so
`from_json(to_json(song))` re-serializes to the identical .mts file.
"""
from __future__ import annotations

import json

from .model import (ConductorMeasure, ConductorTrack, NoteEvent, ShortEvent,
                    Song, Track)

FORMAT_ID = "mtspro-json"
FORMAT_VERSION = 1


def _ev_to_dict(e):
    if isinstance(e, NoteEvent):
        m, b, t = e.duration_parts
        d = {"tick": e.tick, "type": "note", "status": e.status, "channel": e.channel + 1,
             "key": e.key, "velocity": e.velocity, "release": e.release,
             "duration": e.duration}
        if m or b:
            d["duration_mbt"] = [m, b, t]
        return d
    return {"tick": e.tick, "type": e.kind, "status": e.status, "channel": e.channel + 1,
            "data1": e.data1, "data2": e.data2, "pad": e.pad}


def _ev_from_dict(d):
    if d["type"] == "note":
        return NoteEvent(d["tick"], d["status"], d["key"], d["velocity"], d["release"], d["duration"])
    return ShortEvent(d["tick"], d["status"], d["data1"], d["data2"], d.get("pad", 0))


def to_dict(song: Song) -> dict:
    starts = song.measure_starts()
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "source": "Master Tracks Pro (Passport Designs) song file",
        "title": song.title,
        "ppq": song.ppq,
        "measure_count": song.measure_count,
        "chunk_lengths": song.tag_lengths,
        "header_hex": song.header_raw.hex(),
        "conductor": {
            "header_hex": song.conductor.header_raw.hex(),
            "measures": [
                {"measure": i + 1, "start_tick": starts[i], "tempo": m.tempo,
                 "tempo_int": m.tempo_int, "tempo_frac": m.tempo_frac,
                 "meter": f"{m.numerator}/{m.denominator}", "numerator": m.numerator,
                 "denominator": m.denominator, "beat_ticks": m.beat_ticks,
                 "measure_ticks": m.measure_ticks, "reserved_hex": m.reserved.hex(),
                 "beat_mask": m.beat_mask, "flags": m.flags,
                 **({"marker": m.marker, "name_hex": m.name_raw.hex()} if m.name_raw is not None else {})}
                for i, m in enumerate(song.conductor.measures)
            ],
        },
        "tracks": [
            {"tag": t.tag, "name": t.name, "channel": t.channel, "program": t.program,
             "flags": t.flags, "header_hex": t.header_raw.hex(),
             "measures": [[_ev_to_dict(e) for e in m] for m in t.measures]}
            for t in song.tracks
        ],
    }


def from_dict(d: dict) -> Song:
    if d.get("format") != FORMAT_ID:
        raise ValueError("not an mtspro-json document")
    cond = ConductorTrack(header_raw=bytes.fromhex(d["conductor"]["header_hex"]))
    for m in d["conductor"]["measures"]:
        cond.measures.append(ConductorMeasure(
            tempo_int=m["tempo_int"], tempo_frac=m["tempo_frac"], beat_ticks=m["beat_ticks"],
            measure_ticks=m["measure_ticks"], numerator=m["numerator"],
            denominator=m["denominator"], reserved=bytes.fromhex(m["reserved_hex"]),
            beat_mask=m["beat_mask"], flags=m["flags"],
            name_raw=bytes.fromhex(m["name_hex"]) if "name_hex" in m else None))
    song = Song(header_raw=bytes.fromhex(d["header_hex"]), conductor=cond,
                tag_lengths=dict(d.get("chunk_lengths", {})))
    for t in d["tracks"]:
        hdr = bytearray.fromhex(t["header_hex"])
        # Allow simple edits of the decoded fields in the JSON.
        hdr[0x29], hdr[0x2A] = t["channel"], t["program"]
        track = Track(tag=t["tag"], header_raw=bytes(hdr))
        track.measures = [[_ev_from_dict(e) for e in m] for m in t["measures"]]
        song.tracks.append(track)
    return song


def write_file(song: Song, path, indent=1) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_dict(song), f, indent=indent, ensure_ascii=False)
        f.write("\n")


def read_file(path) -> Song:
    with open(path, encoding="utf-8") as f:
        return from_dict(json.load(f))
