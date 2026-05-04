"""Parse PDF / DOCX / TXT CVs into plain text + structured profile."""

from __future__ import annotations
from pathlib import Path
from typing import Union

from . import ai_service


def extract_text(source: Union[Path, str, bytes], filename: str = "") -> str:
    """Extract plain text from a CV file.

    Accepts:
      - a Path or str pointing to the file on disk
      - bytes (in which case `filename` must be passed for suffix detection)
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"CV file not found: {path}")
        suffix = path.suffix.lower()
        data = path.read_bytes()
    elif isinstance(source, bytes):
        data = source
        suffix = Path(filename or "").suffix.lower()
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            from io import BytesIO
            reader = PdfReader(BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if not text:
                # Some PDFs are scanned images — pypdf returns nothing.
                # We don't OCR here; return empty string so the caller can warn.
                return ""
            return text
        except Exception as exc:
            raise RuntimeError(f"PDF parsing failed: {exc}") from exc

    if suffix in (".docx", ".doc"):
        try:
            import docx
            from io import BytesIO
            doc = docx.Document(BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as exc:
            raise RuntimeError(f"DOCX parsing failed: {exc}") from exc

    if suffix == ".txt":
        try:
            return data.decode("utf-8", errors="ignore").strip()
        except Exception as exc:
            raise RuntimeError(f"TXT decoding failed: {exc}") from exc

    # Unknown suffix — try utf-8 as last resort
    try:
        return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


async def parse_profile(cv_text: str) -> dict:
    """Use the LLM to extract structured fields from raw CV text."""
    if not cv_text.strip():
        return {}

    system = (
        "You are a recruiting assistant. Extract structured profile data from a CV. "
        "Return JSON with keys: fullName, email, phone, location, yearsExperience (int), "
        "primaryStack (string), skills (array of strings), summary (1-2 sentences)."
    )
    return await ai_service.chat_json(prompt=cv_text[:8000], system=system)
