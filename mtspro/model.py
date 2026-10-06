"""Data model for Master Tracks Pro (Passport Designs) song files.

Every structure keeps the raw bytes of fields whose meaning is not fully
known, so a parsed song can be written back byte-for-byte (see writer.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NoteEvent:
    """10-byte note record: tick16, status, key, velocity, release velocity, duration32."""
    tick: int          # offset from start of measure, in ticks
    status: int        # 0x9n as stored (low nibble = recorded MIDI channel)
    key: int
    velocity: int
    release: int       # note-off velocity
    duration: int      # packed: u8 measures, u8 beats (assumed), u16 ticks

    @property
    def channel(self) -> int:
        return self.status & 0x0F

    @property
    def duration_parts(self):
        """(measures, beats, ticks) as packed in the 32-bit duration field."""
        d = self.duration
        return d >> 24, (d >> 16) & 0xFF, d & 0xFFFF


@dataclass
class ShortEvent:
    """6-byte record for every other channel message: tick16, status, data1, data2, pad."""
    tick: int
    status: int
    data1: int
    data2: int
    pad: int = 0

    @property
    def channel(self) -> int:
        return self.status & 0x0F

    @property
    def kind(self) -> str:
        return {0x80: "note_off", 0xA0: "poly_aftertouch", 0xB0: "control_change",
                0xC0: "program_change", 0xD0: "channel_aftertouch",
                0xE0: "pitch_bend"}.get(self.status & 0xF0, "unknown")


Event = object  # NoteEvent | ShortEvent


@dataclass
class ConductorMeasure:
    """One record of the conductor track (TK00): tempo, meter and optional marker."""
    tempo_int: int        # BPM integer part (quarter note)
    tempo_frac: int       # BPM fractional part (/65536)
    beat_ticks: int       # ticks per metronome beat (60 = sixteenth at 240 PPQ)
    measure_ticks: int    # length of the measure in ticks
    numerator: int
    denominator: int
    reserved: bytes       # 4 bytes, always zero in known files
    beat_mask: int        # opaque byte (beat grouping / accent pattern?)
    flags: int            # opaque byte (0xFF on most measures carrying a name record)
    name_raw: Optional[bytes] = None  # 32-byte Pascal string block, if present

    @property
    def tempo(self) -> float:
        return self.tempo_int + self.tempo_frac / 65536.0

    @property
    def marker(self) -> Optional[str]:
        if not self.name_raw:
            return None
        n = self.name_raw[0]
        s = self.name_raw[1:1 + n].decode("mac_roman")
        return s or None


@dataclass
class ConductorTrack:
    header_raw: bytes                 # 56 bytes following "TK00" + length
    measures: List[ConductorMeasure] = field(default_factory=list)


@dataclass
class Track:
    tag: str                          # "TK01".. as stored
    header_raw: bytes                 # 56 bytes following tag + length
    measures: List[List[Event]] = field(default_factory=list)

    @property
    def name(self) -> str:
        n = self.header_raw[0]
        return self.header_raw[1:1 + n].decode("mac_roman")

    @property
    def measure_count(self) -> int:
        return int.from_bytes(self.header_raw[0x20:0x22], "big")

    @property
    def flags(self) -> int:
        return self.header_raw[0x28]

    @property
    def channel(self) -> int:
        """Track output channel, 1-16 (0 = no override, play recorded channel)."""
        return self.header_raw[0x29]

    @property
    def program(self) -> int:
        """Track program as stored, 1-128 (0 = none). MIDI program = value - 1."""
        return self.header_raw[0x2A]

    def notes(self):
        for m in self.measures:
            for e in m:
                if isinstance(e, NoteEvent):
                    yield e


@dataclass
class Song:
    header_raw: bytes                 # 56 bytes following "SCOR" + length
    conductor: ConductorTrack
    tracks: List[Track] = field(default_factory=list)
    tag_lengths: dict = field(default_factory=dict)  # preserved chunk length fields

    @property
    def title(self) -> str:
        raw = self.header_raw[:0x20]
        return raw.split(b"\x00", 1)[0].decode("mac_roman")

    @property
    def ppq(self) -> int:
        return int.from_bytes(self.header_raw[0x22:0x24], "big")

    @property
    def measure_count(self) -> int:
        return int.from_bytes(self.header_raw[0x2A:0x2C], "big")

    def measure_starts(self, count: Optional[int] = None) -> List[int]:
        """Absolute tick of the start of each measure (index 0 = measure 1).

        Tracks may contain more measures than the conductor; the last
        conductor measure length is repeated in that case.
        """
        cm = self.conductor.measures
        if count is None:
            count = max([len(cm)] + [len(t.measures) for t in self.tracks])
        starts, t = [], 0
        for i in range(count + 1):
            starts.append(t)
            src = cm[min(i, len(cm) - 1)] if cm else None
            t += src.measure_ticks if src else self.ppq * 4
        return starts

    def note_span(self, starts: List[int], measure_index: int, note: NoteEvent):
        """Absolute (on, off) ticks of a note found in measure `measure_index` (0-based).

        Long durations are stored as whole measures plus ticks, so the end is
        found by stepping forward that many measures from the note's position.
        """
        on = starts[measure_index] + note.tick
        meas, beats, ticks = note.duration_parts
        if meas == 0:
            off = on + beats * self._beat_ticks(measure_index) + ticks
        else:
            end_m = measure_index + meas
            while end_m >= len(starts) - 1:  # extend past the last known measure
                starts.append(starts[-1] + (starts[-1] - starts[-2]))
            off = starts[end_m] + note.tick + beats * self._beat_ticks(end_m) + ticks
        return on, max(off, on + 1)

    def _beat_ticks(self, measure_index: int) -> int:
        cm = self.conductor.measures
        return cm[min(measure_index, len(cm) - 1)].beat_ticks if cm else self.ppq
