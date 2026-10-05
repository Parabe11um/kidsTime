"""One-page, manual SHM programme collector. Writes a review file, never imports it."""

import argparse
import json
import re
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


PAGE = "https://shm.ru/shows/osennie-kanikuly-v-istoricheskom-muzee/"
EDUCATION_PAGE = "https://shm.ru/education/"
MOSCOW = ZoneInfo("Europe/Moscow")
DATE_RE = re.compile(r"(\d{1,2})\s+(октября|ноября|декабря|января|февраля|марта|апреля|мая|июня|июля|августа|сентября)\s+(\d{4})\s+года\s+в\s+(\d{1,2}:\d{2})", re.I)
MONTHS = {name: month for month, name in enumerate(
    "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(), 1
)}
VENUES = {
    "Музей Отечественной войны 1812 года": "Москва, площадь Революции, 2/3",
    "Исторический музей": "Москва, Красная площадь, 1",
}


class ProgrammeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.link = None
        self.link_text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a" and not self.skip:
            self.link = dict(attrs).get("href", "")
            self.link_text = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag == "a" and self.link is not None:
            self.tokens.append((" ".join(self.link_text), self.link))
            self.link = None

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text or self.skip:
            return
        if self.link is None:
            self.tokens.append((text, None))
        else:
            self.link_text.append(text)


def extract(html, start, end, *, page=PAGE, max_age=12):
    parser = ProgrammeParser()
    parser.feed(html)
    tokens = parser.tokens
    if page == PAGE:
        start_idx = next((i for i, (text, _) in enumerate(tokens) if text == "Программа мероприятий"), None)
        if start_idx is None:
            raise ValueError("На странице не найден раздел «Программа мероприятий»; разметка могла измениться")
        end_idx = next((i for i in range(start_idx + 1, len(tokens)) if tokens[i][0] == "Рекомендуем сходить"), len(tokens))
        tokens = tokens[start_idx + 1:end_idx]
    cards = {}
    current = None
    for text, href in tokens:
        url = urljoin(page, href or "")
        match_id = re.fullmatch(r"/education/(\d+)/", urlparse(url).path)
        if match_id and urlparse(url).hostname == "shm.ru":
            key = match_id.group(1)
            if current != key:
                current = key
                cards.setdefault(key, {"url": url, "parts": [], "title": ""})
            if re.search(r"(?<!\d)\d{1,2}\s*\+", text):
                cards[key]["parts"].append(text)
            else:
                cards[key]["title"] = text
        elif current:
            cards[current]["parts"].append(text)

    records = []
    for key, card in cards.items():
        context = " ".join(card["parts"])
        age = re.search(r"(?<!\d)(\d{1,2})\s*\+", context)
        venue = next((name for name in VENUES if name in context), None)
        if not (card["title"] and age and venue) or int(age.group(1)) > max_age:
            continue
        if page == EDUCATION_PAGE and not any(kind in context for kind in ("Мастер-классы", "Музейные занятия")):
            continue
        sessions = []
        for match in DATE_RE.finditer(context):
            day, month, year, hour = match.groups()
            moment = datetime.strptime(f"{year}-{MONTHS[month.lower()]:02d}-{int(day):02d} {hour}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW)
            if start <= moment.date() <= end:
                sessions.append({"starts_at": moment.isoformat()})
        if sessions:
            records.append({
                "external_id": f"shm-education-{key}",
                "title": card["title"],
                "source_url": card["url"],
                "venue_name": venue,
                "address": VENUES[venue],
                "category": "workshops" if "Мастер-класс" in card["title"] else "museums",
                "organizer": "Государственный исторический музей",
                "age_from": int(age.group(1)),
                "sessions": sessions,
            })
    return records


def main():
    parser = argparse.ArgumentParser(description="Собрать факты о сеансах с одной страницы музея; базу не изменяет")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--from-date", type=date.fromisoformat, default=datetime.now(MOSCOW).date())
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--html", type=Path, help="Локальный HTML для проверки без сетевого запроса")
    parser.add_argument("--compare", type=Path, help="Сравнить ID с имеющимся пилотным JSON")
    parser.add_argument("--page", choices=("programme", "education"), default="programme")
    args = parser.parse_args()
    if not 1 <= args.days <= 31:
        parser.error("--days должен быть от 1 до 31")
    page = EDUCATION_PAGE if args.page == "education" else PAGE
    if args.html:
        html = args.html.read_text(encoding="utf-8")
    else:
        request = Request(page, headers={"User-Agent": "KidsTime-manual-pilot/1.0 (one page; contact via site)"})
        with urlopen(request, timeout=15) as response:
            html = response.read(2_000_001)
        if len(html) > 2_000_000:
            parser.error("Ответ превышает 2 МБ")
        html = html.decode("utf-8")
    events = extract(html, args.from_date, args.from_date + timedelta(days=args.days - 1), page=page)
    if not events:
        parser.error("Не найдены сеансы с возрастом и площадкой в указанном диапазоне; файл не записан")
    if args.compare:
        known = json.loads(args.compare.read_text(encoding="utf-8"))
        known = known.get("events", []) if isinstance(known, dict) else known
        known_ids = {item["external_id"] for item in known}
        new_ids = [item["external_id"] for item in events if item["external_id"] not in known_ids]
        print(f"COMPARE known={len(events) - len(new_ids)} new={len(new_ids)} new_ids={','.join(new_ids)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"events": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MODE=CHECK source={page} found={len(events)} sessions={sum(len(e['sessions']) for e in events)} output={args.output}")
    print("База данных не изменялась. Цена и изображения не собирались. Записи требуют ручной проверки.")


if __name__ == "__main__":
    main()
