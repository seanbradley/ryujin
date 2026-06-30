"""Extract DICE BAA text and surface award-size, count, and teaming language.

Prints context windows around funding/award/teaming/abstract terms so we can
ground the cost model and the "can I submit without a partner" question in the
solicitation's own words rather than assumptions.
"""

import re
import sys

PDF = r"C:\Users\sean\projects\ryujin\docs\DICE\HR001126S0010.pdf"

# Phrases worth reading in context for cost + teaming decisions.
PATTERNS = [
    r"award",
    r"multiple\s+awards?",
    r"anticipat\w*",
    r"\$[0-9][0-9,\.]*\s*[MmKkBb]?",
    r"fund\w*",
    r"team\w*",
    r"abstract\w*",
    r"encourag\w*",
    r"single\s+award",
    r"period\s+of\s+performance",
    r"cost\s+shar\w*",
    r"phase\s+[123]",
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
    flat = re.sub(r"\s+", " ", text)
    print(f"Total characters: {len(text)}\n")
    for pat in PATTERNS:
        hits = list(re.finditer(pat, flat, flags=re.IGNORECASE))
        print(f"=== /{pat}/ : {len(hits)} hit(s) ===")
        seen = set()
        for m in hits[:8]:
            s = max(0, m.start() - 110)
            e = min(len(flat), m.end() + 110)
            ctx = flat[s:e].strip()
            if ctx in seen:
                continue
            seen.add(ctx)
            print(f"   ...{ctx}...")
        print()


if __name__ == "__main__":
    main()
