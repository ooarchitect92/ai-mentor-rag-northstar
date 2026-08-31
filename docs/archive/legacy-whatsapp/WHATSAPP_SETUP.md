# WhatsApp Integration Setup Guide

## ✅ Status

Your AI Mentor WhatsApp integration is **WORKING** and ready to use!

### What's Been Configured
- ✅ **Sending Messages**: Messages are successfully being sent to +91 9916039894
- ✅ **Backend Server**: FastAPI server running on port 8000
- ✅ **WhatsApp Credentials**: Meta API tokens and phone number ID configured
- ✅ **Message Types**: Text, Interactive (lists/buttons), and Menu support
- ✅ **Session Management**: Redis caching for user sessions
- ✅ **AI Integration**: Claude AI for answering student questions

---

## 🚀 Quick Start

### 1. **Send Messages to 9916039894**

**Messages have already been sent!** Check your WhatsApp for:
- Program selection menu (CMA, CPA, ACCA, EA)
- Learning mode menu (Teach, Doubt Solving, Quiz, Revision, Job Hunt)
- Welcome message

### 2. **Running Test Scripts**

To send messages programmatically:

```bash
# Test basic sending
python test_whatsapp_send.py

# Comprehensive integration test
python test_whatsapp_integration.py

# Send program menu to any number
python scripts/send_whatsapp_program_menu.py 919916039894
```

---

## 📥 Receiving Messages (Next Step)

To receive messages from users, you need to set up a public webhook:

### Option 1: Using ngrok (Recommended for Local Development)

1. **Download and install ngrok**: https://ngrok.com/download

2. **Start ngrok**:
   ```bash
   ngrok http 8000
   ```
   This gives you a URL like: `https://xxxx-xx-xxx-xx.ngrok.io`

3. **Configure Meta/Facebook App**:
   - Go to: https://developers.facebook.com/apps
   - Select your app → WhatsApp → Configuration
   - Set Webhook URL: `https://xxxx-xx-xxx-xx.ngrok.io/v1/whatsapp/webhook`
   - Set Verify Token to a long, randomly generated secret.
   - Subscribe to: `messages`, `message_status`

4. **Test Webhook**:
   - Meta will send a GET request to verify your webhook
   - The app will respond with the challenge token

### Option 2: Using Cloudflare Tunnel

1. **Install Cloudflare Tunnel**:
   ```bash
   # Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-applications/
   cloudflared tunnel --url http://localhost:8000
   ```

2. **Get your public URL and configure in Meta app**

### Option 3: Using Render, Railway, or Heroku

Deploy your application to a cloud platform with a public URL, then configure the webhook.

---

## 🔧 System Architecture

```
WhatsApp User
     ↓
Meta Graph API
     ↓
FastAPI Backend (/v1/whatsapp/webhook)
     ↓
WhatsApp Message Processor
     ├→ Extract message content
     ├→ Get user session (Redis)
     ├→ Process menu selections
     └→ Call Claude AI for answers
     ↓
Send Response Back to User
```

---

## 📋 Workflow

### User Journey:
1. User sends "Hi" or "Menu" → Program selection menu appears
2. User selects program (1-4) → Mode selection menu appears
3. User selects mode (1-5) → Asked to send question
4. User sends question → Claude AI generates answer with sources
5. User can reply with more questions or type "menu" to reset

### Available Modes:
- **Teach**: Learn concepts step-by-step
- **Doubt Solving**: Get specific question answered
- **Quiz**: Practice MCQs
- **Revision**: Quick formula and concept review
- **Job Hunt**: Resume, interview, and career help

### Supported Programs:
- CMA (Certified Management Accountant)
- CPA (Certified Public Accountant)
- ACCA (Association of Chartered Certified Accountants)
- EA (Enrolled Agent)

---

## 🔌 API Endpoints

### Health Check
```bash
GET /health

Response:
{
  "status": "ok",
  "whatsapp_configured": true,
  "whatsapp_mock": false,
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-6"
}
```

### Send Program Menu (Admin)
```bash
curl -X POST http://localhost:8000/v1/admin/whatsapp/send-program-menu \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"to": "919916039894"}'
```

### Webhook (Incoming Messages)
```bash
# Meta will call:
POST /v1/whatsapp/webhook

# With signature header:
X-Hub-Signature-256: sha256=<signature>
```

### Chat Endpoint
```bash
POST /v1/chat

Body:
{
  "student_id": "whatsapp:919916039894",
  "message": "What is standard costing?",
  "course": "CMA",
  "mode": "teach",
  "level": "beginner"
}
```

---

## 🔐 Security

### Environment Variables (in `.env`)
```
WHATSAPP_ACCESS_TOKEN=...          # Meta Graph API token
WHATSAPP_PHONE_NUMBER_ID=...       # Your WhatsApp Business Account phone ID
WHATSAPP_VERIFY_TOKEN=...          # Webhook verification token
WHATSAPP_APP_SECRET=...            # For signature verification
ADMIN_TOKEN=...                    # Admin API authentication
```

### Signature Verification
All webhook requests from Meta include an `x-hub-signature-256` header that is verified using your `WHATSAPP_APP_SECRET`.

---

## 🧪 Testing

### Send Test Message
```bash
python test_whatsapp_send.py
```

### Full Integration Test
```bash
python test_whatsapp_integration.py
```

### Using curl
```bash
curl -X POST http://localhost:8000/v1/admin/whatsapp/send-program-menu \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"to": "9916039894"}'
```

---

## 🐛 Troubleshooting

### Messages Not Sending
- ❌ Check if backend is running: `netstat -ano | findstr "8000"`
- ❌ Verify `.env` has valid `WHATSAPP_ACCESS_TOKEN`
- ❌ Check if `WHATSAPP_PHONE_NUMBER_ID` is correct

### Not Receiving Messages
- ❌ Webhook URL not public (use ngrok/tunnel)
- ❌ Webhook verify token doesn't match
- ❌ Backend not listening on correct port

### Messages Sent but No Response
- ❌ Redis cache not running (required for session management)
- ❌ Claude API key invalid
- ❌ Qdrant vector store not accessible

### Check Logs
```bash
# Backend logs are in terminal where FastAPI is running
# Look for:
# - "WhatsApp send accepted" (success)
# - "Failed to process WhatsApp message" (error)
# - "WhatsApp status" (delivery confirmation)
```

---

## 📱 Test the Live Bot

**WhatsApp Number**: +91 9916039894

Send a message and expect:
1. Program menu with 4 options
2. Mode menu after selecting program
3. AI-generated answer after sending question

---

## 🔄 Next Steps

1. **✅ Done**: Messages are sending successfully
2. **⏭ Next**: Set up a public webhook using ngrok/tunnel
3. **Then**: Configure webhook in Meta/Facebook app
4. **Finally**: Test receiving messages and full conversation flow

---

## 📞 Support

For issues or questions:
- Check backend logs
- Run the test scripts
- Verify environment variables
- Review Meta/Facebook app configuration

---

**Last Updated**: May 23, 2026
**Status**: ✅ Sending Working | ⏳ Receiving Ready
