import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import BOT_TOKEN, CHANNEL_ID, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT

# Loggingni sozlash
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- FSM (Holatlar) ---
class PresentationState(StatesGroup):
    waiting_for_topic = State()

# --- Asosiy menyu (Reply Keyboard) ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Yangi Taqdimot (Slayd)"), KeyboardButton(text="🎁 Sovg'alar")],
            [KeyboardButton(text="📘 Yangi Mustaqil ish"), KeyboardButton(text="📄 Yangi Referat")],
            [KeyboardButton(text="📚 Kurs ishi yaratish")]
        ],
        resize_keyboard=True
    )

# --- Majburiy obunani tekshirish funksiyasi ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        # Agar foydalanuvchi tark etmagan, bloklamagan bo'lsa
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception:
        return False

# --- /start komandasi ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    # Til o'zgargani haqida xabar (rasmdagidek)
    await message.answer("✅ Til o'zbek tiliga o'zgartirildi.")
    
    welcome_text = (
        f"Assolomu alaykum, {html.bold(message.from_user.full_name)}!\n"
        f"<i>Botimizga xush kelibsiz!</i>\n\n"
        "Ushbu bot orqali siz sun'iy intellekt yordamida:\n\n"
        "🟥 – <b>Slaydlar</b> (prezentatsiyalar)\n"
        "📄 – <b>Referatlar</b>\n"
        "📘 – <b>Mustaqil ishlar</b>\n"
        "📚 – <b>Kurs ishi</b>\n"
        "🟧 – <b>Tezis</b>\n"
        "🟩 – <b>Maqola</b>\n"
        "📝 – <b>Test</b>\n"
        "🧩 – <b>Krossvord</b>\n\n"
        "yaratishingiz mumkin!\n\n"
        "👇 Pastdagi menyudan birini tanlang yoki /manual buyrug'i orqali yo'riqnoma bilan tanishing.\n\n"
        "Savol va takliflar: @jakhon_dev 👍"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_menu())

# --- Taqdimot tugmasi bosilganda ---
@dp.message(F.text == "📖 Yangi Taqdimot (Slayd)")
async def new_presentation(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Majburiy obunani tekshirish
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        sub_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Kanalga o'tish", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]
            ]
        )
        await message.answer(
            "🚫 Botdan foydalanish uchun avval kanalimizga obuna bo'ling:\n\n"
            f"👉 <b>{CHANNEL_ID}</b>",
            reply_markup=sub_markup
        )
        return

    # Agar obuna bo'lgan bo'lsa
    await message.answer("Iltimos, taqdimot mavzusini kiriting (masalan: <i>Amir Temur hayoti va faoliyati</i>):")
    await state.set_state(PresentationState.waiting_for_topic)

# --- Obunani tasdiqlash tugmasi (Callback) ---
@dp.callback_query(F.data == "check_sub")
async def verify_subscription(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        await callback.message.delete()
        await callback.message.answer("Rahmat! Obuna tasdiqlandi. Endi taqdimot mavzusini kiriting:")
        await state.set_state(PresentationState.waiting_for_topic)
    else:
        await callback.answer("Siz hali kanalga obuna bo'lmadingiz! ❌", show_alert=True)

# --- Mavzuni qabul qilish va ma'lumotlarni chiqarish (Rasmdagi kabi) ---
@dp.message(PresentationState.waiting_for_topic)
async def process_topic(message: Message, state: FSMContext):
    topic = message.text
    await state.clear()
    
    # Rasmdagi kabi sozlamalar paneli (Mock ko'rinish)
    summary_text = (
        "<b>Ma'lumotlarni tekshiring:</b>\n\n"
        "📖 Uslub: ⚡️ Professional taqdimot\n"
        "🎨 Shablon: Lemon Lesson Sketch\n"
        "📚 Mavzu: " + topic + "\n"
        "✍️ Yozuv tili: 🇺🇿 O'zbekcha (joriy alifbo)\n"
        "📄 Rejalar soni: 3\n"
        "📑 Sahifalar soni: 10\n"
        "🖼 Rasm uslubi: Shablon rasmlari\n"
        "🧩 Tarkibi: Muqova, Rejalar, Kirish, Xulosa, Foydalanilgan adabiyotlar, E'tiboringiz uchun rahmat\n"
        "👤 Muallif: " + message.from_user.full_name.upper() + "\n"
        "🏛 Universitet: -\n"
        "🏷 Logo: Yo'q\n\n"
        "<b>Rejalar:</b>\n"
        "<i>AI tomonidan yoziladi</i>\n\n"
        "💰 <b>Narxi:</b> 3 000 so'm"
    )
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Ma'lumotlarni tahrirlash", callback_data="edit_info")],
            [InlineKeyboardButton(text="✅ Yaratish", callback_data="start_generation")]
        ]
    )
    
    await message.answer(summary_text, reply_markup=markup)

# --- Render uchun Webhook sozlamalari va ilovani ishga tushirish ---
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)

def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    app.on_startup.append(lambda app: on_startup(bot))
    
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
