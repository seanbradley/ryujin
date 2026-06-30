"""Extract BAA PDF text and scan for threat/domain vocabulary.

Tries pypdf, then pdfminer.six. Prints each match with a short context window
so we can settle, factually, whether DARPA's DICE BAA uses 'drone'/'swarm'
language or frames the program more abstractly.
"""

import re
import sys

PDF = r"C:\Users\sean\projects\ryujin\docs\DICE\HR001126S0010.pdf"
KEYWORDS = [
    "drone",
    "swarm",
    "uav",
    "uas",
    "munition",
    "loitering",
    "kinetic",
    "weapon",
    "lethal",
    "kill",
    "missile",
    "aircraft",
    "robot",
    "autonom",
    "contested",
    "adversar",
    "battlefield",
    "warfighter",
    "combat",
    "jellyfish",
]


def extract_text(path):
    try:
        import pypdf

        reader = pypdf.PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"pypdf failed: {exc}\n")
    try:
        from pdfminer.high_level import extract_text as pm

        return pm(path)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"pdfminer failed: {exc}\n")
    return ""


def main():
    text = extract_text(PDF)
    if not text:
        print("NO TEXT EXTRACTED -- install pypdf or pdfminer.six")
        return
    low = text.lower()
    print(f"Total characters: {len(text)}\n")
    for kw in KEYWORDS:
        hits = [m.start() for m in re.finditer(re.escape(kw), low)]
        print(f"=== '{kw}': {len(hits)} hit(s) ===")
        for h in hits[:6]:
            ctx = text[max(0, h - 70) : h + 70].replace("\n", " ")
            ctx = re.sub(r"\s+", " ", ctx).strip()
            print(f"   ...{ctx}...")
        print()


if __name__ == "__main__":
    main()
