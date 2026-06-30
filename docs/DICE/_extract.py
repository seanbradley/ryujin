"""Dependency-free text extractor for OOXML (docx/pptx/xlsx) files.

Reads the relevant XML parts from the OOXML zip container and strips tags,
preserving paragraph/cell breaks. Used only for quick content scanning.
"""

import re
import sys
import zipfile


def _strip(xml: str) -> str:
    # Insert breaks for paragraph, line-break, tab, and slide-text boundaries.
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:br/>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"</a:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    xml = xml.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    xml = re.sub(r"\n{3,}", "\n\n", xml)
    return xml.strip()


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        return _strip(z.read("word/document.xml").decode("utf-8", "ignore"))


def pptx_text(path: str) -> str:
    out = []
    with zipfile.ZipFile(path) as z:
        names = sorted(
            n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)
        )
        for i, n in enumerate(names, 1):
            out.append(
                f"\n--- slide {i} ---\n" + _strip(z.read(n).decode("utf-8", "ignore"))
            )
    return "\n".join(out)


def xlsx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            raw = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
            shared = re.findall(r"<t[^>]*>(.*?)</t>", raw, re.S)
        wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
        sheets = re.findall(r'<sheet[^>]*name="([^"]+)"', wb)
        out = ["SHEETS: " + " | ".join(sheets), "", "STRING LABELS (deduped):"]
        seen, uniq = set(), []
        for s in shared:
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                uniq.append(s)
        out.extend(uniq)
        return "\n".join(out)


def extract(path: str) -> str:
    p = path.lower()
    if p.endswith(".docx"):
        return docx_text(path)
    if p.endswith(".pptx"):
        return pptx_text(path)
    if p.endswith(".xlsx"):
        return xlsx_text(path)
    return "(unsupported)"


if __name__ == "__main__":
    target = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    text = extract(target)
    print(text[:limit])
    if len(text) > limit:
        print(f"\n... [truncated {len(text) - limit} more chars]")
