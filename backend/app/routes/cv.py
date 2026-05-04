import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dep
from ..models import SettingsORM
from ..services.cv_parser import extract_text, parse_profile
from ._log import log_event

router = APIRouter()

UPLOAD_DIR = Path("uploads/cv")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _get_or_create_settings(session: AsyncSession) -> SettingsORM:
    res = await session.execute(select(SettingsORM).where(SettingsORM.id == 1))
    row = res.scalar_one_or_none()
    if row is None:
        row = SettingsORM(id=1, user_prefs={}, auto_apply_rules={})
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(session_dep),
):
    suffix = Path(file.filename or "cv").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(400, "Only PDF, DOCX or TXT files supported")

    safe_id = uuid.uuid4().hex[:12]
    target = UPLOAD_DIR / f"{safe_id}{suffix}"
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        text = extract_text(target)
    except Exception as exc:
        raise HTTPException(400, f"Could not read CV: {exc}") from exc

    row = await _get_or_create_settings(session)
    row.cv_text = text
    row.cv_filename = file.filename
    prefs = dict(row.user_prefs or {})
    prefs["cvUploaded"] = True
    row.user_prefs = prefs
    await session.commit()

    await log_event(session, "success", "cv", f"Uploaded CV: {file.filename}")

    return {
        "ok": True,
        "filename": file.filename,
        "characters": len(text),
        "url": f"/uploads/cv/{target.name}",
    }


@router.post("/parse")
async def parse_cv(session: AsyncSession = Depends(session_dep)):
    row = await _get_or_create_settings(session)
    if not row.cv_text:
        raise HTTPException(400, "No CV uploaded yet")

    profile = await parse_profile(row.cv_text)

    prefs = dict(row.user_prefs or {})
    if profile.get("fullName"):
        prefs["fullName"] = profile["fullName"]
    if profile.get("email"):
        prefs["email"] = profile["email"]
    if profile.get("phone"):
        prefs["phone"] = profile["phone"]
    if profile.get("location"):
        prefs["location"] = profile["location"]
    if profile.get("skills"):
        existing = list(prefs.get("preferredTech") or [])
        for s in profile["skills"]:
            if s and s not in existing:
                existing.append(s)
        prefs["preferredTech"] = existing
    row.user_prefs = prefs
    await session.commit()

    await log_event(session, "info", "cv", "Parsed CV with AI")

    return {"ok": True, "profile": profile}


@router.get("")
async def get_cv(session: AsyncSession = Depends(session_dep)):
    row = await _get_or_create_settings(session)
    text = row.cv_text or ""
    return {
        "uploaded": bool(text),
        "filename": row.cv_filename,
        # keep preview for backwards compatibility, but expose fullText for the UI
        "preview": text[:600],
        "fullText": text,
        "length": len(text),
    }
