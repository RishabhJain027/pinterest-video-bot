# 📌 Pinterest Video Telegram Bot

A Telegram bot that downloads Pinterest videos and gives you direct high-speed download links + native playable Telegram videos.

---

## 🌟 Key Features

- 📥 **Direct Download Links**: Returns direct MP4 video URLs so you can download immediately in any browser.
- 🎬 **Native Telegram Video Player**: Sends the video directly inside the chat with playable streaming.
- ⚡ **Dual Run Modes**:
  - **Local Polling Mode (Default)**: Run directly on your PC with zero server/domain configuration!
  - **Cloud Webhook Mode**: Ready for free 24/7 cloud hosting on Render or Docker.
- 🔗 **Full URL Support**: Supports `pin.it`, `pinterest.com/pin/...`, country subdomains (like `in.pinterest.com`), and mobile share links.
- 🛡️ **Free & Open Source**: No paid APIs, no subscriptions.

---

## 🚀 Quickstart: Run Locally on Your PC (Easiest)

### 1. Get a Free Telegram Bot Token
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`.
3. Follow the prompts to name your bot and choose a username (e.g., `MyPinterestDownloaderBot`).
4. Copy the **HTTP API token** provided (looks like `7123456789:AAH...`).

### 2. Configure Your Bot Token
Create a `.env` file in this project folder (or copy from `.env.example`):
```env
BOT_TOKEN=your_bot_token_from_botfather
```

### 3. Install Requirements & Start
```bash
pip install -r requirements.txt
python main.py
```
Your bot is now **ONLINE**! Go to your bot on Telegram, send `/start`, and paste any Pinterest link!

---

## ☁️ Cloud Deployment on Render ($0 Free Plan)

If you want the bot running 24/7 in the cloud without keeping your PC on:

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial Pinterest Telegram bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/pinterest-video-bot.git
git push -u origin main
```

### 2. Deploy on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New + → Web Service**.
2. Connect your GitHub repository.
3. Configure settings:
   - **Runtime**: `Docker`
   - **Plan**: `Free`
   - **Port**: `8000`
4. Add Environment Variables:
   - `BOT_TOKEN` = `your_bot_token_from_botfather`
   - `PUBLIC_URL` = `https://your-service-name.onrender.com`
   - `WEBHOOK_SECRET` = `random_long_secret_string`
   - `BOT_MODE` = `webhook`
5. Click **Deploy Web Service**.

---

## 🧪 Testing

Run test suite:
```bash
python -m pytest -v
```

---

## 📄 License
MIT

