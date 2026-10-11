"""Review inventory of children's venues and long-running activities, no DB writes."""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from collect_mosbilet_pilot import BASE, LIST_URL, event_data, fetch, parse_page, venue_from_visible


def listing_cards(page, excluded_ids):
    cards = {}
    for href, label in page.links:
        url = urljoin(BASE, href)
        match = re.fullmatch(r"/event/(\d+)/", urlparse(url).path)
        if match and urlparse(url).hostname == "bilet.mos.ru" and "Для детей" in label:
            external_id = f"mosbilet-{match.group(1)}"
            if external_id not in excluded_ids and re.search(r"·\s*\d{1,2}\+", label):
                cards[match.group(1)] = label
    return cards


def activity_title(title):
    # Ticket capacity is an offer, not a separate attraction.
    title = " ".join(title.split())
    return re.sub(r"\s*\(билет на (?:одного|двух|тр[её]х|четыр[её]х|\d+) человек(?:а)?\)", "", title, flags=re.I).strip()


def inventory_venue(page):
    venue, address = venue_from_visible(page)
    if venue and address:
        return venue, address
    # Зеленоградские адреса часто указывают корпус без улицы и номера дома.
    for index, word in enumerate(page.words):
        if word != "Место проведения" or index + 2 >= len(page.words):
            continue
        name = page.words[index + 1]
        for part in page.words[index + 2:index + 8]:
            if re.fullmatch(r"Зеленоград,\s*корпус\s+\d+[А-Яа-яA-Za-z]?", part, re.I):
                return name, "Москва, " + part
    return venue, address


def prepare(event_id, label, page):
    venue, address = inventory_venue(page)
    structured = event_data(page)
    title = next((item.get("name") for item in structured if item.get("name")), "")
    age = re.search(r"·\s*(\d{1,2})\+", label)
    period = re.search(r"(?:\d{1,2}\s+\w+\s*[—–-]\s*\d{1,2}\s+\w+|\bдо\s+\d{1,2}\s+\w+)", label, re.I)
    flags = []
    if not venue or not address:
        flags.append("Площадка или адрес не найдены в видимой карточке")
    if not title or not age:
        flags.append("Название или возраст требуют проверки")
    if not period:
        flags.append("Период доступности не найден на странице списка")
    return {
        "title": activity_title(title),
        "age_from": int(age.group(1)) if age else None,
        "availability_label": period.group(0) if period else None,
        "source_urls": [f"{BASE}/event/{event_id}/"],
        "source_ids": [f"mosbilet-{event_id}"],
        "kind": "exhibition" if "Выставки" in label else "activity",
        "venue_name": venue,
        "address": address,
        "review_flags": flags,
    }


def group_places(records):
    places = {}
    for record in records:
        # Missing address must never merge unrelated venues.
        key = (record["venue_name"], record["address"]) if record["address"] else tuple(record["source_ids"])
        place = places.setdefault(key, {
            "name": record["venue_name"], "address": record["address"],
            "activities": [], "review_flags": [],
        })
        place["review_flags"].extend(record["review_flags"])
        existing = next((activity for activity in place["activities"] if activity["title"] == record["title"]), None)
        if existing:
            existing["source_ids"].extend(record["source_ids"])
            existing["source_urls"].extend(record["source_urls"])
            existing["review_flags"].append("Несколько карточек одного занятия; проверить варианты билета")
            if existing["availability_label"] != record["availability_label"]:
                existing["review_flags"].append("У вариантов билета различаются периоды; проверить сроки")
                existing["availability_label"] = None
        else:
            place["activities"].append({field: record[field] for field in (
                "title", "age_from", "availability_label", "source_urls", "source_ids", "kind", "review_flags"
            )})
    for place in places.values():
        place["review_flags"] = sorted(set(place["review_flags"]))
        for activity in place["activities"]:
            activity["review_flags"] = sorted(set(activity["review_flags"]))
    return list(places.values())


def main():
    parser = argparse.ArgumentParser(description="Ручной инвентарь детских мест; без импорта")
    parser.add_argument("--exclude", type=Path, required=True, help="JSON с разовыми сеансами, уже разобранными отдельно")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-details", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.max_details <= 24:
        parser.error("--max-details должен быть от 1 до 24")
    excluded = json.loads(args.exclude.read_text(encoding="utf-8"))
    excluded = excluded.get("events", []) if isinstance(excluded, dict) else excluded
    excluded_ids = {item["external_id"] for item in excluded}
    cards = listing_cards(parse_page(fetch(LIST_URL)), excluded_ids)
    if len(cards) > args.max_details:
        parser.error(f"Найдено {len(cards)} карточек, лимит {args.max_details}; файл не записан")
    records = []
    for index, (event_id, label) in enumerate(cards.items()):
        if index:
            time.sleep(1)
        records.append(prepare(event_id, label, parse_page(fetch(f"{BASE}/event/{event_id}/"))))
    places = group_places(records)
    if not places:
        parser.error("Детские площадки не найдены; файл не записан")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"places": places}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MODE=CHECK cards={len(records)} places={len(places)} activities={sum(len(p['activities']) for p in places)} output={args.output}")
    for place in places:
        print(f"{place['name']} | {place['address']} | activities={len(place['activities'])} | flags={'; '.join(place['review_flags']) or 'none'}")
    print("База не изменялась. Периоды требуют редакторской проверки; сеансы не создавались.")


if __name__ == "__main__":
    main()
