# Master Tracks Pro song file format (reverse-engineered)

Passport Designs' Master Tracks Pro (classic Mac OS) song files, as observed in
`antar.mts`. All integers are big-endian (Motorola 68k). The file has no resource
fork content that matters; everything is in the data fork.

Status legend: **confirmed** = verified by byte-exact round trip and musically
consistent output; *assumed* = consistent with the data but not proven.

## Top level

```
"SCOR" u32 len   song header         (len = 0x40, i.e. 8 + 56 bytes)
"TK00" u32 len   conductor header    (len = 0x40)
   N conductor measure records       (N = measure count in TK00 header)
"TK01" u32 len   track header        (len = 0x40)
   N measure blocks                  (N = measure count in track header)
...
"TKnn"  (one chunk per track, then end of file)
```

The chunk length covers only the tag, length and header. The variable-length
data that follows is delimited by the **measure count** in the header. **confirmed**

## SCOR song header (56 bytes)

| offset | size | meaning |
|---|---|---|
| 0x00 | 32 | song title, NUL-terminated (here `ANTAR`) **confirmed** |
| 0x20 | 2  | `0x0100`, unknown (version/flags?) |
| 0x22 | 2  | resolution in PPQ (`240`) **confirmed** |
| 0x24 | 2  | `0x00EA`, unknown (window/display setting?) |
| 0x26 | 4  | `FFFFFFFF`, unknown |
| 0x2A | 2  | song length in measures (`384`) **confirmed** |
| 0x2C | 12 | unknown, mostly zero (`FF` at 0x34) |

## TK00 conductor track

Header (56 bytes): 32 bytes of empty name, u16 measure count at 0x20, u32 unknown
at 0x22, then a copy of a 16-byte conductor record (the "current" tempo/meter).

Each measure has a record of `u16 length` followed by 16 or 48 bytes:

| offset | size | meaning |
|---|---|---|
| 0  | 2 | tempo, integer part, quarter notes per minute (*assumed* quarter-note based) |
| 2  | 2 | tempo, fractional part (/65536) |
| 4  | 2 | ticks per metronome beat (`60` = sixteenth at 240 PPQ) **confirmed** |
| 6  | 2 | measure length in ticks (`780` for 13/16) **confirmed** |
| 8  | 1 | meter numerator **confirmed** |
| 9  | 1 | meter denominator **confirmed** |
| 10 | 4 | zero |
| 14 | 1 | opaque byte (cycles B6/6D/DB, looks like a beam/accent pattern) |
| 15 | 1 | opaque flag (`FF` on most records that carry a name block) |
| 16 | 32 | *(only when length = 48)* Pascal string: marker name **confirmed** |

## TKnn track header (56 bytes)

| offset | size | meaning |
|---|---|---|
| 0x00 | 32 | Pascal string: track name (`PROTEUS / Verb Flute #17`) **confirmed** |
| 0x20 | 2  | measure count (number of blocks that follow) **confirmed** |
| 0x22 | 4  | opaque (decreasing per track; looks like a stale memory handle) |
| 0x26 | 2  | zero |
| 0x28 | 1  | `01` in all tracks: unknown flag (port? play-enable?) |
| 0x29 | 1  | output MIDI channel 1-16 (0 = as recorded, *assumed*) **confirmed** |
| 0x2A | 1  | program 1-128 (0 = none, *assumed*); MIDI program = value - 1 |
| 0x2B | 13 | zero |

## Measure blocks

```
u16 length          bytes that follow, including the FFFF terminator
events...
FFFF                end of measure
```

An empty measure is `0002 FFFF`. Each event starts with `u16 tick`, the offset from
the start of the measure (it may exceed the measure length slightly), then the
MIDI status byte. The low nibble is the channel the event was *recorded* on. On
playback the track's channel overrides it. **confirmed**

**Note (status 9n), 10 bytes**

```
u16 tick | u8 status | u8 key | u8 velocity | u8 release velocity | u32 duration
```

The duration is packed as `u8 measures | u8 beats | u16 ticks`. Notes held across
bar lines store whole measures in the top byte, e.g. `01 00 00F3` = 1 measure + 243
ticks, so the end is found by stepping forward that many measures from the note's
position. The *beats* byte is always 0 in the sample, and its meaning is
*assumed*. **confirmed** for measures/ticks.

**Other channel messages (An, Bn, Cn, Dn, En), 6 bytes**

```
u16 tick | u8 status | u8 data1 | u8 data2 | u8 pad(0)
```

The sample only contains `B0 7B 00` (CC123 All Notes Off). Event sizes for 8n and
Fn (SysEx) have not been observed. The parser rejects unknown statuses rather
than guessing.
