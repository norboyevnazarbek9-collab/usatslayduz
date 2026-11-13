import asyncio
import logging
import sys
import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
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

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# FSM holatlari
class PresentationState(StatesGroup):
    waiting_for_topic = State()

class PaymentState(StatesGroup):
    waiting_for_receipt = State()

# Asosiy menyu
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Yangi Taqdimot (Slayd)"), KeyboardButton(text="🎁 Sovg'alar")],
            [KeyboardButton(text="📘 Yangi Mustaqil ish"), KeyboardButton(text="📄 Yangi Referat")],
            [KeyboardButton(text="📚 Kurs ishi yaratish")]
        ],
        resize_keyboard=True
    )

# Majburiy obunani tekshirish
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception:
        return False

# Professional PowerPoint (.pptx) Generator
def generate_professional_pptx(topic: str, author: str) -> bytes:
    prs = Presentation()
    
    # 1-Slayd: Muqova (Title Slide)
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = f"Mavzu: {topic}"
    subtitle.text = f"Tayyorladi: {author}\nFan: Sun'iy intellekt va zamonaviy texnologiyalar"
    
    # 2-Slayd: Reja
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Reja:"
    tf = slide.placeholders[1].text_frame
    tf.text = "1. Kirish va asosiy tushunchalar"
    p = tf.add_paragraph()
    p.text = f"2. {topic} ning asosiy xususiyatlari"
    p = tf.add_paragraph()
    p.text = "3. Amaliy ahamiyati va tahlili"
    p = tf.add_paragraph()
    p.text = "4. Xulosa va takliflar"
    
    # 3-Slayd: Kirish
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "1. Kirish"
    tf = slide.placeholders[1].text_frame
    tf.text = f"Hozirgi kunda {topic} masalasi dolzarb mavzulardan biri hisoblanadi. Ushbu taqdimotda ushbu yo'nalishdagi asosiy jihatlar atroflicha ko'rib chiqiladi."
    
    # 4-Slayd: Asosiy qism
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "2. Asosiy qism"
    tf = slide.placeholders[1].text_frame
    tf.text = f"• {topic} bo'yicha ilmiy yondashuvlar\n• Zamonaviy talablar va yechimlar\n• Asosiy ko'rsatkichlar va tahlillar"
    
    # 5-Slayd: Tahlil va natijalar
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "3. Tahlil va natijalar"
    tf = slide.placeholders[1].text_frame
    tf.text = "O'tkazilgan tahlillar shuni ko'rsatadiki, mazkur mavzu kelgusida yanada rivojlanish uchun katta salohiyatga ega."
    
    # 6-Slayd: Xulosa
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "4. Xulosa"
    tf = slide.placeholders[1].text_frame
    tf.text = f"Xulosa o'rnida aytish mumkinki, {topic}ni o'rganish va amaliyotga joriy etish muhim natijalarni beradi."
    
    # 7-Slayd: Yakuniy (E'tibor uchun rahmat)
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "E'tiboringiz uchun rahmat!"
    slide.placeholders[1].text_frame.text = "Savollar bo'lsa marhamat."
    
    # Xotiraga saqlash
    file_stream = io.BytesIO()
    prs.save(file_stream)
    file_stream.seek(0)
    return file_stream.read()

# /start komandasi
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
        "👇 Pastdagi menyudan birini tanlang."
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

# Taqdimot tugmasi
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

@dp.callback_query(F.data == "check_sub")
async def verify_subscription(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.delete()
        await callback.message.answer("Rahmat! Obuna tasdiqlandi. Endi taqdimot mavzusini kiriting:")
        await state.set_state(PresentationState.waiting_for_topic)
    else:
        await callback.answer("Siz hali kanalga obuna bo'lmadingiz! ❌", show_alert=True)

# Mavzuni qabul qilish
@dp.message(PresentationState.waiting_for_topic)
async def process_topic(message: Message, state: FSMContext):
    topic = message.text
    await state.update_data(topic=topic)
    
    summary_text = (
        "<b>Ma'lumotlarni tekshiring:</b>\n\n"
        "📖 Uslub: ⚡️ Professional taqdimot\n"
        "🎨 Shablon: Lemon Lesson Sketch\n"
        f"📚 Mavzu: <b>{topic}</b>\n"
        "✍️ Yozuv tili: 🇺🇿 O'zbekcha (joriy alifbo)\n"
        "📄 Rejalar soni: 4\n"
        "📑 Sahifalar soni: 7\n"
        f"👤 Muallif: {message.from_user.full_name.upper()}\n\n"
        "💰 <b>Narxi:</b> 3 000 so'm"
    )
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yaratish (To'lovga o'tish)", callback_data="start_generation")]
        ]
    )
    await message.answer(summary_text, reply_markup=markup)

# To'lovga o'tish
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

@dp.callback_query(F.data == "send_receipt_prompt")
async def prompt_receipt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Iltimos, to'lov cheki skrinshotini rasm ko'rinishida yuboring:")
    await state.set_state(PaymentState.waiting_for_receipt)

# Chekni qabul qilish va adminga yuborish
@dp.message(PaymentState.waiting_for_receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = message.from_user.username or "Kiritilmagan"
    
    data = await state.get_data()
    topic = data.get("topic", "Taqdimot ishi")
    
    await state.clear()
    await message.answer("⏳ Chekingiz adminga yuborildi. Iltimos, tasdiqlashlarini kuting.")
    
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
    
    # Mavzuni vaqtincha saqlab turish uchun admin xabariga bog'laymiz yoki bot xotirasida saqlaymiz
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_file_id,
        caption=admin_text,
        reply_markup=admin_markup
    )

# ADMIN TASDIqlAGANDA SLAYDNI YASAB BERISH QISMI
@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text="✅ <b>Tabriklaymiz!</b> To'lovingiz admin tomonidan tasdiqlandi.\n\n"
                 "🔄 Professional PowerPoint (.pptx) taqdimotingiz tayyorlanmoqda..."
        )
        
        # Admin xabari matnidan mavzuni ajratib olish yoki standart nom berish
        caption = callback.message.caption
        topic_line = [line for line in caption.split("\n") if "Mavzu:" in line]
        topic = topic_line[0].replace("Mavzu: ", "").replace("<b>", "").replace("</b>", "").strip() if topic_line else "Taqdimot"
        
        # PowerPoint faylni generatsiya qilish
        pptx_bytes = generate_professional_pptx(topic=topic, author="SlaydGPT AI")
        document = BufferedInputFile(pptx_bytes, filename=f"taqdimot_{user_id}.pptx")
        
        # Foydalanuvchiga .pptx faylni yuborish
        await bot.send_document(
            chat_id=user_id,
            document=document,
            caption="🎉 <b>Mana sizning tayyor PowerPoint taqdimotingiz!</b>\nUni yuklab olib bemalol foydalanishingiz mumkin."
        )

        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n<b>STATUS: ✅ TASDIQLANGAN VA PPTX YUBORILDI</b>",
            reply_markup=None
        )
        await callback.answer("Muvaffaqiyatli tasdiqlandi va slayd yuborildi!", show_alert=True)
        
    except Exception as e:
        await callback.answer(f"Xatolik: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    try:
        await bot.send_message(
            chat_id=user_id,
            text="❌ Afsuski, to'lovingiz rad etildi yoki chek yaroqsiz deb topildi."
        )
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n<b>STATUS: ❌ RAD ETILDI</b>",
            reply_markup=None
        )
        await callback.answer("To'lov rad etildi.", show_alert=True)
    except Exception as e:
        await callback.answer(f"Xatolik: {e}", show_alert=True)

# Webhook qismi
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)

def main():
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    app.on_startup.append(lambda app: on_startup(bot))
    
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
