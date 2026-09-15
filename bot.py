"""
Trend Qo'shiqlar Telegram Bot
=============================
Admin botga to'g'ridan-to'g'ri mp3/audio fayl yuborib, trend qo'shiqlar
ro'yxatiga qo'shadi. Foydalanuvchilar /trend buyrug'i orqali haqiqiy audio
fayllarni (pleer ko'rinishida) oladi. Bot har kuni belgilangan vaqtda
ro'yxatni kanalga avtomatik yuboradi.

Ishga tushirish:
    pip install -r requirements.txt
    .env faylini to'ldiring (BOT_TOKEN, ADMIN_IDS, CHANNEL_ID, POST_HOUR, POST_MINUTE)
    python bot.py

Qo'shiq qo'shish: admin botga mp3 (audio) faylni yuboradi — shu bo'ldi,
alohida buyruq kerak emas. Xohlasa caption (izoh) sifatida nom yozib qo'ysa,
o'sha nom saqlanadi.
"""

import json
import logging
import os
from datetime import time as dtime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Sozlamalar
# ---------------------------------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
CHANNEL_ID = os.getenv("CHANNEL_ID")  # masalan: @mening_kanalim yoki -1001234567890
POST_HOUR = int(os.getenv("POST_HOUR", "9"))
POST_MINUTE = int(os.getenv("POST_MINUTE", "0"))
TIMEZONE_OFFSET = int(os.getenv("TIMEZONE_OFFSET_HOURS", "5"))  # Toshkent = UTC+5

DATA_FILE = Path(__file__).parent / "songs.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ma'lumotlarni saqlash / o'qish
# ---------------------------------------------------------------------------
# Har bir qo'shiq lug'at (dict) sifatida saqlanadi:
#   {"file_id": "...", "title": "...", "performer": "..."}
def load_songs() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Eski formatdagi (faqat matn) ro'yxatlarga ham moslashuvchan bo'lish
    migrated = []
    for item in data:
        if isinstance(item, str):
            migrated.append({"file_id": None, "title": item, "performer": None})
        else:
            migrated.append(item)
    return migrated


def save_songs(songs: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)


def song_label(song: dict) -> str:
    title = song.get("title") or "Nomsiz qo'shiq"
    performer = song.get("performer")
    return f"{performer} - {title}" if performer else title


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------------------------------------
# Buyruqlar (foydalanuvchilar uchun)
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salom! 👋\n\n"
        "Men trend qo'shiqlar botiman.\n"
        "/trend — hozirgi trend qo'shiqlarni olish\n"
        "/help — barcha buyruqlar"
    )


async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    songs = load_songs()
    if not songs:
        await update.message.reply_text("Hozircha trend qo'shiqlar ro'yxati bo'sh. 🎵")
        return

    await update.message.reply_text(f"🔥 Hozirgi trend qo'shiqlar ({len(songs)} ta):")
    for song in songs:
        if song.get("file_id"):
            await update.message.reply_audio(
                audio=song["file_id"],
                title=song.get("title"),
                performer=song.get("performer"),
            )
        else:
            await update.message.reply_text(f"🎵 {song_label(song)}")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Foydalanuvchi buyruqlari:</b>\n"
        "/trend — trend qo'shiqlarni olish\n\n"
    )
    if is_admin(update.effective_user.id):
        text += (
            "<b>Admin buyruqlari:</b>\n"
            "Qo'shiq qo'shish uchun botga to'g'ridan-to'g'ri mp3 (audio) fayl yuboring.\n"
            "Caption (izoh) yozsangiz, u nom sifatida saqlanadi.\n\n"
            "/list — ro'yxatni raqamlar bilan ko'rish (matn holida)\n"
            "/remove 2 — ro'yxatdan raqami bo'yicha o'chirish\n"
            "/clear — ro'yxatni tozalash\n"
            "/post — ro'yxatni hoziroq kanalga yuborish\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Admin: mp3 fayl yuborib qo'shiq qo'shish
# ---------------------------------------------------------------------------
async def receive_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return  # oddiy foydalanuvchi audio yuborsa, e'tiborsiz qoldiramiz

    audio = update.message.audio
    voice = update.message.voice

    if audio:
        file_id = audio.file_id
        title = audio.title or update.message.caption or "Nomsiz qo'shiq"
        performer = audio.performer
    elif voice:
        file_id = voice.file_id
        title = update.message.caption or "Nomsiz qo'shiq"
        performer = None
    else:
        return

    songs = load_songs()
    songs.append({"file_id": file_id, "title": title, "performer": performer})
    save_songs(songs)

    label = f"{performer} - {title}" if performer else title
    await update.message.reply_text(f"Qo'shildi ✅\n🎵 {label}")


# ---------------------------------------------------------------------------
# Buyruqlar (faqat admin uchun)
# ---------------------------------------------------------------------------
async def list_songs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    songs = load_songs()
    if not songs:
        await update.message.reply_text("Ro'yxat bo'sh.")
        return
    lines = ["📋 Ro'yxat:\n"]
    for i, song in enumerate(songs, start=1):
        lines.append(f"{i}. {song_label(song)}")
    await update.message.reply_text("\n".join(lines))


async def remove_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bu buyruq faqat adminlar uchun.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("To'g'ri format: /remove 2  (raqam /list ro'yxatidagi tartib raqami)")
        return

    idx = int(context.args[0]) - 1
    songs = load_songs()
    if 0 <= idx < len(songs):
        removed = songs.pop(idx)
        save_songs(songs)
        await update.message.reply_text(f"O'chirildi ❌\n{song_label(removed)}")
    else:
        await update.message.reply_text("Bunday raqamli qo'shiq topilmadi.")


async def clear_songs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bu buyruq faqat adminlar uchun.")
        return
    save_songs([])
    await update.message.reply_text("Ro'yxat tozalandi. 🧹")


async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bu buyruq faqat adminlar uchun.")
        return
    await send_daily_list(context)
    await update.message.reply_text("Kanalga yuborildi ✅")


# ---------------------------------------------------------------------------
# Har kunlik avtomatik yuborish
# ---------------------------------------------------------------------------
async def send_daily_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID sozlanmagan, avtomatik yuborish o'tkazib yuborildi.")
        return
    songs = load_songs()
    if not songs:
        logger.info("Ro'yxat bo'sh, kanalga hech narsa yuborilmadi.")
        return

    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"🔥 Bugungi trend qo'shiqlar ({len(songs)} ta):",
    )
    for song in songs:
        if song.get("file_id"):
            await context.bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=song["file_id"],
                title=song.get("title"),
                performer=song.get("performer"),
            )
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"🎵 {song_label(song)}")


# ---------------------------------------------------------------------------
# Botni ishga tushirish
# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylida BOT_TOKEN ni kiriting.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trend", trend))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_songs))
    app.add_handler(CommandHandler("remove", remove_song))
    app.add_handler(CommandHandler("clear", clear_songs))
    app.add_handler(CommandHandler("post", post_now))

    # Admin mp3/audio yoki ovozli xabar yuborganda avtomatik qo'shiladi
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, receive_audio))

    # Har kuni belgilangan vaqtda (mahalliy vaqt, TIMEZONE_OFFSET hisobga olinadi)
    post_time_utc_hour = (POST_HOUR - TIMEZONE_OFFSET) % 24
    app.job_queue.run_daily(
        send_daily_list,
        time=dtime(hour=post_time_utc_hour, minute=POST_MINUTE),
    )

    logger.info("Bot ishga tushdi.")
    app.run_polling()


if __name__ == "__main__":
    main()
    
