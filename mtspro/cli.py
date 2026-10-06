"""Command line interface: python -m mtspro <command> ..."""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser

from . import analysis, jsonio, smf, viewer, writer
from .parser import MTSFormatError, parse_file


def load(path):
    """Load a song from .mts (binary) or mtspro .json."""
    if path.lower().endswith(".json"):
        return jsonio.read_file(path)
    return parse_file(path)


def _out(args, ext, suffix=""):
    if getattr(args, "output", None):
        return args.output
    base = os.path.splitext(args.file)[0]
    return base + suffix + ext


def _parse_range(s):
    if not s:
        return None
    a, _, b = s.partition("-")
    return int(a), int(b or a)


def _midi_opts(args):
    opts = smf.gm_options() if args.gm else smf.ExportOptions()
    if args.recorded_channels:
        opts.channel_mode = "recorded"
    if args.drop_all_notes_off:
        opts.keep_all_notes_off = False
    if args.no_programs:
        opts.programs = "none"
    if args.tempo_scale:
        opts.tempo_scale = args.tempo_scale
    for item in args.gm_program or []:
        tag, _, prog = item.partition("=")
        opts.gm_overrides[tag.upper()] = int(prog)
    return opts


def cmd_info(args):
    print(analysis.report(load(args.file), args.file))


def cmd_dump(args):
    tracks = [t.upper() if t.lower().startswith("tk") else t for t in (args.track or [])]
    print(analysis.dump(load(args.file), tracks or None, _parse_range(args.measures)))


def cmd_midi(args):
    song = load(args.file)
    out = _out(args, ".mid", "_gm" if args.gm else "")
    stats = smf.write_file(song, out, _midi_opts(args))
    print(f"wrote {out}: {stats.notes} notes, {len(song.tracks) + 1} tracks")
    if stats.overlaps_trimmed:
        print(f"  {stats.overlaps_trimmed} overlapping same-pitch notes were shortened (MIDI cannot overlap them)")
    if stats.dropped_events:
        print(f"  {stats.dropped_events} All-Notes-Off events dropped")
    for tag, how in stats.channel_remaps.items():
        print(f"  {tag}: channel {how} (avoids GM drum channel)")


def cmd_json(args):
    song = load(args.file)
    out = _out(args, ".json")
    jsonio.write_file(song, out)
    print(f"wrote {out}")


def cmd_tomts(args):
    song = load(args.file)
    out = _out(args, ".mts", "_rebuilt")
    writer.write_file(song, out)
    print(f"wrote {out}")


def cmd_view(args):
    song = load(args.file)
    out = _out(args, ".html")
    viewer.write_file(song, out, os.path.basename(args.file))
    print(f"wrote {out}")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(out))


def cmd_verify(args):
    with open(args.file, "rb") as f:
        data = f.read()
    song = parse_file(args.file)
    ok1 = writer.serialize(song) == data
    ok2 = writer.serialize(jsonio.from_dict(jsonio.to_dict(song))) == data
    print(f"binary round trip : {'OK (byte-identical)' if ok1 else 'MISMATCH'}")
    print(f"json round trip   : {'OK (byte-identical)' if ok2 else 'MISMATCH'}")
    return 0 if ok1 and ok2 else 1


def cmd_convert(args):
    song = parse_file(args.file)
    outdir = args.outdir or os.path.splitext(args.file)[0] + "_converted"
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, os.path.splitext(os.path.basename(args.file))[0])
    with open(base + "_report.txt", "w", encoding="utf-8") as f:
        f.write(analysis.report(song, os.path.basename(args.file)) + "\n")
    with open(base + "_events.txt", "w", encoding="utf-8") as f:
        f.write(analysis.dump(song) + "\n")
    s1 = smf.write_file(song, base + ".mid")
    s2 = smf.write_file(song, base + "_gm.mid", smf.gm_options())
    jsonio.write_file(song, base + ".json")
    viewer.write_file(song, base + ".html", os.path.basename(args.file))
    with open(args.file, "rb") as f:
        identical = writer.serialize(jsonio.read_file(base + ".json")) == f.read()
    print(f"Converted {args.file!r} ({song.title}) -> {outdir}/")
    print(f"  {os.path.basename(base)}.mid          faithful MIDI (original channels/programs), {s1.notes} notes")
    print(f"  {os.path.basename(base)}_gm.mid       General MIDI listening version")
    print(f"  {os.path.basename(base)}.json         lossless archive (round-trips to .mts: {'yes' if identical else 'NO'})")
    print(f"  {os.path.basename(base)}.html         interactive viewer (piano roll + playback)")
    print(f"  {os.path.basename(base)}_report.txt   analysis report")
    print(f"  {os.path.basename(base)}_events.txt   full event list")
    return 0 if identical else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="mtspro", description="Analyze and convert Master Tracks Pro (.mts) song files.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("file", help=".mts file (or mtspro .json)")
        sp.set_defaults(fn=fn)
        return sp

    add("info", cmd_info, "print an analysis report")
    sp = add("dump", cmd_dump, "print the event list")
    sp.add_argument("-t", "--track", action="append", help="track tag or name (repeatable), e.g. TK03")
    sp.add_argument("-m", "--measures", help="measure range, e.g. 41-48")
    sp = add("midi", cmd_midi, "export a Standard MIDI File (type 1)")
    sp.add_argument("-o", "--output")
    sp.add_argument("--gm", action="store_true", help="General MIDI listening version (GM programs, no CC123, avoid ch10)")
    sp.add_argument("--gm-program", action="append", metavar="TKnn=PROG", help="override GM program (0-127) for a track")
    sp.add_argument("--recorded-channels", action="store_true", help="keep recorded event channels instead of track channels")
    sp.add_argument("--drop-all-notes-off", action="store_true", help="omit CC123 All Notes Off events")
    sp.add_argument("--no-programs", action="store_true", help="omit program changes")
    sp.add_argument("--tempo-scale", type=float, help="multiply tempo (e.g. 0.5) if playback speed seems wrong")
    sp = add("json", cmd_json, "export the lossless JSON archive")
    sp.add_argument("-o", "--output")
    sp = add("tomts", cmd_tomts, "rebuild a binary .mts from an mtspro .json")
    sp.add_argument("-o", "--output")
    sp = add("view", cmd_view, "write the interactive HTML viewer")
    sp.add_argument("-o", "--output")
    sp.add_argument("--open", action="store_true", help="open it in the browser")
    add("verify", cmd_verify, "check that parsing is lossless (byte-identical round trips)")
    sp = add("convert", cmd_convert, "produce every output format at once")
    sp.add_argument("-d", "--outdir")

    args = p.parse_args(argv)
    try:
        return args.fn(args) or 0
    except (MTSFormatError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
