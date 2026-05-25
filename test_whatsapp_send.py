#!/usr/bin/env python3
"""
Test script to send a WhatsApp message to 9916039894
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.whatsapp import WhatsAppClient, normalize_wa_id
from app.config import get_settings
from dotenv import load_dotenv

async def main():
    # Load environment variables
    load_dotenv()
    
    # Get settings
    settings = get_settings()
    
    # Phone number to test
    phone_number = "9916039894"
    
    print("=" * 70)
    print("WhatsApp Test Script")
    print("=" * 70)
    print(f"\nPhone Number (input): {phone_number}")
    
    # Normalize the number
    normalized = normalize_wa_id(phone_number)
    print(f"Phone Number (normalized): {normalized}")
    
    # Check configuration
    print("\nWhatsApp Configuration:")
    print(f"  Mock Mode: {settings.whatsapp_use_mock}")
    print(f"  Access Token: {'✓ Set' if settings.whatsapp_access_token else '✗ Not set'}")
    print(f"  Phone Number ID: {settings.whatsapp_phone_number_id}")
    print(f"  API Version: {settings.whatsapp_graph_api_version}")
    print(f"  Graph Base: {settings.whatsapp_graph_base}")
    
    # Create client
    client = WhatsAppClient()
    print(f"\nClient Configured: {client.configured}")
    
    if not client.configured:
        print("\n❌ WhatsApp client is NOT configured properly!")
        print("   Please check your .env file for:")
        print("   - WHATSAPP_ACCESS_TOKEN or WHATSAPP_TOKEN")
        print("   - WHATSAPP_PHONE_NUMBER_ID")
        print("   Or set WHATSAPP_USE_MOCK=true to test with mock mode")
        return
    
    print("\n" + "=" * 70)
    print("Sending Program Menu to 9916039894...")
    print("=" * 70)
    
    try:
        result = await client.send_program_menu(normalized)
        print(f"\n✓ SUCCESS! Message sent to {normalized}")
        print(f"Response: {result}")
        
        print("\n" + "=" * 70)
        print("Sending Welcome Text Message...")
        print("=" * 70)
        
        result2 = await client.send_text(normalized, 
            "Welcome to AI Mentor! 🎓\n\n"
            "I'm here to help you with CMA, CPA, ACCA, or EA exam preparation.\n\n"
            "Reply with 'menu' or 'hi' to start!")
        print(f"\n✓ SUCCESS! Text message sent to {normalized}")
        print(f"Response: {result2}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    asyncio.run(main())
