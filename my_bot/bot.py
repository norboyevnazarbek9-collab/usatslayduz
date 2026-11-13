import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT

# Loggingni sozlash
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Bot va Dispatcher yaratish
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- FSM (Holatlar) ---
class PresentationState(StatesGroup):
    waiting_for_topic = State()

class PaymentState(StatesGroup):
    waiting_for_receipt = State()

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
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception:
        return False

# --- /start komandasi ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Til o'zbek tiliga o'zgartirildi.")
    
    welcome_text = (
        f"Assalomu alaykum, {html.bold(message.from_user.full_name)}!\n"
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

# --- Mavzuni qabul qilish va saqlash ---
@dp.message(PresentationState.waiting_for_topic)
async def process_topic(message: Message, state: FSMContext):
    topic = message.text
    # Mavzuni FSM xotirasiga saqlab qo'yamiz (to'lov tasdiqlanganda ishlatish uchun)
    await state.update_data(topic=topic)
    
    summary_text = (
        "<b>Ma'lumotlarni tekshiring:</b>\n\n"
        "📖 Uslub: ⚡️ Professional taqdimot\n"
        "🎨 Shablon: Lemon Lesson Sketch\n"
        f"📚 Mavzu: <b>{topic}</b>\n"
        "✍️ Yozuv tili: 🇺🇿 O'zbekcha (joriy alifbo)\n"
        "📄 Rejalar soni: 3\n"
        "📑 Sahifalar soni: 10\n"
        "🖼 Rasm uslubi: Shablon rasmlari\n"
        "🧩 Tarkibi: Muqova, Rejalar, Kirish, Xulosa, Foydalanilgan adabiyotlar\n"
        f"👤 Muallif: {message.from_user.full_name.upper()}\n\n"
        "💰 <b>Narxi:</b> 3 000 so'm"
    )
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Ma'lumotlarni tahrirlash", callback_data="edit_info")],
            [InlineKeyboardButton(text="✅ Yaratish", callback_data="start_generation")]
        ]
    )
    
    await message.answer(summary_text, reply_markup=markup)

# --- "Yaratish" bosilganda to'lovga yo'naltirish ---
@dp.callback_query(F.data == "start_generation")
async def ask_for_payment(callback: CallbackQuery):
    payment_text = (
        "💳 <b>To'lov qilish uchun ma'lumot:</b>\n\n"
        "Karta raqami: <code>9860 0000 0000 0000</code> (HUMO/UZCARD)\n"
        "Karta egasi: ALIYEV VALI\n"
        "Summa: <b>3 000 so'm</b>\n\n"
        "⚠️ Pulni o'tkazib bo'lgach, to'lov cheki (skrinshot)ni shu yerga yuboring va pastdagi tugmani bosing."
    )
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ To'lov qildim (Chek yuborish)", callback_data="send_receipt_prompt")]
        ]
    )
    await callback.message.edit_text(payment_text, reply_markup=markup)

# --- Chek yuborishga tayyorgarlik ---
@dp.callback_query(F.data == "send_receipt_prompt")
async def prompt_receipt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Iltimos, to'lov cheki skrinshotini rasm ko'rinishida yuboring:")
    await state.set_state(PaymentState.waiting_for_receipt)

# --- Foydalanuvchi chek rasmini yuborganda ---
@dp.message(PaymentState.waiting_for_receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = message.from_user.username or "Kiritilmagan"
    
    # Foydalanuvchi yuborgan ma'lumotlarni (mavzuni) saqlab qolgan holda holatni tozalaymiz
    data = await state.get_data()
    topic = data.get("topic", "Noma'lum mavzu")
    
    await state.clear()
    await message.answer("⏳ Chekingiz adminga yuborildi. Iltimos, tasdiqlashlarini kuting.")
    
    # Admin uchun tugmalar va ma'lumot (callback ichida user_id va mavzuni saqlaymiz)
    # Eslatma: callback_data uzunligi chegaralanganligi sababli mavzuni qisqartiramiz yoki faqat user_id olib ishlaymiz
    admin_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")
            ]
        ]
    )
    
    admin_text = (
        f"💰 <b>Yangi to'lov cheki keldi!</b>\n\n"
        f"👤 Foydalanuvchi: {user_name}\n"
        f"🔗 Username: @{username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📚 Mavzu: <b>{topic}</b>"
    )
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_file_id,
        caption=admin_text,
        reply_markup=admin_markup
    )

# --- ADMIN "Tasdiqlash" tugmasini bosganda (Slayd yasash va yuborish qismi) ---
@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    try:
        # 1. Foydalanuvchiga xabar beramiz
        await bot.send_message(
            chat_id=user_id,
            text="✅ <b>Tabriklaymiz!</b> To'lovingiz admin tomonidan tasdiqlandi.\n\n"
                 "🔄 Sun'iy intellekt sizning mavzuingiz bo'yicha taqdimot matni va slaydlarini tayyorladi!"
        )
        
        # 2. Slayd matnini generatsiya qilish (Simulyatsiya yoki tayyor matn yaratish)
        presentation_content = (
            f"=====================================\n"
            f"       TAQDIMOT (SLAYD MATNI)        \n"
            f"=====================================\n\n"
            f"1-Slayd: MAVZU VA KIRISH\n"
            f"• Mavzu: Taqdimot ishi\n"
            f"• Reja va asosiy tushunchalar.\n\n"
            f"2-Slayd: ASOSIY QISM\n"
            f"• Mavzuning batafsil tahlili va muhim jihatlari.\n\n"
            f"3-Slayd: XULOSA\n"
            f"• Yakoniy fikrlar va takliflar.\n\n"
            f"E'tiboringiz uchun rahmat!"
        )
        
        # Matnni fayl (.txt) ko'rinishida tayyorlab jo'natamiz
        file_bytes = presentation_content.encode('utf-8')
        document = BufferedInputFile(file_bytes, filename="taqdimot_slayd.txt")
        
        await bot.send_document(
            chat_id=user_id,
            document=document,
            caption="📄 Mana sizning tayyor taqdimot materialingiz! Uni yuklab olib foydalanishingiz mumkin."
        )

        # Admin xabarini yangilaymiz
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n<b>STATUS: ✅ TASDIQLANGAN VA SLAYD YUBORILDI</b>",
            reply_markup=None
        )
        await callback.answer("Muvaffaqiyatli tasdiqlandi va foydalanuvchiga slayd yuborildi!", show_alert=True)
        
    except Exception as e:
        await callback.answer(f"Xatolik: {e}", show_alert=True)

# --- ADMIN "Rad etish" tugmasini bosganda ---
@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text="❌ Afsuski, to'lovingiz rad etildi yoki chek yaroqsiz deb topildi. Qaytadan urinib ko'ring."
        )
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n<b>STATUS: ❌ RAD ETILDI</b>",
            reply_markup=None
        )
        await callback.answer("To'lov rad etildi.", show_alert=True)
    except Exception as e:
        await callback.answer(f"Xatolik: {e}", show_alert=True)

# --- Render Webhook qismi ---
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
