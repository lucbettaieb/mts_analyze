"""Reader for Master Tracks Pro song files (Mac, late 1980s to 1990s).

File layout (all integers big-endian, Motorola 68k):

    "SCOR" u32 len(=0x40)  56-byte song header (title, PPQ, measure count ...)
    "TK00" u32 len(=0x40)  56-byte header, then N conductor measure records
    "TK01" u32 len(=0x40)  56-byte header, then N measure blocks
    ...
    "TKnn"

The chunk length covers only the tag + header; the data that follows is
delimited by the measure count stored in the header. See FORMAT.md.
"""
from __future__ import annotations

import struct

from .model import (ConductorMeasure, ConductorTrack, NoteEvent, ShortEvent,
                    Song, Track)


class MTSFormatError(Exception):
    pass


def _event_size(status: int) -> int:
    if status < 0x80 or status >= 0xF0:
        raise MTSFormatError(f"unsupported event status 0x{status:02X}")
    # Notes carry their duration, so only note-on records are long.
    return 10 if (status & 0xF0) == 0x90 else 6


def parse_measure_block(body: bytes, where: int):
    """Parse one measure block body (without its u16 length, including FFFF end)."""
    if body[-2:] != b"\xff\xff":
        raise MTSFormatError(f"measure block at 0x{where:X} lacks FFFF terminator")
    events, q, end = [], 0, len(body) - 2
    while q < end:
        status = body[q + 2]
        size = _event_size(status)
        rec = body[q:q + size]
        if len(rec) != size:
            raise MTSFormatError(f"truncated event at 0x{where + q:X}")
        tick = int.from_bytes(rec[0:2], "big")
        if size == 10:
            events.append(NoteEvent(tick, status, rec[3], rec[4], rec[5],
                                    int.from_bytes(rec[6:10], "big")))
        else:
            events.append(ShortEvent(tick, status, rec[3], rec[4], rec[5]))
        q += size
    if q != end:
        raise MTSFormatError(f"measure block at 0x{where:X} has trailing bytes")
    return events


def _parse_conductor_record(body: bytes, where: int) -> ConductorMeasure:
    if len(body) not in (16, 48):
        raise MTSFormatError(f"conductor record at 0x{where:X} has odd size {len(body)}")
    ti, tf, bt, mt = struct.unpack(">HHHH", body[0:8])
    return ConductorMeasure(
        tempo_int=ti, tempo_frac=tf, beat_ticks=bt, measure_ticks=mt,
        numerator=body[8], denominator=body[9], reserved=bytes(body[10:14]),
        beat_mask=body[14], flags=body[15],
        name_raw=bytes(body[16:48]) if len(body) == 48 else None)


def parse(data: bytes) -> Song:
    if data[:4] != b"SCOR":
        raise MTSFormatError("not a Master Tracks Pro song (missing SCOR tag)")
    pos = 0
    tag_lengths = {}

    def chunk_header(expected_prefix: bytes):
        nonlocal pos
        tag = data[pos:pos + 4]
        if not tag.startswith(expected_prefix):
            raise MTSFormatError(f"expected {expected_prefix!r} chunk at 0x{pos:X}, found {tag!r}")
        length = int.from_bytes(data[pos + 4:pos + 8], "big")
        if length < 8 or pos + length > len(data):
            raise MTSFormatError(f"bad chunk length {length} at 0x{pos:X}")
        hdr = data[pos + 8:pos + length]
        tag_lengths[tag.decode("latin-1")] = length
        pos += length
        return tag.decode("latin-1"), hdr

    _, song_hdr = chunk_header(b"SCOR")

    def read_blocks(count: int):
        nonlocal pos
        for _ in range(count):
            ln = int.from_bytes(data[pos:pos + 2], "big")
            body = data[pos + 2:pos + 2 + ln]
            if len(body) != ln:
                raise MTSFormatError(f"truncated block at 0x{pos:X}")
            yield pos, body
            pos += 2 + ln

    # Conductor track
    _, c_hdr = chunk_header(b"TK00")
    conductor = ConductorTrack(header_raw=c_hdr)
    c_count = int.from_bytes(c_hdr[0x20:0x22], "big")
    for where, body in read_blocks(c_count):
        conductor.measures.append(_parse_conductor_record(body, where))

    song = Song(header_raw=song_hdr, conductor=conductor, tag_lengths=tag_lengths)

    while pos < len(data):
        tag, t_hdr = chunk_header(b"TK")
        track = Track(tag=tag, header_raw=t_hdr)
        for where, body in read_blocks(track.measure_count):
            track.measures.append(parse_measure_block(body, where + 2))
        song.tracks.append(track)
    return song


def parse_file(path) -> Song:
    with open(path, "rb") as f:
        return parse(f.read())
