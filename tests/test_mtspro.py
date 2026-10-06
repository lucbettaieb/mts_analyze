import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mtspro import analysis, jsonio, smf, viewer, writer  # noqa: E402
from mtspro.model import NoteEvent  # noqa: E402
from mtspro.parser import MTSFormatError, parse, parse_file  # noqa: E402

SAMPLE = os.path.join(ROOT, "antar.mts")


def read_smf(data):
    """Minimal independent SMF reader -> list of tracks of (abs_tick, bytes)."""
    assert data[:4] == b"MThd"
    _, fmt, ntrk, div = struct.unpack(">IHHH", data[4:14])
    pos, tracks = 14, []
    for _ in range(ntrk):
        assert data[pos:pos + 4] == b"MTrk"
        ln = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        p, end, t, evs, running = pos + 8, pos + 8 + ln, 0, [], None
        while p < end:
            d = 0
            while True:
                b = data[p]; p += 1
                d = (d << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            t += d
            st = data[p]
            if st == 0xFF:
                ln2 = data[p + 2]
                evs.append((t, data[p:p + 3 + ln2])); p += 3 + ln2
            else:
                if st < 0x80:
                    st = running
                else:
                    p += 1
                running = st
                n = 1 if st & 0xF0 in (0xC0, 0xD0) else 2
                evs.append((t, bytes([st]) + data[p:p + n])); p += n
        tracks.append(evs)
        pos = end
    return fmt, div, tracks


@unittest.skipUnless(os.path.exists(SAMPLE), "antar.mts sample not present")
class SampleFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SAMPLE, "rb") as f:
            cls.data = f.read()
        cls.song = parse(cls.data)

    def test_header(self):
        self.assertEqual(self.song.title, "ANTAR")
        self.assertEqual(self.song.ppq, 240)
        self.assertEqual(self.song.measure_count, 384)
        self.assertEqual(len(self.song.conductor.measures), 384)
        self.assertEqual(len(self.song.tracks), 15)

    def test_track_metadata(self):
        t = self.song.tracks[0]
        self.assertEqual(t.name, "PROTEUS / Verb Flute #17")
        self.assertEqual((t.channel, t.program), (9, 18))
        self.assertEqual(sum(1 for t in self.song.tracks for _ in t.notes()), 18259)

    def test_conductor(self):
        m1 = self.song.conductor.measures[0]
        self.assertEqual((m1.tempo, m1.numerator, m1.denominator, m1.measure_ticks), (91.0, 13, 16, 780))
        markers = [m.marker for m in self.song.conductor.measures if m.marker]
        self.assertEqual(markers[:3], ["Introduction", "Theme 1: A", "A"])

    def test_binary_round_trip(self):
        self.assertEqual(writer.serialize(self.song), self.data)

    def test_json_round_trip(self):
        self.assertEqual(writer.serialize(jsonio.from_dict(jsonio.to_dict(self.song))), self.data)

    def test_long_duration_spans_measures(self):
        starts = self.song.measure_starts()
        n = next(e for e in self.song.tracks[5].measures[186]   # TK06 m187: G4 tied 1|0|243
                 if isinstance(e, NoteEvent) and e.duration_parts[0])
        self.assertEqual(n.duration_parts, (1, 0, 243))
        on, off = self.song.note_span(starts, 186, n)
        self.assertEqual(off, starts[188])          # ends exactly on the m189 bar line

    def test_midi_matches_source(self):
        data, stats = smf.export(self.song)
        fmt, div, tracks = read_smf(data)
        self.assertEqual((fmt, div, len(tracks)), (1, 240, 16))
        starts = self.song.measure_starts()
        for ti, t in enumerate(self.song.tracks):
            expected = sorted((self.song.note_span(starts, mi, e)[0], e.key)
                              for mi, m in enumerate(t.measures) for e in m if isinstance(e, NoteEvent))
            got = sorted((tick, ev[1]) for tick, ev in tracks[ti + 1] if ev[0] & 0xF0 == 0x90)
            self.assertEqual(got, expected, t.tag)
            chans = {ev[0] & 0x0F for _, ev in tracks[ti + 1] if ev[0] < 0xF0}
            if t.notes and chans:
                self.assertEqual(chans, {t.channel - 1}, t.tag)
        self.assertEqual(stats.notes, 18259)

    def test_midi_balanced_notes(self):
        _, _, tracks = read_smf(smf.export(self.song, smf.gm_options())[0])
        for evs in tracks[1:]:
            sounding = {}
            for _, ev in evs:
                if ev[0] & 0xF0 == 0x90 and ev[2]:
                    self.assertNotIn(ev[1], sounding); sounding[ev[1]] = 1
                elif ev[0] & 0xF0 == 0x80:
                    self.assertIn(ev[1], sounding); del sounding[ev[1]]
            self.assertFalse(sounding)

    def test_gm_avoids_drum_channel(self):
        _, stats = smf.export(self.song, smf.gm_options())
        self.assertIn("TK04", stats.channel_remaps)
        self.assertEqual(stats.programs["TK01"], 73)  # flute

    def test_reports_render(self):
        self.assertIn("Theme 1: A", analysis.report(self.song))
        self.assertIn("Note", analysis.dump(self.song, ["TK01"], (9, 9)))
        self.assertIn("<canvas", viewer.render(self.song))


class SyntheticTests(unittest.TestCase):
    def test_rejects_non_mts(self):
        with self.assertRaises(MTSFormatError):
            parse(b"MThd\x00\x00\x00\x06")

    def test_detects_bad_block(self):
        with open(SAMPLE, "rb") as f:
            data = bytearray(f.read())
        data[0x1D42:0x1D44] = b"\x00\x00"   # corrupt the first track's first block terminator
        with self.assertRaises(MTSFormatError):
            parse(bytes(data))


if __name__ == "__main__":
    unittest.main()
