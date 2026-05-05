"""Read application form questions safely.

Read-only helper: opens a public job/application page, extracts visible form
questions/labels, and closes the browser. It does NOT fill fields, upload files,
or submit forms. It also does not attempt to bypass ATS anti-bot systems.
"""

from __future__ import annotations

import re
from typing import Any

_BASIC_FIELD_PATTERNS = [
    r"^first name$", r"^last name$", r"^full name$", r"^name$",
    r"^email$", r"^email address$", r"^phone$", r"^phone number$", r"^mobile$",
    r"^resume$", r"^cv$", r"^upload resume$", r"^cover letter$",
    r"^portfolio$", r"^website$", r"^url$",
]

_SPAMMY_TEXT_PATTERNS = [
    r"submit application", r"apply now", r"powered by", r"privacy policy",
    r"terms of service", r"cookie", r"equal opportunity employer",
    r"voluntary self-identification", r"eeo", r"demographic",
    r"^start typing\.\.\.$", r"^start typing$", r"^type here\.\.\.$",
    r"^copy$", r"^required$", r"^no generated answer$",
]


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text.replace("*", "").strip()


def _is_basic_or_noise(question: str) -> bool:
    q = _clean(question).lower().strip(":")
    if q in {"start typing", "start typing...", "type here", "type here...", "copy", "required", "no file chosen", "upload file", "or drag and drop here"}:
        return True
    if not q or len(q) < 3 or len(q) > 320:
        return True
    if any(re.search(p, q, re.I) for p in _SPAMMY_TEXT_PATTERNS):
        return True
    if any(re.search(p, q, re.I) for p in _BASIC_FIELD_PATTERNS):
        return True

    useful_words = [
        "why", "what", "how", "tell", "describe", "experience", "project",
        "salary", "compensation", "notice", "start", "available", "remote",
        "hybrid", "office", "visa", "sponsor", "sponsorship", "authorized",
        "authorised", "right to work", "work eligibility", "relocate", "location",
        "timezone", "years", "proficient", "comfortable", "agree", "consent",
        "require", "preferred", "expected", "worked with", "familiar", "eligible",
        "work in", "based in", "citizen", "security clearance", "hear about", "pronouns", "linkedin",
    ]
    return not ("?" in q or any(w in q for w in useful_words))


_EXTRACT_JS = r"""
() => {
  const isVisible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  };

  const clean = (s) => (s || '').replace(/\s+/g, ' ').replace(/\*/g, '').trim();
  const out = [];

  const shortText = (el) => {
    if (!el || !isVisible(el)) return '';
    const clone = el.cloneNode(true);
    clone.querySelectorAll('input, textarea, select, button, svg, script, style').forEach(n => n.remove());
    const t = clean(clone.innerText || clone.textContent);
    if (!t || t.length > 320) return '';
    return t;
  };

  const labelFor = (el) => {
    const parts = [];
    if (el.id) {
      const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lbl) parts.push(shortText(lbl));
    }
    const attrs = ['aria-label', 'data-label', 'placeholder', 'name'];
    for (const a of attrs) {
      const v = el.getAttribute(a);
      if (v) parts.push(clean(v.replace(/[_-]/g, ' ')));
    }
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      labelledBy.split(/\s+/).forEach((id) => {
        const node = document.getElementById(id);
        if (node) parts.push(shortText(node));
      });
    }
    const closestLabel = el.closest('label');
    if (closestLabel) parts.push(shortText(closestLabel));
    const fieldset = el.closest('fieldset');
    if (fieldset) {
      const legend = fieldset.querySelector('legend');
      if (legend) parts.push(shortText(legend));
    }

    // Walk ancestors. Ashby/Greenhouse often put the label in a sibling div above the input.
    let parent = el.parentElement;
    for (let depth = 0; parent && depth < 5; depth++, parent = parent.parentElement) {
      const lbl = parent.querySelector('label, legend, [class*="label"], [class*="Label"], [class*="question"], [class*="Question"]');
      if (lbl) parts.push(shortText(lbl));
      if (parent.previousElementSibling) parts.push(shortText(parent.previousElementSibling));
      const own = shortText(parent);
      if (own && own.length <= 220) parts.push(own);
    }

    return parts.map(clean).find(Boolean) || '';
  };

  const optionText = (el) => {
    if (!el) return [];
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'select') {
      return Array.from(el.options).map(o => clean(o.textContent)).filter(Boolean).filter(v => !/select|choose/i.test(v));
    }
    if (['radio', 'checkbox'].includes(type)) {
      const name = el.name;
      const group = name ? Array.from(document.querySelectorAll(`input[name="${CSS.escape(name)}"]`)) : [el];
      return Array.from(new Set(group.map(x => labelFor(x) || x.value).map(clean).filter(Boolean)));
    }
    return [];
  };

  const fields = Array.from(document.querySelectorAll('input, textarea, select, [role="textbox"], [role="combobox"], [contenteditable="true"]'));
  for (const el of fields) {
    if (!isVisible(el)) continue;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || tag || '').toLowerCase();
    if (['hidden','submit','button','image','reset','file','password'].includes(type)) continue;
    const question = labelFor(el);
    if (!question) continue;
    out.push({
      question,
      fieldType: tag === 'textarea' ? 'textarea' : (tag === 'select' ? 'select' : type || el.getAttribute('role') || 'text'),
      required: !!el.required || el.getAttribute('aria-required') === 'true' || /required/i.test(question),
      options: optionText(el),
    });
  }

  // Custom question blocks without normal fields.
  const blocks = Array.from(document.querySelectorAll('label, legend, [class*="question"], [class*="Question"], [data-qa*="question"], [data-testid*="question"]'));
  for (const node of blocks) {
    if (!isVisible(node)) continue;
    const text = shortText(node);
    if (text) out.push({ question: text, fieldType: 'unknown', required: /\*/.test(node.innerText || ''), options: [] });
  }

  return out;
}
"""


async def _maybe_open_application_form(page) -> None:
    """Click a safe apply/start button if the job post has not revealed a form yet.

    This never clicks submit. It only moves from job description to the application form.
    """
    patterns = [
        r"^Apply for this job$", r"^Apply now$", r"^Apply$", r"^Start application$",
        r"^Continue to application$", r"^View application$",
    ]
    for pat in patterns:
        for role in ("link", "button"):
            try:
                loc = page.get_by_role(role, name=re.compile(pat, re.I)).first
                if await loc.count() and await loc.is_visible(timeout=1000):
                    await loc.click(timeout=3000)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                    try:
                        await page.wait_for_load_state("networkidle", timeout=12000)
                    except Exception:
                        pass
                    return
            except Exception:
                continue


async def extract_application_questions(url: str, *, timeout_ms: int = 45000, headless: bool = False) -> dict[str, Any]:
    if not url:
        return {"ok": False, "url": url, "title": "", "questions": [], "count": 0, "error": "Missing URL"}

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {"ok": False, "url": url, "title": "", "questions": [], "count": 0, "error": f"Playwright not installed: {exc}"}

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page(viewport={"width": 1365, "height": 900})
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            title = ""
            try:
                title = await page.title()
            except Exception:
                pass

            # Scroll once so lazy form blocks render, then safely open application form if needed.
            try:
                await page.mouse.wheel(0, 900)
                await page.wait_for_timeout(800)
                await page.mouse.wheel(0, -300)
            except Exception:
                pass
            await _maybe_open_application_form(page)
            try:
                await page.wait_for_timeout(1500)
            except Exception:
                pass

            all_raw: list[dict[str, Any]] = []
            for frame in page.frames:
                try:
                    frame_raw = await frame.evaluate(_EXTRACT_JS)
                    if frame_raw:
                        all_raw.extend(frame_raw)
                except Exception:
                    continue

            await browser.close()
            browser = None
    except NotImplementedError:
        return {
            "ok": False,
            "url": url,
            "title": "",
            "questions": [],
            "count": 0,
            "error": "Playwright cannot start Chromium on the current Windows asyncio loop. Run backend with python run_backend.py, not uvicorn --reload.",
        }
    except Exception as exc:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        return {"ok": False, "url": url, "title": "", "questions": [], "count": 0, "error": str(exc)}

    seen: set[str] = set()
    questions: list[dict[str, Any]] = []
    for item in all_raw or []:
        q = _clean(item.get("question"))
        if _is_basic_or_noise(q):
            continue
        key = q.lower().strip(" ?:. ")
        if key in seen:
            continue
        seen.add(key)
        options = [_clean(x) for x in item.get("options") or [] if _clean(x)]
        options = [o for o in options if o.lower().strip(" ?:. ") != key]
        questions.append({
            "question": q,
            "fieldType": item.get("fieldType") or "unknown",
            "required": bool(item.get("required")),
            "options": options[:12],
        })

    return {"ok": True, "url": url, "title": title, "questions": questions[:40], "count": len(questions[:40])}


# ─────────────────────────────────────────────────────────────────────────────
# EXTRA CLEANUP v2.1
# Remove radio/checkbox option labels incorrectly extracted as separate questions.
# ─────────────────────────────────────────────────────────────────────────────
_ORIGINAL_extract_application_questions = extract_application_questions


def _dedupe_and_drop_option_questions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    option_texts: set[str] = set()
    for item in items or []:
        for opt in item.get("options") or []:
            key = _clean(opt).lower().strip(" ?:. ")
            if key:
                option_texts.add(key)

    sensitive_option_prefixes = (
        "i am authorized to work", "i am authorised to work", "i am not authorized", "i am not authorised",
        "i do not need", "i will need to be sponsored",
    )

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        q = _clean(item.get("question"))
        key = q.lower().strip(" ?:. ")
        if not key:
            continue
        if key in option_texts:
            continue
        if any(key.startswith(p) for p in sensitive_option_prefixes):
            continue
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


async def extract_application_questions(url: str, *, timeout_ms: int = 45000, headless: bool = False) -> dict[str, Any]:
    result = await _ORIGINAL_extract_application_questions(url, timeout_ms=timeout_ms, headless=headless)
    if result.get("ok"):
        questions = _dedupe_and_drop_option_questions(result.get("questions") or [])
        result["questions"] = questions
        result["count"] = len(questions)
    return result
