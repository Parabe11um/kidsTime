"""Bounded read-only review of the existing Mosbilet places inventory."""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from collect_mosbilet_pilot import BASE, LIST_URL, event_data, fetch, parse_page


def source_id(url):
    parsed = urlparse(url)
    match = re.fullmatch(r"/event/(\d+)/", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "bilet.mos.ru" or not match or parsed.query:
        raise ValueError(f"Неожиданная ссылка на первоисточник: {url}")
    return match.group(1)


def structured_dates(page):
    dates = []
    for event in event_data(page):
        start = event.get("startDate")
        end = event.get("endDate")
        if not isinstance(start, str):
            continue
        try:
            started = datetime.fromisoformat(start)
            ended = datetime.fromisoformat(end) if isinstance(end, str) else None
        except ValueError:
            continue
        dates.append({"starts_at": started.isoformat(), "ends_at": ended.isoformat() if ended else None})
    return dates


def audit(inventory, listing_labels, details):
    report = []
    for place in inventory:
        for activity in place["activities"]:
            offers = []
            flags = list(activity["review_flags"])
            for url in activity["source_urls"]:
                event_id = source_id(url)
                label = listing_labels.get(event_id)
                page = details.get(event_id)
                dates = structured_dates(page) if page is not None else []
                price = re.search(r"\bот\s+([\d\s]+)\s*₽", label or "")
                offers.append({
                    "source_id": f"mosbilet-{event_id}",
                    "source_url": url,
                    "listing_label": label,
                    "price_hint": "от " + price.group(1).strip() + " ₽" if price else
                        "Бесплатно" if label and label.startswith("Бесплатно") else None,
                    "structured_dates": dates,
                })
                if label is None:
                    flags.append(f"Карточка {event_id} отсутствует в текущей выдаче")
                if page is None:
                    flags.append(f"Страница {event_id} не получена")
                elif not dates:
                    flags.append(f"В карточке {event_id} нет дат JSON-LD")
            if len(offers) > 1:
                flags.append("Варианты билетов: сроки и цены проверять отдельно")
            if not activity["availability_label"]:
                flags.append("Нет общего срока для вариантов билетов")
            report.append({
                "venue_name": place["name"], "address": place["address"],
                "title": activity["title"], "kind": activity["kind"],
                "age_from": activity["age_from"],
                "availability_label": activity["availability_label"],
                "offers": offers, "review_flags": sorted(set(flags)),
                "editorial_status": "review_required",
            })
    return report


def main():
    parser = argparse.ArgumentParser(description="Проверка сроков и билетов без импорта")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    places = json.loads(args.input.read_text(encoding="utf-8"))["places"]
    urls = {url for place in places for activity in place["activities"] for url in activity["source_urls"]}
    if len(places) != 10 or len(urls) != 18:
        parser.error(f"Ожидались 10 мест и 18 карточек; получено {len(places)} и {len(urls)}; файл не записан")
    ids = [source_id(url) for url in sorted(urls)]
    listing = parse_page(fetch(LIST_URL))
    labels = {}
    for href, label in listing.links:
        try:
            labels[source_id(href if href.startswith("https://") else BASE + href)] = label
        except ValueError:
            continue
    details = {}
    for index, event_id in enumerate(ids):
        if index:
            time.sleep(1)
        try:
            details[event_id] = parse_page(fetch(f"{BASE}/event/{event_id}/"))
        except (OSError, ValueError) as error:
            print(f"FETCH_ERROR id={event_id} error={type(error).__name__}")
    activities = audit(places, labels, details)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"activities": activities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MODE=CHECK activities={len(activities)} detail_pages={len(details)}/{len(ids)} output={args.output}")
    for item in activities:
        print(f"{item['venue_name']} | {item['title']} | {item['kind']} | {item['age_from']}+ | период={item['availability_label'] or 'РАЗНЫЕ'}")
        for offer in item["offers"]:
            spans = ", ".join(f"{date['starts_at']} — {date['ends_at'] or '?'}" for date in offer["structured_dates"])
            print(f"  {offer['source_id']} | {offer['price_hint'] or 'цена не найдена'} | JSON-LD={spans or 'нет'}")
        if item["review_flags"]:
            print("  ПРОВЕРИТЬ: " + "; ".join(item["review_flags"]))
    print("База не изменялась. JSON-LD и цены из выдачи не означают наличие билетов или ежедневные сеансы.")


if __name__ == "__main__":
    main()
