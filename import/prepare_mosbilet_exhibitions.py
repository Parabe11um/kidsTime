"""Convert reviewed exhibition inventory into unpublished staging candidates."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def prepare(activities):
    exhibitions = [item for item in activities if item["kind"] == "exhibition"]
    if len(exhibitions) != 11:
        raise ValueError(f"Ожидались 11 выставок, найдено {len(exhibitions)}")
    result = []
    for item in exhibitions:
        offers = item["offers"]
        if len(offers) != 1 or len(offers[0]["structured_dates"]) != 1:
            raise ValueError(f"Неоднозначные даты: {item['title']}")
        offer = offers[0]
        span = offer["structured_dates"][0]
        start = datetime.fromisoformat(span["starts_at"])
        end = datetime.fromisoformat(span["ends_at"])
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError(f"Некорректный период: {item['title']}")
        if not item["venue_name"] or not item["address"] or not item["title"]:
            raise ValueError(f"Не хватает названия или площадки: {item['title']}")
        if item["age_from"] is None or item["age_from"] > 14:
            raise ValueError(f"Проверьте возраст: {item['title']}")
        if item["review_flags"]:
            raise ValueError(f"Есть замечания к записи: {item['title']}")
        price = re.fullmatch(r"от\s+([\d\s]+)\s*₽", offer["price_hint"] or "")
        if not price:
            raise ValueError(f"Цена для редакторской проверки не найдена: {item['title']}")
        result.append({
            "external_id": offer["source_id"],
            "title": item["title"],
            "source_url": offer["source_url"],
            "venue_name": item["venue_name"],
            "address": item["address"],
            "category": "museums",
            "age_from": item["age_from"],
            "price_from": int(price.group(1).replace(" ", "")),
            "available_from": start.date().isoformat(),
            "available_until": end.date().isoformat(),
            "sessions": [],
            "review_flags": [
                "Цена и период требуют подтверждения перед публикацией; часы JSON-LD не являются сеансом.",
                "Текст, обложка, организатор и площадка требуют редакторской проверки.",
            ],
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="11 выставок для очереди проверки, без записи в базу")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    activities = json.loads(args.input.read_text(encoding="utf-8"))["activities"]
    events = prepare(activities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"events": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MODE=CHECK candidates={len(events)} sessions=0 output={args.output}")
    for event in events:
        print(f"{event['external_id']} | {event['title']} | {event['available_from']} — {event['available_until']} | {event['price_from']} ₽")
    print("База не изменялась; публикация не выполнялась. Проверить условия и площадки перед переносом в Event.")


if __name__ == "__main__":
    main()
