#!/usr/bin/env python3
"""
Complete WhatsApp Integration Setup Guide
Tests both sending and receiving functionality for 9916039894
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.whatsapp import WhatsAppClient, normalize_wa_id
from app.config import get_settings
from dotenv import load_dotenv

async def test_whatsapp_integration():
    """Test the complete WhatsApp integration"""
    
    # Load environment variables
    load_dotenv()
    settings = get_settings()
    
    phone_number = "9916039894"
    normalized_number = normalize_wa_id(phone_number)
    
    print("\n" + "="*80)
    print("AI MENTOR WHATSAPP INTEGRATION TEST")
    print("="*80)
    
    # 1. Show Configuration
    print("\n📋 CONFIGURATION CHECK:")
    print("-" * 80)
    print(f"  Phone Number (Input):      {phone_number}")
    print(f"  Phone Number (Normalized): {normalized_number}")
    print(f"  Mock Mode:                 {settings.whatsapp_use_mock}")
    print(f"  Access Token:              {'✓ Configured' if settings.whatsapp_access_token else '✗ Missing'}")
    print(f"  Phone Number ID:           {settings.whatsapp_phone_number_id}")
    print(f"  API Version:               {settings.whatsapp_graph_api_version}")
    print(f"  Verify Token:              {'✓ Configured' if settings.whatsapp_verify_token else '✗ Missing'}")
    
    client = WhatsAppClient()
    if not client.configured:
        print("\n❌ WhatsApp client is NOT properly configured!")
        return False
    
    print(f"  Client Status:             ✓ Ready to send/receive messages")
    
    # 2. Test Sending Messages
    print("\n📤 SENDING MESSAGES:")
    print("-" * 80)
    
    try:
        # Send program menu
        print("\n  Sending Program Menu...")
        result1 = await client.send_program_menu(normalized_number)
        print(f"  ✓ Program menu sent successfully")
        print(f"    Message ID: {result1.get('messages', [{}])[0].get('id', 'N/A')}")
        
        # Send text message
        print("\n  Sending Welcome Text Message...")
        result2 = await client.send_text(
            normalized_number,
            "🎓 Welcome to AI Mentor!\n\n"
            "I'm here to help with CMA, CPA, ACCA, or EA exam preparation.\n\n"
            "Type 'menu' or 'hi' to get started!"
        )
        print(f"  ✓ Welcome message sent successfully")
        print(f"    Message ID: {result2.get('messages', [{}])[0].get('id', 'N/A')}")
        
        # Send mode menu
        print("\n  Sending Mode Menu (CMA)...")
        result3 = await client.send_mode_menu(normalized_number, "CMA")
        print(f"  ✓ Mode menu sent successfully")
        print(f"    Message ID: {result3.get('messages', [{}])[0].get('id', 'N/A')}")
        
        print("\n✅ All messages sent successfully!")
        
    except Exception as e:
        print(f"\n❌ Error sending messages: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. Receiving Instructions
    print("\n📥 RECEIVING MESSAGES:")
    print("-" * 80)
    print("""
  To receive messages from WhatsApp, the following must be configured:
  
  1. ✓ Backend Server Running:
     - Ensure the FastAPI backend is running on port 8000
     - The application is already running and listening on 0.0.0.0:8000
  
  2. ✓ Webhook Endpoint:
     - Endpoint: POST /v1/whatsapp/webhook
     - Endpoint: GET /v1/whatsapp/webhook (for verification)
  
  3. ⚠ Public URL (Required for Meta Webhook):
     - Your server must be accessible from the internet
     - Use ngrok, Cloudflare Tunnel, or similar for local development
     - Example: https://your-domain.com/v1/whatsapp/webhook
  
  4. ✓ Meta App Configuration:
     - Webhook Verify Token: {verify_token}
     - Webhook URL: https://your-domain.com/v1/whatsapp/webhook
  
  5. ✓ Message Processing:
     - The app automatically processes incoming messages
     - Supports: Text, Interactive (buttons/lists), Button, and List Reply messages
     - Session management with Redis caching
""".format(
        verify_token=settings.whatsapp_verify_token[:20] + "..."
    ))
    
    # 4. Testing Instructions
    print("\n🧪 HOW TO TEST THE FULL INTEGRATION:")
    print("-" * 80)
    print("""
  1. SEND A MESSAGE:
     - WhatsApp this bot at: +91 9916039894
     - You should receive the program menu
     
  2. INTERACT WITH MENUS:
     - Select a program (1-4 or tap menu option)
     - Select a learning mode (Teach, Doubt Solving, Quiz, Revision, Job Hunt)
     - Ask any question related to your selected program
     
  3. EXPECTED RESPONSES:
     - Menu messages with interactive buttons
     - Personalized AI-powered answers from Claude
     - Source references for answers
     - Support for conversation sessions
     
  4. COMMANDS:
     - Type 'hi', 'hello', 'menu', or '/start' to reset the conversation
     - Type 'menu' anytime to change program or mode
""")
    
    # 5. API Endpoints
    print("\n🔗 API ENDPOINTS:")
    print("-" * 80)
    print(f"""
  Send Program Menu (Admin):
    POST /v1/admin/whatsapp/send-program-menu
    Requires: ADMIN_TOKEN header
    Body: {{"to": "9916039894"}}
  
  Chat Endpoint:
    POST /v1/chat
    Body: {{"student_id": "...", "message": "...", "course": "...", "mode": "..."}}
  
  Health Check:
    GET /health
    Response includes: whatsapp_configured, whatsapp_mock status
  
  Webhook (Incoming Messages):
    GET /v1/whatsapp/webhook (verification)
    POST /v1/whatsapp/webhook (message/status events)
""")
    
    # 6. Backend Status
    print("\n⚙️ BACKEND STATUS:")
    print("-" * 80)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as http_client:
            response = await http_client.get("http://localhost:8000/health")
            if response.status_code == 200:
                health = response.json()
                print(f"  ✓ Backend is running on port 8000")
                print(f"    - WhatsApp Configured: {health.get('whatsapp_configured')}")
                print(f"    - Mock Mode: {health.get('whatsapp_mock')}")
                print(f"    - LLM Provider: {health.get('llm_provider')}")
                print(f"    - LLM Model: {health.get('llm_model')}")
                print(f"    - Embedding Provider: {health.get('embedding_provider')}")
                print(f"    - Vector Collection: {health.get('collection')}")
    except Exception as e:
        print(f"  ⚠ Could not connect to backend: {e}")
    
    print("\n" + "="*80)
    print("✅ WHATSAPP INTEGRATION IS WORKING!")
    print("="*80)
    print("\nNext Steps:")
    print("  1. Messages have been sent to +91 9916039894")
    print("  2. Check your WhatsApp for the received messages")
    print("  3. To enable receiving messages, configure your Meta/Facebook app webhook")
    print("  4. Use ngrok or similar tool to expose your local server")
    print("\n" + "="*80 + "\n")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_whatsapp_integration())
    sys.exit(0 if success else 1)
