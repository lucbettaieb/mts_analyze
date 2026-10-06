# mtspro: resurrect Master Tracks Pro songs

`mtspro` analyzes and converts song files from **Passport Designs Master Tracks Pro**,
the classic Mac OS MIDI sequencer, into modern formats. It is pure Python (3.8+)
and has no dependencies.

The file format was reverse-engineered from `antar.mts`. See [FORMAT.md](FORMAT.md)
for the specification.

## No-install web version

`web/dist/Master Tracks Converter.html` is a single page that does everything in
the browser: open a song, listen to it, and save the MIDI files, the lossless
JSON or a zip of everything. Double-click it; nothing else is needed. Rebuild it
after changing `web/template.html` with `python3 web/build.py antar.mts`. The
song is optional and pre-loads in the page. The JavaScript port produces
byte-identical output to the Python tool.

The same page is published with GitHub Pages from `docs/index.html`
(https://lucbettaieb.github.io/mts_analyze/). The build never bundles a song
into that copy because Pages sites are public, so visitors open their own file.

## Quick start

```sh
python3 -m mtspro convert antar.mts -d output
```

| file | what it is |
|---|---|
| `antar.mid` | **Faithful MIDI** (type 1, 240 PPQ): tempo map, meters, markers, track names, original channels and program numbers, every note with its release velocity, and the CC123 events. Use it to drive the original hardware (Proteus, TX802, ...) or any DAW. |
| `antar_gm.mid` | **Listening MIDI** for General MIDI synths and soundfonts. Programs are guessed from track names (flute→GM 73, marimba→12, ...), the Marimba track is moved off GM drum channel 10, and the All-Notes-Off events are removed. |
| `antar.json` | **Lossless open archive**. Every byte of the original is represented (decoded fields plus raw hex for unknown ones), and `tomts` rebuilds a byte-identical `.mts` from it. |
| `antar.html` | **Interactive viewer**: piano roll, markers, mute/solo, hover info and a built-in preview synth. Open it in any browser. |
| `antar_report.txt` | Analysis report: tempo/meter map, markers, per-track statistics. |
| `antar_events.txt` | Full event list in measure\|beat\|tick form, like MTS Pro's Event List. |

## Commands

```sh
python3 -m mtspro info    antar.mts               # analysis report
python3 -m mtspro dump    antar.mts -t TK03 -m 41-48   # event list
python3 -m mtspro midi    antar.mts [-o out.mid]  # faithful MIDI
python3 -m mtspro midi    antar.mts --gm          # GM listening version
python3 -m mtspro midi    antar.mts --gm --gm-program TK07=12   # override a GM instrument
python3 -m mtspro json    antar.mts               # lossless JSON
python3 -m mtspro tomts   antar.json              # JSON -> .mts (edit the JSON, rebuild)
python3 -m mtspro view    antar.mts --open        # HTML viewer
python3 -m mtspro verify  antar.mts               # prove parsing is lossless
```

Other `midi` options: `--recorded-channels`, `--drop-all-notes-off`,
`--no-programs`, and `--tempo-scale 0.5` (in case the tempo should be read
differently). Every command also accepts an `mtspro` `.json` file as input.

## Getting real sound

* **Open-source DAWs and notation**: import `antar.mid` (or `antar_gm.mid`) into
  MuseScore, Ardour, LMMS, Rosegarden or Qtractor. Markers, meters and tempo carry over.
* **Render to audio**:
  `fluidsynth -F antar.wav -r 44100 GeneralUser.sf2 output/antar_gm.mid`
  (`brew install fluid-synth`; any GM soundfont works).
* **Authentic sound**: the faithful MIDI keeps the original program numbers. With
  an E-mu Proteus/1, Yamaha TX802, TX16W and Roland RD-1000 (or emulations) on
  the channels in the report, it plays the original patches.

## About `antar.mts`

The song is "ANTAR": 15 tracks, 18,259 notes, about 11 minutes at ♩=91/89. It is
in 13/16 with passages in 12/16, 10/16 and 8/16. Markers: Introduction, Theme 1: A,
A, B, Theme 1: A', A', B'. The instruments are Proteus flute/marimba/vibes/
glockenspiel/pads, TX802 clarinets/bassoons/choir, TX16W celesta and RD-1000 piano.

## Tests

```sh
python3 -m unittest discover -s tests
```

The tests check the byte-identical binary and JSON round trips, decode the
MIDI output with an independent reader and compare every note against the
source, check that note-ons and note-offs balance, and confirm that corrupt input
is rejected.
