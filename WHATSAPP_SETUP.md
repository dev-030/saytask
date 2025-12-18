# WhatsApp Bot Setup Guide

## Quick Start

### 1. Install ngrok (if not already installed)

```bash
# Download from https://ngrok.com/download
# Or use snap:
sudo snap install ngrok
```

### 2. Configure ngrok with your auth token

```bash
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

### 3. Start your Django server

```bash
cd /home/jamil/Desktop/saytask
source venv/bin/activate
python manage.py runserver
```

### 4. Start ngrok in another terminal

```bash
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abcd-1234-5678.ngrok-free.app -> http://localhost:8000
```

### 5. Configure Twilio WhatsApp Sandbox

1. Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. Click on "Sandbox settings"
3. Set the webhook URL to:
   ```
   https://YOUR-NGROK-URL.ngrok-free.app/chatbot/whatsapp/webhook/
   ```
   Example: `https://abcd-1234-5678.ngrok-free.app/chatbot/whatsapp/webhook/`
4. Set HTTP method to `POST`
5. Click "Save"

### 6. Join the WhatsApp Sandbox

1. From the Twilio console, you'll see a join code like: `join <word>-<word>`
2. On your phone, open WhatsApp
3. Send the join code to the number shown in Twilio console
4. You'll receive a confirmation message

### 7. Test the Bot

Make sure your user account in the app has a phone number set (the same one you're using for WhatsApp).

**Test Messages**:

```
Meeting tomorrow at 3pm
```
Expected: Bot asks for details about the meeting

```
Team standup about project updates in conference room A
```
Expected: Bot confirms and asks about reminders

```
Buy groceries by Friday evening
```
Expected: Bot creates a task and asks about reminders

```
Note: Remember to call the client next week
```
Expected: Bot confirms note is saved

### 8. Verify in Database

Check if entries are created:

```bash
source venv/bin/activate
python manage.py shell
```

```python
from actions.models import Event, Task, Note
from authentication.models import UserAccount

# Check your user
user = UserAccount.objects.get(email='your@email.com')
print(f"Phone: {user.phone_number}")

# Check events
events = Event.objects.filter(user=user)
for e in events:
    print(f"Event: {e.title} at {e.event_datetime}")

# Check tasks
tasks = Task.objects.filter(user=user)
for t in tasks:
    print(f"Task: {t.title} by {t.end_time}")

# Check notes
notes = Note.objects.filter(user=user)
for n in notes:
    print(f"Note: {n.title}")
```

## Troubleshooting

### Issue: "You don't have a phone number added in the app"

**Solution**: Add your phone number to your user account:

```python
# In Django shell
from authentication.models import UserAccount
user = UserAccount.objects.get(email='your@email.com')
user.phone_number = '+1234567890'  # Your WhatsApp number with country code
user.save()
```

### Issue: "No response from bot"

**Checklist**:
1. ✅ Is Django server running?
2. ✅ Is ngrok running and forwarding to port 8000?
3. ✅ Did you update the Twilio webhook URL with the ngrok URL?
4. ✅ Is the webhook URL correct? `/chatbot/whatsapp/webhook/`
5. ✅ Check Django logs for errors

### Issue: "Internal server error"

Check the Django console for error messages:
```bash
# Look for errors in the terminal where Django is running
# Or check logs
tail -f /path/to/logs/django.log
```

Common issues:
- Missing OpenAI API key
- Database connection issues
- User phone number not matching

### Issue: "Bot responds but nothing in database"

Check Django logs for database creation errors. The bot will still respond even if database creation fails (graceful degradation).

## Production Deployment

For production, replace ngrok with your actual domain:

```
https://yourdomain.com/chatbot/whatsapp/webhook/
```

Make sure to:
1. Set `DEBUG = False` in settings.py
2. Configure proper `ALLOWED_HOSTS`
3. Use a production WSGI server (gunicorn, uwsgi)
4. Set up HTTPS (Let's Encrypt)
5. Update Twilio webhook to production URL

## Environment Variables Required

Make sure these are set in your `.env` file:

```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_whatsapp_number
OPENAI_API_KEY=your_openai_api_key
```

## Phone Number Format

Users' phone numbers should be stored with country code:
```
+1234567890     # Good
1234567890      # Acceptable (bot will try to match)
+1-234-567-890  # Acceptable (bot cleans format)
```

The bot will try multiple matching strategies to be flexible.
