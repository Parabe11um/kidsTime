import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.catalog.models import (
    ActivityFormat,
    AvailabilityStatus,
    Category,
    Event,
    EventSession,
    ImportedEvent,
    ImportedEventStatus,
    Organizer,
    PublicationStatus,
    Venue,
)


class ImportPromotionError(Exception):
    pass


def _integer(payload, key, default=None):
    value = payload.get(key, default)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ImportPromotionError(f"Поле {key} должно быть целым числом.") from exc


def _decimal(payload, key, default=None):
    value = payload.get(key, default)
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ImportPromotionError(f"Поле {key} должно быть числом.") from exc


def _boolean(payload, key, default=False):
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "да"}:
            return True
        if normalized in {"false", "no", "0", "нет", ""}:
            return False
    raise ImportPromotionError(f"Поле {key} должно быть логическим значением.")


def _stable_slug(prefix, item):
    digest = hashlib.sha256(f"{item.source_id}:{item.external_id}".encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _venue_slug(name, address):
    digest = hashlib.sha256(f"{name}:{address}".encode()).hexdigest()[:16]
    return f"venue-{digest}"


def _category(payload):
    value = str(payload.get("category") or "").strip()
    if not value:
        raise ImportPromotionError("Укажите category — slug или название существующей категории.")
    category = Category.objects.filter(slug=value).first() or Category.objects.filter(name__iexact=value).first()
    if not category:
        raise ImportPromotionError(f"Категория {value!r} не найдена.")
    return category


def _coordinates(payload):
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if latitude in (None, "") and longitude in (None, ""):
        return None
    if latitude in (None, "") or longitude in (None, ""):
        raise ImportPromotionError("Для площадки нужны одновременно latitude и longitude.")
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ImportPromotionError("Координаты площадки должны быть числами.") from exc
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ImportPromotionError("Координаты площадки выходят за допустимый диапазон.")
    return Point(longitude, latitude, srid=4326)


def _aware_datetime(value):
    parsed = parse_datetime(str(value or ""))
    if not isinstance(parsed, datetime):
        raise ImportPromotionError(f"Некорректная дата сеанса: {value!r}.")
    if parsed.tzinfo is None:
        raise ImportPromotionError(f"У даты сеанса должен быть указан часовой пояс: {value!r}.")
    return parsed


@transaction.atomic
def promote_imported_event(item: ImportedEvent):
    payload = item.normalized_payload
    title = str(item.title or payload.get("title") or "").strip()
    venue_name = str(payload.get("venue_name") or "").strip()
    address = str(payload.get("address") or "").strip()
    if not title:
        raise ImportPromotionError("Не указано название мероприятия.")
    if not venue_name or not address:
        raise ImportPromotionError("Укажите venue_name и address.")

    category = _category(payload)
    organizer_name = str(payload.get("organizer") or item.source.name).strip()
    organizer = Organizer.objects.filter(name=organizer_name).first()
    if not organizer:
        organizer = Organizer.objects.create(name=organizer_name)
    venue = Venue.objects.filter(name=venue_name, address=address).first()
    if not venue:
        venue = Venue.objects.create(
            name=venue_name,
            address=address,
            slug=_venue_slug(venue_name, address),
            district=str(payload.get("district") or "")[:120],
            metro=str(payload.get("metro") or "")[:120],
            location=_coordinates(payload),
            is_published=False,
        )

    short_description = str(payload.get("short_description") or payload.get("description") or title).strip()
    description = str(payload.get("description") or short_description).strip()
    event_defaults = {
        "title": title[:220],
        "short_description": short_description[:300],
        "description": description,
        "category": category,
        "venue": venue,
        "organizer": organizer,
        "source": item.source,
        "source_url": str(payload.get("source_url") or item.source_url or ""),
        "age_from": _integer(payload, "age_from", 0),
        "age_to": _integer(payload, "age_to", 14),
        "price_from": _decimal(payload, "price_from", Decimal("0")),
        "price_to": _decimal(payload, "price_to"),
        "is_free": _boolean(payload, "is_free", False),
        "duration_minutes": _integer(payload, "duration_minutes"),
        "activity_format": (
            payload.get("activity_format")
            if payload.get("activity_format") in ActivityFormat.values
            else ActivityFormat.INDOOR
        ),
        "status": PublicationStatus.DRAFT,
    }

    event = item.event
    if event:
        for field, value in event_defaults.items():
            setattr(event, field, value)
    else:
        event = Event(slug=_stable_slug("event", item), **event_defaults)
    try:
        event.full_clean()
    except ValidationError as exc:
        raise ImportPromotionError("; ".join(exc.messages)) from exc
    event.save()

    if "sessions" in payload:
        sessions = payload.get("sessions")
        if not isinstance(sessions, list):
            raise ImportPromotionError("Поле sessions должно быть массивом.")
        prepared_sessions = []
        for session in sessions:
            if not isinstance(session, dict):
                raise ImportPromotionError("Каждый сеанс должен быть объектом.")
            starts_at = _aware_datetime(session.get("starts_at"))
            ends_at = _aware_datetime(session.get("ends_at")) if session.get("ends_at") else None
            if ends_at and ends_at < starts_at:
                raise ImportPromotionError("Окончание сеанса не может быть раньше его начала.")
            session_object = EventSession(
                event=event,
                starts_at=starts_at,
                ends_at=ends_at,
                price=_decimal(session, "price"),
                availability=(
                    session.get("availability")
                    if session.get("availability") in AvailabilityStatus.values
                    else AvailabilityStatus.UNKNOWN
                ),
                booking_url=str(session.get("booking_url") or ""),
            )
            try:
                session_object.full_clean()
            except ValidationError as exc:
                raise ImportPromotionError("; ".join(exc.messages)) from exc
            prepared_sessions.append(session_object)
        event.sessions.all().delete()
        EventSession.objects.bulk_create(prepared_sessions)

    item.event = event
    item.status = ImportedEventStatus.IMPORTED
    item.validation_errors = []
    item.save(update_fields=("event", "status", "validation_errors", "updated_at"))
    return event
