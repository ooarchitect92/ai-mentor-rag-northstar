import asyncio
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.webhook_queue as webhook_queue_module
import app.whatsapp as whatsapp_module
from app.admin_store import AdminStore
from app.config import get_settings
from app.main import app
from app.schemas import ChatResponse
from app.whatsapp import WhatsAppClient


ZIPLIN_PHONE_ID = "ziplin-phone-id"
ZIPLIN_RELAY_TOKEN = "ziplin-relay-token-that-is-at-least-32-characters"
ZIPLIN_APP_SECRET = "ziplin-test-app-secret"
STUDENT_NUMBER = "919535210826"
UNKNOWN_STUDENT_NUMBER = "919999990123"


@pytest.fixture
def ziplin_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("ADMIN_DATABASE_FILE", str(tmp_path / "admin.sqlite3"))
    monkeypatch.setenv("FEEDBACK_MEDIA_DIRECTORY", str(tmp_path / "feedback-media"))
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(tmp_path / "runtime-config.json"))
    monkeypatch.setenv("WHATSAPP_MESSAGING_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_USE_MOCK", "false")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "ziplin-verify-token")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", ZIPLIN_APP_SECRET)
    monkeypatch.setenv("META_APP_SECRET", "")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "ziplin-access-token")
    monkeypatch.setenv("WHATSAPP_TOKEN", "")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", ZIPLIN_PHONE_ID)
    monkeypatch.setenv("WHATSAPP_GRAPH_BASE", "https://graph.example.test/v25.0")
    monkeypatch.setenv("WHATSAPP_RELAY_TOKEN", ZIPLIN_RELAY_TOKEN)
    monkeypatch.setenv("WHATSAPP_OPEN_CMA_ACCESS", "false")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS", f"{STUDENT_NUMBER}:CMA")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS_FILE", "")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS_GOOGLE_SHEET_ID", "")
    get_settings.cache_clear()
    whatsapp_module._load_enrollment_workbook.cache_clear()

    client = TestClient(app)
    yield client

    client.close()
    get_settings.cache_clear()
    whatsapp_module._load_enrollment_workbook.cache_clear()


def incoming_payload(phone_ids, *, text="Explain variance analysis"):
    changes = []
    for index, phone_id in enumerate(phone_ids):
        value = {
            "contacts": [{"wa_id": STUDENT_NUMBER, "profile": {"name": "Ziplin Student"}}],
            "messages": [
                {
                    "id": f"wamid.ziplin-inbound-{index}",
                    "from": STUDENT_NUMBER,
                    "timestamp": "1700000000",
                    "type": "text",
                    "text": {"body": text},
                }
            ],
        }
        if phone_id is not None:
            value["metadata"] = {"phone_number_id": phone_id}
        changes.append({"field": "messages", "value": value})
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "ziplin-waba", "changes": changes}],
    }


def test_ziplin_direct_webhook_verifies_and_accepts_a_signed_post(ziplin_client, monkeypatch):
    verification = ziplin_client.get(
        "/v1/whatsapp/ziplin/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "ziplin-verify-token",
            "hub.challenge": "24680",
        },
    )
    assert verification.status_code == 200
    assert verification.text == "24680"
    assert verification.headers["content-type"].startswith("text/plain")

    scheduled = []
    monkeypatch.setattr(main_module, "schedule_whatsapp_webhook", scheduled.append)
    payload = incoming_payload([ZIPLIN_PHONE_ID])
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(
        ZIPLIN_APP_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    accepted = ziplin_client.post(
        "/v1/whatsapp/ziplin/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": signature,
        },
    )

    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    event_id = accepted.json()["event_id"]
    assert scheduled == [event_id]
    with AdminStore()._connect() as connection:
        row = connection.execute(
            "SELECT status, payload FROM whatsapp_webhook_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    assert row["status"] == "pending"
    assert "wamid.ziplin-inbound-0" in row["payload"]


def test_ziplin_relay_rejects_missing_wrong_and_unconfigured_tokens(
    ziplin_client,
    monkeypatch,
):
    payload = incoming_payload([ZIPLIN_PHONE_ID])

    missing = ziplin_client.post("/v1/whatsapp/ziplin/relay", json=payload)
    wrong = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=payload,
        headers={"x-ziplin-relay-token": "wrong-token"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["detail"] == "Invalid Ziplin relay token"
    assert wrong.json()["detail"] == "Invalid Ziplin relay token"

    monkeypatch.setenv("WHATSAPP_RELAY_TOKEN", "")
    get_settings.cache_clear()
    unconfigured = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=payload,
        headers={"x-ziplin-relay-token": ZIPLIN_RELAY_TOKEN},
    )

    assert unconfigured.status_code == 503
    assert unconfigured.json()["detail"] == "Ziplin WhatsApp webhook relay is not configured"
    assert asyncio.run(AdminStore().whatsapp_queue_summary())["counts"]["pending"] == 0


@pytest.mark.parametrize(
    ("phone_ids", "case"),
    [
        (["another-phone-id"], "wrong"),
        ([None], "missing"),
        ([ZIPLIN_PHONE_ID, "another-phone-id"], "mixed"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_ziplin_relay_ignores_wrong_missing_and_mixed_phone_ids(
    ziplin_client,
    monkeypatch,
    phone_ids,
    case,
):
    scheduled = []
    monkeypatch.setattr(main_module, "schedule_whatsapp_webhook", scheduled.append)

    response = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=incoming_payload(phone_ids),
        headers={"x-ziplin-relay-token": ZIPLIN_RELAY_TOKEN},
    )

    assert response.status_code == 200, case
    assert response.json() == {
        "status": "ignored",
        "event_id": None,
        "reason": "different_phone_number",
    }
    assert scheduled == []
    assert asyncio.run(AdminStore().whatsapp_queue_summary())["counts"]["pending"] == 0


class StubResponse:
    def __init__(self, status_code, payload=None, *, text="", reason_phrase=""):
        self.status_code = status_code
        self.is_error = status_code >= 400
        self._payload = payload
        self.text = text
        self.reason_phrase = reason_phrase

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def install_recording_http_client(monkeypatch, response):
    calls = []

    class RecordingAsyncClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, *, headers, json):
            calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": self.timeout,
                }
            )
            return response

    monkeypatch.setattr(whatsapp_module.httpx, "AsyncClient", RecordingAsyncClient)
    return calls


def test_outbound_client_posts_to_ziplin_phone_id_with_bearer_auth(
    ziplin_client,
    monkeypatch,
):
    response_payload = {"messaging_product": "whatsapp", "messages": [{"id": "wamid.outbound"}]}
    calls = install_recording_http_client(
        monkeypatch,
        StubResponse(200, response_payload),
    )

    result = asyncio.run(
        WhatsAppClient().send_text("+91 95352 10826", "Ziplin outbound test")
    )

    assert result == response_payload
    assert calls == [
        {
            "url": f"https://graph.example.test/v25.0/{ZIPLIN_PHONE_ID}/messages",
            "headers": {
                "Authorization": "Bearer ziplin-access-token",
                "Content-Type": "application/json",
            },
            "json": {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": STUDENT_NUMBER,
                "type": "text",
                "text": {"preview_url": False, "body": "Ziplin outbound test"},
            },
            "timeout": get_settings().request_timeout_seconds,
        }
    ]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            StubResponse(
                400,
                {
                    "error": {
                        "code": 131030,
                        "type": "OAuthException",
                        "message": "Recipient phone number not in allowed list",
                    }
                },
                reason_phrase="Bad Request",
            ),
            "HTTP 400, code 131030.*Recipient phone number not in allowed list",
        ),
        (
            StubResponse(
                503,
                ValueError("not json"),
                text="upstream unavailable",
                reason_phrase="Service Unavailable",
            ),
            "HTTP 503, code None.*Service Unavailable",
        ),
    ],
    ids=["meta-json-error", "non-json-error"],
)
def test_outbound_client_surfaces_meta_errors(
    ziplin_client,
    monkeypatch,
    response,
    expected,
):
    calls = install_recording_http_client(monkeypatch, response)

    with pytest.raises(RuntimeError, match=expected):
        asyncio.run(WhatsAppClient().send_text(STUDENT_NUMBER, "This will fail"))

    assert len(calls) == 1
    assert calls[0]["url"].endswith(f"/{ZIPLIN_PHONE_ID}/messages")


class InMemoryCache:
    instances = []

    def __init__(self):
        self.values = {}
        self.closed = False
        self.__class__.instances.append(self)

    async def set_if_absent(self, key, ttl_seconds):
        if key in self.values:
            return False
        self.values[key] = "processing"
        return True

    async def get_text(self, key):
        return self.values.get(key)

    async def set_text(self, key, value, ttl_seconds):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)

    async def aclose(self):
        self.closed = True


class StubMentor:
    async def answer(self, request):
        assert request.student_id == f"whatsapp:{STUDENT_NUMBER}"
        assert request.course == "CMA"
        assert request.message == "Explain variance analysis"
        return ChatResponse(answer="Ziplin integration answer.", sources=[])

    async def aclose(self):
        return None

    @staticmethod
    def refusal():
        return "refusal"

    @staticmethod
    def image_refusal(course):
        return f"image refusal {course}"

    @staticmethod
    def course_refusal(course):
        return f"course refusal {course}"


class StubImageMentor:
    requests = []

    async def answer(self, request):
        raise AssertionError("An image question must use the image answer path")

    async def answer_image(self, request):
        self.__class__.requests.append(request)
        return ChatResponse(answer="Ziplin image answer.", sources=[])

    async def aclose(self):
        return None

    @staticmethod
    def refusal():
        return "refusal"

    @staticmethod
    def image_refusal(course):
        return f"image refusal {course}"

    @staticmethod
    def course_refusal(course):
        return f"course refusal {course}"


class StubImageVision:
    def __init__(self):
        self.calls = []

    async def extract_question_from_image(self, **kwargs):
        self.calls.append(kwargs)
        return "Explain the material variance shown in this image"


def image_payload(phone_id):
    value = {
        "contacts": [
            {
                "wa_id": UNKNOWN_STUDENT_NUMBER,
                "profile": {"name": "Unknown Image Student"},
            }
        ],
        "messages": [
            {
                "id": "wamid.ziplin-open-cma-image",
                "from": UNKNOWN_STUDENT_NUMBER,
                "timestamp": "1700000001",
                "type": "image",
                "image": {
                    "id": "ziplin-media-123",
                    "mime_type": "image/png",
                    "caption": "Please teach me how to solve this",
                },
            }
        ],
    }
    if phone_id is not None:
        value["metadata"] = {"phone_number_id": phone_id}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ziplin-waba",
                "changes": [{"field": "messages", "value": value}],
            }
        ],
    }


def install_image_http_client(monkeypatch):
    calls = []

    class ImageHTTPResponse:
        def __init__(self, *, payload=None, content=b""):
            self.status_code = 200
            self.is_error = False
            self._payload = payload
            self.content = content
            self.text = ""
            self.reason_phrase = "OK"

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class RecordingImageAsyncClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, *, headers):
            calls.append({"method": "GET", "url": url, "headers": headers})
            if url == "https://graph.example.test/v25.0/ziplin-media-123":
                return ImageHTTPResponse(
                    payload={
                        "url": "https://media.example.test/ziplin-media-123.png",
                        "mime_type": "image/png",
                        "file_size": 17,
                    }
                )
            if url == "https://media.example.test/ziplin-media-123.png":
                return ImageHTTPResponse(content=b"ziplin-image-bytes")
            raise AssertionError(f"Unexpected image GET: {url}")

        async def post(self, url, *, headers, json):
            calls.append(
                {
                    "method": "POST",
                    "url": url,
                    "headers": headers,
                    "json": json,
                }
            )
            return ImageHTTPResponse(
                payload={"messages": [{"id": "wamid.ziplin-image-outbound"}]}
            )

    monkeypatch.setattr(whatsapp_module.httpx, "AsyncClient", RecordingImageAsyncClient)
    return calls


def test_ziplin_relay_runs_queue_worker_bot_and_outbound_http(
    ziplin_client,
    monkeypatch,
):
    scheduled = []
    monkeypatch.setattr(main_module, "schedule_whatsapp_webhook", scheduled.append)
    InMemoryCache.instances.clear()
    monkeypatch.setattr(whatsapp_module, "Cache", InMemoryCache)
    monkeypatch.setattr(whatsapp_module, "MentorService", StubMentor)
    outbound_calls = install_recording_http_client(
        monkeypatch,
        StubResponse(200, {"messages": [{"id": "wamid.ziplin-outbound"}]}),
    )

    response = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=incoming_payload([ZIPLIN_PHONE_ID]),
        headers={"x-ziplin-relay-token": ZIPLIN_RELAY_TOKEN},
    )
    assert response.status_code == 200
    event_id = response.json()["event_id"]
    assert scheduled == [event_id]

    asyncio.run(webhook_queue_module.run_whatsapp_webhook_event(event_id))

    with AdminStore()._connect() as connection:
        event = connection.execute(
            "SELECT status, attempts, last_error FROM whatsapp_webhook_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    assert dict(event) == {"status": "completed", "attempts": 1, "last_error": None}
    assert len(outbound_calls) == 1
    assert outbound_calls[0]["url"] == (
        f"https://graph.example.test/v25.0/{ZIPLIN_PHONE_ID}/messages"
    )
    assert outbound_calls[0]["json"]["to"] == STUDENT_NUMBER
    assert outbound_calls[0]["json"]["type"] == "text"
    assert "Ziplin integration answer." in outbound_calls[0]["json"]["text"]["body"]
    assert InMemoryCache.instances[0].closed is True


def test_ziplin_unknown_number_gets_cma_teach_menu_and_answer(
    ziplin_client,
    monkeypatch,
):
    monkeypatch.setenv("WHATSAPP_OPEN_CMA_ACCESS", "true")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS", "")
    get_settings.cache_clear()
    scheduled = []
    monkeypatch.setattr(main_module, "schedule_whatsapp_webhook", scheduled.append)
    InMemoryCache.instances.clear()
    monkeypatch.setattr(whatsapp_module, "Cache", InMemoryCache)
    monkeypatch.setattr(whatsapp_module, "MentorService", StubMentor)
    outbound_calls = install_recording_http_client(
        monkeypatch,
        StubResponse(200, {"messages": [{"id": "wamid.ziplin-open-cma-outbound"}]}),
    )
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ziplin-waba",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": ZIPLIN_PHONE_ID},
                            "contacts": [
                                {
                                    "wa_id": STUDENT_NUMBER,
                                    "profile": {"name": "Unknown Ziplin Student"},
                                }
                            ],
                            "messages": [
                                {
                                    "id": "wamid.ziplin-open-cma-hi",
                                    "from": STUDENT_NUMBER,
                                    "type": "text",
                                    "text": {"body": "Hi"},
                                },
                                {
                                    "id": "wamid.ziplin-open-cma-teach",
                                    "from": STUDENT_NUMBER,
                                    "type": "text",
                                    "text": {"body": "mode:teach"},
                                },
                                {
                                    "id": "wamid.ziplin-open-cma-question",
                                    "from": STUDENT_NUMBER,
                                    "type": "text",
                                    "text": {"body": "Explain variance analysis"},
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }

    response = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=payload,
        headers={"x-ziplin-relay-token": ZIPLIN_RELAY_TOKEN},
    )
    assert response.status_code == 200
    event_id = response.json()["event_id"]
    assert scheduled == [event_id]

    asyncio.run(webhook_queue_module.run_whatsapp_webhook_event(event_id))

    with AdminStore()._connect() as connection:
        event = connection.execute(
            "SELECT status, attempts, last_error FROM whatsapp_webhook_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    assert dict(event) == {"status": "completed", "attempts": 1, "last_error": None}
    assert [call["json"]["type"] for call in outbound_calls] == [
        "text",
        "interactive",
        "text",
        "text",
    ]
    mode_menu_payload = outbound_calls[1]["json"]["interactive"]
    assert mode_menu_payload["header"]["text"] == "CMA"
    assert any(
        row["id"] == "mode:teach" and row["title"] == "Teach"
        for row in mode_menu_payload["action"]["sections"][0]["rows"]
    )
    assert "Ziplin integration answer." in outbound_calls[-1]["json"]["text"]["body"]
    assert all(call["json"]["to"] == STUDENT_NUMBER for call in outbound_calls)
    assert InMemoryCache.instances[0].closed is True


def test_ziplin_unknown_number_image_uses_cma_teach_and_preserves_phone_id_isolation(
    ziplin_client,
    monkeypatch,
):
    monkeypatch.setenv("WHATSAPP_OPEN_CMA_ACCESS", "true")
    monkeypatch.setenv("WHATSAPP_ENROLLMENTS", "")
    get_settings.cache_clear()

    scheduled = []
    monkeypatch.setattr(main_module, "schedule_whatsapp_webhook", scheduled.append)
    InMemoryCache.instances.clear()
    StubImageMentor.requests.clear()
    vision = StubImageVision()
    monkeypatch.setattr(whatsapp_module, "Cache", InMemoryCache)
    monkeypatch.setattr(whatsapp_module, "GeminiService", lambda: vision)
    monkeypatch.setattr(whatsapp_module, "MentorService", StubImageMentor)
    http_calls = install_image_http_client(monkeypatch)

    wrong_number_response = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=image_payload("another-phone-id"),
        headers={"x-ziplin-relay-token": ZIPLIN_RELAY_TOKEN},
    )

    assert wrong_number_response.status_code == 200
    assert wrong_number_response.json() == {
        "status": "ignored",
        "event_id": None,
        "reason": "different_phone_number",
    }
    assert scheduled == []
    assert http_calls == []
    assert vision.calls == []
    assert StubImageMentor.requests == []
    assert asyncio.run(AdminStore().whatsapp_queue_summary())["counts"]["pending"] == 0

    accepted_response = ziplin_client.post(
        "/v1/whatsapp/ziplin/relay",
        json=image_payload(ZIPLIN_PHONE_ID),
        headers={"x-ziplin-relay-token": ZIPLIN_RELAY_TOKEN},
    )

    assert accepted_response.status_code == 200
    event_id = accepted_response.json()["event_id"]
    assert scheduled == [event_id]

    asyncio.run(webhook_queue_module.run_whatsapp_webhook_event(event_id))

    with AdminStore()._connect() as connection:
        event = connection.execute(
            "SELECT status, attempts, last_error FROM whatsapp_webhook_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    assert dict(event) == {"status": "completed", "attempts": 1, "last_error": None}

    assert vision.calls == [
        {
            "image_bytes": b"ziplin-image-bytes",
            "mime_type": "image/png",
            "caption": "Please teach me how to solve this",
            "course": "CMA",
        }
    ]
    assert len(StubImageMentor.requests) == 1
    mentor_request = StubImageMentor.requests[0]
    assert mentor_request.student_id == f"whatsapp:{UNKNOWN_STUDENT_NUMBER}"
    assert mentor_request.course == "CMA"
    assert mentor_request.mode == "teach"
    assert mentor_request.message == "Explain the material variance shown in this image"

    get_calls = [call for call in http_calls if call["method"] == "GET"]
    post_calls = [call for call in http_calls if call["method"] == "POST"]
    assert [call["url"] for call in get_calls] == [
        "https://graph.example.test/v25.0/ziplin-media-123",
        "https://media.example.test/ziplin-media-123.png",
    ]
    assert all(
        call["headers"] == {"Authorization": "Bearer ziplin-access-token"}
        for call in get_calls
    )
    assert len(post_calls) == 2
    assert all(
        call["url"] == f"https://graph.example.test/v25.0/{ZIPLIN_PHONE_ID}/messages"
        for call in post_calls
    )
    assert all(call["json"]["to"] == UNKNOWN_STUDENT_NUMBER for call in post_calls)
    assert "I received your CMA image" in post_calls[0]["json"]["text"]["body"]
    assert "Ziplin image answer." in post_calls[1]["json"]["text"]["body"]
    assert InMemoryCache.instances[0].closed is True
