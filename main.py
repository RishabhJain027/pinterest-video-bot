import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load .env file
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Pinterest Video Telegram Bot")
    parser.add_argument(
        "--mode",
        choices=["polling", "webhook", "server"],
        default=os.getenv("BOT_MODE", "server"),
        help="Run mode: 'server' (recommended: runs web server + polling/webhook), 'polling' (cli only), 'webhook'",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for webhook server")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port for webhook server")
    args = parser.parse_args()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token.lower() in {"replace_me", "your_telegram_bot_token_here", "123456:replace_me"}:
        print("\n" + "=" * 65)
        print("[!] ACTION REQUIRED: Set your Telegram BOT_TOKEN in .env")
        print("=" * 65)
        print("1. Open Telegram and message @BotFather")
        print("2. Send /newbot and choose a bot name and username")
        print("3. Copy the HTTP API token provided by BotFather")
        print("4. Paste it into your .env file:")
        print("   BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz")
        print("5. Run: python main.py")
        print("=" * 65 + "\n")
        sys.exit(1)

    if args.mode == "polling":
        from app.bot import run_polling
        try:
            asyncio.run(run_polling())
        except KeyboardInterrupt:
            print("\n[!] Bot stopped by user.")
    else:
        import uvicorn
        print(f"[*] Starting Server on port {args.port}...")
        uvicorn.run("app.bot:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

