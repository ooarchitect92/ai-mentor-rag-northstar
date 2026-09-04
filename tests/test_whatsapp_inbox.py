import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.whatsapp as whatsapp_module
from app.admin_store import AdminStore
from app.config import get_settings
from app.main import app
from app.whatsapp import WhatsAppClient


BUSINESS_PHONE_ID = "ziplin-inbox-phone-id"
STUDENT_PHONE = "919876543210"
APP_SECRET = "ziplin-inbox-app-secret"
ADMIN_HEADERS = {"x-admin-token": "test-admin-token"}


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture(autouse=True)
def isolated_inbox_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("ADMIN_DATABASE_FILE", str(tmp_path / "admin.sqlite3"))
    monkeypatch.setenv("FEEDBACK_MEDIA_DIRECTORY", str(tmp_path / "feedback-media"))
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(tmp_path / "runtime-config.json"))
    monkeypatch.setenv("MENTOR_SYSTEM_PROMPT_FILE", str(tmp_path / "mentor-prompt.txt"))
    monkeypatch.setenv("WHATSAPP_MESSAGING_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_USE_MOCK", "false")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
    monkeypatch.setenv("META_APP_SECRET", "")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("WHATSAPP_TOKEN", "")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", BUSINESS_PHONE_ID)
    monkeypatch.setenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "ziplin-waba")
    monkeypatch.setenv("WHATSAPP_GRAPH_BASE", "https://graph.example.test/v25.0")
    monkeypatch.setenv("WHATSAPP_MESSAGE_RETENTION_DAYS", "90")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS_FILE", "")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS_GOOGLE_SHEET_ID", "")
    get_settings.cache_clear()
    whatsapp_module._load_enrollment_workbook.cache_clear()
    yield
    get_settings.cache_clear()
    whatsapp_module._load_enrollment_workbook.cache_clear()


@pytest.fixture
def inbox_client(monkeypatch):
    scheduled: list[str] = []
    monkeypatch.setattr(main_module, "schedule_whatsapp_webhook", scheduled.append)
    with TestClient(app) as client:
        yield client, scheduled


def inbound_payload(
    *,
    phone_id: str = BUSINESS_PHONE_ID,
    message_id: str = "wamid.inbox-inbound",
    sender: str = STUDENT_PHONE,
    profile_name: str = "Inbox Student",
    text: str = "Explain variance analysis",
    timestamp: str | None = None,
):
    timestamp = timestamp or str(int(datetime.now(UTC).timestamp()))
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ziplin-waba",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {
                                "phone_number_id": phone_id,
                                "display_phone_number": "+91 90000 00000",
                            },
                            "contacts": [
                                {"wa_id": sender, "profile": {"name": profile_name}}
                            ],
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": sender,
                                    "timestamp": timestamp,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def status_payload(
    status: str,
    timestamp: str,
    *,
    message_id: str = "wamid.inbox-outbound",
    phone_id: str = BUSINESS_PHONE_ID,
    recipient: str = STUDENT_PHONE,
):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ziplin-waba",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": phone_id},
                            "statuses": [
                                {
                                    "id": message_id,
                                    "recipient_id": recipient,
                                    "timestamp": timestamp,
                                    "status": status,
                                    "conversation": {"id": "meta-billing-conversation"},
                                    "errors": [{"title": "must not be exposed"}],
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def signed_direct_post(client: TestClient, payload: dict):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(
        APP_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/v1/whatsapp/ziplin/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": signature,
        },
    )


class AcceptedMetaResponse:
    status_code = 200
    is_error = False
    reason_phrase = "OK"
    text = ""

    def __init__(self, message_id: str):
        self.message_id = message_id

    def json(self):
        return {"messaging_product": "whatsapp", "messages": [{"id": self.message_id}]}


def install_accepted_meta_client(monkeypatch, message_id: str):
    class AcceptedMetaClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, *, headers=None, json=None):
            return AcceptedMetaResponse(message_id)

    monkeypatch.setattr(whatsapp_module.httpx, "AsyncClient", AcceptedMetaClient)


def test_inbox_normalizes_duplicate_inbound_once_and_masks_sensitive_identity():
    store = AdminStore()
    payload = inbound_payload()

    first = run(store.enqueue_whatsapp_webhook(payload))
    duplicate = run(store.enqueue_whatsapp_webhook(payload))

    assert duplicate["id"] == first["id"]
    listing = run(store.list_whatsapp_conversations(BUSINESS_PHONE_ID))
    assert listing["total"] == 1
    conversation = listing["items"][0]
    assert conversation["masked_phone"].endswith("3210")
    assert STUDENT_PHONE not in json.dumps(conversation)
    assert set(conversation) == {
        "id",
        "profile_name",
        "masked_phone",
        "display_name",
        "message_count",
        "last_message",
    }
    assert conversation["message_count"] == 1
    assert set(conversation["last_message"]) == {
        "id",
        "direction",
        "message_type",
        "text",
        "has_media",
        "status",
        "created_at",
        "status_at",
    }

    messages = run(
        store.list_whatsapp_messages(conversation["id"], BUSINESS_PHONE_ID)
    )
    assert messages is not None
    assert messages["total"] == 1
    assert messages["items"][0]["direction"] == "inbound"
    assert messages["items"][0]["text"] == "Explain variance analysis"
    serialized = json.dumps(messages)
    for sensitive in (
        STUDENT_PHONE,
        "display_phone_number",
        "business_phone_number_id",
        "meta_message_id",
        "meta-billing-conversation",
        "must not be exposed",
        "payload",
    ):
        assert sensitive not in serialized


@pytest.mark.parametrize(
    "phone_profile",
    (
        STUDENT_PHONE,
        f"+{STUDENT_PHONE}",
        "+91 98765 43210",
        "(91) 98765-43210",
    ),
)
def test_inbox_suppresses_phone_equivalent_profile_names(phone_profile):
    store = AdminStore()
    run(store.enqueue_whatsapp_webhook(inbound_payload(profile_name=phone_profile)))

    conversation = run(store.list_whatsapp_conversations(BUSINESS_PHONE_ID))[
        "items"
    ][0]
    assert conversation["profile_name"] is None
    assert conversation["display_name"] == conversation["masked_phone"]
    assert STUDENT_PHONE not in json.dumps(conversation)

    detail = run(
        store.list_whatsapp_messages(conversation["id"], BUSINESS_PHONE_ID)
    )
    assert detail is not None
    assert detail["conversation"]["profile_name"] is None
    assert detail["conversation"]["display_name"] == conversation["masked_phone"]
    assert STUDENT_PHONE not in json.dumps(detail["conversation"])


@pytest.mark.parametrize("profile_name", ("Inbox Student", "CMA Learner 42"))
def test_inbox_preserves_legitimate_profile_names(profile_name):
    store = AdminStore()
    run(store.enqueue_whatsapp_webhook(inbound_payload(profile_name=profile_name)))

    conversation = run(store.list_whatsapp_conversations(BUSINESS_PHONE_ID))[
        "items"
    ][0]
    assert conversation["profile_name"] == profile_name
    assert conversation["display_name"] == profile_name


def test_status_callbacks_are_normalized_without_regressing_a_terminal_read_status():
    store = AdminStore()
    assert run(
        store.record_whatsapp_outbound_message(
            business_phone_number_id=BUSINESS_PHONE_ID,
            meta_message_id="wamid.inbox-outbound",
            contact_phone=STUDENT_PHONE,
            message_type="text",
            body="A recorded mentor answer",
            status="accepted",
            created_at="1700000000",
        )
    )

    run(store.enqueue_whatsapp_webhook(status_payload("read", "1700000300")))
    run(store.enqueue_whatsapp_webhook(status_payload("delivered", "1700000400")))
    run(store.enqueue_whatsapp_webhook(status_payload("failed", "1700000500")))

    listing = run(store.list_whatsapp_conversations(BUSINESS_PHONE_ID))
    conversation_id = listing["items"][0]["id"]
    timeline = run(store.list_whatsapp_messages(conversation_id, BUSINESS_PHONE_ID))
    assert timeline is not None
    assert timeline["total"] == 1
    message = timeline["items"][0]
    assert message["direction"] == "outbound"
    assert message["status"] == "read"
    assert message["status_at"] == datetime.fromtimestamp(1700000300, UTC).isoformat()


def test_inbox_api_requires_auth_uses_no_store_and_validates_ids_and_limits(inbox_client):
    client, _scheduled = inbox_client
    store = AdminStore()
    run(store.enqueue_whatsapp_webhook(inbound_payload()))
    conversation = run(store.list_whatsapp_conversations(BUSINESS_PHONE_ID))["items"][0]
    detail_path = f"/v1/admin/whatsapp/conversations/{conversation['id']}/messages"

    assert client.get("/v1/admin/whatsapp/conversations").status_code == 401
    assert client.get(detail_path).status_code == 401

    listing = client.get("/v1/admin/whatsapp/conversations", headers=ADMIN_HEADERS)
    assert listing.status_code == 200
    assert listing.headers["cache-control"] == "no-store"
    detail = client.get(detail_path, headers=ADMIN_HEADERS)
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "no-store"

    assert client.get(
        "/v1/admin/whatsapp/conversations/not-a-uuid/messages",
        headers=ADMIN_HEADERS,
    ).status_code == 404
    assert client.get(
        f"/v1/admin/whatsapp/conversations/{uuid4()}/messages",
        headers=ADMIN_HEADERS,
    ).status_code == 404

    for limit in (0, 101):
        assert client.get(
            f"/v1/admin/whatsapp/conversations?limit={limit}",
            headers=ADMIN_HEADERS,
        ).status_code == 422
        assert client.get(
            f"{detail_path}?limit={limit}", headers=ADMIN_HEADERS
        ).status_code == 422
    assert client.get(
        "/v1/admin/whatsapp/conversations?offset=-1", headers=ADMIN_HEADERS
    ).status_code == 422
    assert client.get(
        f"{detail_path}?offset=-1", headers=ADMIN_HEADERS
    ).status_code == 422


def test_signed_direct_ziplin_webhook_rejects_wrong_phone_without_inbox_persistence(
    inbox_client,
):
    client, scheduled = inbox_client

    response = signed_direct_post(
        client,
        inbound_payload(
            phone_id="another-business-phone-id",
            message_id="wamid.wrong-phone-inbox",
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ignored",
        "event_id": None,
        "reason": "different_phone_number",
    }
    assert scheduled == []
    listing = client.get(
        "/v1/admin/whatsapp/conversations", headers=ADMIN_HEADERS
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 0


def test_paused_webhook_keeps_status_receipts_but_discards_mixed_inbound_messages(
    inbox_client, monkeypatch
):
    client, scheduled = inbox_client
    store = AdminStore()
    run(
        store.record_whatsapp_outbound_message(
            business_phone_number_id=BUSINESS_PHONE_ID,
            meta_message_id="wamid.paused-outbound",
            contact_phone=STUDENT_PHONE,
            message_type="text",
            body="A previously accepted reply",
            status="accepted",
        )
    )
    monkeypatch.setenv("WHATSAPP_MESSAGING_ENABLED", "false")
    get_settings.cache_clear()

    payload = inbound_payload(
        message_id="wamid.must-not-survive-pause",
        text="This message must not be queued",
    )
    payload["entry"][0]["changes"][0]["value"]["statuses"] = [
        {
            "id": "wamid.paused-outbound",
            "recipient_id": STUDENT_PHONE,
            "timestamp": str(int(datetime.now(UTC).timestamp())),
            "status": "read",
        }
    ]

    response = signed_direct_post(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "paused"
    assert response.json()["event_id"]
    assert scheduled == [response.json()["event_id"]]
    listing = run(store.list_whatsapp_conversations(BUSINESS_PHONE_ID))
    assert listing["total"] == 1
    timeline = run(
        store.list_whatsapp_messages(listing["items"][0]["id"], BUSINESS_PHONE_ID)
    )
    assert timeline is not None
    assert timeline["total"] == 1
    assert timeline["items"][0]["status"] == "read"
    assert "must not be queued" not in json.dumps(timeline)


def test_signed_direct_inbox_preserves_untrusted_content_as_json_text(inbox_client):
    client, scheduled = inbox_client
    profile = '<img src=x onerror="globalThis.pwned=true">'
    message = '</script><svg onload="globalThis.pwned=true">literal student text</svg>'

    accepted = signed_direct_post(
        client,
        inbound_payload(
            message_id="wamid.xss-inbox",
            profile_name=profile,
            text=message,
        ),
    )

    assert accepted.status_code == 200
    assert scheduled == [accepted.json()["event_id"]]
    listing = client.get(
        "/v1/admin/whatsapp/conversations", headers=ADMIN_HEADERS
    )
    assert listing.headers["content-type"].startswith("application/json")
    conversation = listing.json()["items"][0]
    assert conversation["profile_name"] == profile
    assert conversation["display_name"] == profile
    detail = client.get(
        f"/v1/admin/whatsapp/conversations/{conversation['id']}/messages",
        headers=ADMIN_HEADERS,
    )
    assert detail.headers["content-type"].startswith("application/json")
    assert detail.json()["items"][0]["text"] == message


def test_real_whatsapp_client_centrally_records_meta_accepted_outbound(monkeypatch):
    install_accepted_meta_client(monkeypatch, "wamid.persisted-outbound")

    result = run(WhatsAppClient().send_text(STUDENT_PHONE, "Recorded mentor answer"))

    assert result["messages"][0]["id"] == "wamid.persisted-outbound"
    listing = run(AdminStore().list_whatsapp_conversations(BUSINESS_PHONE_ID))
    assert listing["total"] == 1
    conversation = listing["items"][0]
    timeline = run(
        AdminStore().list_whatsapp_messages(conversation["id"], BUSINESS_PHONE_ID)
    )
    assert timeline is not None
    assert len(timeline["items"]) == 1
    message = timeline["items"][0]
    assert message["direction"] == "outbound"
    assert message["message_type"] == "text"
    assert message["text"] == "Recorded mentor answer"
    assert message["has_media"] is False
    assert message["status"] == "accepted"


def test_mock_whatsapp_send_does_not_create_a_genuine_conversation(monkeypatch):
    monkeypatch.setenv("WHATSAPP_USE_MOCK", "true")
    get_settings.cache_clear()

    result = run(WhatsAppClient().send_text(STUDENT_PHONE, "Mock-only answer"))

    assert result["mock"] is True
    assert run(AdminStore().list_whatsapp_conversations(BUSINESS_PHONE_ID))["total"] == 0


def test_outbound_persistence_failure_does_not_turn_meta_acceptance_into_failure(
    monkeypatch, caplog
):
    install_accepted_meta_client(monkeypatch, "wamid.accepted-despite-storage-failure")

    async def fail_persistence(self, **values):
        raise OSError("inbox database unavailable")

    monkeypatch.setattr(
        AdminStore, "record_whatsapp_outbound_message", fail_persistence
    )

    result = run(WhatsAppClient().send_text(STUDENT_PHONE, "Still accepted by Meta"))

    assert result["messages"] == [
        {"id": "wamid.accepted-despite-storage-failure"}
    ]
    assert "conversation record could not be persisted" in caplog.text
