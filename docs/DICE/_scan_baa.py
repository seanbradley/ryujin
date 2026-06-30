"""Quick BAA scanner: dump context around abstract-format keywords.

Usage:  python docs/DICE/_scan_baa.py
"""

import re
import sys

from pypdf import PdfReader

PDF = "docs/DICE/HR001126S0010.pdf"
KEYS = [
    "open source",
    "open-source",
    "publicly",
    "publish",
    "intellectual property",
    "data rights",
    "government purpose",
    "fundamental research",
    "interchang",
    "heterogene",
    "reconfigur",
    "role",
]


def main() -> None:
    reader = PdfReader(PDF)
    pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    full = "\n".join(t for _, t in pages)
    full = re.sub(r"[ \t]+", " ", full)

    for key in KEYS:
        print("=" * 78)
        print(f"KEY: {key!r}")
        print("=" * 78)
        for m in re.finditer(re.escape(key), full, flags=re.IGNORECASE):
            a = max(0, m.start() - 280)
            b = min(len(full), m.end() + 280)
            snippet = full[a:b].replace("\n", " ")
            print("...", snippet, "...\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
