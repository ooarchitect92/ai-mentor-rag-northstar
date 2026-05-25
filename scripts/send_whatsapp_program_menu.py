import argparse
import asyncio

from dotenv import load_dotenv

from app.whatsapp import WhatsAppClient, normalize_wa_id


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send the AI Mentor WhatsApp program menu.")
    parser.add_argument("to", help="Recipient WhatsApp number, with or without India country code.")
    args = parser.parse_args()

    load_dotenv()
    to = normalize_wa_id(args.to)
    await WhatsAppClient().send_program_menu(to)
    print(f"Sent program menu to {to}")


if __name__ == "__main__":
    asyncio.run(main())
