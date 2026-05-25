# 🚀 WHATSAPP SEND & RECEIVE - COMPLETE SETUP

## ✅ Current Status

| Component | Status | Details |
|-----------|--------|---------|
| **Sending** | ✅ WORKING | Messages successfully sent to +91 9916039894 |
| **Backend Server** | ✅ RUNNING | Port 8000, ready to receive webhooks |
| **Configuration** | ✅ COMPLETE | All .env variables set |
| **Receiving** | ⏳ SETUP NEEDED | Needs ngrok + Meta webhook configuration |

---

## 🎯 SIMPLE 3-STEP SETUP

### STEP 1️⃣: Setup ngrok (5 minutes)

**A. Download:**
- Go to https://ngrok.com/download
- Download for Windows
- Extract the ZIP file

**B. Setup Account (Recommended):**
- Go to https://ngrok.com/signup
- Create free account
- Copy your auth token from dashboard

**C. Configure ngrok:**
```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

**D. Start tunnel (KEEP RUNNING):**
```bash
ngrok http 8000
```

**You should see:**
```
Forwarding    https://XXXX-XXXX.ngrok.io -> http://127.0.0.1:8000
```

✅ **Copy this URL** (you'll need it in Step 2)

---

### STEP 2️⃣: Configure Meta Webhook (5 minutes)

**A. Go to Meta Dashboard:**
- https://developers.facebook.com/apps
- Login with your Meta account
- Select your WhatsApp app

**B. Find Webhook Settings:**
- Left menu: WhatsApp > Configuration
- Look for "Webhooks" section

**C. Set Webhook URL:**
- Field: "Webhook URL"
- Paste: `https://YOUR-NGROK-URL.ngrok.io/v1/whatsapp/webhook`
- Replace YOUR-NGROK-URL with your actual ngrok URL from Step 1

**D. Set Verify Token:**
- Field: "Verify Token"
- Paste: `97acdd2ec2eebbe7ca34b83cde9b36fb718a75df64851289445ba3d74bfc3f99`

**E. Click "Verify and Save"**
- Meta will test your webhook
- Should see "Webhook verified successfully"
- If error → Check backend is running, ngrok is connected, URL is correct

**F. Subscribe to Events:**
- Check: ✅ messages
- Check: ✅ message_status
- Click Save

---

### STEP 3️⃣: Test Send & Receive (2 minutes)

**Test Sending:**
```bash
python send_message.py menu
```
✅ Should see: "✅ Sent! Message ID: ..."
✅ Check WhatsApp: Should receive menu

**Test Receiving:**
1. Open WhatsApp
2. Send message to bot: "hi"
3. Should receive program menu back within 2-3 seconds

**Test Full Conversation:**
1. Reply "1" for CMA program
2. Reply "2" for Doubt Solving
3. Ask question: "What is standard costing?"
4. Should get AI answer from Claude

---

## 📋 REQUIRED TERMINALS

Keep these 3 terminals open at all times:

### Terminal 1: Backend Server
```bash
# Already running on port 8000
# If you stopped it, run:
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Status check:
```bash
netstat -ano | findstr "8000"
# Should show: TCP 0.0.0.0:8000 LISTENING
```

### Terminal 2: ngrok Tunnel
```bash
ngrok http 8000
```

Keep this window open. Shows:
```
Session Status: online
Forwarding: https://xxxx-xxxx.ngrok.io -> http://127.0.0.1:8000
```

### Terminal 3: Testing (Optional)
```bash
python send_message.py menu
python test_whatsapp_integration.py
# etc
```

---

## 🧪 QUICK TEST COMMANDS

Once everything is configured, run these to verify:

```bash
# Test 1: Send program menu
python send_message.py menu
# Expected: Message ID shown, menu appears in WhatsApp

# Test 2: Send text message
python send_message.py text "Hello test"
# Expected: Message ID shown, text appears in WhatsApp

# Test 3: Full integration test
python test_whatsapp_integration.py
# Expected: Shows configuration status and sends test messages

# Test 4: Test specific mode menu
python send_message.py mode CMA
# Expected: CMA mode menu appears in WhatsApp
```

---

## 📱 TESTING PHONE NUMBER

**WhatsApp Bot Number:** +91 9916039894

**Expected Interaction:**
```
You: Hi
Bot: [Program menu appears with 4 options]

You: 1 (or tap CMA)
Bot: [Mode menu appears with 5 options]

You: 2 (or tap Doubt Solving)
Bot: Send your question now

You: What is cost accounting?
Bot: [AI answer + sources] 🎉
```

---

## 🔄 SYSTEM FLOW

```
WhatsApp User sends message
         ↓
Meta routes to: https://xxxx-xxxx.ngrok.io/v1/whatsapp/webhook
         ↓
ngrok forwards to: http://localhost:8000/v1/whatsapp/webhook
         ↓
Backend receives message
         ↓
Backend queries Claude AI
         ↓
Backend sends response back to Meta
         ↓
User receives message in WhatsApp ✅
```

---

## ⚙️ ENVIRONMENT VARIABLES (Already Set)

These are in your `.env` file:

```
WHATSAPP_ACCESS_TOKEN=...          ✅ Meta API token
WHATSAPP_PHONE_NUMBER_ID=...       ✅ Your WhatsApp Business number
WHATSAPP_VERIFY_TOKEN=...          ✅ For webhook verification
WHATSAPP_APP_SECRET=...            ✅ For signature verification
ANTHROPIC_API_KEY=...              ✅ Claude API key
REDIS_URL=...                      ✅ Session cache
QDRANT_URL=...                     ✅ Vector database
```

All configured ✅

---

## 🔍 TROUBLESHOOTING

### ❌ "Webhook verification failed"

**Solution:**
1. ✅ Check backend is running: `netstat -ano | findstr "8000"`
2. ✅ Check ngrok is running: Watch ngrok terminal
3. ✅ Check URL is correct: `https://your-ngrok.ngrok.io/v1/whatsapp/webhook`
4. ✅ Check token matches: `97acdd2ec2eebbe7ca34b83cde9b36fb718a75df64851289445ba3d74bfc3f99`
5. ✅ Click "Verify and Save" again in Meta dashboard

### ❌ "Messages not being received"

**Solution:**
1. ✅ Check ngrok shows "Session Status: online"
2. ✅ Check "messages" is subscribed in Meta webhook events
3. ✅ Check Meta dashboard shows webhook as "Active"
4. ✅ Restart ngrok: Ctrl+C, then run again: `ngrok http 8000`
5. ✅ Check backend logs for errors

### ❌ "No response from bot"

**Solution:**
1. ✅ Check Redis is accessible (session cache needed)
2. ✅ Check Claude API key is valid
3. ✅ Check Qdrant vector database is accessible
4. ✅ Look at backend logs for error messages
5. ✅ Run: `python test_whatsapp_integration.py` for diagnostics

### ❌ "ngrok keeps disconnecting"

**Solution:**
1. ✅ Create ngrok account: https://ngrok.com
2. ✅ Add auth token: `ngrok config add-authtoken YOUR_TOKEN`
3. ✅ Use: `ngrok http --region=us 8000` for stability
4. ✅ Keep terminal open, don't minimize

---

## 📝 STEP-BY-STEP DETAILED WALKTHROUGH

### Full Setup from Scratch

**Phase 1: Preparation (10 mins)**
1. Download ngrok from https://ngrok.com/download
2. Extract to a folder (e.g., C:\ngrok\)
3. Create ngrok account at https://ngrok.com/signup
4. Get auth token from dashboard

**Phase 2: ngrok Setup (5 mins)**
1. Open new PowerShell/Terminal
2. Navigate to ngrok folder (or add to PATH)
3. Run: `ngrok config add-authtoken YOUR_TOKEN`
4. Run: `ngrok http 8000`
5. Note the forwarding URL (copy it!)

**Phase 3: Meta Configuration (10 mins)**
1. Go to https://developers.facebook.com/apps
2. Login with Meta account
3. Select WhatsApp app
4. Go to Configuration/Webhooks
5. Set Webhook URL: `https://your-ngrok.ngrok.io/v1/whatsapp/webhook`
6. Set Verify Token: `97acdd2ec2eebbe7ca34b83cde9b36fb718a75df64851289445ba3d74bfc3f99`
7. Click "Verify and Save"
8. Subscribe to: messages, message_status
9. Save and verify "Active" status

**Phase 4: Testing (5 mins)**
1. Run: `python send_message.py menu`
2. Check WhatsApp for message
3. Send "hi" to bot in WhatsApp
4. Should receive program menu back
5. Complete conversation flow

---

## 💡 PRO TIPS

1. **Keep ngrok running:** If you close it, your tunnel URL changes and webhook stops working
2. **Backend auto-reload:** Backend reloads code automatically, no need to restart
3. **Multiple terminals:** Use separate terminals for backend and ngrok, keep both open
4. **Check logs:** Look at backend terminal logs for detailed error messages
5. **Test frequently:** Use `python send_message.py menu` to verify setup

---

## ✨ KEY FEATURES AFTER SETUP

Once configured, bot supports:

✅ **Programs:**
- CMA (Certified Management Accountant)
- CPA (Certified Public Accountant)
- ACCA (Association of Chartered Certified Accountants)
- EA (Enrolled Agent)

✅ **Learning Modes:**
- Teach: Learn concepts step-by-step
- Doubt Solving: Get specific doubts cleared
- Quiz: Practice with MCQs
- Revision: Quick formulas & concepts
- Job Hunt: Resume & interview help

✅ **AI Features:**
- Claude AI powered answers
- Document references
- Session persistence
- Conversation memory

---

## 📞 QUICK REFERENCE

| What | Command/URL |
|------|------------|
| **ngrok download** | https://ngrok.com/download |
| **ngrok signup** | https://ngrok.com/signup |
| **Start ngrok** | `ngrok http 8000` |
| **Start backend** | `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload` |
| **Meta Dashboard** | https://developers.facebook.com/apps |
| **Test send** | `python send_message.py menu` |
| **Test integration** | `python test_whatsapp_integration.py` |
| **Bot number** | +91 9916039894 |

---

## 🎯 YOU'RE ALMOST THERE!

All backend infrastructure is ready. Just need to:

1. ✅ Download ngrok
2. ✅ Start ngrok tunnel
3. ✅ Configure Meta webhook
4. ✅ Test!

That's it! 🚀

---

**Last Updated:** May 23, 2026
**Status:** Ready for final configuration
