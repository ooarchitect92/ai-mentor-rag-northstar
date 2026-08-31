"""Safe live diagnostics for the isolated Ziplin WhatsApp integration.

The default command is read-only. A real template is sent only when the
operator supplies --send-template and an explicit recipient.
"""

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the live Ziplin WhatsApp integration.")
    parser.add_argument("--public-base-url", default="")
    parser.add_argument(
        "--probe-relay",
        action="store_true",
        help="Queue a harmless status-only event through the public relay.",
    )
    parser.add_argument(
        "--send-template",
        action="store_true",
        help="Send the configured start template to the explicit test recipient.",
    )
    parser.add_argument("--recipient", default="")
    return parser.parse_args()


async def call(
    client: httpx.AsyncClient,
    name: str,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
) -> tuple[Check, dict]:
    try:
        response = await client.request(method, url, headers=headers, json=payload)
    except Exception as exc:
        # Exception text can contain a URL with credentials, so report only its type.
        return Check(name, False, type(exc).__name__), {}
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.is_error:
        error = body.get("error") if isinstance(body, dict) else {}
        if not isinstance(error, dict):
            error = {}
        detail = f"HTTP {response.status_code}"
        if error.get("code") is not None:
            detail += f", code {error['code']}"
        if error.get("message"):
            detail += f": {str(error['message'])[:200]}"
        return Check(name, False, detail), body
    return Check(name, True, f"HTTP {response.status_code}"), body


def show(check: Check) -> None:
    label = "SKIP" if not check.required else ("OK" if check.ok else "FAIL")
    print(f"[{label}] {check.name}: {check.detail}")


async def run() -> int:
    args = parse_args()
    load_dotenv()
    token = os.getenv("WHATSAPP_ACCESS_TOKEN") or os.getenv("WHATSAPP_TOKEN") or ""
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or ""
    waba_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or ""
    app_id = os.getenv("META_APP_ID") or os.getenv("FACEBOOK_APP_ID") or ""
    app_secret = os.getenv("WHATSAPP_APP_SECRET") or os.getenv("META_APP_SECRET") or ""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN") or ""
    relay_token = os.getenv("WHATSAPP_RELAY_TOKEN") or ""
    callback_url = (os.getenv("WHATSAPP_WEBHOOK_CALLBACK_URL") or "").rstrip("/")
    public_base = (
        args.public_base_url or os.getenv("NORTHSTAR_PUBLIC_BASE_URL") or ""
    ).rstrip("/")
    graph_base = (
        os.getenv("WHATSAPP_GRAPH_BASE")
        or f"https://graph.facebook.com/{os.getenv('WHATSAPP_GRAPH_API_VERSION') or 'v25.0'}"
    ).rstrip("/")
    template_name = os.getenv("WHATSAPP_START_TEMPLATE_NAME") or "hello_world"
    template_language = os.getenv("WHATSAPP_START_TEMPLATE_LANGUAGE") or "en_US"

    checks = [
        Check("outbound access token configured", bool(token), "present" if token else "missing"),
        Check("Phone Number ID configured", bool(phone_id), "present" if phone_id else "missing"),
        Check("WABA ID configured", bool(waba_id), "present" if waba_id else "missing"),
        Check("webhook verification token configured", bool(verify_token), "present" if verify_token else "missing"),
        Check("Ziplin relay token configured", bool(relay_token), "present" if relay_token else "missing"),
    ]
    if not token or not phone_id:
        for check in checks:
            show(check)
        return 1

    auth = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        permission_check, body = await call(
            client, "Meta token permissions", "GET", f"{graph_base}/me/permissions", headers=auth
        )
        if permission_check.ok:
            granted = {
                str(item.get("permission"))
                for item in body.get("data") or []
                if item.get("status") == "granted"
            }
            required = {"whatsapp_business_management", "whatsapp_business_messaging"}
            missing = sorted(required - granted)
            permission_check = Check(
                permission_check.name,
                not missing,
                "required permissions granted" if not missing else "missing " + ", ".join(missing),
            )
        checks.append(permission_check)

        phone_check, body = await call(
            client,
            "configured Meta phone",
            "GET",
            f"{graph_base}/{phone_id}?fields=id,quality_rating,code_verification_status,platform_type",
            headers=auth,
        )
        if phone_check.ok:
            matched = str(body.get("id") or "") == phone_id
            phone_check = Check(
                phone_check.name,
                matched,
                "authorized; "
                f"quality={body.get('quality_rating') or 'unknown'}, "
                f"verification={body.get('code_verification_status') or 'unknown'}, "
                f"platform={body.get('platform_type') or 'unknown'}",
            )
        checks.append(phone_check)

        if waba_id:
            waba_check, body = await call(
                client,
                "phone belongs to configured WABA",
                "GET",
                f"{graph_base}/{waba_id}/phone_numbers?fields=id",
                headers=auth,
            )
            if waba_check.ok:
                ids = {str(item.get("id") or "") for item in body.get("data") or []}
                waba_check = Check(
                    waba_check.name,
                    phone_id in ids,
                    "configured Phone Number ID found" if phone_id in ids else "Phone Number ID absent",
                )
            checks.append(waba_check)

            query = str(httpx.QueryParams({"fields": "name,status,language", "name": template_name}))
            template_check, body = await call(
                client,
                "approved start template",
                "GET",
                f"{graph_base}/{waba_id}/message_templates?{query}",
                headers=auth,
            )
            if template_check.ok:
                approved = any(
                    item.get("name") == template_name
                    and item.get("language") == template_language
                    and item.get("status") == "APPROVED"
                    for item in body.get("data") or []
                )
                template_check = Check(
                    template_check.name,
                    approved,
                    f"{template_name}/{template_language} " + ("APPROVED" if approved else "not approved"),
                )
            checks.append(template_check)

        if app_id and app_secret:
            query = str(
                httpx.QueryParams(
                    {"input_token": token, "access_token": f"{app_id}|{app_secret}"}
                )
            )
            app_check, body = await call(
                client, "Meta token app ownership", "GET", f"{graph_base}/debug_token?{query}"
            )
            if app_check.ok:
                data = body.get("data") or {}
                matched = bool(data.get("is_valid")) and str(data.get("app_id") or "") == app_id
                app_check = Check(
                    app_check.name,
                    matched,
                    "valid and app matched" if matched else "invalid or belongs to another app",
                )
            checks.append(app_check)
        else:
            checks.append(Check("Meta app ownership", True, "app secret unavailable in relay mode", False))

        if callback_url and verify_token:
            challenge = "ZIPLIN_WEBHOOK_OK"
            query = str(
                httpx.QueryParams(
                    {
                        "hub.mode": "subscribe",
                        "hub.verify_token": verify_token,
                        "hub.challenge": challenge,
                    }
                )
            )
            try:
                response = await client.get(f"{callback_url}?{query}")
                ok = response.status_code == 200 and response.text == challenge
                checks.append(
                    Check(
                        "existing Xolox callback challenge",
                        ok,
                        "challenge echoed" if ok else f"HTTP {response.status_code}; mismatch",
                    )
                )
            except Exception as exc:
                checks.append(Check("existing Xolox callback challenge", False, type(exc).__name__))

        callback_path = urlparse(callback_url).path.rstrip("/").lower()
        relay_mode = bool(
            callback_url
            and not callback_path.endswith(
                ("/v1/whatsapp/webhook", "/v1/whatsapp/ziplin/webhook")
            )
        )
        if relay_mode:
            public_origin = urlparse(public_base)
            stable_public_origin = bool(
                public_origin.scheme == "https"
                and public_origin.hostname
                and not public_origin.hostname.casefold().endswith(".trycloudflare.com")
            )
            checks.append(
                Check(
                    "stable public Ziplin relay origin",
                    stable_public_origin,
                    (
                        public_base
                        if stable_public_origin
                        else "a permanent HTTPS NORTHSTAR_PUBLIC_BASE_URL is missing"
                    ),
                )
            )

        if public_base:
            ready_check, body = await call(
                client, "public NorthStar readiness", "GET", f"{public_base}/ready"
            )
            if ready_check.ok:
                ready_check = Check(
                    ready_check.name,
                    body.get("status") == "ready",
                    str(body.get("status") or "unexpected response"),
                )
            checks.append(ready_check)

            if args.probe_relay:
                relay_check, body = await call(
                    client,
                    "authenticated public Ziplin relay",
                    "POST",
                    f"{public_base}/v1/whatsapp/ziplin/relay",
                    headers={"X-Ziplin-Relay-Token": relay_token},
                    payload={
                        "object": "whatsapp_business_account",
                        "entry": [
                            {
                                "id": waba_id,
                                "changes": [
                                    {
                                        "field": "messages",
                                        "value": {
                                            "metadata": {"phone_number_id": phone_id},
                                            "statuses": [
                                                {
                                                    "id": f"wamid.ziplin-diagnostic.{time.time_ns()}",
                                                    "status": "read",
                                                    "recipient_id": "000000000000",
                                                }
                                            ],
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                )
                if relay_check.ok:
                    relay_check = Check(
                        relay_check.name,
                        body.get("status") == "accepted",
                        str(body.get("status") or "unexpected response"),
                    )
                checks.append(relay_check)

        if args.send_template:
            recipient = args.recipient or os.getenv("WHATSAPP_TEST_TO") or ""
            digits = "".join(character for character in recipient if character.isdigit())
            if not digits:
                checks.append(Check("explicit template send", False, "recipient is missing"))
            else:
                send_check, body = await call(
                    client,
                    "explicit template send",
                    "POST",
                    f"{graph_base}/{phone_id}/messages",
                    headers={**auth, "Content-Type": "application/json"},
                    payload={
                        "messaging_product": "whatsapp",
                        "to": digits,
                        "type": "template",
                        "template": {
                            "name": template_name,
                            "language": {"code": template_language},
                        },
                    },
                )
                if send_check.ok:
                    accepted = bool(body.get("messages"))
                    send_check = Check(
                        send_check.name,
                        accepted,
                        "accepted by Meta" if accepted else "Meta returned no message ID",
                    )
                checks.append(send_check)

    for check in checks:
        show(check)
    failures = [check for check in checks if check.required and not check.ok]
    print(f"Summary: {len(checks) - len(failures)}/{len(checks)} checks passed or safely skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
