#!/usr/bin/env python3
"""
Easy WhatsApp Message Sender
Send text messages, menus, or test sequences to 9916039894
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.whatsapp import WhatsAppClient, normalize_wa_id
from dotenv import load_dotenv

async def send_menu():
    """Send the program menu"""
    load_dotenv()
    client = WhatsAppClient()
    phone = "919916039894"
    
    print(f"\n📤 Sending program menu to {phone}...")
    result = await client.send_program_menu(normalize_wa_id(phone))
    message_id = result.get('messages', [{}])[0].get('id', 'N/A')
    print(f"✅ Sent! Message ID: {message_id}\n")

async def send_text(message):
    """Send a text message"""
    load_dotenv()
    client = WhatsAppClient()
    phone = "9916039894"
    
    print(f"\n📤 Sending message to {phone}...")
    result = await client.send_text(normalize_wa_id(phone), message)
    message_id = result.get('messages', [{}])[0].get('id', 'N/A')
    print(f"✅ Sent! Message ID: {message_id}\n")

async def send_mode_menu(course):
    """Send the mode menu for a course"""
    load_dotenv()
    client = WhatsAppClient()
    phone = "9916039894"
    
    print(f"\n📤 Sending {course} mode menu to {phone}...")
    result = await client.send_mode_menu(normalize_wa_id(phone), course)
    message_id = result.get('messages', [{}])[0].get('id', 'N/A')
    print(f"✅ Sent! Message ID: {message_id}\n")

async def test_sequence():
    """Send a sequence of test messages"""
    print("\n" + "="*60)
    print("SENDING TEST SEQUENCE TO 9916039894")
    print("="*60)
    
    # 1. Program menu
    print("\n1️⃣ Sending program menu...")
    await send_menu()
    await asyncio.sleep(2)
    
    # 2. Welcome message
    print("2️⃣ Sending welcome message...")
    await send_text(
        "🎓 Welcome to AI Mentor!\n\n"
        "I can help you with:\n"
        "• CMA (Certified Management Accountant)\n"
        "• CPA (Certified Public Accountant)\n"
        "• ACCA (Association of Chartered Certified Accountants)\n"
        "• EA (Enrolled Agent)\n\n"
        "Select from the menu above or type a number (1-4)"
    )
    await asyncio.sleep(2)
    
    # 3. CMA mode menu
    print("3️⃣ Sending CMA mode menu...")
    await send_mode_menu("CMA")
    await asyncio.sleep(2)
    
    # 4. Instructions
    print("4️⃣ Sending instructions...")
    await send_text(
        "📚 Choose how you want to learn:\n\n"
        "1. Teach - Learn concepts step by step\n"
        "2. Doubt Solving - Get specific doubts cleared\n"
        "3. Quiz - Practice with MCQs\n"
        "4. Revision - Quick formulas & concepts\n"
        "5. Job Hunt - Resume & interview help\n\n"
        "Reply with a number or select from menu"
    )
    
    print("\n✅ Test sequence completed!\n")

def show_help():
    """Show help message"""
    print("""
╔════════════════════════════════════════════════════════════╗
║         WhatsApp Message Sender - Help                     ║
╚════════════════════════════════════════════════════════════╝

Usage:
  python send_message.py <command> [args]

Commands:
  menu                    - Send program menu (CMA, CPA, ACCA, EA)
  text <message>         - Send a text message
  mode <course>          - Send mode menu for a course
  test                   - Send a test sequence of messages
  help                   - Show this help message

Examples:
  python send_message.py menu
  python send_message.py text "Hello, this is a test message"
  python send_message.py mode CMA
  python send_message.py test

Phone Number: +91 9916039894
    """)

async def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "help":
        show_help()
    elif command == "menu":
        await send_menu()
    elif command == "text" and len(sys.argv) > 2:
        message = " ".join(sys.argv[2:])
        await send_text(message)
    elif command == "mode" and len(sys.argv) > 2:
        course = sys.argv[2].upper()
        if course not in ["CMA", "CPA", "ACCA", "EA"]:
            print(f"❌ Invalid course: {course}")
            print("Valid courses: CMA, CPA, ACCA, EA")
            return
        await send_mode_menu(course)
    elif command == "test":
        await test_sequence()
    else:
        print(f"❌ Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹ Cancelled\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
