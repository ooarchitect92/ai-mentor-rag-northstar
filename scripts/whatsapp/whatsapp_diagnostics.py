"""Safe live diagnostics for the isolated Ziplin WhatsApp integration.

The default command is read-only. A real template is sent only when the
operator supplies --send-template and an explicit recipient.
"""

import argparse
import asyncio
import ipaddress
import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from app.whatsapp import WhatsAppClient


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def callback_state(value: str):
    """Apply the same canonical Ziplin callback rules as the backend."""
    try:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").rstrip(".").casefold()
        supported_port = parsed.port in {None, 443}
    except ValueError:
        return urlparse(""), False, False, ""
    direct = bool(
        parsed.path == "/v1/whatsapp/ziplin/webhook"
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )
    dns_hostname = bool(hostname and "." in hostname)
    try:
        ipaddress.ip_address(hostname)
        dns_hostname = False
    except ValueError:
        dns_hostname = (
            dns_hostname
            and hostname != "localhost"
            and not hostname.endswith((".localhost", ".local"))
        )
    stable = bool(
        parsed.scheme.casefold() == "https"
        and dns_hostname
        and supported_port
        and not parsed.username
        and not parsed.password
        and not hostname.endswith(".trycloudflare.com")
    )
    return parsed, direct, stable, hostname


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the live Ziplin WhatsApp integration.")
    parser.add_argument("--public-base-url", default="")
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
        code = error.get("code")
        if isinstance(code, int) and not isinstance(code, bool):
            detail += f", code {code}"
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
    callback_url = os.getenv("WHATSAPP_WEBHOOK_CALLBACK_URL") or ""
    public_base = (
        args.public_base_url or os.getenv("NORTHSTAR_PUBLIC_BASE_URL") or ""
    ).rstrip("/")
    graph_base = (
        os.getenv("WHATSAPP_GRAPH_BASE")
        or f"https://graph.facebook.com/{os.getenv('WHATSAPP_GRAPH_API_VERSION') or 'v25.0'}"
    ).rstrip("/")
    template_name = os.getenv("WHATSAPP_START_TEMPLATE_NAME") or "hello_world"
    template_language = os.getenv("WHATSAPP_START_TEMPLATE_LANGUAGE") or "en_US"

    callback, direct_callback, stable_callback, callback_hostname = callback_state(
        callback_url
    )
    if not public_base and stable_callback:
        public_base = f"{callback.scheme}://{callback.netloc}".rstrip("/")

    checks = [
        Check("outbound access token configured", bool(token), "present" if token else "missing"),
        Check("Phone Number ID configured", bool(phone_id), "present" if phone_id else "missing"),
        Check("WABA ID configured", bool(waba_id), "present" if waba_id else "missing"),
        Check("webhook verification token configured", bool(verify_token), "present" if verify_token else "missing"),
        Check("Meta App Secret configured", bool(app_secret), "present" if app_secret else "missing"),
        Check(
            "direct Ziplin callback configured",
            direct_callback,
            "canonical direct path" if direct_callback else "expected /v1/whatsapp/ziplin/webhook",
        ),
        Check(
            "permanent HTTPS callback hostname",
            stable_callback,
            callback_hostname or "missing",
        ),
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

            if app_id:
                subscription_check, body = await call(
                    client,
                    "configured Meta app subscribed to WABA",
                    "GET",
                    f"{graph_base}/{waba_id}/subscribed_apps",
                    headers=auth,
                )
                if subscription_check.ok:
                    subscribed_app_ids = {
                        str((item.get("whatsapp_business_api_data") or {}).get("id") or "")
                        for item in body.get("data") or []
                        if isinstance(item, dict)
                    }
                    subscription_check = Check(
                        subscription_check.name,
                        subscribed_app_ids == {app_id},
                        "only the configured Ziplin app is subscribed"
                        if subscribed_app_ids == {app_id}
                        else "configured app absent or an unexpected app is also subscribed",
                    )
                checks.append(subscription_check)

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
            app_auth = {"Authorization": f"Bearer {app_id}|{app_secret}"}
            subscription_check, body = await call(
                client,
                "Meta app direct webhook subscription",
                "GET",
                f"{graph_base}/{app_id}/subscriptions",
                headers=app_auth,
            )
            if subscription_check.ok:
                subscriptions = [
                    item
                    for item in body.get("data") or []
                    if isinstance(item, dict)
                    and item.get("object") == "whatsapp_business_account"
                ]
                matched_subscription = next(
                    (
                        item
                        for item in subscriptions
                        if str(item.get("callback_url") or "") == callback_url
                    ),
                    None,
                )
                field_names = {
                    str(field.get("name") if isinstance(field, dict) else field)
                    for field in (matched_subscription or {}).get("fields") or []
                }
                matched = matched_subscription is not None and "messages" in field_names
                subscription_check = Check(
                    subscription_check.name,
                    matched,
                    "configured callback and messages field are active"
                    if matched
                    else "callback differs, is absent, or lacks the messages field",
                )
            checks.append(subscription_check)
        else:
            checks.append(Check("Meta app direct webhook subscription", False, "app ID or App Secret missing"))

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
                        "direct NorthStar callback challenge",
                        ok,
                        "challenge echoed" if ok else f"HTTP {response.status_code}; mismatch",
                    )
                )
            except Exception as exc:
                checks.append(Check("direct NorthStar callback challenge", False, type(exc).__name__))

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

        if args.send_template:
            recipient = args.recipient or os.getenv("WHATSAPP_TEST_TO") or ""
            digits = "".join(character for character in recipient if character.isdigit())
            if not digits:
                checks.append(Check("explicit template send", False, "recipient is missing"))
            else:
                try:
                    body = await WhatsAppClient().send_start_message(
                        to=digits,
                        template_name=template_name,
                        language_code=template_language,
                    )
                    accepted = bool(body.get("messages"))
                    send_check = Check(
                        "explicit template send through NorthStar",
                        accepted,
                        "accepted by Meta and handed to conversation persistence"
                        if accepted
                        else "Meta returned no message ID",
                    )
                except Exception as exc:
                    send_check = Check(
                        "explicit template send through NorthStar",
                        False,
                        type(exc).__name__,
                    )
                checks.append(send_check)

    for check in checks:
        show(check)
    failures = [check for check in checks if check.required and not check.ok]
    print(f"Summary: {len(checks) - len(failures)}/{len(checks)} checks passed or safely skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
