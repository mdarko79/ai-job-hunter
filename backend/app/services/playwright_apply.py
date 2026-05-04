"""Browser automation for filling and (optionally) submitting applications.

Two modes:
  - semi_auto_apply: fills the form and stops, leaving the human to click Submit
  - auto_apply: fills + submits, only when called from a context that has already
    verified all auto-apply rules

A screenshot is always saved before the submit step.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
SCREENSHOT_DIR = UPLOAD_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def fill_form(
    job_url: str,
    user_data: dict[str, Any],
    cv_path: str | None,
    cover_letter: str | None,
    submit: bool = False,
) -> dict[str, Any]:
    """Open the job URL in a real browser, autofill what we can, save a screenshot.
    Returns: { ok, screenshot, message }
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "message": "Playwright not installed"}

    screenshot = SCREENSHOT_DIR / f"apply-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)

            # Best-effort autofill — selectors vary widely across ATS systems.
            field_map = {
                "full_name": user_data.get("fullName", ""),
                "first_name": (user_data.get("fullName") or "").split(" ")[0],
                "last_name": " ".join((user_data.get("fullName") or "").split(" ")[1:]),
                "email": user_data.get("email", ""),
                "phone": user_data.get("phone", ""),
                "location": user_data.get("location", ""),
                "city": user_data.get("location", ""),
            }
            for name, value in field_map.items():
                if not value:
                    continue
                for sel in (
                    f"input[name*='{name}' i]",
                    f"input[id*='{name}' i]",
                    f"input[placeholder*='{name.replace('_', ' ')}' i]",
                ):
                    try:
                        await page.fill(sel, value, timeout=1500)
                        break
                    except Exception:
                        continue

            # Cover letter -> first textarea
            if cover_letter:
                try:
                    await page.fill("textarea", cover_letter, timeout=2000)
                except Exception:
                    pass

            # CV upload
            if cv_path and Path(cv_path).exists():
                try:
                    await page.set_input_files("input[type='file']", cv_path)
                except Exception:
                    pass

            await page.wait_for_timeout(800)
            await page.screenshot(path=str(screenshot), full_page=True)

            if submit:
                # Try to click submit. Be defensive — if anything fails, do not retry.
                for sel in (
                    "button:has-text('Submit application')",
                    "button:has-text('Submit')",
                    "button[type='submit']",
                ):
                    try:
                        await page.click(sel, timeout=2000)
                        await page.wait_for_timeout(2500)
                        break
                    except Exception:
                        continue

            await browser.close()
        return {"ok": True, "screenshot": str(screenshot), "message": "Form filled"}
    except Exception as e:
        return {"ok": False, "screenshot": str(screenshot) if screenshot.exists() else None, "message": str(e)}
