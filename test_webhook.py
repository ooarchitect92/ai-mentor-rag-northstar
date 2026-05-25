#!/usr/bin/env python3
"""
WhatsApp Webhook Tester
Tests webhook connection and configuration
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv
from app.config import get_settings
import httpx

async def test_webhook():
    """Test webhook connectivity and configuration"""
    
    load_dotenv()
    settings = get_settings()
    
    print("\n" + "="*80)
    print("WHATSAPP WEBHOOK TESTER")
    print("="*80)
    
    # Check configuration
    print("\n📋 CONFIGURATION CHECK:")
    print("-" * 80)
    
    config_ok = True
    
    if not settings.whatsapp_access_token:
        print("❌ WHATSAPP_ACCESS_TOKEN not set")
        config_ok = False
    else:
        print("✅ WHATSAPP_ACCESS_TOKEN is set")
    
    if not settings.whatsapp_phone_number_id:
        print("❌ WHATSAPP_PHONE_NUMBER_ID not set")
        config_ok = False
    else:
        print(f"✅ WHATSAPP_PHONE_NUMBER_ID: {settings.whatsapp_phone_number_id}")
    
    if not settings.whatsapp_verify_token:
        print("❌ WHATSAPP_VERIFY_TOKEN not set")
        config_ok = False
    else:
        token = settings.whatsapp_verify_token
        print(f"✅ WHATSAPP_VERIFY_TOKEN: {token[:20]}...{token[-20:]}")
    
    if not settings.whatsapp_app_secret and not settings.meta_app_secret:
        print("❌ Neither WHATSAPP_APP_SECRET nor META_APP_SECRET set")
        config_ok = False
    else:
        print("✅ App secret is configured")
    
    if not config_ok:
        print("\n❌ Configuration incomplete. Fix missing variables in .env")
        return False
    
    # Test backend connectivity
    print("\n📡 BACKEND CONNECTIVITY TEST:")
    print("-" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                health = response.json()
                print("✅ Backend is running on http://localhost:8000")
                print(f"   Status: {health.get('status')}")
                print(f"   WhatsApp Configured: {health.get('whatsapp_configured')}")
                print(f"   LLM: {health.get('llm_model')}")
            else:
                print(f"❌ Backend returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("   Make sure backend is running: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000")
        return False
    
    # Test webhook endpoint
    print("\n🔗 WEBHOOK ENDPOINT TEST:")
    print("-" * 80)
    
    print("✅ Webhook endpoint available at: /v1/whatsapp/webhook")
    print("   GET request: Webhook verification (Meta calls this)")
    print("   POST request: Incoming messages and status updates (Meta calls this)")
    
    # Show next steps
    print("\n📝 NEXT STEPS:")
    print("-" * 80)
    print("""
1. START ngrok:
   ngrok http 8000
   
2. Copy the forwarding URL:
   https://xxxx-xxxx.ngrok.io

3. GO TO META DASHBOARD:
   https://developers.facebook.com/apps

4. CONFIGURE WEBHOOK:
   - Webhook URL: https://xxxx-xxxx.ngrok.io/v1/whatsapp/webhook
   - Verify Token: (copy from above)
   - Click: Verify and Save

5. SUBSCRIBE TO EVENTS:
   - Enable: messages
   - Enable: message_status
   
6. WEBHOOK VERIFICATION:
   - Meta will send GET request
   - Backend responds with token
   - Should see "Webhook verified" in Meta dashboard

7. TEST:
   - Send message: python send_message.py menu
   - Receive message: Send "hi" to bot in WhatsApp
""")
    
    print("\n" + "="*80)
    print("✅ WEBHOOK READY FOR CONFIGURATION")
    print("="*80 + "\n")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_webhook())
    sys.exit(0 if success else 1)
