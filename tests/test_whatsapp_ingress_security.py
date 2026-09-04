import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main_module
import app.whatsapp as whatsapp_module
from app.admin_store import AdminStore
from app.config import get_settings
from app.main import app
from scripts.whatsapp.whatsapp_diagnostics import callback_state


PHONE_NUMBER_ID = "security-phone-number-id"
WABA_ID = "security-whatsapp-business-account-id"
APP_SECRET = "security-app-secret"
VERIFY_TOKEN = "security-verify-token"
RELAY_TOKEN = "security-relay-token-that-is-longer-than-32-characters"
CONTACT_PHONE = "919876543210"


@pytest.fixture(autouse=True)
def isolated_ingress_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("ADMIN_DATABASE_FILE", str(tmp_path / "admin.sqlite3"))
    monkeypatch.setenv("FEEDBACK_MEDIA_DIRECTORY", str(tmp_path / "feedback-media"))
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(tmp_path / "runtime-config.json"))
    monkeypatch.setenv("MENTOR_SYSTEM_PROMPT_FILE", str(tmp_path / "mentor-prompt.txt"))
    monkeypatch.setenv("WHATSAPP_MESSAGING_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_USE_MOCK", "false")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
    monkeypatch.setenv("META_APP_SECRET", "")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "security-test-access-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    monkeypatch.setenv("WHATSAPP_BUSINESS_ACCOUNT_ID", WABA_ID)
    monkeypatch.setenv("WHATSAPP_RELAY_TOKEN", RELAY_TOKEN)
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS_FILE", "")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS_GOOGLE_SHEET_ID", "")
    get_settings.cache_clear()
    whatsapp_module._load_enrollment_workbook.cache_clear()
    yield
    get_settings.cache_clear()
    whatsapp_module._load_enrollment_workbook.cache_clear()


@pytest.fixture
def ingress_client():
    with TestClient(app) as client:
        yield client


def message_change(
    *,
    phone_number_id: str | None = PHONE_NUMBER_ID,
    message_id: str = "wamid.security-inbound",
) -> dict:
    value = {
        "contacts": [{"wa_id": CONTACT_PHONE, "profile": {"name": "Security Student"}}],
        "messages": [
            {
                "id": message_id,
                "from": CONTACT_PHONE,
                "timestamp": "1700000000",
                "type": "text",
                "text": {"body": "Explain standard costing"},
            }
        ],
    }
    if phone_number_id is not None:
        value["metadata"] = {"phone_number_id": phone_number_id}
    return {"field": "messages", "value": value}


def status_change(
    *,
    phone_number_id: str | None = PHONE_NUMBER_ID,
    message_id: str = "wamid.security-outbound",
) -> dict:
    value = {
        "statuses": [
            {
                "id": message_id,
                "recipient_id": CONTACT_PHONE,
                "timestamp": "1700000300",
                "status": "read",
            }
        ]
    }
    if phone_number_id is not None:
        value["metadata"] = {"phone_number_id": phone_number_id}
    return {"field": "messages", "value": value}


def webhook_payload(*changes: dict, entry_id: str = WABA_ID) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": entry_id, "changes": list(changes) or [message_change()]}],
    }


def signature_for(body: bytes) -> str:
    return "sha256=" + hmac.new(
        APP_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()


def signed_post(client: TestClient, payload: dict):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return client.post(
        "/v1/whatsapp/ziplin/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": signature_for(body),
        },
    )


def webhook_event_count() -> int:
    with AdminStore()._connect() as connection:
        return int(
            connection.execute("SELECT COUNT(*) FROM whatsapp_webhook_events").fetchone()[0]
        )


@pytest.mark.parametrize("signature", (None, "sha256=" + "0" * 64))
def test_direct_webhook_rejects_missing_or_invalid_hmac_without_queueing(
    ingress_client, signature
):
    body = json.dumps(webhook_payload(message_change())).encode("utf-8")
    headers = {"content-type": "application/json"}
    if signature:
        headers["x-hub-signature-256"] = signature

    response = ingress_client.post(
        "/v1/whatsapp/ziplin/webhook", content=body, headers=headers
    )

    assert response.status_code == 401
    assert webhook_event_count() == 0


@pytest.mark.parametrize(
    ("configured", "supplied"),
    (("", ""), ("", VERIFY_TOKEN), (VERIFY_TOKEN, ""), ("   ", "   ")),
)
def test_webhook_verification_fails_closed_for_empty_tokens(
    ingress_client, monkeypatch, configured, supplied
):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", configured)
    get_settings.cache_clear()

    response = ingress_client.get(
        "/v1/whatsapp/ziplin/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": supplied,
            "hub.challenge": "must-not-be-returned",
        },
    )

    assert response.status_code == 403
    assert response.text != "must-not-be-returned"
    assert webhook_event_count() == 0


@pytest.mark.parametrize(
    ("path", "headers"),
    (
        (
            "/v1/whatsapp/ziplin/webhook",
            {"x-hub-signature-256": "sha256=" + "0" * 64},
        ),
        (
            "/v1/whatsapp/webhook",
            {"x-hub-signature-256": "sha256=" + "0" * 64},
        ),
        (
            "/v1/whatsapp/relay",
            {"x-northstar-relay-token": RELAY_TOKEN},
        ),
        (
            "/v1/whatsapp/ziplin/relay",
            {"x-ziplin-relay-token": RELAY_TOKEN},
        ),
    ),
)
def test_every_webhook_ingress_rejects_declared_body_over_two_mib(
    ingress_client, path, headers
):
    oversized = b"x" * (main_module._WHATSAPP_WEBHOOK_MAX_BODY_BYTES + 1)

    response = ingress_client.post(path, content=oversized, headers=headers)

    assert response.status_code == 413
    assert webhook_event_count() == 0


def test_bounded_reader_stops_consuming_chunked_body_at_limit():
    half = main_module._WHATSAPP_WEBHOOK_MAX_BODY_BYTES // 2
    chunks = [b"a" * half, b"b" * half, b"c", b"must-not-be-read"]
    receive_calls = 0

    async def receive():
        nonlocal receive_calls
        chunk = chunks[receive_calls]
        receive_calls += 1
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": receive_calls < len(chunks),
        }

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/whatsapp/ziplin/webhook",
            "headers": [],
        },
        receive,
    )

    with pytest.raises(HTTPException) as captured:
        asyncio.run(main_module._read_bounded_whatsapp_body(request))

    assert captured.value.status_code == 413
    assert receive_calls == 3


@pytest.mark.parametrize(
    ("path", "headers"),
    (
        (
            "/v1/whatsapp/ziplin/webhook",
            {"x-hub-signature-256": "sha256=" + "0" * 64},
        ),
        (
            "/v1/whatsapp/ziplin/relay",
            {"x-ziplin-relay-token": RELAY_TOKEN},
        ),
    ),
)
def test_direct_and_relay_routes_stop_chunked_streams_above_limit(path, headers):
    half = main_module._WHATSAPP_WEBHOOK_MAX_BODY_BYTES // 2
    chunks_sent: list[int] = []

    async def send_chunked():
        async def content():
            for index, chunk in enumerate(
                (b"a" * half, b"b" * half, b"c", b"must-not-be-read"),
                start=1,
            ):
                chunks_sent.append(index)
                yield chunk

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                path,
                content=content(),
                headers={**headers, "content-length": "1"},
            )

    response = asyncio.run(send_chunked())

    assert response.status_code == 413
    assert chunks_sent == [1, 2, 3]
    assert webhook_event_count() == 0


@pytest.mark.parametrize(
    "body",
    (b'{"entry":', b"\xff", b"[]", b'"not an object"', b"null"),
)
def test_signed_malformed_or_nonobject_json_never_reaches_queue(ingress_client, body):
    response = ingress_client.post(
        "/v1/whatsapp/ziplin/webhook",
        content=body,
        headers={"x-hub-signature-256": signature_for(body)},
    )

    assert response.status_code == 400
    assert webhook_event_count() == 0


@pytest.mark.parametrize(
    ("payload", "reason"),
    (
        ({"object": "not_whatsapp", "entry": []}, "invalid_webhook_routing"),
        (
            webhook_payload({"field": "not_messages", "value": {}}),
            "invalid_webhook_routing",
        ),
        (webhook_payload(message_change(phone_number_id=None)), "different_phone_number"),
        (webhook_payload(status_change(phone_number_id=None)), "different_phone_number"),
        (
            webhook_payload(message_change(phone_number_id="another-phone-number-id")),
            "different_phone_number",
        ),
        (
            webhook_payload(status_change(phone_number_id="another-phone-number-id")),
            "different_phone_number",
        ),
        (
            webhook_payload(
                message_change(message_id="wamid.correct-part"),
                message_change(
                    phone_number_id="another-phone-number-id",
                    message_id="wamid.foreign-part",
                ),
            ),
            "different_phone_number",
        ),
    ),
)
def test_invalid_missing_wrong_and_mixed_routing_is_rejected_as_one_batch(
    ingress_client, payload, reason
):
    response = signed_post(ingress_client, payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ignored",
        "event_id": None,
        "reason": reason,
    }
    assert webhook_event_count() == 0
    assert asyncio.run(
        AdminStore().list_whatsapp_conversations(PHONE_NUMBER_ID)
    )["total"] == 0


def test_wrong_waba_status_cannot_mutate_or_persist_foreign_receipt(ingress_client):
    store = AdminStore()
    assert asyncio.run(
        store.record_whatsapp_outbound_message(
            business_phone_number_id=PHONE_NUMBER_ID,
            meta_message_id="wamid.security-outbound",
            contact_phone=CONTACT_PHONE,
            message_type="text",
            body="Accepted mentor answer",
            status="accepted",
        )
    )

    response = signed_post(
        ingress_client,
        webhook_payload(status_change(), entry_id="another-business-account-id"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ignored",
        "event_id": None,
        "reason": "different_business_account",
    }
    assert webhook_event_count() == 0
    listing = asyncio.run(store.list_whatsapp_conversations(PHONE_NUMBER_ID))
    timeline = asyncio.run(
        store.list_whatsapp_messages(listing["items"][0]["id"], PHONE_NUMBER_ID)
    )
    assert timeline is not None
    assert timeline["items"][0]["status"] == "accepted"


@pytest.mark.parametrize(
    ("callback_url", "expected"),
    (
        (
            "https://mentor.example.test./v1/whatsapp/ziplin/webhook",
            (True, True),
        ),
        ("https://8.8.8.8/v1/whatsapp/ziplin/webhook", (True, False)),
        ("https://[2001:4860:4860::8888]/v1/whatsapp/ziplin/webhook", (True, False)),
        ("https://[invalid-host/v1/whatsapp/ziplin/webhook", (False, False)),
        ("https://mentor.example.test/v1/whatsapp/webhook", (False, True)),
    ),
)
def test_direct_callback_requires_canonical_path_and_dns_hostname(
    callback_url, expected
):
    assert main_module._direct_whatsapp_callback_state(callback_url) == expected


@pytest.mark.parametrize(
    "callback_url",
    (
        "https://mentor.example.test/v1/whatsapp/ziplin/webhook",
        "https://mentor.example.test/v1/whatsapp/ziplin/webhook?source=legacy",
        "https://mentor.example.test/V1/WhatsApp/Ziplin/Webhook",
        "https://mentor.example.test/v1/whatsapp/ziplin/webhook/",
        "https://mentor.example.test/v1/whatsapp/webhook",
        "https://localhost/v1/whatsapp/ziplin/webhook",
        "https://mentor.local/v1/whatsapp/ziplin/webhook",
        "https://8.8.8.8/v1/whatsapp/ziplin/webhook",
        "https://mentor.example.test:8443/v1/whatsapp/ziplin/webhook",
        "https://user:secret@mentor.example.test/v1/whatsapp/ziplin/webhook",
        "https://temporary.trycloudflare.com./v1/whatsapp/ziplin/webhook",
        "https://[invalid-host/v1/whatsapp/ziplin/webhook",
    ),
)
def test_runtime_and_diagnostics_share_callback_rules(callback_url):
    _parsed, direct, stable, _hostname = callback_state(callback_url)

    assert (direct, stable) == main_module._direct_whatsapp_callback_state(
        callback_url
    )
