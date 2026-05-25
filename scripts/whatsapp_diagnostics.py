import hashlib
import hmac
import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def proof(token: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


async def get_json(client: httpx.AsyncClient, name: str, url: str, token: str) -> CheckResult:
    try:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if response.status_code >= 400:
            return CheckResult(name, False, response.text)
        return CheckResult(name, True, response.text)
    except Exception as exc:
        return CheckResult(name, False, str(exc))


async def post_json(client: httpx.AsyncClient, name: str, url: str, token: str, payload: dict) -> CheckResult:
    try:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        if response.status_code >= 400:
            return CheckResult(name, False, response.text)
        return CheckResult(name, True, response.text)
    except Exception as exc:
        return CheckResult(name, False, str(exc))


def summarize_debug_token(raw_json: str) -> str:
    import json

    data = json.loads(raw_json).get("data", {})
    scopes = ",".join(data.get("scopes", []))
    granular = []
    for item in data.get("granular_scopes", []):
        granular.append(f"{item.get('scope')} -> {','.join(item.get('target_ids', []))}")
    return (
        f"valid={data.get('is_valid')} app_id={data.get('app_id')} type={data.get('type')} "
        f"expires_at={data.get('expires_at')} scopes={scopes} granular={'; '.join(granular)}"
    )


async def main() -> None:
    load_dotenv()
    token = os.getenv("WHATSAPP_TOKEN") or os.getenv("WHATSAPP_ACCESS_TOKEN") or ""
    app_id = os.getenv("META_APP_ID") or os.getenv("FACEBOOK_APP_ID") or ""
    app_secret = os.getenv("META_APP_SECRET") or os.getenv("WHATSAPP_APP_SECRET") or ""
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or ""
    waba_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or ""
    graph_base = (os.getenv("WHATSAPP_GRAPH_BASE") or "https://graph.facebook.com/v25.0").rstrip("/")
    test_to = os.getenv("WHATSAPP_TEST_TO") or "919739868498"

    missing = [
        name
        for name, value in {
            "WHATSAPP_TOKEN": token,
            "META_APP_ID": app_id,
            "META_APP_SECRET": app_secret,
            "WHATSAPP_PHONE_NUMBER_ID": phone_id,
            "WHATSAPP_BUSINESS_ACCOUNT_ID": waba_id,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing required env values: {', '.join(missing)}")

    app_access_token = f"{app_id}|{app_secret}"
    appsecret_proof = proof(token, app_secret)

    checks = [
        (
            "debug_token",
            f"{graph_base}/debug_token?input_token={token}&access_token={app_access_token}",
        ),
        ("me", f"{graph_base}/me?fields=id,name&appsecret_proof={appsecret_proof}"),
        (
            "phone_object",
            f"{graph_base}/{phone_id}?fields=id,display_phone_number,verified_name,quality_rating&appsecret_proof={appsecret_proof}",
        ),
        (
            "waba_phone_numbers",
            f"{graph_base}/{waba_id}/phone_numbers?fields=id,display_phone_number,verified_name,quality_rating&appsecret_proof={appsecret_proof}",
        ),
        ("waba_subscribed_apps", f"{graph_base}/{waba_id}/subscribed_apps?appsecret_proof={appsecret_proof}"),
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        for name, url in checks:
            result = await get_json(client, name, url, token)
            detail = summarize_debug_token(result.detail) if result.ok and name == "debug_token" else result.detail
            print(f"[{'OK' if result.ok else 'FAIL'}] {result.name}: {detail}")

        send_payload = {
            "messaging_product": "whatsapp",
            "to": test_to,
            "type": "template",
            "template": {"name": "hello_world", "language": {"code": "en_US"}},
        }
        send_result = await post_json(client, "send_hello_world_template", f"{graph_base}/{phone_id}/messages", token, send_payload)
        print(f"[{'OK' if send_result.ok else 'FAIL'}] {send_result.name}: {send_result.detail}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
