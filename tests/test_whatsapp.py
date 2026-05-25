import asyncio

from app.config import get_settings
from app.whatsapp import (
    WhatsAppBot,
    WhatsAppIncomingMessage,
    WhatsAppClient,
    build_chat_request,
    extract_incoming_messages,
    extract_status_events,
    normalize_mode_selection,
    normalize_program_selection,
    mode_menu,
    program_menu,
    split_whatsapp_text,
    text_menu,
)


class FakeWhatsAppCache:
    def __init__(self) -> None:
        self.values = {}

    async def set_if_absent(self, key: str, ttl_seconds: int) -> bool:
        return True

    async def get_text(self, key: str) -> str | None:
        return self.values.get(key)

    async def set_text(self, key: str, value: str, ttl_seconds: int) -> None:
        self.values[key] = value

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class FakeWhatsAppClient:
    def __init__(self) -> None:
        self.texts = []
        self.program_menus = []
        self.mode_menus = []

    async def send_text(self, to: str, body: str) -> dict:
        self.texts.append((to, body))
        return {}

    async def send_program_menu(self, to: str) -> dict:
        self.program_menus.append(to)
        return {}

    async def send_mode_menu(self, to: str, course: str) -> dict:
        self.mode_menus.append((to, course))
        return {}


def test_extract_incoming_text_message():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "919999999999", "profile": {"name": "Student"}}],
                            "messages": [
                                {
                                    "from": "919999999999",
                                    "id": "wamid.test",
                                    "type": "text",
                                    "text": {"body": "CMA: Explain variance analysis"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_incoming_messages(payload)

    assert len(messages) == 1
    assert messages[0].sender == "919999999999"
    assert messages[0].message_id == "wamid.test"
    assert messages[0].text == "CMA: Explain variance analysis"
    assert messages[0].profile_name == "Student"


def test_build_chat_request_allows_course_prefix():
    request = build_chat_request(
        "919999999999",
        "What is materiality?",
        mode_override="teach",
        course_override="CPA",
    )

    assert request.student_id == "whatsapp:919999999999"
    assert request.course == "CPA"
    assert request.mode == "teach"
    assert request.message == "What is materiality?"


def test_split_whatsapp_text_keeps_chunks_below_limit():
    chunks = split_whatsapp_text("word " * 100, max_chars=80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 80 for chunk in chunks)


def test_interactive_list_reply_extracts_mode_id():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919999999999",
                                    "id": "wamid.mode",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {"id": "mode:job_hunt", "title": "Job Hunt"},
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_incoming_messages(payload)

    assert messages[0].text == "mode:job_hunt"


def test_interactive_list_reply_extracts_program_id():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919999999999",
                                    "id": "wamid.program",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {"id": "program:cpa", "title": "CPA"},
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_incoming_messages(payload)

    assert messages[0].text == "program:cpa"


def test_extract_status_events_includes_errors():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.status",
                                    "status": "failed",
                                    "timestamp": "1710000000",
                                    "recipient_id": "919999999999",
                                    "conversation": {"id": "conv.test"},
                                    "errors": [{"code": 131026, "title": "Message undeliverable"}],
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    events = extract_status_events(payload)

    assert len(events) == 1
    assert events[0].message_id == "wamid.status"
    assert events[0].status == "failed"
    assert events[0].recipient_id == "919999999999"
    assert events[0].errors[0]["code"] == 131026


def test_send_start_message_uses_whatsapp_template_payload(monkeypatch):
    monkeypatch.setenv("WHATSAPP_USE_MOCK", "true")
    monkeypatch.setenv("WHATSAPP_START_TEMPLATE_NAME", "hello_world")
    monkeypatch.setenv("WHATSAPP_START_TEMPLATE_LANGUAGE", "en_US")
    get_settings.cache_clear()

    client = WhatsAppClient()
    result = asyncio.run(client.send_start_message("9916039894"))
    get_settings.cache_clear()

    payload = result["payload"]
    assert payload["to"] == "919916039894"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "hello_world"
    assert payload["template"]["language"]["code"] == "en_US"


def test_first_customer_reply_after_invite_opens_program_menu():
    bot = WhatsAppBot()
    bot.cache = FakeWhatsAppCache()
    bot.client = FakeWhatsAppClient()

    message = WhatsAppIncomingMessage(
        message_id="wamid.reply",
        sender="919916039894",
        text="yes",
        message_type="text",
    )
    asyncio.run(bot._handle_message(message))

    assert bot.client.program_menus == ["919916039894"]
    assert "Thanks for replying" in bot.client.texts[0][1]
    assert "CMA" in bot.client.texts[0][1]


def test_normalize_mode_selection_accepts_numbers_names_and_inline_questions():
    option, question = normalize_mode_selection("2")
    assert option["mode"] == "doubt_solving"
    assert question == ""

    option, question = normalize_mode_selection("Job Hunt: prepare me for FP&A")
    assert option["mode"] == "job_hunt"
    assert question == "prepare me for FP&A"


def test_normalize_program_selection_accepts_numbers_names_and_inline_questions():
    option, question = normalize_program_selection("2")
    assert option["course"] == "CPA"
    assert question == ""

    option, question = normalize_program_selection("ACCA: Explain audit risk")
    assert option["course"] == "ACCA"
    assert question == "Explain audit risk"


def test_text_menu_starts_with_programs():
    menu = text_menu()

    assert menu == program_menu()
    assert "CMA" in menu
    assert "CPA" in menu
    assert "ACCA" in menu
    assert "EA" in menu


def test_mode_menu_contains_only_allowed_modes():
    menu = mode_menu("CPA")

    assert "Teach" in menu
    assert "Doubt Solving" in menu
    assert "Quiz" in menu
    assert "Revision" in menu
    assert "Job Hunt" in menu
