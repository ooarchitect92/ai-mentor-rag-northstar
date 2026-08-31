# Complete WhatsApp Setup - Step by Step

## 📋 System Status

✅ Backend Server: Running on port 8000
✅ Message Sending: Working and tested  
⏳ Message Receiving: Needs webhook configuration
✅ All environment variables: Configured in .env

---

## 🎯 What We Need to Do

To enable **both sending AND receiving** WhatsApp messages, we need to:

1. **Expose your local server publicly** using ngrok
2. **Configure Meta/Facebook webhook** to point to your public URL
3. **Test the complete flow**

---

## STEP-BY-STEP SETUP

### STEP 1: Download and Setup ngrok

**What is ngrok?**
- Tool that creates a secure tunnel from your local computer to the internet
- Converts http://localhost:8000 to https://public-url.ngrok.io
- Meta can then send webhooks to your public URL

**Installation:**

1. **Download ngrok:**
   - Go to: https://ngrok.com/download
   - Download version for Windows
   - Extract the ZIP file to a folder (e.g., C:\ngrok\)

2. **Add ngrok to your system PATH (Optional but recommended):**
   - Right-click "This PC" → Properties
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Under "User variables", click "New"
   - Variable name: `PATH` (if not exists)
   - Variable value: Add `C:\ngrok\` (or wherever you extracted)
   - Click OK

3. **Create ngrok account (Optional but recommended):**
   - Go to: https://ngrok.com/signup
   - Sign up with email/Google
   - Go to dashboard and copy your authtoken
   - Open terminal and run:
     ```bash
     ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
     ```
   - This unlocks better features and longer tunnel duration

---

### STEP 2: Start ngrok Tunnel

**Important: Keep ngrok running while testing!**

1. **Open a NEW terminal/PowerShell** (keep your current backend terminal open)

2. **Navigate to ngrok folder** (if not in PATH):
   ```bash
   cd C:\ngrok\
   ```

3. **Start the tunnel:**
   ```bash
   ngrok http 8000
   ```

4. **You should see output like:**
   ```
   ngrok by @inconshrevable                          (Ctrl+C to quit)

   Session Status                online
   Account                       yourname@email.com
   Version                       3.x.x
   Region                        us
   Latency                       45ms
   Web Interface                 http://127.0.0.1:4040
   Forwarding                    https://1234-56-789-10.ngrok.io -> http://127.0.0.1:8000

   Connections                   ttl     opn     dl      in      out
                                 0       0       0       0B      0B
   ```

5. **Copy your ngrok URL:**
   ```
   https://1234-56-789-10.ngrok.io
   ```
   (Your actual URL will be different)

6. **Test the tunnel:**
   - Open in browser: https://1234-56-789-10.ngrok.io/health
   - Should see JSON response
   - If you see an error, backend might be down

**IMPORTANT: Keep this terminal open! Your tunnel will disconnect if you close it.**

---

### STEP 3: Configure Meta/Facebook App Webhook

**This is the most important step!**

#### 3.1: Go to Meta Developer Dashboard

1. **Open:**
   - https://developers.facebook.com/apps
   - Login with your Meta/Facebook account

2. **Select your app:**
   - Find and click on your WhatsApp app
   - If you don't have one, create one

#### 3.2: Navigate to Webhook Settings

1. **Find WhatsApp section:**
   - Left sidebar: Products → WhatsApp
   - Or look for "Configuration" tab

2. **Look for "Webhooks" or "Configuration" section**

#### 3.3: Set Webhook URL

1. **Find "Webhook URL" field**

2. **Delete any existing content**

3. **Paste your ngrok URL with the webhook path:**
   ```
   https://1234-56-789-10.ngrok.io/v1/whatsapp/webhook
   ```

   **Important:** 
   - Replace `1234-56-789-10` with YOUR ngrok URL
   - Include `/v1/whatsapp/webhook` path
   - Must use HTTPS (not HTTP)
   - No trailing slash at the end

#### 3.4: Set Verify Token

1. **Find "Verify Token" field**

2. **Delete any existing content**

3. **Paste this token:**
   ```
   generate-a-long-random-verify-token
   ```

   This token is configured in your .env file and backend will respond with it.

#### 3.5: Save Webhook

1. **Click "Verify and Save"** or **"Save"**

2. **What happens next:**
   - Meta sends a GET request to your webhook URL
   - Your backend receives it and responds with the verify token
   - Meta confirms the webhook works
   - You should see a success message

3. **If you see errors:**
   - Check that ngrok is running and connected
   - Check that the URL is correct
   - Check that the verify token matches exactly
   - Look at your backend logs for error messages

#### 3.6: Subscribe to Webhook Events

1. **Look for "Subscribe to this webhook" section**

2. **Enable these events:**
   - ☑ **messages** (for incoming messages)
   - ☑ **message_status** (for delivery status)
   - Optional: message_template_status_update

3. **Make sure these fields are subscribed:**
   - ☑ messages.new_messages
   - ☑ messages.message_received
   - ☑ messages.message_sent
   - ☑ messages.message_delivered
   - ☑ messages.message_read

4. **Click Save**

---

### STEP 4: Verify Everything is Connected

**After configuring webhook:**

1. **Check ngrok shows activity:**
   - Watch the terminal where ngrok is running
   - You should see POST requests coming in

2. **Check backend logs:**
   - Look at the terminal where backend is running
   - Should show messages being processed

3. **Check Meta dashboard:**
   - Go back to webhook settings
   - Status should show "Active" or "Verified"
   - Shows when last request was received

---

### STEP 5: Test Sending Messages

**Verify sending still works:**

```bash
# In a new terminal, run:
python send_message.py menu

# You should see:
# ✅ Sent! Message ID: ...
```

**Check WhatsApp:**
- Open WhatsApp
- Look at chat with bot (+91 9916039894)
- You should see the menu message appear

---

### STEP 6: Test Receiving Messages

**Now test that receiving works:**

1. **Open WhatsApp** on your phone or web

2. **Send a message to the bot:**
   - Start a conversation with the bot number
   - Type: "hi"

3. **Watch the flow:**
   - In ngrok terminal: Should see POST request
   - In backend terminal: Should see message processing logs
   - In WhatsApp: Should receive program menu back

4. **Complete interaction:**
   - Select program (1-4 or tap option)
   - Select learning mode (1-5 or tap option)  
   - Ask a question
   - Get AI answer from Claude

---

## 🧪 Testing Commands

Once everything is set up, use these to test:

```bash
# Send program menu
python send_message.py menu

# Send text message
python send_message.py text "Your message"

# Send learning mode menu
python send_message.py mode CMA

# Run full integration test
python test_whatsapp_integration.py

# Run comprehensive test
python test_whatsapp_send.py
```

---

## 📊 Terminal Windows You Need

Keep these 3 terminals open during testing:

### Terminal 1: Backend Server
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Status: Should show "Application startup complete"

### Terminal 2: ngrok Tunnel  
```bash
ngrok http 8000
```
Status: Should show "Session Status online" and your forwarding URL

### Terminal 3: Testing (Optional)
```bash
python send_message.py menu
python test_whatsapp_integration.py
# etc
```

---

## 🔍 What to Look For in Logs

### Backend Terminal (Terminal 1)

**Success messages:**
```
INFO: "WhatsApp send accepted type=text to=919916039894"
INFO: "WhatsApp status delivered for message=..."
INFO: "Processing message from whatsapp:919916039894"
```

**Error messages to fix:**
```
ERROR: "WhatsApp webhook signature verification failed"
→ Fix: Check WHATSAPP_APP_SECRET in .env

ERROR: "Invalid WhatsApp verify token"  
→ Fix: Check verify token in Meta dashboard matches .env

ERROR: "Failed to connect to Redis"
→ Fix: Ensure Redis is running

ERROR: "Claude API error"
→ Fix: Check ANTHROPIC_API_KEY is valid
```

### ngrok Terminal (Terminal 2)

**Good signs:**
```
200 POST /v1/whatsapp/webhook      (incoming message)
200 GET /v1/whatsapp/webhook       (verification)
```

**Bad signs:**
```
404 errors → Webhook URL path is wrong
503 errors → Backend not responding
Connection refused → Backend is down
```

---

## ⚠️ Common Issues and Fixes

### Issue: "Webhook URL verification failed"

**Causes:**
1. Backend not running
2. ngrok not running or disconnected
3. ngrok URL changed (happens when you restart)
4. Verify token doesn't match

**Fix:**
```
1. Check backend: netstat -ano | findstr "8000"
2. Check ngrok: Look at ngrok terminal for "Session Status online"
3. If ngrok restarted, update URL in Meta dashboard
4. Verify token must match the long random value configured in your environment.
5. Click "Verify and Save" again
```

### Issue: "Not receiving messages"

**Causes:**
1. Webhook not verified
2. Messages event not subscribed
3. ngrok disconnected
4. Backend crashed

**Fix:**
```
1. Check Meta dashboard: webhook status should show "Active"
2. Check subscriptions: "messages" should be enabled
3. Check ngrok terminal: Should show "Session Status online"
4. Restart backend and ngrok
5. Re-verify webhook in Meta dashboard
```

### Issue: "Messages received but no response"

**Causes:**
1. Redis not running (session cache)
2. Claude API key invalid
3. Vector database not accessible
4. Backend error in processing

**Fix:**
```
1. Check Redis: redis-cli ping (should respond PONG)
2. Check Claude key: Verify ANTHROPIC_API_KEY is valid
3. Check Qdrant: Verify QDRANT_URL in .env is accessible
4. Look at backend logs for error messages
5. Run test_whatsapp_send.py for detailed diagnostics
```

### Issue: "ngrok keeps disconnecting"

**Causes:**
1. Internet connection unstable
2. Free ngrok account has time limits
3. Running multiple ngrok sessions

**Fix:**
```
1. Create ngrok account: https://ngrok.com
2. Add auth token: ngrok config add-authtoken TOKEN
3. Use paid plan for longer sessions
4. Close other ngrok sessions
5. Run: ngrok http --region=us 8000 (for better stability)
```

---

## ✅ Complete Checklist

- [ ] ngrok downloaded and installed
- [ ] ngrok account created and auth token added
- [ ] ngrok tunnel started (`ngrok http 8000`)
- [ ] ngrok shows "Session Status online"
- [ ] Copied ngrok URL (https://...)
- [ ] Backend running on port 8000
- [ ] Backend responds to health check
- [ ] Logged into Meta Developer Dashboard
- [ ] Found WhatsApp app in dashboard
- [ ] Webhook URL set to: https://your-ngrok/v1/whatsapp/webhook
- [ ] Verify token set correctly
- [ ] Clicked "Verify and Save" successfully
- [ ] Subscribed to "messages" event
- [ ] Subscribed to "message_status" event
- [ ] Field subscriptions enabled (new_messages, etc.)
- [ ] Meta dashboard shows webhook as "Active"
- [ ] Tested sending: `python send_message.py menu`
- [ ] Received message in WhatsApp
- [ ] Tested receiving: Sent "hi" to bot
- [ ] Received program menu back
- [ ] Completed full conversation flow

---

## 📱 Phone Number for Testing

**WhatsApp Bot Number:** +91 9916039894

Send a message and expect:
1. Program menu appears
2. Select program
3. Mode menu appears
4. Select mode
5. Get prompt to ask question
6. Ask any question
7. Get AI answer

---

## 🎯 Next Steps

1. **If you haven't already:**
   - Download and setup ngrok
   - Create ngrok account (free)
   - Add auth token

2. **Start ngrok:**
   ```bash
   ngrok http 8000
   ```

3. **Configure Meta webhook:**
   - Go to https://developers.facebook.com/apps
   - Find your WhatsApp app
   - Set webhook URL and verify token
   - Subscribe to events

4. **Test:**
   - Send message: `python send_message.py menu`
   - Receive message: Send "hi" to bot in WhatsApp
   - Complete conversation

5. **Keep running:**
   - Terminal 1: Backend
   - Terminal 2: ngrok
   - Check logs for activity

---

## 🆘 Need Help?

Check these resources:

1. **Backend logs** - Shows what's happening
2. **ngrok dashboard** - Shows tunneling activity
3. **Meta dashboard** - Shows webhook status
4. **test_whatsapp_send.py** - Detailed diagnostics
5. **test_whatsapp_integration.py** - Full system test

---

**Status: Everything Ready!**
Just need to complete webhook configuration and you'll have full send/receive working! 🚀
