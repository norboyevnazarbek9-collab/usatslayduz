import asyncio
import io
import json
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from config import (
    ADMIN_IDS,
    BOT_TOKEN,
    DEFAULT_PRICE,
    PAYMENT_CARD,
    REQUIRED_CHANNELS,
    SERVICE_LABELS,
    SERVICE_PRICES,
)
from pptx_builder import create_presentation_bytes
from prompts import (
    build_abstract_prompt,
    build_coursework_prompt,
    build_independent_prompt,
    build_slide_prompt,
    clean_text,
)

logging.basicConfig(level=logging.INFO)
router = Router()


# --- FSM Holatlar ---
class OrderStates(StatesGroup):
    waiting_topic = State()
    waiting_subject = State()
    waiting_slides_count = State()
    waiting_receipt = State()
    waiting_promo = State()


# --- Xotiradagi vaqtinchalik ma'lumotlar (proda DB ga ko'chiring) ---
USER_BONUSES: dict[int, int] = {}      # user_id -> bonus balans (so'mda)
USER_REFERRALS: dict[int, int] = {}    # user_id -> taklif qilganlar soni
PENDING_ORDERS: dict[str, dict] = {}   # order_id -> buyurtma ma'lumotlari


# --- Klaviaturalar ---
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Yangi Taqdimot (Slayd)"),
                KeyboardButton(text="Sovg'alar"),
            ],
            [
                KeyboardButton(text="Yangi Mustaqil ish"),
                KeyboardButton(text="Yangi Referat"),
            ],
            [
                KeyboardButton(text="Kurs ishi yaratish"),
            ],
        ],
        resize_keyboard=True,
    )


def subscription_keyboard(channels: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, ch in enumerate(channels, start=1):
        clean_ch = ch.lstrip("@")
        url = f"https://t.me/{clean_ch}" if not ch.startswith("-") else "https://t.me/"
        rows.append([InlineKeyboardButton(text=f"Kanal {idx} ga a'zo bo'lish", url=url)])
    rows.append([InlineKeyboardButton(text="Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gifts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Promo-kod kiritish", callback_data="enter_promo")],
        ]
    )


def admin_order_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Tasdiqlash", callback_data=f"approve:{order_id}"),
                InlineKeyboardButton(text="Rad etish", callback_data=f"reject:{order_id}"),
            ]
        ]
    )


# --- Yordamchi funksiyalar ---
async def is_user_subscribed(bot: Bot, user_id: int, channels: list[str]) -> tuple[bool, list[str]]:
    if not channels:
        return True, []

    not_sub: list[str] = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ("left", "kicked"):
                not_sub.append(ch)
        except Exception as e:
            logging.warning(f"Kanalni tekshirishda xato ({ch}): {e}")
            continue

    return len(not_sub) == 0, not_sub


async def notify_admins(
    bot: Bot,
    text: str,
    photo_file_id: str | None = None,
    doc_file_id: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> int:
    if not ADMIN_IDS:
        return 0

    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            if photo_file_id:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_file_id,
                    caption=text,
                    reply_markup=reply_markup,
                )
            elif doc_file_id:
                await bot.send_document(
                    chat_id=admin_id,
                    document=doc_file_id,
                    caption=text,
                    reply_markup=reply_markup,
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=reply_markup,
                )
            sent += 1
        except Exception as e:
            logging.warning(f"Adminga yuborishda xato ({admin_id}): {e}")
            continue
    return sent


def get_payment_text(service_key: str, user_id: int) -> tuple[int, str]:
    base_price = SERVICE_PRICES.get(service_key, DEFAULT_PRICE)  # Standart 7 000 so'm
    bonus = USER_BONUSES.get(user_id, 0)
    final_price = max(0, base_price - bonus)

    card_line = (
        f"Karta raqami: {PAYMENT_CARD}"
        if PAYMENT_CARD
        else "To'lov kartasi hozircha kiritilmagan. Chek yuboring yoki admin bilan bog'laning."
    )
    bonus_line = f"Bonus chegirma: {bonus:,} so'm\n".replace(",", " ") if bonus > 0 else ""
    price_str = f"{final_price:,} so'm".replace(",", " ")

    text = (
        f"Xizmat: {SERVICE_LABELS.get(service_key, 'Xizmat')}\n"
        f"{bonus_line}"
        f"To'lov summasi: {price_str}\n"
        f"{card_line}\n\n"
        f"To'lov cheki (rasm yoki fayl) yuboring."
    )
    return final_price, text


async def call_llm(prompt: str) -> str:
    """
    Bu yerga o'zingizning LLM API chaqiruvingizni qo'ying.
    Masalan: OpenAI / Gemini SDK orqali matn qaytaradi.
    """
    raise NotImplementedError("call_llm() funksiyasiga LLM API chaqiruvini ulang.")


async def deliver_service(bot: Bot, chat_id: int, order: dict) -> None:
    service_key = order["service_key"]
    mavzu = clean_text(order["topic"])
    fan = clean_text(order["subject"])
    slides_count = order.get("slides_count", 7)

    await bot.send_message(chat_id=chat_id, text="Material tayyorlanmoqda, biroz kuting...")

    if service_key == "slide":
        prompt = build_slide_prompt(mavzu=mavzu, fan=fan, slayd_soni=slides_count)
        raw = await call_llm(prompt)
        raw_clean = clean_text(raw)

        # JSON ajratib olish
        start_idx = raw_clean.find("{")
        end_idx = raw_clean.rfind("}")
        slides_list: list[dict] = []
        if start_idx != -1 and end_idx != -1:
            try:
                parsed = json.loads(raw_clean[start_idx : end_idx + 1])
                if isinstance(parsed, dict) and isinstance(parsed.get("slides"), list):
                    slides_list = parsed["slides"]
            except Exception as e:
                logging.warning(f"Slayd JSON parse xatosi: {e}")

        if not slides_list:
            slides_list = [
                {
                    "title": f"{mavzu} — Asosiy fikrlar",
                    "bullets": [
                        f"{fan} fani doirasida {mavzu} tahlili.",
                        "Nazariy asoslar va amaliy qo'llanilishi.",
                        "Asosiy natijalar va tavsiyalar.",
                    ],
                    "speaker_notes": f"{mavzu} mavzusi bo'yicha qisqacha izoh.",
                }
            ]

        pptx_buf = create_presentation_bytes(
            slides_data=slides_list,
            topic=mavzu,
            subject=fan,
            author=order.get("full_name", "Foydalanuvchi"),
        )
        doc = BufferedInputFile(pptx_buf.getvalue(), filename=f"taqdimot_{chat_id}.pptx")
        await bot.send_document(chat_id=chat_id, document=doc, caption="Tayyor taqdimot (.pptx)")
        return

    if service_key == "independent":
        prompt = build_independent_prompt(mavzu=mavzu, fan=fan)
        title_prefix = "Mustaqil ish"
    elif service_key == "abstract":
        prompt = build_abstract_prompt(mavzu=mavzu, fan=fan)
        title_prefix = "Referat"
    else:
        prompt = build_coursework_prompt(mavzu=mavzu, fan=fan)
        title_prefix = "Kurs ishi"

    raw_text = await call_llm(prompt)
    final_text = clean_text(raw_text)

    # Uzun matnni bo'lib yuborish
    chunk_size = 3800
    for i in range(0, len(final_text), chunk_size):
        await bot.send_message(chat_id=chat_id, text=final_text[i : i + chunk_size])

    file_bytes = io.BytesIO(final_text.encode("utf-8"))
    txt_doc = BufferedInputFile(file_bytes.getvalue(), filename=f"{title_prefix.lower().replace(' ', '_')}_{chat_id}.txt")
    await bot.send_document(chat_id=chat_id, document=txt_doc, caption=f"Tayyor {title_prefix}")


# --- Handlerlar ---
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id

    # Referal parametrini tekshirish: /start 123456
    args = (message.text or "").split(maxsplit=1)
    if len(args) == 2 and args[1].strip().isdigit():
        ref_id = int(args[1].strip())
        if ref_id != user_id and ref_id not in USER_REFERRALS:
            USER_REFERRALS[ref_id] = USER_REFERRALS.get(ref_id, 0) + 1
            USER_BONUSES[ref_id] = USER_BONUSES.get(ref_id, 0) + 2000

    ok, missing = await is_user_subscribed(bot, user_id, REQUIRED_CHANNELS)
    if not ok:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_keyboard(missing),
        )
        return

    await message.answer(
        "Assalomu alaykum! Kerakli bo'limni tanlang:",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot) -> None:
    ok, missing = await is_user_subscribed(bot, callback.from_user.id, REQUIRED_CHANNELS)
    if ok:
        await callback.message.delete()
        await callback.message.answer("Obuna tasdiqlandi! Bo'limni tanlang:", reply_markup=main_menu_keyboard())
    else:
        await callback.answer("Hali barcha kanallarga obuna bo'lmadingiz.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=subscription_keyboard(missing))


@router.message(F.text == "Sovg'alar")
async def panel_gifts(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    bonus = USER_BONUSES.get(user_id, 0)
    refs = USER_REFERRALS.get(user_id, 0)

    text = (
        "Sovg'alar va bonuslar bo'limi:\n\n"
        f"Joriy bonus balansingiz: {bonus:,} so'm\n".replace(",", " ")
        + f"Taklif qilingan do'stlar: {refs} ta\n"
        + f"Standart xizmat narxi: {DEFAULT_PRICE:,} so'm\n\n".replace(",", " ")
        + f"Shaxsiy referal havolangiz:\n{ref_link}\n\n"
        + "Do'stingiz havola orqali kirsa, hisobingizga 2 000 so'm bonus qo'shiladi."
    )
    await message.answer(text, reply_markup=gifts_keyboard())


@router.callback_query(F.data == "enter_promo")
async def cb_enter_promo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderStates.waiting_promo)
    await callback.message.answer("Promo-kodni kiriting (masalan: START7000):")
    await callback.answer()


@router.message(OrderStates.waiting_promo)
async def process_promo(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip().upper()
    user_id = message.from_user.id
    if code in ("START7000", "BONUS2026"):
        USER_BONUSES[user_id] = max(USER_BONUSES.get(user_id, 0), 3000)
        await message.answer("Promo-kod qabul qilindi! 3 000 so'm bonus qo'shildi.", reply_markup=main_menu_keyboard())
    else:
        await message.answer("Promo-kod topilmadi yoki amal qilish muddati tugagan.", reply_markup=main_menu_keyboard())
    await state.clear()


@router.message(
    F.text.in_(
        {
            "Yangi Taqdimot (Slayd)",
            "Yangi Mustaqil ish",
            "Yangi Referat",
            "Kurs ishi yaratish",
        }
    )
)
async def start_service_order(message: Message, bot: Bot, state: FSMContext) -> None:
    ok, missing = await is_user_subscribed(bot, message.from_user.id, REQUIRED_CHANNELS)
    if not ok:
        await message.answer(
            "Avval majburiy obuna kanallariga a'zo bo'ling:",
            reply_markup=subscription_keyboard(missing),
        )
        return

    mapping = {
        "Yangi Taqdimot (Slayd)": "slide",
        "Yangi Mustaqil ish": "independent",
        "Yangi Referat": "abstract",
        "Kurs ishi yaratish": "coursework",
    }
    service_key = mapping[message.text]
    await state.clear()
    await state.update_data(service_key=service_key)
    await state.set_state(OrderStates.waiting_topic)
    await message.answer(f"{SERVICE_LABELS[service_key]} uchun mavzuni kiriting:")


@router.message(OrderStates.waiting_topic)
async def process_topic(message: Message, state: FSMContext) -> None:
    topic = clean_text(message.text)
    if len(topic) < 2:
        await message.answer("Mavzu juda qisqa. Iltimos, aniq mavzu kiriting:")
        return

    await state.update_data(topic=topic)
    await state.set_state(OrderStates.waiting_subject)
    await message.answer("Fan yoki yo'nalish nomini kiriting:")


@router.message(OrderStates.waiting_subject)
async def process_subject(message: Message, state: FSMContext) -> None:
    subject = clean_text(message.text) or "Umumiy"
    data = await state.get_data()
    service_key = data["service_key"]

    await state.update_data(subject=subject)

    if service_key == "slide":
        await state.set_state(OrderStates.waiting_slides_count)
        await message.answer("Nechta slayd bo'lsin? (Masalan: 7, 5 dan 15 gacha son kiriting):")
        return

    price, pay_text = get_payment_text(service_key, message.from_user.id)
    await state.update_data(slides_count=7, price=price)
    await state.set_state(OrderStates.waiting_receipt)
    await message.answer(pay_text)


@router.message(OrderStates.waiting_slides_count)
async def process_slides_count(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (3 <= int(raw) <= 20):
        await message.answer("Iltimos, 3 dan 20 gacha bo'lgan son kiriting (masalan: 7):")
        return

    slides_count = int(raw)
    data = await state.get_data()
    service_key = data["service_key"]
    price, pay_text = get_payment_text(service_key, message.from_user.id)

    await state.update_data(slides_count=slides_count, price=price)
    await state.set_state(OrderStates.waiting_receipt)
    await message.answer(pay_text)


@router.message(OrderStates.waiting_receipt, F.photo | F.document)
async def process_receipt(message: Message, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    user = message.from_user
    order_id = f"{user.id}_{message.message_id}"

    photo_id = message.photo[-1].file_id if message.photo else None
    doc_id = message.document.file_id if message.document else None

    order = {
        "order_id": order_id,
        "user_id": user.id,
        "username": f"@{user.username}" if user.username else "yo'q",
        "full_name": clean_text(user.full_name) or "Foydalanuvchi",
        "service_key": data["service_key"],
        "topic": data["topic"],
        "subject": data["subject"],
        "slides_count": data.get("slides_count", 7),
        "price": data.get("price", DEFAULT_PRICE),
    }
    PENDING_ORDERS[order_id] = order

    admin_caption = (
        f"Yangi to'lov cheki!\n"
        f"Buyurtma ID: {order_id}\n"
        f"Foydalanuvchi: {order['full_name']} ({order['username']})\n"
        f"ID: {user.id}\n"
        f"Xizmat: {SERVICE_LABELS[order['service_key']]}\n"
        f"Mavzu: {order['topic']}\n"
        f"Fan: {order['subject']}\n"
        f"Summa: {order['price']:,} so'm".replace(",", " ")
    )

    sent_count = await notify_admins(
        bot=bot,
        text=admin_caption,
        photo_file_id=photo_id,
        doc_file_id=doc_id,
        reply_markup=admin_order_keyboard(order_id),
    )

    await state.clear()

    if sent_count > 0:
        await message.answer(
            "Chekingiz adminga yuborildi. Tasdiqlangach material darhol yuboriladi.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        # Agar ADMIN_IDS hali kiritilmagan bo'lsa ham bot to'xtab qolmaydi
        await message.answer(
            "Admin ID hali kiritilmagan. Chekingiz vaqtincha qabul qilindi.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(OrderStates.waiting_receipt)
async def invalid_receipt(message: Message) -> None:
    await message.answer("Iltimos, to'lov chekini rasm yoki fayl ko'rinishida yuboring.")


@router.callback_query(F.data.startswith("approve:"))
async def cb_approve_order(callback: CallbackQuery, bot: Bot) -> None:
    if ADMIN_IDS and callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return

    order_id = callback.data.split(":", 1)[1]
    order = PENDING_ORDERS.pop(order_id, None)
    if not order:
        await callback.answer("Buyurtma topilmadi yoki allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    # Ishlatilgan bonusni yechish
    used_bonus = max(0, SERVICE_PRICES.get(order["service_key"], DEFAULT_PRICE) - order["price"])
    if used_bonus > 0 and order["user_id"] in USER_BONUSES:
        USER_BONUSES[order["user_id"]] = max(0, USER_BONUSES[order["user_id"]] - used_bonus)

    await callback.answer("Tasdiqlandi!")
    await bot.send_message(chat_id=order["user_id"], text="To'lovingiz tasdiqlandi! Material tayyorlanmoqda...")
    await deliver_service(bot=bot, chat_id=order["user_id"], order=order)


@router.callback_query(F.data.startswith("reject:"))
async def cb_reject_order(callback: CallbackQuery, bot: Bot) -> None:
    if ADMIN_IDS and callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return

    order_id = callback.data.split(":", 1)[1]
    order = PENDING_ORDERS.pop(order_id, None)
    await callback.answer("Rad etildi.")
    if order:
        await bot.send_message(
            chat_id=order["user_id"],
            text="To'lov cheki tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning.",
        )


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylda ko'rsatilmagan.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
