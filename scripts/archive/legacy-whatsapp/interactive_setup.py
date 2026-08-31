#!/usr/bin/env python3
"""
Interactive WhatsApp Setup Checklist
Guides you through the complete setup process
"""
import time
import sys

def print_banner(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_section(title):
    print(f"\n{'─'*80}")
    print(f"  {title}")
    print("─"*80)

def print_task(num, task, completed=False):
    status = "✅" if completed else "☐"
    print(f"  {status} {num}. {task}")

def print_code_block(code):
    print(f"\n  $ {code}\n")

def pause():
    input("  Press ENTER to continue...")

def show_setup_checklist():
    """Show interactive setup checklist"""
    
    print_banner("WHATSAPP SEND & RECEIVE - INTERACTIVE SETUP")
    
    completed_steps = 0
    total_steps = 3
    
    # PHASE 1: ngrok Setup
    print_section("PHASE 1: Download & Setup ngrok (5 minutes)")
    
    print("""
  This phase gets your local server accessible from the internet.
  
  What you'll do:
  1. Download ngrok (small executable)
  2. Create a free ngrok account
  3. Configure authentication
  4. Start the tunnel
""")
    
    pause()
    
    print_section("PHASE 1A: Download ngrok")
    print("""
  1. Open browser and go to: https://ngrok.com/download
  2. Download the version for Windows (ngrok-v3-stable-windows-amd64.zip)
  3. Extract the ZIP file (you get ngrok.exe)
  4. Remember the folder path
  
  Examples:
  - C:\\ngrok\\
  - C:\\Users\\YourName\\Downloads\\ngrok\\
  - C:\\Program Files\\ngrok\\
""")
    
    pause()
    
    print_section("PHASE 1B: Create ngrok Account (Recommended)")
    print("""
  1. Open: https://ngrok.com/signup
  2. Sign up with email or Google account
  3. Check email for verification
  4. Login to dashboard
  5. Copy your authtoken (looks like: YOUR_VERY_LONG_TOKEN)
""")
    
    pause()
    
    print_section("PHASE 1C: Configure ngrok")
    print("""
  1. Open a new PowerShell/Terminal
  2. Navigate to ngrok folder:
""")
    print_code_block("cd C:\\ngrok\\")
    print("""
  3. Configure with your auth token:
""")
    print_code_block("ngrok config add-authtoken YOUR_AUTH_TOKEN")
    print("""
     (Replace YOUR_AUTH_TOKEN with actual token from dashboard)
  
  4. Verify configuration:
""")
    print_code_block("ngrok --version")
    print("""
     Should show: ngrok version 3.x.x
""")
    
    pause()
    
    print_section("PHASE 1D: Start ngrok Tunnel ⭐ KEEP RUNNING")
    print("""
  1. In the same terminal, run:
""")
    print_code_block("ngrok http 8000")
    print("""
  2. You should see output:
  
     Session Status                online
     Account                       yourname@email.com
     Version                       3.x.x
     Region                        us
     Web Interface                 http://127.0.0.1:4040
     Forwarding                    https://XXXX-XXXX.ngrok.io -> http://127.0.0.1:8000
  
  3. YOUR NGROK URL IS: https://XXXX-XXXX.ngrok.io
     (Copy this, you'll need it in Phase 2)
  
  ⭐ IMPORTANT: Keep this terminal window OPEN!
     If you close it, the tunnel stops and webhook breaks!
  
  To check if working:
""")
    print_code_block("# In browser, open: https://XXXX-XXXX.ngrok.io/health")
    print("""
     Should show JSON with status info
""")
    
    pause()
    
    completed_steps += 1
    
    # PHASE 2: Meta Configuration
    print_section("PHASE 2: Configure Meta/Facebook Webhook (10 minutes)")
    
    print(f"""
  This phase connects Meta to your server using ngrok URL.
  
  ⚠️  REMEMBER: Your ngrok URL from Phase 1
""")
    
    pause()
    
    print_section("PHASE 2A: Access Meta Developer Dashboard")
    print("""
  1. Open browser: https://developers.facebook.com/apps
  2. Login with your Meta/Facebook account
  3. Find and select your WhatsApp app
     (If you don't have one, create one first)
  4. You should see WhatsApp in the product list
""")
    
    pause()
    
    print_section("PHASE 2B: Find Webhook Configuration")
    print("""
  1. In left menu: Products → WhatsApp
  2. Look for "Configuration" section
     (It may also be called "Webhooks" or "Settings")
  3. Find these fields:
     - Webhook URL
     - Verify Token
""")
    
    pause()
    
    print_section("PHASE 2C: Configure Webhook URL")
    print("""
  1. Find "Webhook URL" field
  2. Clear any existing content
  3. Paste your ngrok URL with path:
""")
    print("""
  https://YOUR-NGROK-URL.ngrok.io/v1/whatsapp/webhook
  
  Example (your URL will be different):
  https://1234-56-789-10.ngrok.io/v1/whatsapp/webhook
  
  ⚠️  IMPORTANT:
  ✓ Must start with HTTPS (not HTTP)
  ✓ Must include /v1/whatsapp/webhook path
  ✓ No trailing slash at end
  ✓ Replace YOUR-NGROK-URL with your actual URL
""")
    
    pause()
    
    print_section("PHASE 2D: Configure Verify Token")
    print("""
  1. Find "Verify Token" field
  2. Clear any existing content
  3. Paste this token:
""")
    print("""
  generate-a-long-random-verify-token
  
  This token is configured in your backend.
  When Meta verifies, your backend responds with this token.
""")
    
    pause()
    
    print_section("PHASE 2E: Verify and Save ⭐ IMPORTANT STEP")
    print("""
  1. Click "Verify and Save" (or "Save" button)
  2. Meta will send a test GET request to your webhook
  3. Your backend will respond with the token
  4. You should see: "Webhook verified successfully"
  
  If you see an error:
  ✓ Check that backend is running on port 8000
  ✓ Check that ngrok is running and shows "online"
  ✓ Check that URL is correct (no typos)
  ✓ Check that verify token matches EXACTLY
  ✓ Try clicking "Verify and Save" again
  ✓ Look at backend logs for error messages
""")
    
    pause()
    
    print_section("PHASE 2F: Subscribe to Webhook Events ⭐ REQUIRED")
    print("""
  1. Look for "Subscribe to this webhook" section
  2. Make sure these are ENABLED (checked):
     ☑ messages
     ☑ message_status
     ☑ (optional) message_template_status_update
  
  3. Optionally configure field subscriptions:
     ☑ messages.new_messages
     ☑ messages.message_received
     ☑ messages.message_sent
     ☑ messages.message_delivered
     ☑ messages.message_read
  
  4. Click "Save" or "Update"
  
  Verify: Return to webhook config, status should show "Active"
""")
    
    pause()
    
    completed_steps += 1
    
    # PHASE 3: Testing
    print_section("PHASE 3: Test Send & Receive (10 minutes)")
    
    print("""
  Now that everything is configured, let's test it!
  
  You should have 3 windows open:
  1. Terminal with BACKEND running (port 8000)
  2. Terminal with NGROK running (tunnel open)
  3. Terminal for TESTING (where you run commands)
""")
    
    pause()
    
    print_section("PHASE 3A: Test Sending Messages")
    print("""
  1. Open a 3rd terminal (keep backend & ngrok running!)
  2. Navigate to project folder:
""")
    print_code_block("cd C:\\Users\\anant\\OneDrive\\Pictures\\ai-mentor-rag-northstar\\ai-mentor-rag-northstar")
    print("""
  3. Send a test message:
""")
    print_code_block("python send_message.py menu")
    print("""
  4. You should see:
     ✅ Sent! Message ID: wamid.HBgM...
  
  5. Check WhatsApp:
     Open WhatsApp chat with bot (+91 9916039894)
     Should see a program menu appear
""")
    
    pause()
    
    print_section("PHASE 3B: Test Receiving Messages")
    print("""
  Now test that incoming messages work!
  
  1. Watch ngrok terminal
     You should see: POST /v1/whatsapp/webhook 200
  
  2. Watch backend terminal
     You should see: "WhatsApp send accepted type=text"
  
  3. In WhatsApp, send a message to bot:
     Send: "hi"
  
  4. In ngrok terminal you should see request coming in
  
  5. In backend terminal you should see:
     "Processing message from whatsapp:..."
     "WhatsApp send accepted type=..."
  
  6. In WhatsApp you should get back:
     [Program selection menu]
""")
    
    pause()
    
    print_section("PHASE 3C: Test Full Conversation Flow")
    print("""
  Complete a full conversation to verify everything works:
  
  You:     "hi" (or send any greeting)
  Bot:     [Program menu with 4 options]
  
  You:     "1" (or tap CMA)
  Bot:     [Mode menu with 5 options]
  
  You:     "2" (or tap Doubt Solving)
  Bot:     "Send your question now."
  
  You:     "What is standard costing?"
  Bot:     [AI answer with sources] 🎉
  
  You:     "What is marginal costing?"
  Bot:     [Another AI answer] 🎉
  
  You:     "menu"
  Bot:     [Back to program menu] ✅
  
  If everything works, setup is complete! 🎉
""")
    
    pause()
    
    completed_steps += 1
    
    # Summary
    print_banner("SETUP COMPLETE!")
    
    print(f"""
  ✅ Phase 1: ngrok Tunnel (10 min)
  ✅ Phase 2: Meta Webhook Config (10 min)
  ✅ Phase 3: Testing & Verification (10 min)
  
  Total time: ~30 minutes
  
  Your system now has:
  ✓ Local backend server on http://localhost:8000
  ✓ Public tunnel via ngrok to https://your-ngrok.ngrok.io
  ✓ Meta webhook configured and verified
  ✓ Message sending WORKING
  ✓ Message receiving WORKING
  
  Key commands to remember:
  
  $ ngrok http 8000              # Start tunnel (Terminal 1)
  $ python -m uvicorn ...        # Start backend (Terminal 2)
  $ python send_message.py menu  # Send test (Terminal 3)
  
  Bot number: +91 9916039894
  
  Keep ngrok and backend running while testing!
  
  Happy coding! 🚀
""")

if __name__ == "__main__":
    show_setup_checklist()
    print("\n" + "="*80)
    print("  Setup guide complete. You can now follow the steps!")
    print("="*80 + "\n")
