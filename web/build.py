"""Build the browser converter.

    python3 web/build.py [song.mts]

Writes web/dist/converter.html (page body, for publishing as a claude.ai
Artifact) and web/dist/Master Tracks Converter.html (a complete page anyone
can double-click). The optional song is bundled so the page opens with it.
"""
import base64
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        page = f.read()
    sample = sys.argv[1] if len(sys.argv) > 1 else None
    if sample:
        with open(sample, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        name = os.path.basename(sample)
    else:
        b64, name = "", ""
    page = page.replace("__SAMPLE_B64__", b64).replace("__SAMPLE_NAME__", name)
    out = os.path.join(HERE, "dist")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "converter.html"), "w", encoding="utf-8") as f:
        f.write(page)
    standalone = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                  '</head>\n<body>\n' + page + '\n</body>\n</html>\n')
    with open(os.path.join(out, "Master Tracks Converter.html"), "w", encoding="utf-8") as f:
        f.write(standalone)
    print(f"wrote {out}/converter.html and {out}/Master Tracks Converter.html"
          + (f" (bundled {name})" if sample else ""))


if __name__ == "__main__":
    main()
