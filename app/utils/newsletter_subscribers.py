"""Listă abonați newsletter (fișier JSONL în ``plugins/newsletter/``)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import PROJECT_ROOT

_SUB_PATH = PROJECT_ROOT / "plugins" / "newsletter" / "subscribers.jsonl"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def subscribers_file_path() -> Path:
    return _SUB_PATH


def normalize_email(raw: str) -> str:
    return " ".join(raw.split()).strip().lower()


def list_subscribers_detailed() -> list[dict[str, str]]:
    if not _SUB_PATH.is_file():
        return []
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for line in _SUB_PATH.read_text(encoding="utf-8").splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        email = ""
        locale = "ro"
        if line_str.startswith("{") and line_str.endswith("}"):
            try:
                data = json.loads(line_str)
                email = normalize_email(data.get("email", ""))
                locale = (data.get("locale") or "ro").strip().lower()
            except Exception:
                email = ""
        else:
            email = normalize_email(line_str)

        if email and _EMAIL_RE.match(email) and email not in seen:
            seen.add(email)
            out.append({"email": email, "locale": locale})
    return out


def list_subscribers() -> list[str]:
    return [item["email"] for item in list_subscribers_detailed()]


def append_subscriber_if_new(email: str, locale: str = "ro") -> bool:
    """Returnează True dacă adresa e nouă și fișierul a fost actualizat."""
    email_norm = normalize_email(email)
    if not email_norm or not _EMAIL_RE.match(email_norm):
        return False
    _SUB_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_subscribers = list_subscribers_detailed()
    existing_emails = {s["email"] for s in existing_subscribers}
    if email_norm in existing_emails:
        return False
    
    row_data = json.dumps({"email": email_norm, "locale": locale or "ro"}, ensure_ascii=False)
    with _SUB_PATH.open("a", encoding="utf-8") as f:
        f.write(row_data + "\n")
    return True


def remove_subscriber(email: str) -> bool:
    """Șterge toate liniile care normalizează la această adresă. Returnează True dacă s-a schimbat ceva."""
    target = normalize_email(email)
    if not target or not _SUB_PATH.is_file():
        return False
    existing_subs = list_subscribers_detailed()
    kept: list[dict[str, str]] = [s for s in existing_subs if s["email"] != target]
    if len(kept) == len(existing_subs):
        return False
    lines = [json.dumps(s, ensure_ascii=False) for s in kept]
    body = "\n".join(lines)
    if body:
        body += "\n"
    _SUB_PATH.write_text(body, encoding="utf-8")
    return True
