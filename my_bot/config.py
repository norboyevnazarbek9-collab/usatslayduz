import os
from dotenv import load_dotenv

load_dotenv()


def parse_admin_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    result: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if item.isdigit():
            result.append(int(item))
    return result


def parse_channels(raw: str | None) -> list[str]:
    if not raw:
        return []
    channels: list[str] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if not item.startswith("@") and not item.lstrip("-").isdigit():
            item = "@" + item
        channels.append(item)
    return channels


BOT_TOKEN: str = (os.getenv("BOT_TOKEN") or "").strip()

# Bo'sh qolsa ham bot xatosiz ishlaydi
ADMIN_IDS: list[int] = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
REQUIRED_CHANNELS: list[str] = parse_channels(os.getenv("REQUIRED_CHANNELS", ""))
PAYMENT_CARD: str = (os.getenv("PAYMENT_CARD") or "").strip()

# Barcha xizmatlar uchun standart narx: 7 000 so'm
DEFAULT_PRICE: int = int(os.getenv("DEFAULT_PRICE", "7000"))

SERVICE_LABELS: dict[str, str] = {
    "slide": "Yangi Taqdimot (Slayd)",
    "independent": "Yangi Mustaqil ish",
    "abstract": "Yangi Referat",
    "coursework": "Kurs ishi yaratish",
}

SERVICE_PRICES: dict[str, int] = {
    "slide": DEFAULT_PRICE,
    "independent": DEFAULT_PRICE,
    "abstract": DEFAULT_PRICE,
    "coursework": DEFAULT_PRICE,
}
