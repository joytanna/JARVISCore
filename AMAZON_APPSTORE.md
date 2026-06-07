# JARVIS AI — Amazon Appstore Submission (FREE)

## Why Amazon Appstore?
- **$0 to publish** (vs Google Play's $25)
- Available on all Amazon Fire tablets, Fire TV
- Can be installed on any Android phone via the Amazon Shopping app
- 100M+ compatible devices
- Revenue share: 70% to developer (same as Google Play)

---

## Step 1 — Create Developer Account (Free)
1. Go to: https://developer.amazon.com/apps-and-games
2. Click "Sign In" with your Amazon account (or create one)
3. Go to "Developer Console" → "Submit an App"
4. It's **completely free** to sign up

---

## Step 2 — Build the APK

### Option A: PWABuilder (No-code, browser-based — RECOMMENDED)
1. Go to **https://www.pwabuilder.com**
2. Enter URL: `http://YOUR_SERVER_IP:8100/android`
   - Note: For public submission, you need a public HTTPS URL
   - Use Cloudflare Tunnel (free): `cloudflared tunnel --url http://localhost:8100`
   - Or ngrok free: `ngrok http 8100`
3. Click "Start" → wait for analysis
4. Click "Package For Stores" → "Android"
5. Fill in:
   - Package ID: `ai.jarvis.app`
   - App name: `JARVIS AI`
   - Version: `1.0.0`
6. Download the APK/AAB — it's free

### Option B: GitHub Actions (Automated)
Push to GitHub — the workflow in `.github/workflows/build_apk.yml` builds automatically.
Download the APK from the GitHub Release.

### Option C: Manual with Bubblewrap
```bash
# Install requirements
npm install -g @bubblewrap/cli
# (Also need Android Studio with SDK)

# Build
mkdir jarvis-android && cd jarvis-android
bubblewrap init --manifest https://YOUR_PUBLIC_URL/static/android_manifest.json
# Answer:
#   Package ID: ai.jarvis.app
#   App name: JARVIS AI
#   Start URL: /android
#   Splash color: #030810
#   Theme color: #06b6d4

bubblewrap build
# Output: app-release-signed.aab
```

---

## Step 3 — Amazon Submission Form

### App Information
- **App title**: JARVIS AI — Personal Assistant
- **App SKU**: jarvis-ai-v1
- **Category**: Productivity
- **Sub-category**: AI & Machine Learning

### Description (Short, 1200 chars max):
```
JARVIS AI is your personal intelligent assistant powered by Gemini 2.5 Flash.

Unlike basic voice assistants, JARVIS has 275+ tools:
• Email, contacts, and messaging
• Budget and expense tracking
• Habit tracker with streaks
• Pomodoro focus timer
• Stock price tracker
• YouTube transcript summarizer
• Weather, news, Wikipedia
• World clock, dictionary
• Home PC remote control

Voice-first design: hold the mic button, speak naturally.

Free: 20 AI conversations/day
Pro: $3.99/month — unlimited + all tools
Lifetime: $49.99 — pay once, own forever

Use code LAUNCH2026 for 40% off Pro!
```

### Description (Full, 4000 chars max):
```
JARVIS AI is the most feature-rich personal AI assistant available — more powerful than 
Google Assistant or Siri because it's built for power users.

🤖 POWERED BY GEMINI 2.5 FLASH
Google's latest AI model, available for free in the JARVIS app. No account required. 
Privacy-first: your data stays on your device.

⚡ 275+ TOOLS
Most AI assistants have 10-20 capabilities. JARVIS has 275+:

COMMUNICATION
• Read and compose emails
• Contact management
• Send SMS and WhatsApp messages
• Meeting transcription

PRODUCTIVITY
• Pomodoro focus timer
• Habit tracker with streaks and analytics
• Flashcard system (spaced repetition)
• To-do list management
• Calendar integration

FINANCE
• Budget and expense tracking
• Stock price tracker with alerts
• Crypto prices
• Monthly expense reports

INFORMATION
• Real-time weather
• Wikipedia search
• News headlines
• Stock prices
• YouTube video transcript + AI summary
• Dictionary, synonyms, word of the day
• Unit converter

DEVICE CONTROL (when connected to JARVIS home server)
• Lock, sleep, shutdown your PC remotely
• Control PC volume and brightness
• Take screenshots of your PC
• Kill processes
• Wi-Fi management

LEARNING & FUN
• Flashcards with spaced repetition (SM-2 algorithm)
• Language translation (100+ languages)
• Dictionary, rhymes, etymology
• Jokes, random facts, quotes
• Dice roller, coin flipper

🎤 VOICE-FIRST DESIGN
Hold the large microphone button and speak naturally. JARVIS understands context 
and gives intelligent, concise answers — British accent, dry wit, always polite.

📊 FREE vs PRO vs LIFETIME

FREE (no payment required):
✓ 20 AI conversations per day
✓ Voice input and output
✓ Weather, time, calculator
✓ Dictionary and world clock
✓ Basic habit tracking (3 habits)
✓ Translation (5/day)
✓ Facts, jokes, word of the day

PRO ($3.99/month or $34.99/year):
✓ Everything in Free
✓ Unlimited AI conversations
✓ Email management
✓ Contact sync from your phone
✓ Full budget tracker
✓ Advanced habits (unlimited)
✓ Pomodoro timer
✓ Stock tracker
✓ YouTube transcript
✓ QR code generator
✓ PC remote control
✓ Flashcard system

LIFETIME ($49.99 — one payment):
✓ Everything in Pro
✓ All future features included
✓ 2 device activations

💡 TRY BEFORE YOU BUY
Use code BETA for a 14-day free Pro trial.
Use code LAUNCH2026 for 40% off your first year.

🔒 PRIVACY FIRST
No accounts required. No data sold. AI processing happens either locally on your 
home server or via Google's privacy-respecting Gemini API. Your conversations 
are stored only on your own devices.
```

### Keywords (max 30):
`AI assistant, voice assistant, Gemini AI, personal assistant, productivity, 
smart home, PC control, email, contacts, budget, habits, pomodoro, flashcards, 
stocks, weather, news, note taking, translation, dictionary, timer`

---

## Step 4 — Assets Required

### Icons
- 114×114 px PNG
- 512×512 px PNG (already in static/icon-512.png)

### Screenshots (minimum 3, up to 10)
Take these screenshots from the Android app:
1. **Home screen** — orb glowing cyan, JARVIS AI text, suggestion chips
2. **Listening state** — orb glowing green, voice wave bars animating, "LISTENING" label
3. **Chat screen** — conversation showing AI response cards
4. **Actions grid** — all the quick action buttons
5. **Settings / upgrade screen** — pricing tiers, discount code field
6. **Bootloader** — the terminal-style boot animation

For screenshots without a real phone:
- Use Chrome DevTools → Device Simulation → Pixel 6
- Open `http://localhost:8100/android`
- Take screenshots at each step

### Video Preview (optional but recommended)
Record a 30-second demo:
- Boot → orb appears → user says "Jarvis, what's the weather?"
- Voice wave → thinking → response card appears
- Show actions grid, settings

---

## Step 5 — Pricing & In-App Purchases

Amazon supports in-app purchases (IAP):
- Register as a seller in Amazon Developer Console
- Create IAP items:
  - `jarvis_pro_monthly`: Subscription, $3.99/month
  - `jarvis_pro_annual`: Subscription, $34.99/year
  - `jarvis_lifetime`: Non-consumable, $49.99

Amazon takes **30%** (similar to Google Play).

**Alternatively**: Keep using LemonSqueezy (external payment).
Amazon allows external payment links for non-digital goods, but for digital 
subscriptions Amazon IAP is required to be in the store.

---

## Step 6 — Submit

1. Log into https://developer.amazon.com/apps-and-games/console/app/list
2. Click "Add a New App" → Android
3. Fill in all fields from Step 3
4. Upload APK (from Step 2)
5. Upload screenshots and icons
6. Set pricing: Free with IAP
7. Select countries: All (or India first for testing)
8. Click Submit

**Review time**: Usually 1-3 business days.

---

## Alternative Free Distribution — GitHub Releases

Your GitHub Actions workflow already creates a GitHub Release with the APK.
Users can download it directly from:
`https://github.com/YOUR_USERNAME/JARVISCore/releases/latest`

To install:
1. Download the APK on Android
2. Settings → Security → Allow from unknown sources
3. Open the downloaded file and install

This is completely free and bypasses any store entirely.

---

## Revenue Estimate (Amazon Appstore)

At $3.99/month Pro:
- 50 Pro users:  $199/month (~$2,400/year)  
- 200 Pro users: $796/month (~$9,552/year)
- 1000 Pro users: $3,990/month (~$47,880/year)

After Amazon's 30% cut:
- 1000 users → ~$33,516/year net

India alone has 50M+ Amazon app users. If even 0.1% convert to Pro...
