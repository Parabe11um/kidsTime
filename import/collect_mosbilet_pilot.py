"""Manual, bounded Mosbilet children's events inventory. No database writes."""

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BASE = "https://bilet.mos.ru"
LIST_URL = BASE + "/dlya-detey/"
MOSCOW = ZoneInfo("Europe/Moscow")
ADDRESS_WORDS = ("улица", "шоссе", "проспект", "переулок", "проезд", "площадь", "набережная", "бульвар", "дом")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.link = None
        self.link_text = []
        self.links = []
        self.words = []
        self.script_type = None
        self.script_text = []
        self.jsonld = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script":
            self.script_type = attributes.get("type")
            self.script_text = []
            self.skip += 1
        elif tag == "style":
            self.skip += 1
        elif tag == "a" and not self.skip:
            self.link = attributes.get("href")
            self.link_text = []

    def handle_data(self, data):
        if self.script_type == "application/ld+json":
            self.script_text.append(data)
        if self.skip:
            return
        value = " ".join(data.split())
        if value:
            self.words.append(value)
            if self.link is not None:
                self.link_text.append(value)

    def handle_endtag(self, tag):
        if tag == "a" and self.link is not None:
            self.links.append((self.link, " ".join(self.link_text)))
            self.link = None
        elif tag == "script":
            if self.script_type == "application/ld+json":
                try:
                    self.jsonld.append(json.loads("".join(self.script_text)))
                except json.JSONDecodeError:
                    pass
            self.script_type = None
            self.skip = max(0, self.skip - 1)
        elif tag == "style":
            self.skip = max(0, self.skip - 1)


def parse_page(html):
    page = Page()
    page.feed(html)
    return page


def child_candidates(page, start, end):
    candidates = {}
    if start.year != 2026 or start.month != 10 or end.month != 10:
        raise ValueError("Пилот ограничен октябрём 2026 года")
    date_labels = [f"{day} октября" for day in range(start.day, end.day + 1)]
    for href, label in page.links:
        path = urlparse(urljoin(BASE, href)).path
        match = re.fullmatch(r"/event/(\d+)/", path)
        if not match or not re.search(r"\bДля детей\b", label):
            continue
        if not re.search(r"\b(?:Мастер-классы|Встречи|Квесты|Игры|Для детей)\s*·\s*(?:0|3|6|8|12)\+", label):
            continue
        # A single calendar date; skip exhibitions, date ranges and ticket variants.
        if not any(
            re.search(rf"(?<![\d–—-]){re.escape(day_label)}\b", label)
            and not re.search(rf"\bдо\s+{re.escape(day_label)}\b", label)
            for day_label in date_labels
        ):
            continue
        candidates[match.group(1)] = label
    return candidates


def event_data(page):
    events = []
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            kind = value.get("@type")
            if kind == "Event" or isinstance(kind, list) and "Event" in kind:
                events.append(value)
            for key in ("@graph", "mainEntity", "itemListElement"):
                if key in value:
                    visit(value[key])
    for block in page.jsonld:
        visit(block)
    return events


def venue_from_visible(page):
    for index, word in enumerate(page.words):
        if word == "Место проведения" and index + 1 < len(page.words):
            name = page.words[index + 1]
            after = page.words[index + 2:index + 8]
            address = next((part for part in after if any(marker in part.lower() for marker in ADDRESS_WORDS)), None)
            if name and address:
                return name, "Москва, " + address if not address.startswith("Москва") else address
    return None, None


def prepare(event_id, listing_label, page, start, end):
    venue, address = venue_from_visible(page)
    structured = event_data(page)
    issues = []
    if not venue or not address:
        issues.append("Не найден адрес площадки в видимой карточке")
    sessions = []
    titles = []
    for item in structured:
        title = item.get("name")
        if title:
            titles.append(title)
        raw_start = item.get("startDate")
        if not isinstance(raw_start, str):
            continue
        try:
            starts = datetime.fromisoformat(raw_start)
        except ValueError:
            continue
        if starts.tzinfo is None or not start <= starts.astimezone(MOSCOW).date() <= end:
            continue
        session = {"starts_at": starts.isoformat()}
        raw_end = item.get("endDate")
        if isinstance(raw_end, str):
            try:
                ends = datetime.fromisoformat(raw_end)
                if ends.tzinfo is not None and ends > starts:
                    session["ends_at"] = ends.isoformat()
            except ValueError:
                pass
        sessions.append(session)
        structured_address = item.get("location", {}).get("address", {}) if isinstance(item.get("location"), dict) else {}
        if isinstance(structured_address, dict):
            candidate_address = structured_address.get("name", "")
            if candidate_address and address and candidate_address.lower() not in address.lower():
                issues.append("Адрес в JSON-LD отличается от адреса видимой площадки")
    if not sessions:
        issues.append("Нет точного сеанса с часовым поясом в JSON-LD")
    age = re.search(r"·\s*(\d{1,2})\+", listing_label)
    if not age or not titles:
        issues.append("Не найден возраст или название")
    return {
        "external_id": f"mosbilet-{event_id}",
        "title": titles[0] if titles else "",
        "source_url": f"{BASE}/event/{event_id}/",
        "venue_name": venue,
        "address": address,
        "category": "workshops" if "Мастер-классы" in listing_label else "",
        "age_from": int(age.group(1)) if age else None,
        "sessions": sessions,
        "is_free": listing_label.startswith("Бесплатно"),
        "review_flags": sorted(set(issues)),
    }


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"}), timeout=15) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("Страница превышает 2 МБ")
    return body.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Один день детской афиши; JSON для проверки, без импорта")
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-details", type=int, default=8)
    parser.add_argument("--compare", type=Path, help="Сравнить ID с ранее собранным JSON")
    args = parser.parse_args()
    if not 1 <= args.max_details <= 12:
        parser.error("--max-details должен быть от 1 до 12")
    if not 1 <= args.days <= 14:
        parser.error("--days должен быть от 1 до 14")
    end = args.from_date + timedelta(days=args.days - 1)
    candidates = child_candidates(parse_page(fetch(LIST_URL)), args.from_date, end)
    records = []
    for index, (event_id, label) in enumerate(list(candidates.items())[:args.max_details]):
        if index:
            time.sleep(1)
        records.append(prepare(event_id, label, parse_page(fetch(f"{BASE}/event/{event_id}/")), args.from_date, end))
    if not records:
        parser.error("Подходящих карточек с одной датой не найдено; файл не записан")
    if args.compare:
        known = json.loads(args.compare.read_text(encoding="utf-8"))
        known = known.get("events", []) if isinstance(known, dict) else known
        known_ids = {record["external_id"] for record in known}
        new_ids = [record["external_id"] for record in records if record["external_id"] not in known_ids]
        print(f"COMPARE known={len(records) - len(new_ids)} new={len(new_ids)} new_ids={','.join(new_ids)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"events": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MODE=CHECK listing={len(candidates)} inspected={len(records)} exact_sessions={sum(bool(row['sessions']) for row in records)} output={args.output}")
    for row in records:
        print(f"{row['external_id']} | {row['title']} | {len(row['sessions'])} session(s) | flags={'; '.join(row['review_flags']) or 'none'}")
    print("База не изменялась; записи требуют редакторской проверки.")


if __name__ == "__main__":
    main()
