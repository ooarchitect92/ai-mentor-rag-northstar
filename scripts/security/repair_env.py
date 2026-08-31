"""Safely repair local NorthStar environment settings without printing secrets."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
BACKUP_DIRECTORY = ROOT / "data" / "backups"


def parse_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    return key.strip(), value.strip().strip('"').strip("'")


def secure_updates(lines: list[str]) -> dict[str, str]:
    existing = dict(item for line in lines if (item := parse_line(line)))
    updates = {
        "APP_ENVIRONMENT": "production",
        "EMBEDDING_PROVIDER": "hash",
        "COURSE_RETRIEVAL_ENABLED": "true",
        "WHATSAPP_MESSAGING_ENABLED": "true",
    }
    relay = existing.get("WHATSAPP_RELAY_TOKEN", "").strip()
    if len(relay) < 32:
        updates["WHATSAPP_RELAY_TOKEN"] = secrets.token_hex(32)
    imported_whatsapp_token = os.getenv("NORTHSTAR_REPAIR_WHATSAPP_TOKEN", "").strip()
    if imported_whatsapp_token:
        updates["WHATSAPP_ACCESS_TOKEN"] = imported_whatsapp_token
        updates["WHATSAPP_TOKEN"] = imported_whatsapp_token
    for source, target in {
        "NORTHSTAR_REPAIR_META_APP_SECRET": "META_APP_SECRET",
        "NORTHSTAR_REPAIR_WHATSAPP_VERIFY_TOKEN": "WHATSAPP_VERIFY_TOKEN",
        "NORTHSTAR_REPAIR_WHATSAPP_PHONE_NUMBER_ID": "WHATSAPP_PHONE_NUMBER_ID",
        "NORTHSTAR_REPAIR_WHATSAPP_BUSINESS_ACCOUNT_ID": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "NORTHSTAR_REPAIR_META_APP_ID": "META_APP_ID",
        "NORTHSTAR_REPAIR_WHATSAPP_CALLBACK_URL": "WHATSAPP_WEBHOOK_CALLBACK_URL",
    }.items():
        value = os.getenv(source, "").strip()
        if value:
            updates[target] = value
    if updates.get("META_APP_SECRET"):
        updates["WHATSAPP_APP_SECRET"] = updates["META_APP_SECRET"]
    if updates.get("META_APP_ID"):
        updates["FACEBOOK_APP_ID"] = updates["META_APP_ID"]
    if os.getenv("NORTHSTAR_REPAIR_CLEAR_META_IDENTITY", "").strip().casefold() in {
        "1",
        "true",
        "yes",
    }:
        # Relay deployments must not retain an unrelated app secret or WABA ID:
        # doing so makes diagnostics misleading and can accept signatures from
        # the previous Meta application. The verified App ID and phone token can
        # still be imported in the same atomic repair operation.
        updates["META_APP_SECRET"] = ""
        updates["WHATSAPP_APP_SECRET"] = ""
        updates["WHATSAPP_BUSINESS_ACCOUNT_ID"] = ""
    return updates


def render(lines: list[str], updates: dict[str, str]) -> list[str]:
    remaining = dict(updates)
    rendered: list[str] = []
    for line in lines:
        parsed = parse_line(line)
        if parsed and parsed[0] in remaining:
            key = parsed[0]
            rendered.append(f"{key}={remaining.pop(key)}")
        else:
            rendered.append(line)
    if remaining:
        if rendered and rendered[-1].strip():
            rendered.append("")
        rendered.append("# Security/runtime values maintained by scripts/security/repair_env.py")
        rendered.extend(f"{key}={value}" for key, value in remaining.items())
    return rendered


def main() -> None:
    if not ENV_FILE.is_file():
        raise SystemExit(f"Environment file not found: {ENV_FILE}")
    original = ENV_FILE.read_text(encoding="utf-8-sig")
    lines = original.splitlines()
    updates = secure_updates(lines)
    revised = "\n".join(render(lines, updates)).rstrip() + "\n"

    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_DIRECTORY / f"env-before-token-repair-{timestamp}.bak"
    backup.write_text(original, encoding="utf-8", newline="\n")

    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=ENV_FILE.parent,
        prefix=".env.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(revised)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, ENV_FILE)
    print(f"Backup: {backup.relative_to(ROOT)}")
    print("Updated keys: " + ", ".join(sorted(updates)))
    print("Secret values were not printed.")


if __name__ == "__main__":
    main()
