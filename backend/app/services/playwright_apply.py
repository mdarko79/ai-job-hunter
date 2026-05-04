"""Real browser application submission with Playwright.

This service is deliberately conservative:
- It fills the form and uploads the CV where possible.
- It clicks Submit only when submit=True.
- It returns submitted=True only after a visible confirmation signal.
- If confirmation is not detected, the caller must NOT mark the application as submitted.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

UPLOAD_DIR = Path("uploads")
SCREENSHOT_DIR = UPLOAD_DIR / "screenshots"
CV_DIR = UPLOAD_DIR / "cv"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

CONFIRMATION_RE = re.compile(
    r"(thank you|thanks for applying|application submitted|successfully submitted|"
    r"we received your application|application received|your application has been received|"
    r"we'?ll be in touch|you have applied|applied successfully|submission received)",
    re.I,
)

NEGATIVE_RE = re.compile(
    r"(required|please fill|invalid|error|captcha|recaptcha|verify you are human|"
    r"something went wrong|unable to submit)",
    re.I,
)


def _latest_cv_path() -> str | None:
    if not CV_DIR.exists():
        return None
    files = [p for p in CV_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt"}]
    if not files:
        return None
    return str(max(files, key=lambda p: p.stat().st_mtime))


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _clean_phone(phone: str) -> str:
    return str(phone or "").replace("(UK)", "").strip()


def _url_to_api_path(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        rel = path.resolve().relative_to(Path("uploads").resolve())
        return "/uploads/" + rel.as_posix()
    except Exception:
        return str(path)


def _screenshot_path(company: str = "apply") -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", company or "apply").strip("-")[:40] or "apply"
    return SCREENSHOT_DIR / f"{safe}-{int(time.time())}.png"


async def _safe_screenshot(page, path: Path | None, full_page: bool = True) -> str | None:
    if not path:
        return None
    try:
        await page.screenshot(path=str(path), full_page=full_page)
        return _url_to_api_path(path)
    except Exception:
        return None


async def _wait_network(page, ms: int = 1000) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=ms)
    except Exception:
        pass


async def _dismiss_common_popups(page) -> None:
    patterns = [
        r"accept all", r"accept", r"agree", r"got it", r"continue", r"close", r"dismiss",
    ]
    for pat in patterns:
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=re.compile(pat, re.I)).first
                if await loc.count():
                    await loc.click(timeout=1200)
                    await page.wait_for_timeout(250)
                    return
            except Exception:
                continue


async def _click_apply_if_needed(page, context) -> None:
    # Some ATS pages show the form immediately. If it is already visible, do nothing.
    try:
        if await page.locator("form").count() and await page.locator("input, textarea, select").count() >= 3:
            return
    except Exception:
        pass

    apply_re = re.compile(r"^(apply|apply now|apply for this job|start application|submit application)$", re.I)
    candidates = []
    try:
        candidates.append(page.get_by_role("link", name=apply_re).first)
    except Exception:
        pass
    try:
        candidates.append(page.get_by_role("button", name=apply_re).first)
    except Exception:
        pass
    candidates.extend([
        page.locator("a[href*='apply']").first,
        page.locator("button:has-text('Apply')").first,
        page.locator("a:has-text('Apply')").first,
    ])

    for loc in candidates:
        try:
            if await loc.count() == 0:
                continue
            try:
                async with context.expect_page(timeout=2500) as new_page_info:
                    await loc.click(timeout=2500)
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                # The caller still uses old page object; we cannot reassign here.
                # If a new tab opened, bring it to front and copy URL by navigation on original page.
                await page.goto(new_page.url, wait_until="domcontentloaded", timeout=30000)
                await new_page.close()
            except Exception:
                await loc.click(timeout=2500)
            await page.wait_for_timeout(1200)
            await _wait_network(page, 5000)
            return
        except Exception:
            continue


async def _fill_first_working(page, selectors: list[Any], value: str) -> bool:
    if not value:
        return False
    for sel in selectors:
        try:
            loc = sel if hasattr(sel, "fill") else page.locator(str(sel)).first
            if await loc.count() == 0:
                continue
            await loc.fill(str(value), timeout=1500)
            return True
        except Exception:
            continue
    return False


async def _fill_by_label_or_selector(page, label_patterns: list[str], selectors: list[str], value: str) -> bool:
    if not value:
        return False

    locators = []
    for pat in label_patterns:
        try:
            locators.append(page.get_by_label(re.compile(pat, re.I)).first)
        except Exception:
            pass
        try:
            locators.append(page.get_by_placeholder(re.compile(pat, re.I)).first)
        except Exception:
            pass

    locators.extend(selectors)
    return await _fill_first_working(page, locators, value)


async def _fill_candidate_fields(page, prefs: dict[str, Any]) -> dict[str, bool]:
    full_name = str(prefs.get("fullName") or prefs.get("name") or "").strip()
    first_name, last_name = _split_name(full_name)
    email = str(prefs.get("email") or "").strip()
    phone = _clean_phone(str(prefs.get("phone") or ""))
    location = str(prefs.get("location") or "").strip() or "UK"
    linkedin = str(prefs.get("linkedin") or prefs.get("linkedIn") or prefs.get("linkedinUrl") or "").strip()
    github = str(prefs.get("github") or prefs.get("githubUrl") or "").strip()

    results = {}
    results["fullName"] = await _fill_by_label_or_selector(
        page,
        [r"full.*name", r"name"],
        [
            "input[name*='full'][name*='name' i]",
            "input[id*='full'][id*='name' i]",
            "input[name='name']",
            "input[id='name']",
        ],
        full_name,
    )
    results["firstName"] = await _fill_by_label_or_selector(
        page,
        [r"first.*name", r"given.*name"],
        ["input[name*='first' i]", "input[id*='first' i]", "input[name*='given' i]"],
        first_name,
    )
    results["lastName"] = await _fill_by_label_or_selector(
        page,
        [r"last.*name", r"surname", r"family.*name"],
        ["input[name*='last' i]", "input[id*='last' i]", "input[name*='surname' i]"],
        last_name,
    )
    results["email"] = await _fill_by_label_or_selector(
        page,
        [r"email", r"e-mail"],
        ["input[type='email']", "input[name*='email' i]", "input[id*='email' i]"],
        email,
    )
    results["phone"] = await _fill_by_label_or_selector(
        page,
        [r"phone", r"mobile", r"telephone"],
        ["input[type='tel']", "input[name*='phone' i]", "input[id*='phone' i]", "input[name*='mobile' i]"],
        phone,
    )
    results["location"] = await _fill_by_label_or_selector(
        page,
        [r"location", r"city", r"where.*located", r"current.*location"],
        ["input[name*='location' i]", "input[id*='location' i]", "input[name*='city' i]"],
        location,
    )
    if linkedin:
        results["linkedin"] = await _fill_by_label_or_selector(
            page,
            [r"linkedin", r"linked in"],
            ["input[name*='linkedin' i]", "input[id*='linkedin' i]"],
            linkedin,
        )
    if github:
        results["github"] = await _fill_by_label_or_selector(
            page,
            [r"github", r"portfolio", r"website"],
            ["input[name*='github' i]", "input[id*='github' i]", "input[name*='website' i]"],
            github,
        )
    return results


async def _upload_cv(page, cv_path: str | None) -> bool:
    cv_path = cv_path or _latest_cv_path()
    if not cv_path:
        return False
    p = Path(cv_path)
    if not p.exists():
        return False

    # Apply to all file inputs. Most ATS forms have one resume input; if they have
    # cover-letter upload too, setting the CV there is usually harmless but we prefer
    # resume-labelled inputs first.
    try:
        file_inputs = page.locator("input[type='file']")
        count = await file_inputs.count()
    except Exception:
        return False

    if count == 0:
        return False

    uploaded = False
    preferred_indices = []
    other_indices = []
    for i in range(count):
        try:
            inp = file_inputs.nth(i)
            meta = " ".join([
                await inp.get_attribute("name") or "",
                await inp.get_attribute("id") or "",
                await inp.get_attribute("accept") or "",
                await inp.get_attribute("aria-label") or "",
            ]).lower()
            if any(x in meta for x in ["resume", "cv", "file", "upload"]):
                preferred_indices.append(i)
            else:
                other_indices.append(i)
        except Exception:
            other_indices.append(i)

    for i in preferred_indices + other_indices:
        try:
            await file_inputs.nth(i).set_input_files(str(p), timeout=4000)
            uploaded = True
        except Exception:
            continue
    return uploaded


async def _fill_textareas(page, cover_letter: str | None, answers: dict[str, str] | None) -> int:
    answers = answers or {}
    filled = 0

    # Explicit custom answers first: if a question text appears near a textarea, fill it.
    for question, answer in answers.items():
        if not answer:
            continue
        try:
            locator = page.locator(
                f"xpath=//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                f"{repr(str(question).lower()[:60])})]/following::textarea[1]"
            ).first
            if await locator.count():
                await locator.fill(str(answer), timeout=1500)
                filled += 1
        except Exception:
            pass

    if not cover_letter:
        return filled

    # Prefer cover-letter / motivation textareas.
    cover_patterns = [r"cover", r"why.*you", r"motivation", r"additional.*information", r"anything.*else", r"message"]
    for pat in cover_patterns:
        try:
            loc = page.get_by_label(re.compile(pat, re.I)).first
            if await loc.count():
                current = await loc.input_value(timeout=1000)
                if not current.strip():
                    await loc.fill(cover_letter, timeout=2000)
                    return filled + 1
        except Exception:
            continue

    # Fallback: first empty textarea that is not obviously demographic / salary.
    try:
        textareas = page.locator("textarea")
        count = await textareas.count()
        for i in range(count):
            ta = textareas.nth(i)
            meta = " ".join([
                await ta.get_attribute("name") or "",
                await ta.get_attribute("id") or "",
                await ta.get_attribute("placeholder") or "",
                await ta.get_attribute("aria-label") or "",
            ]).lower()
            if any(bad in meta for bad in ["gender", "race", "ethnic", "disability", "veteran", "salary"]):
                continue
            try:
                current = await ta.input_value(timeout=1000)
                if not current.strip():
                    await ta.fill(cover_letter, timeout=2000)
                    filled += 1
                    break
            except Exception:
                continue
    except Exception:
        pass
    return filled


async def _tick_consent_checkboxes(page) -> int:
    clicked = 0
    consent_re = re.compile(r"(agree|consent|privacy|terms|data processing|gdpr|i accept)", re.I)
    bad_re = re.compile(r"(gender|race|ethnic|veteran|disability|lgbt|sexual|pronoun)", re.I)
    try:
        labels = page.locator("label")
        count = await labels.count()
        for i in range(min(count, 80)):
            label = labels.nth(i)
            try:
                text = (await label.inner_text(timeout=500)).strip()
            except Exception:
                continue
            if not text or bad_re.search(text) or not consent_re.search(text):
                continue
            try:
                await label.click(timeout=1000)
                clicked += 1
            except Exception:
                pass
    except Exception:
        pass
    return clicked


async def _required_missing(page) -> list[str]:
    try:
        return await page.evaluate(
            """
            () => {
              const out = [];
              const els = Array.from(document.querySelectorAll('input, textarea, select'));
              const visible = (el) => {
                const s = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return s && s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0;
              };
              const labelFor = (el) => {
                const id = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
                const wrapped = el.closest('label');
                const aria = el.getAttribute('aria-label');
                const name = el.getAttribute('name') || el.getAttribute('id') || el.getAttribute('placeholder') || el.type || 'field';
                return (aria || (id && id.innerText) || (wrapped && wrapped.innerText) || name).trim().slice(0, 90);
              };
              for (const el of els) {
                if (!visible(el) || el.disabled) continue;
                const required = el.required || el.getAttribute('aria-required') === 'true';
                if (!required) continue;
                const type = (el.getAttribute('type') || '').toLowerCase();
                let empty = false;
                if (type === 'file') empty = !el.files || el.files.length === 0;
                else if (type === 'checkbox' || type === 'radio') empty = !el.checked;
                else empty = !String(el.value || '').trim();
                if (empty) out.push(labelFor(el));
              }
              return Array.from(new Set(out)).slice(0, 10);
            }
            """
        )
    except Exception:
        return []


async def _click_submit(page) -> bool:
    submit_patterns = [
        r"submit application", r"submit", r"send application", r"apply now", r"apply", r"send",
    ]
    for pat in submit_patterns:
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=re.compile(pat, re.I)).last
                if await loc.count():
                    await loc.click(timeout=3000)
                    return True
            except Exception:
                continue
    for sel in ["button[type='submit']", "input[type='submit']"]:
        try:
            loc = page.locator(sel).last
            if await loc.count():
                await loc.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


async def _detect_confirmation(page) -> tuple[bool, str]:
    await page.wait_for_timeout(2500)
    await _wait_network(page, 8000)
    url = page.url.lower()
    if any(x in url for x in ["success", "confirmation", "thank", "submitted"]):
        return True, f"confirmation URL: {page.url}"

    try:
        text = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        text = ""

    if CONFIRMATION_RE.search(text or ""):
        return True, "confirmation text detected"

    if NEGATIVE_RE.search(text or ""):
        return False, "page shows validation/error/captcha text"

    # Very conservative: if we cannot prove confirmation, return false.
    return False, "no confirmation signal detected"


async def fill_form(
    *,
    url: str,
    prefs: dict[str, Any],
    cover_letter: str | None = None,
    answers: dict[str, str] | None = None,
    cv_path: str | None = None,
    submit: bool = False,
    save_screenshot: bool = True,
    headless: bool = False,
    company: str = "apply",
) -> dict[str, Any]:
    """Fill and optionally submit an application form.

    Returns keys:
      ok: bool                  # automation completed the requested action
      filled: bool              # some fields/upload were filled
      submitted: bool           # confirmed external submission
      screenshotUrl: str|None   # final screenshot served by FastAPI /uploads
      message: str
      evidence: list[str]
      finalUrl: str
    """
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError  # noqa: F401
        from playwright.async_api import async_playwright
    except ImportError as exc:
        return {
            "ok": False,
            "filled": False,
            "submitted": False,
            "screenshotUrl": None,
            "message": "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium",
            "evidence": [str(exc)],
            "finalUrl": url,
        }

    screenshot = _screenshot_path(company)
    evidence: list[str] = []
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless, slow_mo=80 if not headless else 0)
            context = await browser.new_context(
                accept_downloads=True,
                locale="en-GB",
                timezone_id="Europe/London",
                viewport={"width": 1365, "height": 900},
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await _wait_network(page, 8000)
            await _dismiss_common_popups(page)
            await _click_apply_if_needed(page, context)
            await _dismiss_common_popups(page)

            field_results = await _fill_candidate_fields(page, prefs or {})
            evidence.append("fields: " + ", ".join([f"{k}={v}" for k, v in field_results.items()]))

            cv_uploaded = await _upload_cv(page, cv_path)
            evidence.append(f"cvUploaded={cv_uploaded}")

            textarea_count = await _fill_textareas(page, cover_letter, answers)
            evidence.append(f"textareasFilled={textarea_count}")

            consent_count = await _tick_consent_checkboxes(page)
            if consent_count:
                evidence.append(f"consentCheckboxesClicked={consent_count}")

            await page.wait_for_timeout(700)
            before_submit_url = await _safe_screenshot(page, screenshot if save_screenshot else None)

            filled_any = any(field_results.values()) or cv_uploaded or textarea_count > 0

            if not submit:
                return {
                    "ok": True,
                    "filled": filled_any,
                    "submitted": False,
                    "screenshotUrl": before_submit_url,
                    "message": "Form filled. Submit was not clicked.",
                    "evidence": evidence,
                    "finalUrl": page.url,
                }

            missing = await _required_missing(page)
            if missing:
                evidence.append("missingRequired=" + "; ".join(missing))
                return {
                    "ok": False,
                    "filled": filled_any,
                    "submitted": False,
                    "screenshotUrl": before_submit_url,
                    "message": "Required fields are still missing; not clicking Submit: " + ", ".join(missing),
                    "evidence": evidence,
                    "finalUrl": page.url,
                }

            clicked = await _click_submit(page)
            evidence.append(f"submitClicked={clicked}")
            if not clicked:
                return {
                    "ok": False,
                    "filled": filled_any,
                    "submitted": False,
                    "screenshotUrl": before_submit_url,
                    "message": "Could not find a Submit button/link.",
                    "evidence": evidence,
                    "finalUrl": page.url,
                }

            confirmed, reason = await _detect_confirmation(page)
            evidence.append(reason)
            after_path = _screenshot_path(company + "-submitted")
            final_shot = await _safe_screenshot(page, after_path if save_screenshot else None)

            return {
                "ok": bool(confirmed),
                "filled": filled_any,
                "submitted": bool(confirmed),
                "screenshotUrl": final_shot or before_submit_url,
                "message": "Application submitted and confirmation detected." if confirmed else "Submit clicked, but confirmation was not detected. Not marking as submitted.",
                "evidence": evidence,
                "finalUrl": page.url,
            }
    except Exception as exc:
        return {
            "ok": False,
            "filled": False,
            "submitted": False,
            "screenshotUrl": None,
            "message": str(exc),
            "evidence": evidence,
            "finalUrl": url,
        }
    finally:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
