from __future__ import annotations

import asyncio
import html
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .downloader import (
    download_pinterest_video,
    extract_pinterest_url,
    is_pinterest_url,
)


# Load environment variables from .env file if present
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pinterest-bot")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")

if not TOKEN:
    log.warning("⚠️ BOT_TOKEN is not set! Set it in your .env file or environment variables.")

app = FastAPI(title="Pinterest Video Downloader Bot", version="2.0.0")


def tg_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TOKEN}/{method}"


async def telegram(method: str, data: dict | None = None, files: dict | None = None) -> Any:
    """Make an asynchronous request to the Telegram Bot API."""
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Please set BOT_TOKEN in .env")
    async with httpx.AsyncClient(timeout=180) as client:
        if files:
            response = await client.post(tg_url(method), data=data or {}, files=files)
        else:
            response = await client.post(tg_url(method), json=data or {})
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload))
        return payload["result"]


async def send_message(chat_id: int | str, text: str, parse_mode: str | None = None, reply_markup: dict | None = None) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await telegram("sendMessage", payload)


async def send_video_file(chat_id: int | str, path: str, title: str, duration: int | None = None, width: int | None = None, height: int | None = None) -> dict:
    """Send downloaded video to Telegram as native playable video, falling back to document if needed."""
    filename = Path(path).name
    caption = title[:1024]
    with open(path, "rb") as handle:
        data: dict[str, Any] = {
            "chat_id": str(chat_id),
            "caption": caption,
            "supports_streaming": "true",
        }
        if duration:
            data["duration"] = str(int(duration))
        if width:
            data["width"] = str(int(width))
        if height:
            data["height"] = str(int(height))

        try:
            return await telegram(
                "sendVideo",
                data=data,
                files={"video": (filename, handle, "video/mp4")},
            )
        except Exception as exc:
            log.warning("sendVideo failed (%s), falling back to sendDocument", exc)
            handle.seek(0)
            return await telegram(
                "sendDocument",
                data={"chat_id": str(chat_id), "caption": caption},
                files={"document": (filename, handle, "video/mp4")},
            )


async def handle_update(update: dict) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    text = (message.get("text") or "").strip()
    if not text:
        return

    if text in {"/start", "/help"}:
        welcome_text = (
            "📌 <b>Pinterest Video Downloader Bot</b>\n\n"
            "Send me any Pinterest link and I will download the video and give you the direct download link!\n\n"
            "<b>Supported Links:</b>\n"
            "• <code>https://pin.it/abc1234</code>\n"
            "• <code>https://www.pinterest.com/pin/123456789/</code>\n"
            "• <code>https://in.pinterest.com/pin/...</code>\n\n"
            "💡 <i>Tip: Just share or paste the Pinterest link directly here!</i>"
        )
        await send_message(chat_id, welcome_text, parse_mode="HTML")
        return

    pinterest_url = extract_pinterest_url(text)
    if not pinterest_url:
        await send_message(
            chat_id,
            "❌ <b>Invalid Pinterest URL</b>\n\nPlease send a valid Pinterest link, for example:\n"
            "<code>https://pin.it/xxxxxx</code> or <code>https://www.pinterest.com/pin/...</code>",
            parse_mode="HTML",
        )
        return

    # Notify user that download has started
    status_msg = await send_message(chat_id, "⏳ <b>Downloading Pinterest video...</b>\n<i>Please wait a few seconds...</i>", parse_mode="HTML")
    status_id = status_msg.get("message_id")
    result: dict[str, Any] | None = None

    try:
        # Download video in background thread
        result = await asyncio.to_thread(download_pinterest_video, pinterest_url)

        # Notify user that file is being sent
        try:
            await telegram("editMessageText", {
                "chat_id": chat_id,
                "message_id": status_id,
                "text": "🚀 <b>Uploading video to Telegram...</b>",
                "parse_mode": "HTML",
            })
        except Exception:
            pass

        title = result.get("title", "Pinterest Video")
        safe_title = html.escape(title)
        direct_url = result.get("direct_url")

        # Upload video to chat
        tg_file_res = await send_video_file(
            chat_id=chat_id,
            path=result["path"],
            title=f"🎬 {title}",
            duration=result.get("duration"),
            width=result.get("width"),
            height=result.get("height"),
        )

        # Extract file_id if available for proxy download link
        file_id = None
        if "video" in tg_file_res:
            file_id = tg_file_res["video"].get("file_id")
        elif "document" in tg_file_res:
            file_id = tg_file_res["document"].get("file_id")

        # Build download link message
        download_text_lines = [
            f"✅ <b>Downloaded Successfully!</b>",
            f"📌 <b>Title:</b> {safe_title}",
        ]

        if direct_url:
            download_text_lines.append(
                f"\n🔗 <b>Direct CDN Video Link:</b>\n<a href=\"{html.escape(direct_url, quote=True)}\">⬇️ Click Here to Download MP4</a>"
            )

        if PUBLIC_URL and file_id:
            proxy_link = f"{PUBLIC_URL}/download/{file_id}"
            download_text_lines.append(
                f"\n🌐 <b>Bot Web Link:</b>\n<a href=\"{html.escape(proxy_link, quote=True)}\">⬇️ Download from Bot Server</a>"
            )

        await send_message(chat_id, "\n".join(download_text_lines), parse_mode="HTML")

    except Exception as exc:
        log.exception("Pinterest download failed")
        error_msg = str(exc)
        if "No video formats found" in error_msg:
            err_text = "❌ This Pin does not contain a downloadable video (it might be an image, carousel, or private)."
        else:
            err_text = f"❌ <b>Download Failed:</b>\n{html.escape(error_msg[:500])}"
        await send_message(chat_id, err_text, parse_mode="HTML")
    finally:
        # Delete temporary status message
        if status_id:
            try:
                await telegram("deleteMessage", {"chat_id": chat_id, "message_id": status_id})
            except Exception:
                pass

        # Cleanup local file and directory
        if result and result.get("path"):
            try:
                p = Path(result["path"])
                p.unlink(missing_ok=True)
                if result.get("temp_dir"):
                    Path(result["temp_dir"]).rmdir()
                else:
                    p.parent.rmdir()
            except OSError:
                pass


# -------------------------------------------------------------
# Polling Mode (for local running without webhooks)
# -------------------------------------------------------------
async def run_polling():
    """Run bot continuously via Telegram long polling."""
    if not TOKEN:
        print("=" * 60)
        print("❌ ERROR: BOT_TOKEN is missing!")
        print("Please create a .env file and add your Telegram bot token:")
        print("BOT_TOKEN=your_telegram_bot_token_here")
        print("=" * 60)
        return

    try:
        # Remove any existing webhook so polling receives updates
        await telegram("deleteWebhook", {"drop_pending_updates": False})
        bot_info = await telegram("getMe")
        print("=" * 60)
        print(f"🤖 Bot @{bot_info.get('username')} is ONLINE in POLLING mode!")
        print("Ready to receive Pinterest links from Telegram.")
        print("Press Ctrl+C to stop.")
        print("=" * 60)
    except Exception as exc:
        log.error("Failed to connect to Telegram: %s", exc)
        return

    offset = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                response = await client.post(
                    tg_url("getUpdates"),
                    json={"offset": offset, "timeout": 30, "allowed_updates": ["message", "edited_message"]},
                )
                if response.status_code != 200:
                    await asyncio.sleep(3)
                    continue

                payload = response.json()
                if not payload.get("ok"):
                    await asyncio.sleep(3)
                    continue

                updates = payload.get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    asyncio.create_task(handle_update(update))

        except (httpx.RequestError, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError):
                break
            await asyncio.sleep(2)
        except Exception as exc:
            log.warning("Polling error: %s", exc)
            await asyncio.sleep(3)


# -------------------------------------------------------------
# FastAPI Routes (for Webhook mode & direct file proxy)
# -------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "ok": True,
        "service": "Pinterest Video Downloader Bot",
        "mode": "webhook" if PUBLIC_URL else "polling/standalone",
    }


@app.get("/health")
async def health():
    return {"ok": True, "service": "pinterest-free-bot"}


@app.get("/download/{file_id}")
async def download_proxy(file_id: str):
    """Return a token-free redirect to Telegram's file CDN URL."""
    file_info = await telegram("getFile", {"file_id": file_id})
    return RedirectResponse(url=f"https://api.telegram.org/file/bot{TOKEN}/{file_info['file_path']}")


@app.post("/telegram/webhook/{secret}")
async def webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=403)
    update = await request.json()
    asyncio.create_task(handle_update(update))
    return {"ok": True}


@app.on_event("startup")
async def startup():
    if TOKEN and PUBLIC_URL and os.getenv("BOT_MODE", "webhook") == "webhook":
        webhook_url = f"{PUBLIC_URL}/telegram/webhook/{WEBHOOK_SECRET}"
        try:
            await telegram("setWebhook", {"url": webhook_url, "drop_pending_updates": False})
            log.info("Telegram webhook configured: %s", webhook_url.replace(WEBHOOK_SECRET, "***"))
        except Exception:
            log.exception("Could not configure Telegram webhook")
    else:
        # If no public URL is provided or mode is polling, run polling in the background
        log.info("Starting Telegram Polling in background...")
        asyncio.create_task(run_polling())


