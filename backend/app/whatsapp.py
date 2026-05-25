import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .cache import Cache
from .config import get_settings
from .mentor import MentorService
from .schemas import ChatRequest


logger = logging.getLogger("uvicorn.error")

COURSES = {"CMA", "CPA", "ACCA", "EA", "GENERAL"}
MODES = {"teach", "quiz", "revise", "job_hunt", "doubt_solving"}
LEVELS = {"beginner", "intermediate", "advanced"}
HI_TRIGGERS = {"hi", "hii", "hello", "hey", "start", "/start", "menu", "help", "program", "programs"}

PROGRAM_OPTIONS = [
    {
        "id": "program:cma",
        "label": "CMA",
        "course": "CMA",
        "description": "Certified Management Accountant",
    },
    {
        "id": "program:cpa",
        "label": "CPA",
        "course": "CPA",
        "description": "Certified Public Accountant",
    },
    {
        "id": "program:acca",
        "label": "ACCA",
        "course": "ACCA",
        "description": "Association of Chartered Certified Accountants",
    },
    {
        "id": "program:ea",
        "label": "EA",
        "course": "EA",
        "description": "Enrolled Agent",
    },
]

MODE_OPTIONS = [
    {
        "id": "mode:teach",
        "label": "Teach",
        "mode": "teach",
        "description": "Learn a concept step by step",
        "example": "Explain standard costing with a simple example.",
    },
    {
        "id": "mode:doubt_solving",
        "label": "Doubt Solving",
        "mode": "doubt_solving",
        "description": "Clear one specific doubt",
        "example": "Why is sales volume variance different from sales mix variance?",
    },
    {
        "id": "mode:quiz",
        "label": "Quiz",
        "mode": "quiz",
        "description": "Get practice questions",
        "example": "Give me 5 MCQs on variance analysis.",
    },
    {
        "id": "mode:revise",
        "label": "Revision",
        "mode": "revise",
        "description": "Revise quickly before exam",
        "example": "Revise marginal costing formulas.",
    },
    {
        "id": "mode:job_hunt",
        "label": "Job Hunt",
        "mode": "job_hunt",
        "description": "Resume, interview, and career help",
        "example": "Prepare me for a Big 4 FP&A interview.",
    },
]

MODE_BY_VALUE = {}
for option in MODE_OPTIONS:
    MODE_BY_VALUE[option["id"]] = option
    MODE_BY_VALUE[option["label"].lower()] = option
    MODE_BY_VALUE[option["mode"]] = option
MODE_BY_VALUE.update(
    {
        "1": MODE_OPTIONS[0],
        "2": MODE_OPTIONS[1],
        "doubt": MODE_OPTIONS[1],
        "doubt solving": MODE_OPTIONS[1],
        "doubt-solving": MODE_OPTIONS[1],
        "3": MODE_OPTIONS[2],
        "4": MODE_OPTIONS[3],
        "revision": MODE_OPTIONS[3],
        "revise": MODE_OPTIONS[3],
        "5": MODE_OPTIONS[4],
        "job": MODE_OPTIONS[4],
        "job hunt": MODE_OPTIONS[4],
        "job-hunt": MODE_OPTIONS[4],
    }
)

PROGRAM_BY_VALUE = {}
for option in PROGRAM_OPTIONS:
    PROGRAM_BY_VALUE[option["id"]] = option
    PROGRAM_BY_VALUE[option["label"].lower()] = option
    PROGRAM_BY_VALUE[option["course"].lower()] = option
PROGRAM_BY_VALUE.update(
    {
        "1": PROGRAM_OPTIONS[0],
        "2": PROGRAM_OPTIONS[1],
        "3": PROGRAM_OPTIONS[2],
        "4": PROGRAM_OPTIONS[3],
        "cma us": PROGRAM_OPTIONS[0],
        "cma usa": PROGRAM_OPTIONS[0],
        "cpa us": PROGRAM_OPTIONS[1],
        "cpa usa": PROGRAM_OPTIONS[1],
    }
)


def normalize_wa_id(value: str, default_country_code: str = "91") -> str:
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) == 10:
        return f"{default_country_code}{digits}"
    return digits


@dataclass(frozen=True)
class WhatsAppIncomingMessage:
    message_id: str
    sender: str
    text: str
    message_type: str
    profile_name: str | None = None


@dataclass(frozen=True)
class WhatsAppStatusEvent:
    message_id: str
    status: str
    recipient_id: str
    timestamp: str
    conversation_id: str | None
    errors: list[dict[str, Any]]


def verify_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    settings = get_settings()
    app_secret = settings.whatsapp_app_secret or settings.meta_app_secret
    if not app_secret:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def extract_incoming_messages(payload: dict[str, Any]) -> list[WhatsAppIncomingMessage]:
    messages: list[WhatsAppIncomingMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts_by_id = {
                contact.get("wa_id"): (contact.get("profile") or {}).get("name")
                for contact in value.get("contacts", [])
            }

            for raw_message in value.get("messages", []):
                sender = str(raw_message.get("from", ""))
                message_id = str(raw_message.get("id", ""))
                message_type = str(raw_message.get("type", ""))
                text = ""
                if message_type == "text":
                    text = str((raw_message.get("text") or {}).get("body", "")).strip()
                elif message_type == "interactive":
                    interactive = raw_message.get("interactive") or {}
                    if interactive.get("type") == "list_reply":
                        reply = interactive.get("list_reply") or {}
                        text = str(reply.get("id") or reply.get("title") or "").strip()
                    elif interactive.get("type") == "button_reply":
                        reply = interactive.get("button_reply") or {}
                        text = str(reply.get("id") or reply.get("title") or "").strip()
                elif message_type == "button":
                    button = raw_message.get("button") or {}
                    text = str(button.get("payload") or button.get("text") or "").strip()

                if sender and message_id:
                    messages.append(
                        WhatsAppIncomingMessage(
                            message_id=message_id,
                            sender=sender,
                            text=text,
                            message_type=message_type,
                            profile_name=contacts_by_id.get(sender),
                        )
                    )

    return messages


def extract_status_events(payload: dict[str, Any]) -> list[WhatsAppStatusEvent]:
    events: list[WhatsAppStatusEvent] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for raw_status in value.get("statuses", []):
                message_id = str(raw_status.get("id", ""))
                status = str(raw_status.get("status", ""))
                recipient_id = str(raw_status.get("recipient_id", ""))
                timestamp = str(raw_status.get("timestamp", ""))
                conversation = raw_status.get("conversation") or {}
                errors = raw_status.get("errors") or []

                if message_id and status:
                    events.append(
                        WhatsAppStatusEvent(
                            message_id=message_id,
                            status=status,
                            recipient_id=recipient_id,
                            timestamp=timestamp,
                            conversation_id=conversation.get("id"),
                            errors=errors if isinstance(errors, list) else [],
                        )
                    )

    return events


def split_whatsapp_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = max(
            remaining.rfind("\n\n", 0, max_chars),
            remaining.rfind("\n", 0, max_chars),
            remaining.rfind(" ", 0, max_chars),
        )
        if split_at < max_chars * 0.5:
            split_at = max_chars

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


def mode_session_key(sender: str) -> str:
    return f"whatsapp:mode:{sender}"


def program_session_key(sender: str) -> str:
    return f"whatsapp:program:{sender}"


def conversation_started_key(sender: str) -> str:
    return f"whatsapp:started:{sender}"


def text_menu() -> str:
    return program_menu()


def program_menu() -> str:
    return (
        "*AI Mentor*\n"
        "First choose your program:\n\n"
        "1. CMA\n"
        "2. CPA\n"
        "3. ACCA\n"
        "4. EA\n\n"
        "Reply with 1-4 or tap the program option."
    )


def mode_menu(course: str) -> str:
    return (
        f"*{course} selected*\n"
        "Now choose how I should help you:\n\n"
        "1. Teach\n"
        "2. Doubt Solving\n"
        "3. Quiz\n"
        "4. Revision\n"
        "5. Job Hunt\n\n"
        "Reply with 1-5 or tap the menu option."
    )


def normalize_program_selection(text: str) -> tuple[dict[str, str] | None, str]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return None, ""

    lower = cleaned.lower()
    for option in PROGRAM_OPTIONS:
        for prefix in (f"{option['label'].lower()}:", f"{option['course'].lower()}:", f"{option['id']}:"):
            if lower.startswith(prefix):
                return option, cleaned[len(prefix) :].strip()

    return PROGRAM_BY_VALUE.get(lower), ""


def normalize_mode_selection(text: str) -> tuple[dict[str, str] | None, str]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return None, ""

    lower = cleaned.lower()
    for option in MODE_OPTIONS:
        for prefix in (f"{option['label'].lower()}:", f"{option['mode']}:", f"{option['id']}:"):
            if lower.startswith(prefix):
                return option, cleaned[len(prefix) :].strip()

    return MODE_BY_VALUE.get(lower), ""


def mode_prompt(option: dict[str, str]) -> str:
    return (
        f"*{option['label']} selected*\n"
        "Send your question now.\n\n"
        f"Example: {option['example']}\n\n"
        "Type *menu* anytime to change program or mode."
    )


def format_whatsapp_answer(answer: str, course: str, option: dict[str, str], sources: list[str]) -> str:
    parts = [f"*{course} | {option['label']}*", answer.strip()]
    if sources:
        parts.append("*Sources:* " + ", ".join(sources[:3]))
    parts.append("_Type menu to change program or mode._")
    return "\n\n".join(part for part in parts if part)


def _validated_setting(value: str, allowed: set[str], fallback: str, *, upper: bool = False) -> str:
    candidate = value.upper() if upper else value
    return candidate if candidate in allowed else fallback


def build_chat_request(
    sender: str,
    text: str,
    mode_override: str | None = None,
    course_override: str | None = None,
) -> ChatRequest:
    settings = get_settings()
    course = course_override or _validated_setting(settings.whatsapp_default_course, COURSES, "GENERAL", upper=True)
    mode = mode_override or _validated_setting(settings.whatsapp_default_mode, MODES, "doubt_solving")
    level = _validated_setting(settings.whatsapp_default_level, LEVELS, "beginner")

    stripped = text.strip()
    if not course_override:
        upper_text = stripped.upper()
        for candidate_course in COURSES:
            for prefix in (f"{candidate_course}:", f"[{candidate_course}]"):
                if upper_text.startswith(prefix):
                    course = candidate_course
                    stripped = stripped[len(prefix) :].strip()
                    break
            else:
                continue
            break

    return ChatRequest(
        student_id=f"whatsapp:{sender}",
        course=course,
        message=stripped or text,
        level=level,
        mode=mode,
        use_cache=True,
    )


class WhatsAppClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.whatsapp_use_mock or (self._token() and self.settings.whatsapp_phone_number_id))

    def _token(self) -> str:
        return self.settings.whatsapp_access_token or self.settings.whatsapp_token

    def _graph_base(self) -> str:
        if self.settings.whatsapp_graph_base:
            return self.settings.whatsapp_graph_base.rstrip("/")
        return f"https://graph.facebook.com/{self.settings.whatsapp_graph_api_version}"

    def _send_url(self) -> str:
        return f"{self._graph_base()}/{self.settings.whatsapp_phone_number_id}/messages"

    async def _post_message(self, payload: dict) -> dict[str, Any]:
        if self.settings.whatsapp_use_mock:
            logger.info("[Mock WhatsApp] %s", payload)
            return {"mock": True, "payload": payload}

        if not self.configured:
            raise RuntimeError("WhatsApp access token and phone number ID are required")

        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(self._send_url(), headers=headers, json=payload)
            response.raise_for_status()
            try:
                result = response.json()
            except ValueError:
                result = {"raw": response.text}

        logger.info(
            "WhatsApp send accepted type=%s to=%s response=%s",
            payload.get("type"),
            payload.get("to"),
            result,
        )
        return result

    async def send_text(self, to: str, body: str) -> dict[str, Any]:
        to = normalize_wa_id(to)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body,
            },
        }
        return await self._post_message(payload)

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        to = normalize_wa_id(to)
        template: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template,
        }
        return await self._post_message(payload)

    async def send_start_message(
        self,
        to: str,
        template_name: str | None = None,
        language_code: str | None = None,
    ) -> dict[str, Any]:
        return await self.send_template(
            to=to,
            template_name=template_name or self.settings.whatsapp_start_template_name,
            language_code=language_code or self.settings.whatsapp_start_template_language,
        )

    async def send_program_menu(self, to: str) -> dict[str, Any]:
        to = normalize_wa_id(to)
        rows = [
            {
                "id": option["id"],
                "title": option["label"],
                "description": option["description"],
            }
            for option in PROGRAM_OPTIONS
        ]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "AI Mentor"},
                "body": {"text": "Choose your program."},
                "footer": {"text": "You can also reply 1-4."},
                "action": {
                    "button": "Select program",
                    "sections": [{"title": "Programs", "rows": rows}],
                },
            },
        }
        return await self._post_message(payload)

    async def send_mode_menu(self, to: str, course: str) -> dict[str, Any]:
        to = normalize_wa_id(to)
        rows = [
            {
                "id": option["id"],
                "title": option["label"],
                "description": option["description"],
            }
            for option in MODE_OPTIONS
        ]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": course},
                "body": {"text": "Choose how I should help you."},
                "footer": {"text": "You can also reply 1-5."},
                "action": {
                    "button": "Select option",
                    "sections": [{"title": "Learning modes", "rows": rows}],
                },
            },
        }
        return await self._post_message(payload)


class WhatsAppBot:
    def __init__(self) -> None:
        self.cache = Cache()
        self.client = WhatsAppClient()
        self.settings = get_settings()

    async def handle_payload(self, payload: dict[str, Any]) -> None:
        for event in extract_status_events(payload):
            if event.errors:
                logger.warning(
                    "WhatsApp status %s for message=%s recipient=%s errors=%s",
                    event.status,
                    event.message_id,
                    event.recipient_id,
                    event.errors,
                )
            else:
                logger.info(
                    "WhatsApp status %s for message=%s recipient=%s conversation=%s",
                    event.status,
                    event.message_id,
                    event.recipient_id,
                    event.conversation_id,
                )

        for message in extract_incoming_messages(payload):
            dedupe_key = f"whatsapp:inbound:{message.message_id}"
            if not await self.cache.set_if_absent(dedupe_key, ttl_seconds=86400):
                continue

            try:
                await self._handle_message(message)
            except Exception:
                logger.exception("Failed to process WhatsApp message %s", message.message_id)

    async def _handle_message(self, message: WhatsAppIncomingMessage) -> None:
        if not message.text:
            await self.client.send_text(
                message.sender,
                "Please send a text question or choose one menu option.",
            )
            return

        incoming = message.text.strip()
        if incoming.lower() in HI_TRIGGERS:
            await self.cache.delete(program_session_key(message.sender))
            await self.cache.delete(mode_session_key(message.sender))
            await self.cache.set_text(
                conversation_started_key(message.sender),
                "1",
                ttl_seconds=self.settings.whatsapp_session_ttl_seconds,
            )
            await self.client.send_text(message.sender, program_menu())
            await self.client.send_program_menu(message.sender)
            return

        selected_program, program_inline_question = normalize_program_selection(incoming)
        if selected_program:
            await self.cache.set_text(
                program_session_key(message.sender),
                selected_program["course"],
                ttl_seconds=self.settings.whatsapp_session_ttl_seconds,
            )
            await self.cache.delete(mode_session_key(message.sender))
            await self.client.send_text(message.sender, mode_menu(selected_program["course"]))
            await self.client.send_mode_menu(message.sender, selected_program["course"])
            if program_inline_question:
                await self.client.send_text(
                    message.sender,
                    "I saved your program. Please choose Teach, Doubt Solving, Quiz, Revision, or Job Hunt before I answer that question.",
                )
            return

        selected_course = await self.cache.get_text(program_session_key(message.sender))

        selected_option, inline_question = normalize_mode_selection(incoming)
        if selected_option:
            if selected_course not in COURSES:
                await self.cache.set_text(
                    conversation_started_key(message.sender),
                    "1",
                    ttl_seconds=self.settings.whatsapp_session_ttl_seconds,
                )
                await self.client.send_text(
                    message.sender,
                    "Thanks for replying. Let's choose your program first.",
                )
                await self.client.send_program_menu(message.sender)
                return

            await self.cache.set_text(
                mode_session_key(message.sender),
                selected_option["mode"],
                ttl_seconds=self.settings.whatsapp_session_ttl_seconds,
            )
            if not inline_question:
                await self.client.send_text(message.sender, mode_prompt(selected_option))
                return
            incoming = inline_question

        selected_mode = await self.cache.get_text(mode_session_key(message.sender))
        selected_course = await self.cache.get_text(program_session_key(message.sender))
        if selected_course not in COURSES:
            await self.cache.set_text(
                conversation_started_key(message.sender),
                "1",
                ttl_seconds=self.settings.whatsapp_session_ttl_seconds,
            )
            await self.client.send_text(
                message.sender,
                "Thanks for replying. Let's get you set up first.\n\n" + program_menu(),
            )
            await self.client.send_program_menu(message.sender)
            return

        if selected_mode not in MODES:
            await self.client.send_text(message.sender, mode_menu(selected_course))
            await self.client.send_mode_menu(message.sender, selected_course)
            return

        selected_option = next(option for option in MODE_OPTIONS if option["mode"] == selected_mode)

        try:
            mentor = MentorService()
            response = await mentor.answer(
                build_chat_request(
                    message.sender,
                    incoming,
                    mode_override=selected_mode,
                    course_override=selected_course,
                )
            )
            source_names = []
            if response.sources:
                for source in response.sources[:3]:
                    if source.title and source.title not in source_names:
                        source_names.append(source.title)
            answer = format_whatsapp_answer(response.answer, selected_course, selected_option, source_names)
        except Exception:
            logger.exception("Claude mentor answer failed for WhatsApp sender %s", message.sender)
            answer = "I had trouble generating that answer right now. Please try again in a moment."

        for chunk in split_whatsapp_text(answer, self.settings.whatsapp_max_reply_chars):
            await self.client.send_text(message.sender, chunk)


async def process_whatsapp_webhook(payload: dict[str, Any]) -> None:
    await WhatsAppBot().handle_payload(payload)
