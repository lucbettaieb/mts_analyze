"""Build the browser converter.

    python3 web/build.py [song.mts]

Writes:
  web/dist/converter.html               page body, for publishing as a claude.ai Artifact
  web/dist/Master Tracks Converter.html complete page anyone can double-click
  docs/index.html                       GitHub Pages site (never bundles a song: it is public)

The optional song is bundled into the web/dist pages so they open with it.
"""
import base64
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def standalone(page: str) -> str:
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + page + '\n</body>\n</html>\n')


def fill(template: str, b64: str, name: str) -> str:
    return template.replace("__SAMPLE_B64__", b64).replace("__SAMPLE_NAME__", name)


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(path, ROOT)}")


def main():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        template = f.read()
    b64 = name = ""
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        name = os.path.basename(sys.argv[1])
        print(f"bundling {name} into web/dist")

    page = fill(template, b64, name)
    write(os.path.join(HERE, "dist", "converter.html"), page)
    write(os.path.join(HERE, "dist", "Master Tracks Converter.html"), standalone(page))

    write(os.path.join(ROOT, "docs", "index.html"), standalone(fill(template, "", "")))
    write(os.path.join(ROOT, "docs", ".nojekyll"), "")


if __name__ == "__main__":
    main()
