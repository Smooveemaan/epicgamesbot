import requests
import json
from datetime import datetime, timezone, timedelta
from telegram import Bot
import html
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATE_FILE = "sent_games.json"

URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"

MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

MSK = timezone(timedelta(hours=3))

def load_sent():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(data), f, ensure_ascii=False, indent=2)

def pick_image(el):
    for img in el.get("keyImages", []):
        if img.get("type") in ("OfferImageWide", "DieselStoreFrontWide"):
            return img.get("url")

    images = el.get("keyImages", [])
    if images:
        return images[0].get("url")

    return None

def build_store_url(el):
    slug = el.get("productSlug")
    if slug:
        return f"https://store.epicgames.com/p/{slug}"
    mappings = el.get("catalogNs", {}).get("mappings", [])
    if mappings:
        return f"https://store.epicgames.com/p/{mappings[0].get('pageSlug')}"
    return "https://store.epicgames.com/"

def get_free_games():
    r = requests.get(URL, timeout=20)
    data = r.json()

    elements = data["data"]["Catalog"]["searchStore"]["elements"]

    result = []

    for el in elements:
        promos = el.get("promotions")
        if not promos:
            continue

        offers = promos.get("promotionalOffers")
        if not offers:
            continue

        # Пробегаем все промо-офферы
        for offer_group in offers:
            for promo in offer_group.get("promotionalOffers", []):
                if promo["discountSetting"]["discountPercentage"] != 0:
                    continue

                result.append({
                    "id": el["id"],
                    "title": el["title"],
                    "image": pick_image(el),
                    "url": build_store_url(el),
                    "start": promo.get("startDate"),
                    "end": promo.get("endDate")
                })

    return result

def format_ru_date_with_time(dt):
    if not dt:
        return ""
    d = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    d_msk = d.astimezone(MSK)
    return f"{d_msk.day} {MONTHS_RU[d_msk.month - 1]} {d_msk.hour:02d}:{d_msk.minute:02d}"

def main():
    bot = Bot(token=BOT_TOKEN)

    sent = load_sent()
    games = get_free_games()
    new_sent = set(sent)  # начинаем с уже отправленных

    for g in games:
        if g["id"] in sent:
            continue  # пропускаем уже отправленные

        # Экранируем название игры
        safe_title = html.escape(g["title"])
        url = g["url"]
        end = format_ru_date_with_time(g["end"])
        caption = f'<a href="{url}"><b>{safe_title}</b></a>\n\n<i>Бесплатно до {end} МСК</i>'

        if g["image"]:
            bot.send_photo(
                chat_id=CHAT_ID,
                photo=g["image"],
                caption=caption,
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                chat_id=CHAT_ID,
                text=caption,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        # Добавляем в sent только после успешной отправки
        new_sent.add(g["id"])

    save_sent(new_sent)

print("Отправка игры:", g["title"])
print("URL:", g["url"])
print("CHAT_ID:", CHAT_ID)

if __name__ == "__main__":
    main()
