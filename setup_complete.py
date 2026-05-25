#!/usr/bin/env python3
"""
Complete WhatsApp Setup and Configuration Tool
Handles ngrok setup, Meta app configuration, and full testing
"""
import asyncio
import sys
import os
from pathlib import Path
import subprocess
import json

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv
from app.config import get_settings
from app.whatsapp import WhatsAppClient, normalize_wa_id

class WhatsAppSetupManager:
    def __init__(self):
        load_dotenv()
        self.settings = get_settings()
        self.phone_number = "9916039894"
        self.normalized_phone = normalize_wa_id(self.phone_number)
        
    def print_header(self, title):
        print("\n" + "="*80)
        print(f"  {title}")
        print("="*80)
    
    def print_step(self, step_num, description):
        print(f"\n{'='*80}")
        print(f"STEP {step_num}: {description}")
        print("="*80)
    
    def print_section(self, title):
        print(f"\n{'─'*80}")
        print(f"  {title}")
        print("─"*80)
    
    async def verify_backend(self):
        """Verify backend is running"""
        self.print_step(1, "Verify Backend Server is Running")
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get("http://localhost:8000/health")
                if response.status_code == 200:
                    health = response.json()
                    print(f"\n✅ Backend is running on http://localhost:8000")
                    print(f"   WhatsApp Configured: {health.get('whatsapp_configured')}")
                    print(f"   LLM: {health.get('llm_model')}")
                    print(f"   Vector Collection: {health.get('collection')}")
                    return True
        except Exception as e:
            print(f"\n❌ Backend is NOT running: {e}")
            print("   Please run: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload")
            return False
    
    async def test_sending(self):
        """Test message sending"""
        self.print_step(2, "Test Message Sending")
        
        try:
            client = WhatsAppClient()
            if not client.configured:
                print("\n❌ WhatsApp client not configured")
                return False
            
            print(f"\nSending messages to {self.normalized_phone}...")
            
            # Send program menu
            result = await client.send_program_menu(self.normalized_phone)
            msg_id = result.get('messages', [{}])[0].get('id', 'N/A')
            print(f"✅ Program menu sent: {msg_id}")
            
            # Send welcome text
            result = await client.send_text(self.normalized_phone,
                "🎓 Welcome to AI Mentor!\n\n"
                "Testing: Both sending AND receiving will now work!\n\n"
                "Type 'hi' to start.")
            msg_id = result.get('messages', [{}])[0].get('id', 'N/A')
            print(f"✅ Welcome message sent: {msg_id}")
            
            return True
        except Exception as e:
            print(f"\n❌ Error sending: {e}")
            return False
    
    def show_ngrok_setup(self):
        """Show detailed ngrok setup instructions"""
        self.print_step(3, "Setup ngrok for Public Access")
        
        print("""
┌─ NGROK INSTALLATION & SETUP ──────────────────────────────────────────────────┐
│                                                                                  │
│  1. DOWNLOAD NGROK:                                                            │
│     Go to: https://ngrok.com/download                                          │
│     Download for Windows (ngrok-v3-stable-windows-amd64.zip or latest)        │
│                                                                                  │
│  2. EXTRACT AND ADD TO PATH:                                                   │
│     - Extract the zip file (you'll get ngrok.exe)                             │
│     - Save it somewhere like: C:\\Program Files\\ngrok\\                       │
│     - OR add the extraction folder to Windows PATH                             │
│                                                                                  │
│  3. CREATE NGROK ACCOUNT (Optional but recommended):                           │
│     - Go to: https://dashboard.ngrok.com/signup                                │
│     - Create free account                                                       │
│     - Get your authtoken from dashboard                                        │
│                                                                                  │
│  4. CONFIGURE NGROK (if you got authtoken):                                    │
│     - Run: ngrok config add-authtoken YOUR_AUTH_TOKEN                         │
│     - This gives you better features and longer tunnel duration                │
│                                                                                  │
│  5. START NGROK TUNNEL:                                                        │
│     - Open a NEW terminal (keep current one for backend)                       │
│     - Run: ngrok http 8000                                                     │
│     - You'll see output like:                                                  │
│                                                                                  │
│         Session Status                online                                    │
│         Account                        <your-account>                          │
│         Version                        3.X.X                                   │
│         Region                         us,eu,au,ap,jp,in                       │
│         Latency                        45ms                                     │
│         Web Interface                  http://127.0.0.1:4040                  │
│         Forwarding                     https://xxxx-xx-xxxxx.ngrok.io -> ...  │
│                                                                                  │
│     Copy the URL: https://xxxx-xx-xxxxx.ngrok.io                             │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

IMPORTANT: Your ngrok URL will change each time unless you have a paid account!
           Keep ngrok running while testing. When done, close and restart.
""")

    def show_meta_configuration(self):
        """Show detailed Meta app configuration"""
        self.print_step(4, "Configure Meta/Facebook App Webhook")
        
        verify_token = self.settings.whatsapp_verify_token
        
        print(f"""
┌─ META APP CONFIGURATION (DETAILED STEPS) ─────────────────────────────────────┐
│                                                                                  │
│  PREREQUISITES:                                                                │
│  ✓ Backend running on port 8000                                               │
│  ✓ ngrok tunnel established (e.g., https://xxxx-xx.ngrok.io)                 │
│  ✓ Meta/Facebook Business Account setup                                       │
│                                                                                  │
│  STEP-BY-STEP CONFIGURATION:                                                  │
│                                                                                  │
│  1. GO TO META DEVELOPER DASHBOARD:                                            │
│     URL: https://developers.facebook.com/apps                                 │
│     - Login with your Meta account                                             │
│     - Select your WhatsApp app (if not created, create one)                   │
│                                                                                  │
│  2. NAVIGATE TO WHATSAPP CONFIGURATION:                                       │
│     - Left sidebar: Products → WhatsApp                                       │
│     - Click on "Configuration" or "Webhooks"                                  │
│                                                                                  │
│  3. EDIT WEBHOOK URL:                                                          │
│     - Look for "Webhook URL" field                                             │
│     - Clear current value                                                      │
│     - Paste your ngrok URL: https://your-ngrok-url.ngrok.io/v1/whatsapp/webhook
│                                                                                  │
│  4. SET VERIFY TOKEN:                                                          │
│     - Look for "Verify Token" field                                            │
│     - Clear current value                                                      │
│     - Paste this token:                                                        │
│       {verify_token}                                    │
│                                                                                  │
│  5. CLICK "VERIFY AND SAVE":                                                   │
│     - Meta will send a GET request to your webhook                             │
│     - Our backend will respond with the token                                  │
│     - You should see "Webhook verified successfully"                           │
│                                                                                  │
│  6. SUBSCRIBE TO WEBHOOK EVENTS:                                               │
│     - Look for "Subscribe to this webhook" section                             │
│     - Check/Enable these events:                                               │
│       ☑ messages                                                               │
│       ☑ message_status                                                         │
│       ☑ message_template_status_update (optional)                             │
│     - Click "Save"                                                             │
│                                                                                  │
│  7. VERIFY FIELD ACCESS:                                                       │
│     - Ensure you have these webhook field subscriptions:                       │
│       ☑ messages.new_messages                                                 │
│       ☑ messages.message_received                                             │
│       ☑ messages.message_sent                                                 │
│       ☑ messages.message_delivered                                            │
│       ☑ messages.message_read                                                 │
│                                                                                  │
│  WEBHOOK VERIFICATION PROCESS (Automatic):                                     │
│  When you save, Meta sends a GET request:                                      │
│    GET /v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=...          │
│  Our app responds with the challenge token, and Meta marks it as verified.    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

IMPORTANT NOTES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. If webhook verification FAILS:
   - Check that backend is running on port 8000
   - Check that ngrok is tunneling to port 8000
   - Verify your verify token matches EXACTLY
   - Check backend logs for error messages

2. Webhook URL format MUST be exact:
   ✓ CORRECT:   https://xxxx-xxxx.ngrok.io/v1/whatsapp/webhook
   ✗ WRONG:     https://xxxx-xxxx.ngrok.io (missing path)
   ✗ WRONG:     http://xxxx-xxxx.ngrok.io (must be https)

3. After configuration:
   - Keep ngrok running
   - Keep backend running  
   - Messages should now flow in automatically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    def show_testing_guide(self):
        """Show detailed testing guide"""
        self.print_step(5, "Testing Both Sending and Receiving")
        
        print("""
┌─ TESTING CHECKLIST ───────────────────────────────────────────────────────────┐
│                                                                                  │
│  ✅ SENDING VERIFICATION:                                                      │
│                                                                                  │
│  1. Backend is running:                                                        │
│     - Check: netstat -ano | findstr "8000"                                    │
│     - Should see: TCP 0.0.0.0:8000 LISTENING                                  │
│                                                                                  │
│  2. Send test message:                                                         │
│     python send_message.py menu                                               │
│     - Should see: "✅ Sent! Message ID: ..."                                   │
│                                                                                  │
│  3. Check WhatsApp:                                                            │
│     - Go to WhatsApp on phone/web                                              │
│     - Open chat with the bot number                                            │
│     - Should see menu/text messages                                            │
│                                                                                  │
│  ✅ RECEIVING VERIFICATION:                                                    │
│                                                                                  │
│  1. Ngrok is running:                                                          │
│     - Open separate terminal                                                    │
│     - Run: ngrok http 8000                                                     │
│     - Note the forwarding URL                                                  │
│                                                                                  │
│  2. Webhook is configured:                                                     │
│     - Go to Meta Dashboard                                                      │
│     - Check webhook URL shows your ngrok URL                                  │
│     - Status should show "Active"                                              │
│                                                                                  │
│  3. Send message FROM WhatsApp:                                                │
│     - Go to WhatsApp chat with bot                                             │
│     - Type: "hi"                                                               │
│     - Wait 2-3 seconds                                                         │
│                                                                                  │
│  4. Check backend logs:                                                        │
│     - Look at terminal where backend is running                                │
│     - Should see:                                                              │
│       "WhatsApp send accepted type=text to=91..."                             │
│       or                                                                        │
│       "WhatsApp status delivered/sent for message=..."                         │
│                                                                                  │
│  5. Receive response:                                                          │
│     - In WhatsApp, you should get back:                                        │
│       "Program menu" with button options                                       │
│                                                                                  │
│  ✅ FULL CONVERSATION TEST:                                                    │
│                                                                                  │
│  1. Send "hi" → Receive program menu                                           │
│  2. Reply "1" or select "CMA" → Receive mode menu                              │
│  3. Reply "2" or select "Doubt Solving" → Get prompt to ask question          │
│  4. Ask question → Get AI answer from Claude                                   │
│  5. Ask another question → Continue conversation                               │
│  6. Send "menu" → Reset and show program menu again                            │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
""")

    def show_backend_logs_guide(self):
        """Show how to check backend logs"""
        self.print_step(6, "Monitoring Backend Logs")
        
        print("""
┌─ BACKEND LOGS ────────────────────────────────────────────────────────────────┐
│                                                                                  │
│  Look for these messages in the terminal where backend is running:             │
│                                                                                  │
│  ✓ INCOMING MESSAGE:                                                           │
│    "WhatsApp message from sender=91xxxxx text='hi' type=text"                 │
│    "WhatsApp send accepted type=text to=91xxxxx response={...}"               │
│                                                                                  │
│  ✓ MESSAGE DELIVERY:                                                           │
│    "WhatsApp status delivered for message=xxxxx recipient=91xxxxx"            │
│    "WhatsApp status sent for message=xxxxx recipient=91xxxxx"                 │
│                                                                                  │
│  ✓ SESSION PROCESSING:                                                         │
│    "Processing message from whatsapp:91xxxxx"                                 │
│    "Session state: program=CMA mode=doubt_solving"                            │
│                                                                                  │
│  ✗ ERRORS TO WATCH FOR:                                                        │
│    "WhatsApp webhook signature verification failed"                           │
│    → Check: WHATSAPP_APP_SECRET in .env                                       │
│                                                                                  │
│    "Failed to connect to Redis"                                               │
│    → Check: Redis is running                                                   │
│                                                                                  │
│    "Invalid WhatsApp verify token"                                            │
│    → Check: Token in Meta dashboard matches .env                              │
│                                                                                  │
│    "Claude API error"                                                          │
│    → Check: ANTHROPIC_API_KEY is valid                                        │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
""")

    def show_troubleshooting(self):
        """Show comprehensive troubleshooting guide"""
        self.print_step(7, "Troubleshooting Guide")
        
        print("""
┌─ TROUBLESHOOTING ─────────────────────────────────────────────────────────────┐
│                                                                                  │
│  PROBLEM: Messages not sending                                                │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Check backend is running: netstat -ano | findstr "8000"                 │
│    2. Verify .env has WHATSAPP_ACCESS_TOKEN                                   │
│    3. Check WHATSAPP_PHONE_NUMBER_ID is correct                               │
│    4. Run: python test_whatsapp_send.py (for detailed error)                  │
│                                                                                  │
│  PROBLEM: Webhook verification failing                                        │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Ensure backend is running: python -m uvicorn ...                        │
│    2. Check ngrok is tunneling to 8000: ngrok http 8000                       │
│    3. Verify token EXACTLY matches in Meta dashboard                          │
│    4. Check backend logs for error messages                                    │
│    5. Try webhook verification again in Meta dashboard                        │
│                                                                                  │
│  PROBLEM: Not receiving messages from WhatsApp                                │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Check ngrok is running and connected                                    │
│    2. Verify webhook URL in Meta is correct (with /v1/whatsapp/webhook)      │
│    3. Check "messages" is subscribed in Meta webhook events                   │
│    4. Restart both backend and ngrok                                          │
│    5. Check backend logs for incoming requests                                │
│                                                                                  │
│  PROBLEM: Messages received but no response                                   │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Check Redis is running: redis-cli ping                                  │
│    2. Check Claude API key: python -c "import anthropic; ..."                 │
│    3. Check Qdrant vector store is accessible                                 │
│    4. Look at backend error logs for detailed message                         │
│                                                                                  │
│  PROBLEM: ngrok keeps disconnecting                                           │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Create free ngrok account: https://ngrok.com                            │
│    2. Add auth token: ngrok config add-authtoken YOUR_TOKEN                   │
│    3. Use: ngrok http --region=us 8000 (for better stability)                │
│    4. Keep terminal open and don't close ngrok                                │
│                                                                                  │
│  PROBLEM: "Invalid WhatsApp webhook signature"                                │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Check WHATSAPP_APP_SECRET in .env                                       │
│    2. Compare with Meta dashboard app secret                                  │
│    3. They must match exactly                                                  │
│    4. Restart backend after changing .env                                     │
│                                                                                  │
│  PROBLEM: "Redis connection error"                                            │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Check REDIS_URL in .env                                                 │
│    2. Ensure Redis server is running                                          │
│    3. Try: redis-cli ping (should respond PONG)                               │
│    4. For Docker: docker ps (check redis container)                           │
│                                                                                  │
│  PROBLEM: Getting "Claude API error"                                          │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Check ANTHROPIC_API_KEY in .env is valid                                │
│    2. Verify key starts with "sk-ant-"                                        │
│    3. Check your Claude API account has credits                               │
│    4. Test API manually: python test_claude_api.py                            │
│                                                                                  │
│  PROBLEM: Webhook URL keeps showing as "inactive"                             │
│  ────────────────────────────────────────────────────────────────────────────  │
│  Solutions:                                                                     │
│    1. Verify backend is actually running                                      │
│    2. Check ngrok URL is correct in Meta dashboard                            │
│    3. Full URL should be: https://YOUR-NGROK.ngrok.io/v1/whatsapp/webhook   │
│    4. Don't add trailing slashes                                              │
│    5. Click "Verify and Save" again in Meta dashboard                         │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
""")

    def show_complete_summary(self):
        """Show complete setup summary"""
        self.print_header("COMPLETE WHATSAPP SETUP - SUMMARY")
        
        print("""
╔════════════════════════════════════════════════════════════════════════════════╗
║                    WHATSAPP INTEGRATION COMPLETE GUIDE                         ║
╚════════════════════════════════════════════════════════════════════════════════╝

YOUR SETUP CONSISTS OF 3 MAIN COMPONENTS:

1. BACKEND SERVER (Already Running ✓)
   └─ FastAPI on localhost:8000
   └─ Handles WhatsApp webhooks
   └─ Processes messages with Claude AI
   
2. PUBLIC TUNNEL (You need to setup)
   └─ ngrok (or Cloudflare Tunnel)
   └─ Makes localhost:8000 publicly accessible
   └─ Provides HTTPS URL for webhooks
   
3. META WEBHOOK CONFIGURATION (You need to configure)
   └─ Points to your tunnel URL
   └─ Meta sends messages to your server
   └─ Your server responds with answers

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUICK START CHECKLIST:

☐ 1. BACKEND SERVER:
     ✓ Already running on port 8000
     ✓ Check: netstat -ano | findstr "8000"
     ✓ If stopped, run: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

☐ 2. SETUP NGROK:
     □ Download from: https://ngrok.com/download
     □ Extract ngrok.exe to a folder
     □ Open new terminal
     □ Run: ngrok http 8000
     □ Copy the forwarding URL (https://xxxx-xxxx.ngrok.io)
     □ KEEP THIS TERMINAL OPEN!

☐ 3. CONFIGURE META WEBHOOK:
     □ Go to: https://developers.facebook.com/apps
     □ Select your WhatsApp app
     □ Navigate to: WhatsApp → Configuration
     □ Webhook URL: https://your-ngrok-url/v1/whatsapp/webhook
     □ Verify Token: {verify_token_display}
     □ Click: Verify and Save
     □ Subscribe to: messages, message_status

☐ 4. TEST SENDING:
     □ Run: python send_message.py menu
     □ Check WhatsApp for menu
     □ Verify messages appear

☐ 5. TEST RECEIVING:
     □ Open WhatsApp chat with bot
     □ Send: "hi"
     □ Should receive program menu
     □ Select program → Select mode → Ask question
     □ Should get AI answer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TERMINAL WINDOWS YOU NEED:

Terminal 1: Backend Server (Already Running)
   $ python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   Keep this running! Shows: "Application startup complete"

Terminal 2: ngrok Tunnel
   $ ngrok http 8000
   Keep this running! Shows: "Forwarding https://xxxx.ngrok.io -> http://127.0.0.1:8000"

Terminal 3: Testing (Optional)
   $ python send_message.py menu
   $ python test_whatsapp_integration.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXPECTED FLOW:

User sends WhatsApp message
        ↓
Meta sends to: https://your-ngrok.ngrok.io/v1/whatsapp/webhook
        ↓
ngrok forwards to: http://localhost:8000/v1/whatsapp/webhook
        ↓
Backend processes and queries Claude AI
        ↓
Backend sends response back to Meta
        ↓
User receives message in WhatsApp

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY ENVIRONMENT VARIABLES (Already Set in .env):

WHATSAPP_ACCESS_TOKEN=...           ✓ Your Meta API token
WHATSAPP_PHONE_NUMBER_ID=...        ✓ Your WhatsApp Business phone ID
WHATSAPP_VERIFY_TOKEN=...           ✓ Webhook verification token
WHATSAPP_APP_SECRET=...             ✓ For signature verification
WHATSAPP_GRAPH_BASE=...             ✓ Meta Graph API endpoint
ANTHROPIC_API_KEY=...               ✓ Claude AI API key
REDIS_URL=...                       ✓ Session cache
QDRANT_URL=...                      ✓ Vector database

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONTACT FOR TESTING:

WhatsApp Bot Number: +91 9916039894

Send a message and you should:
1. Receive program menu (CMA, CPA, ACCA, EA)
2. Select program
3. Receive learning mode menu
4. Select mode
5. Ask any question
6. Get AI-powered answer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TESTING COMMANDS:

# Send program menu
python send_message.py menu

# Send custom text
python send_message.py text "Testing message"

# Send mode menu
python send_message.py mode CMA

# Run full integration test
python test_whatsapp_integration.py

# Run comprehensive test
python test_whatsapp_send.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT: Follow the steps below in order!

""".format(verify_token_display=self.settings.whatsapp_verify_token[:20] + "..."))

    async def run_setup(self):
        """Run complete setup"""
        self.print_header("AI MENTOR - COMPLETE WHATSAPP SETUP")
        
        # Step 1: Verify backend
        print("\n📋 STEP 1: Verifying Backend...\n")
        if not await self.verify_backend():
            print("\n❌ SETUP CANNOT CONTINUE: Backend must be running!")
            print("   Start backend with: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload")
            return False
        
        # Step 2: Test sending
        print("\n📋 STEP 2: Testing Message Sending...\n")
        if not await self.test_sending():
            print("\n⚠️  Sending test failed, but we'll continue with setup instructions")
        
        # Step 3: Show ngrok setup
        self.show_ngrok_setup()
        
        # Step 4: Show Meta configuration
        self.show_meta_configuration()
        
        # Step 5: Show testing guide
        self.show_testing_guide()
        
        # Step 6: Show logs guide
        self.show_backend_logs_guide()
        
        # Step 7: Show troubleshooting
        self.show_troubleshooting()
        
        # Summary
        self.show_complete_summary()
        
        return True

async def main():
    manager = WhatsAppSetupManager()
    success = await manager.run_setup()
    
    if success:
        print("\n" + "="*80)
        print("✅ SETUP INSTRUCTIONS DISPLAYED")
        print("="*80)
        print("\nFOLLOW THE STEPS ABOVE TO COMPLETE YOUR SETUP!")
        print("\nKey steps:")
        print("  1. Download and run ngrok")
        print("  2. Configure Meta webhook")
        print("  3. Test with WhatsApp")
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
