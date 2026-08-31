import argparse
import asyncio

from dotenv import load_dotenv

from app.cache import Cache
from app.whatsapp import WhatsAppClient, get_enrolled_courses, normalize_wa_id, ordered_courses


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send the enrolled-course WhatsApp learning-mode menu.")
    parser.add_argument("to", help="Recipient WhatsApp number, with or without India country code.")
    args = parser.parse_args()

    load_dotenv()
    to = normalize_wa_id(args.to)
    courses = await get_enrolled_courses(Cache(), to)
    if not courses:
        raise SystemExit("Recipient is not enrolled for WhatsApp mentor access.")
    client = WhatsAppClient()
    ordered = ordered_courses(courses)
    if len(ordered) == 1:
        await client.send_mode_menu(to, ordered[0])
        print(f"Sent {ordered[0]} mode menu to {to}")
    else:
        await client.send_program_menu(to, courses)
        print(f"Sent enrolled-course menu {ordered} to {to}")


if __name__ == "__main__":
    asyncio.run(main())
