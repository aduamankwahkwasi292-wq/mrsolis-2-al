"""
Ingest PPTX / PDF / DOCX / TXT into a common structure:

    [{"number": 1, "title": "...", "bullets": ["...", "..."], "notes": "..."}, ...]

Real decks are messy: manually placed textboxes instead of real placeholders,
stray page/chapter-number textboxes, dates, footers. This module is written
against an actual lecture deck (not a clean synthetic one), so the noise
filters below are driven by real structure, not assumptions.
"""
from __future__ import annotations

import re
from typing import List, Optional, Dict, Any

_BARE_NUMBER = re.compile(r"^\d{1,4}$")
_NOISE_PLACEHOLDER_NAMES = {"SLIDE_NUMBER", "DATE", "FOOTER", "HEADER"}


def _is_noise_text(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if _BARE_NUMBER.fullmatch(t):
        return True
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", t):  # stray date strings
        return True
    return False


def ingest_pptx(path: str) -> List[Dict[str, Any]]:
    from pptx import Presentation

    prs = Presentation(path)
    slides_out = []
    for i, slide in enumerate(prs.slides, 1):
        candidates = []  # (top, text, shape)
        for shape in slide.shapes:
            if shape.is_placeholder:
                ph_type_name = str(shape.placeholder_format.type).split(" ")[0]
                if ph_type_name in _NOISE_PLACEHOLDER_NAMES:
                    continue
            if not getattr(shape, "has_text_frame", False):
                continue
            text = shape.text_frame.text.strip()
            if not text or _is_noise_text(text):
                continue
            top = shape.top if shape.top is not None else 10 ** 9
            candidates.append((top, shape))

        candidates.sort(key=lambda c: c[0])

        title = None
        body_shapes = [s for _, s in candidates]
        if candidates:
            first_top, first_shape = candidates[0]
            first_text = first_shape.text_frame.text.strip()
            if len(first_text.split()) <= 14 and "\n" not in first_text:
                title = first_text
                body_shapes = [s for _, s in candidates[1:]]

        bullets: List[str] = []
        for shape in body_shapes:
            for para in shape.text_frame.paragraphs:
                ptext = "".join(run.text for run in para.runs).strip() or para.text.strip()
                if ptext and not _is_noise_text(ptext):
                    bullets.append(ptext)

        notes = None
        if slide.has_notes_slide:
            nt = slide.notes_slide.notes_text_frame.text.strip()
            if nt:
                notes = nt

        if title or bullets or notes:
            slides_out.append({"number": i, "title": title, "bullets": bullets, "notes": notes})
    return slides_out


def ingest_pdf(path: str) -> List[Dict[str, Any]]:
    import fitz  # PyMuPDF - materially better than pdfplumber at surviving
    # LaTeX-typeset PDFs' font/ligature encoding, which matters a lot for
    # math notation specifically (superscripts, minus signs, quotes).

    slides_out = []
    doc = fitz.open(path)
    for i, page in enumerate(doc, 1):
        text = page.get_text()
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        lines = [ln for ln in lines if not _is_noise_text(ln)]
        if not lines:
            continue
        title = None
        body_lines = lines
        if len(lines[0].split()) <= 14:
            title = lines[0]
            body_lines = lines[1:]
        if title or body_lines:
            slides_out.append({"number": i, "title": title, "bullets": body_lines, "notes": None})
    doc.close()
    return slides_out


def ingest_docx(path: str) -> List[Dict[str, Any]]:
    import docx

    doc = docx.Document(path)
    sections: List[Dict[str, Any]] = []
    current = None
    n = 0

    def flush():
        nonlocal current
        if current and (current["title"] or current["bullets"]):
            sections.append(current)
        current = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "") if para.style else ""
        is_heading = style.lower().startswith("heading") or style.lower() == "title"
        if is_heading:
            flush()
            n += 1
            current = {"number": n, "title": text, "bullets": [], "notes": None}
        else:
            if current is None:
                n += 1
                current = {"number": n, "title": None, "bullets": [], "notes": None}
            current["bullets"].append(text)
    flush()

    if not sections:
        # No headings anywhere: chunk the whole doc into fixed-size
        # paragraph groups so downstream extraction still has something
        # slide-shaped to work with.
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        chunk = 6
        for idx in range(0, len(paras), chunk):
            group = paras[idx: idx + chunk]
            sections.append({
                "number": idx // chunk + 1,
                "title": group[0] if len(group[0].split()) <= 14 else None,
                "bullets": group[1:] if len(group[0].split()) <= 14 else group,
                "notes": None,
            })
    return sections


def ingest_txt(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    # Split on blank lines into pseudo-slides; first line of each block is
    # the title if short.
    blocks = re.split(r"\n\s*\n", text)
    slides_out = []
    n = 0
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        n += 1
        title = lines[0] if len(lines[0].split()) <= 14 else None
        bullets = lines[1:] if title else lines
        slides_out.append({"number": n, "title": title, "bullets": bullets, "notes": None})
    return slides_out


def ingest_file(path: str, filename: Optional[str] = None) -> List[Dict[str, Any]]:
    name = (filename or path).lower()
    if name.endswith(".pptx"):
        return ingest_pptx(path)
    if name.endswith(".pdf"):
        return ingest_pdf(path)
    if name.endswith(".docx"):
        return ingest_docx(path)
    if name.endswith((".txt", ".md")):
        return ingest_txt(path)
    raise ValueError(f"Unsupported file type: {name}")
