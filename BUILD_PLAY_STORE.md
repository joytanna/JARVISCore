# JARVIS AI — Google Play Store Publishing Guide

## Overview
JARVIS AI is published as a **TWA (Trusted Web Activity)** — a native Android app wrapper around the PWA.
This gives you a real Play Store listing, homescreen icon, and offline support without building a native Android app.

---

## Step 1 — Set Up LemonSqueezy (Payments)

1. Go to **https://lemonsqueezy.com** and create a free account
2. Create your store (e.g., "JARVIS AI")
3. Create 3 Products:
   - **JARVIS Pro — Monthly** ($3.99/month) → enable License Keys
   - **JARVIS Pro — Annual** ($34.99/year) → enable License Keys
   - **JARVIS Lifetime** ($49.99 one-time) → enable License Keys
4. For each product: Settings → License Keys → Enable
5. Copy the product checkout URLs (e.g., `https://jarvisai.lemonsqueezy.com/buy/xxx`)
6. Update `config.py` / `.env` with:
   ```
   LS_LINK_PRO_MONTHLY=https://jarvisai.lemonsqueezy.com/buy/pro-monthly
   LS_LINK_PRO_ANNUAL=https://jarvisai.lemonsqueezy.com/buy/pro-annual
   LS_LINK_LIFETIME=https://jarvisai.lemonsqueezy.com/buy/lifetime
   LEMONSQUEEZY_API_KEY=your_api_key_from_lemonsqueezy
   LEMONSQUEEZY_STORE_ID=your_store_id
   ```
7. Set up discount codes in LemonSqueezy:
   - LAUNCH2026 → 40% off annual
   - BETA → 14-day trial (handled in code)
   - STUDENT25 → 25% off annual
   - FRIEND15 → 15% off monthly

---

## Step 2 — Set Up Your HTTPS Server (Required for Play Store)

The TWA requires your JARVIS server to be accessible via HTTPS.
Options:
- **ngrok** (quick): `ngrok http 8100` → gives you a temp HTTPS URL
- **Cloudflare Tunnel** (free, permanent): `cloudflared tunnel --url http://localhost:8100`
- **VPS + Nginx + Let's Encrypt** (production): DigitalOcean/Linode $6/month

For Play Store, you need a permanent domain. Example: `https://api.jarvis.ai`

---

## Step 3 — Build the Android APK with Bubblewrap

### Prerequisites
```bash
npm install -g @bubblewrap/cli
# Also need: Android Studio, Java JDK 11+
```

### Initialize TWA project
```bash
mkdir jarvis-android && cd jarvis-android
bubblewrap init --manifest https://YOUR_SERVER/.well-known/manifest.json
```

Answer the prompts:
- Package name: `ai.jarvis.app`
- App name: `JARVIS AI`
- Start URL: `https://YOUR_SERVER/android`
- Launcher icon: `icon-512.png`
- Splash color: `#030810`
- Theme color: `#06b6d4`

### Build AAB (Android App Bundle for Play Store)
```bash
bubblewrap build
# Outputs: app-release-signed.aab
```

### Or use PWABuilder (no-code, browser-based)
1. Go to **https://www.pwabuilder.com**
2. Enter your server URL (e.g., `https://YOUR_SERVER/android`)
3. Click "Build" → "Android" → Download APK/AAB
4. No local setup needed!

---

## Step 4 — Digital Asset Links (Verify your domain)

After building, get your app's SHA-256 fingerprint:
```bash
keytool -v -keystore android.keystore -alias android -storepass android -keypass android
# Copy the SHA256: value
```

Update `static/.well-known/assetlinks.json`:
```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "ai.jarvis.app",
    "sha256_cert_fingerprints": ["YOUR:ACTUAL:SHA256:FINGERPRINT:HERE"]
  }
}]
```

Verify at: `https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://YOUR_SERVER`

---

## Step 5 — Google Play Console

1. Go to **https://play.google.com/console**
2. Pay the $25 one-time developer fee
3. Create new app: "JARVIS AI"
4. Upload your AAB file
5. Fill in store listing:

### Store Listing
**Short description (80 chars):**
> JARVIS AI — Personal AI powered by Gemini 2.5 Flash

**Full description (4000 chars):**
```
JARVIS AI is your personal intelligent assistant — more powerful than Google Assistant because it's truly yours.

🤖 POWERED BY GEMINI 2.5 FLASH
The latest Google AI, available free. Unlimited conversations. No data sold. Privacy-first.

⚡ 275+ TOOLS — UNLIKE ANY OTHER ASSISTANT
• Email reading & composing
• Contact management
• Budget & expense tracking
• Habit tracking with streaks
• Pomodoro focus timer
• Flashcard system (spaced repetition)
• Stock price tracker
• YouTube transcript summariser
• World clock & timezone converter
• Dictionary, synonyms, word of the day
• Weather, news, Wikipedia
• QR code generator
• And 260+ more tools

🖥️ CONNECT TO YOUR HOME PC
JARVIS runs as a service on your Windows PC. The app gives you full remote control:
• Lock, sleep, shutdown your PC
• Control volume & brightness
• Take screenshots remotely
• Kill processes
• Read anything on your screen

🎤 VOICE-FIRST DESIGN
Hold the mic button and speak naturally. JARVIS understands context and gives intelligent answers.

📊 FREE vs PRO
Free: 20 AI conversations/day, basic tools
Pro ($3.99/mo): Unlimited AI + all 275 tools
Lifetime ($49.99): Pay once, own forever

Use code LAUNCH2026 for 40% off!
```

### Screenshots needed (mandatory):
- Screenshot 1: Home screen with orb (idle state)
- Screenshot 2: Voice listening state
- Screenshot 3: Chat conversation
- Screenshot 4: Actions grid
- Screenshot 5: Settings / upgrade screen

---

## Step 6 — App Signing & Privacy Policy

### Privacy Policy (required by Play Store)
Host at: `https://YOUR_SERVER/privacy`

Add this endpoint to jarvis.py or host a simple HTML page covering:
- What data is collected (minimal — only stored locally)
- No data sold to third parties
- Microphone used only for voice commands
- Contact data stays on device

### Content Rating
- Fill out the rating questionnaire
- JARVIS AI should get **Everyone** rating (no violence, no adult content)

---

## Step 7 — Revenue Projections

At $3.99/month Pro:
- 100 users = $399/month ($4,788/year)
- 1,000 users = $3,990/month ($47,880/year)
- 5,000 users = $19,950/month ($239,400/year)

LemonSqueezy takes **5% + $0.50** per transaction.
Google Play takes **15%** (first $1M, then 30%) for in-app purchases.
Since you're using external payments (LemonSqueezy), Google's cut is **0%** on subscriptions.

---

## Step 8 — Marketing Your App

1. **ASO (App Store Optimization)**
   - Keywords: AI assistant, voice assistant, Gemini, personal AI, productivity
   - Update regularly — fresh apps rank better

2. **Social Media**
   - Post demo videos on TikTok, YouTube Shorts, Instagram
   - Show the bootloader → orb → voice → answer sequence

3. **Product Hunt**
   - Launch on Product Hunt for free publicity

4. **Reddit**
   - r/artificial, r/productivity, r/Android

5. **Discount codes**
   - BETA for your first users → converts them to paid when trial ends

---

## Checklist Before Publishing

- [ ] HTTPS server running with valid SSL certificate
- [ ] `assetlinks.json` updated with real SHA-256 fingerprint
- [ ] LemonSqueezy products created with correct checkout URLs
- [ ] Privacy policy hosted and linked
- [ ] Store listing screenshots captured
- [ ] AAB signed and uploaded to Play Console
- [ ] App reviewed (usually 1-3 days for new apps)
- [ ] Discount code LAUNCH2026 ready to promote at launch

---

## Quick Commands Reference

```bash
# Build TWA with bubblewrap
npm install -g @bubblewrap/cli
bubblewrap init --manifest https://YOUR_SERVER/static/android_manifest.json
bubblewrap build

# Test locally before publishing
bubblewrap run

# Update after code changes
bubblewrap update
bubblewrap build

# Get signing cert fingerprint
keytool -list -v -keystore android.keystore
```

---

## Support & Updates

Once live, JARVIS updates automatically — users always get the latest version when you update `ui/android.html` on your server.
No app store update needed for UI/feature changes. Only update the Play Store if:
- You change permissions
- You update the package name or signing
- Major version releases
