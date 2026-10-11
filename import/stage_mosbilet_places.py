"""Stage the reviewed Mosbilet venue inventory locally, unpublished.

Run with ``python manage.py shell < import/stage_mosbilet_places.py`` after
placing the JSON in /app/import. Set KIDSTIME_APPLY_PLACES=1 to apply.
"""

import json
import os
from pathlib import Path

from django.db import transaction

from apps.catalog.models import Venue


inventory_path = Path("/app/import/mosbilet_places_review_2026-10-06.json")
places = json.loads(inventory_path.read_text(encoding="utf-8"))["places"]
if len(places) != 10 or sum(len(place["activities"]) for place in places) != 15:
    raise SystemExit("ERROR: ожидались 10 площадок и 15 занятий; база не изменена")

names = [place["name"] for place in places]
if len(set(names)) != 10 or any(not place["address"] or place["review_flags"] for place in places):
    raise SystemExit("ERROR: дубли, пустой адрес или замечания; база не изменена")

apply = os.environ.get("KIDSTIME_APPLY_PLACES") == "1"
print("MODE=APPLY" if apply else "MODE=CHECK — база не изменяется")

with transaction.atomic():
    created = 0
    for place in places:
        name, address = place["name"], place["address"]
        matches = list(Venue.objects.select_for_update().filter(name__iexact=name))
        if matches:
            if len(matches) != 1:
                raise SystemExit(f"ERROR: неоднозначное совпадение для {name}")
            venue = matches[0]
            if name != "Государственный Дарвиновский музей" or venue.pk != 3:
                if venue.address != address or venue.is_published:
                    raise SystemExit(f"ERROR: уже существует неожиданная площадка: {name}")
            print(f"EXISTING id={venue.pk} name={name} published={venue.is_published}")
            continue

        if name == "Государственный Дарвиновский музей":
            raise SystemExit("ERROR: ранее существовавший Дарвиновский музей не найден")
        source_ids = place["activities"][0]["source_ids"]
        if not source_ids or not source_ids[0].startswith("mosbilet-"):
            raise SystemExit(f"ERROR: нет ID первоисточника для {name}")
        slug = "mosbilet-place-" + source_ids[0].removeprefix("mosbilet-")
        if Venue.objects.filter(slug=slug).exists():
            raise SystemExit(f"ERROR: адрес страницы занят: {slug}")
        venue = Venue(name=name, slug=slug, address=address, is_published=False)
        venue.full_clean()
        if apply:
            venue.save()
        created += 1
        print(f"{'CREATED' if apply else 'WOULD_CREATE'} name={name} slug={slug} address={address}")

    if not apply and created != 9:
        raise SystemExit(f"ERROR: ожидались 9 новых мест, найдено {created}; база не изменена")

print(f"SUMMARY: {'created' if apply else 'would_create'}={created}, published=0")
