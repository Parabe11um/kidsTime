from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import (
    ActivityFormat,
    AvailabilityStatus,
    Category,
    Event,
    EventSession,
    Organizer,
    PublicationStatus,
    Source,
    Venue,
)


class Command(BaseCommand):
    help = "Идемпотентно создаёт демонстрационные карточки KidsTime."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать результат и откатить все изменения.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write("MODE=DRY-RUN" if dry_run else "MODE=APPLY")
        self.stdout.write(
            "Проверяем демонстрационное наполнение; изменения будут отменены."
            if dry_run
            else "Создаём или обновляем только демонстрационные данные KidsTime."
        )

        counters = {"categories": 0, "venues": 0, "events": 0, "sessions": 0}
        categories = {}
        for sort_order, (slug, name, color) in enumerate(
            (
                ("parks", "Парки", "#72C89A"),
                ("theatre", "Театры", "#FF766E"),
                ("museums", "Музеи", "#8A7BEF"),
                ("workshops", "Мастер-классы", "#F2B84B"),
                ("animals", "Животные", "#4E97D1"),
            ),
            start=1,
        ):
            category, created = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "accent_color": color, "sort_order": sort_order * 10},
            )
            categories[slug] = category
            counters["categories"] += int(created)

        organizer, _ = Organizer.objects.update_or_create(
            name="Демо-редакция KidsTime",
            defaults={"website": "https://example.com", "is_partner": False},
        )
        source, _ = Source.objects.update_or_create(
            name="Демонстрационные данные",
            defaults={
                "url": "https://example.com",
                "usage_notes": "Тестовый источник. Не публиковать как реальные мероприятия.",
                "last_checked_at": timezone.now(),
            },
        )

        venue_specs = {
            "zaryadye": ("Парк «Зарядье»", "Москва, улица Варварка, 6с1", "Тверской", "Китай-город", 37.6286, 55.7511),
            "moscow-zoo": ("Московский зоопарк", "Москва, Большая Грузинская улица, 1", "Пресненский", "Баррикадная", 37.5772, 55.7625),
            "darwin-museum": ("Государственный Дарвиновский музей", "Москва, улица Вавилова, 57", "Академический", "Академическая", 37.5612, 55.6911),
            "vdnh": ("ВДНХ", "Москва, проспект Мира, 119", "Останкинский", "ВДНХ", 37.6331, 55.8298),
            "garage": ("Музей современного искусства «Гараж»", "Москва, Крымский Вал, 9с32", "Якиманка", "Парк культуры", 37.6011, 55.7270),
            "sokolniki": ("Парк «Сокольники»", "Москва, улица Сокольнический Вал, 1с1", "Сокольники", "Сокольники", 37.6730, 55.7944),
        }
        venues = {}
        for slug, (name, address, district, metro, lng, lat) in venue_specs.items():
            venue, created = Venue.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "address": address,
                    "district": district,
                    "metro": metro,
                    "location": Point(lng, lat, srid=4326),
                    "stroller_access": True,
                    "is_published": True,
                    "last_verified_at": timezone.now(),
                },
            )
            venues[slug] = venue
            counters["venues"] += int(created)

        event_specs = (
            {
                "slug": "family-day-zaryadye",
                "title": "Семейный день в Зарядье",
                "category": "parks",
                "venue": "zaryadye",
                "description": "Прогулочный маршрут, игровые площадки и познавательные пространства для семейного выходного.",
                "age": (3, 14),
                "price": (0, 0),
                "free": True,
                "format": ActivityFormat.BOTH,
                "featured": True,
                "recommended": True,
                "cover": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80",
            },
            {
                "slug": "animals-near-us",
                "title": "Животные рядом с нами",
                "category": "animals",
                "venue": "moscow-zoo",
                "description": "Семейная программа о повадках животных и бережном отношении к природе.",
                "age": (5, 12),
                "price": (750, 1200),
                "free": False,
                "format": ActivityFormat.OUTDOOR,
                "featured": True,
                "recommended": False,
                "cover": "https://images.unsplash.com/photo-1474511320723-9a56873867b5?auto=format&fit=crop&w=1200&q=80",
            },
            {
                "slug": "science-lab",
                "title": "Научная лаборатория для детей",
                "category": "museums",
                "venue": "darwin-museum",
                "description": "Интерактивное занятие с простыми опытами и понятными объяснениями природных явлений.",
                "age": (7, 12),
                "price": (600, 900),
                "free": False,
                "format": ActivityFormat.INDOOR,
                "featured": False,
                "recommended": True,
                "cover": "https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1200&q=80",
            },
            {
                "slug": "creative-weekend",
                "title": "Творческие выходные",
                "category": "workshops",
                "venue": "garage",
                "description": "Мастерская для детей и родителей: цвет, коллаж и небольшой семейный арт-проект.",
                "age": (4, 10),
                "price": (900, 1500),
                "free": False,
                "format": ActivityFormat.INDOOR,
                "featured": False,
                "recommended": True,
                "cover": "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?auto=format&fit=crop&w=1200&q=80",
            },
            {
                "slug": "space-adventure",
                "title": "Космическое приключение",
                "category": "museums",
                "venue": "vdnh",
                "description": "Познавательный маршрут для тех, кто хочет узнать больше о космосе и технике.",
                "age": (6, 14),
                "price": (500, 1100),
                "free": False,
                "format": ActivityFormat.INDOOR,
                "featured": True,
                "recommended": True,
                "cover": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1200&q=80",
            },
            {
                "slug": "park-quest",
                "title": "Семейный квест в парке",
                "category": "parks",
                "venue": "sokolniki",
                "description": "Неспешный квест с заданиями на внимание, движение и командную работу.",
                "age": (5, 13),
                "price": (350, 700),
                "free": False,
                "format": ActivityFormat.OUTDOOR,
                "featured": False,
                "recommended": False,
                "cover": "https://images.unsplash.com/photo-1542810634-71277d95dcbb?auto=format&fit=crop&w=1200&q=80",
            },
        )

        for index, spec in enumerate(event_specs):
            event, created = Event.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "short_description": spec["description"],
                    "description": spec["description"],
                    "category": categories[spec["category"]],
                    "venue": venues[spec["venue"]],
                    "organizer": organizer,
                    "source": source,
                    "source_url": "https://example.com",
                    "cover_url": spec["cover"],
                    "age_from": spec["age"][0],
                    "age_to": spec["age"][1],
                    "price_from": Decimal(str(spec["price"][0])),
                    "price_to": Decimal(str(spec["price"][1])),
                    "is_free": spec["free"],
                    "duration_minutes": 90 + index * 15,
                    "activity_format": spec["format"],
                    "status": PublicationStatus.PUBLISHED,
                    "is_featured": spec["featured"],
                    "is_recommended": spec["recommended"],
                    "published_until": timezone.localdate() + timedelta(days=90),
                    "last_verified_at": timezone.now(),
                },
            )
            counters["events"] += int(created)
            session_day = timezone.localdate() + timedelta(days=(index % 5) + 1)
            session_start = timezone.make_aware(datetime.combine(session_day, time(hour=10 + index)))
            demo_booking_url = f"https://example.com/demo/{spec['slug']}"
            _, session_created = EventSession.objects.update_or_create(
                event=event,
                booking_url=demo_booking_url,
                defaults={
                    "starts_at": session_start,
                    "ends_at": session_start + timedelta(minutes=event.duration_minutes),
                    "price": event.price_from,
                    "availability": AvailabilityStatus.AVAILABLE,
                },
            )
            counters["sessions"] += int(session_created)

        if dry_run:
            transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "SUMMARY: "
                f"created_categories={counters['categories']}, "
                f"created_venues={counters['venues']}, "
                f"created_events={counters['events']}, "
                f"created_sessions={counters['sessions']}, "
                f"rolled_back={'yes' if dry_run else 'no'}"
            )
        )
