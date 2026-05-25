import argparse
import asyncio

from app.whatsapp import WhatsAppClient, normalize_wa_id


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send the initial WhatsApp template invite.")
    parser.add_argument("to", help="Recipient WhatsApp number, with or without India country code.")
    parser.add_argument("--template-name", help="Approved WhatsApp template name to send.")
    parser.add_argument("--language-code", help="Template language code, for example en_US.")
    args = parser.parse_args()

    to = normalize_wa_id(args.to)
    client = WhatsAppClient()
    result = await client.send_start_message(
        to=to,
        template_name=args.template_name,
        language_code=args.language_code,
    )
    print({"status": "sent", "to": to, "meta_response": result})


if __name__ == "__main__":
    asyncio.run(main())
