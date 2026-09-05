import hashlib
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import (
    ImportedEvent,
    ImportedEventStatus,
    ImportRun,
    ImportRunStatus,
    Source,
)


NORMALIZED_FIELDS = (
    "title",
    "short_description",
    "description",
    "source_url",
    "venue_name",
    "address",
    "district",
    "metro",
    "latitude",
    "longitude",
    "category",
    "organizer",
    "age_from",
    "age_to",
    "price_from",
    "price_to",
    "is_free",
    "duration_minutes",
    "activity_format",
    "sessions",
    "images",
)


class Command(BaseCommand):
    help = "Помещает заранее полученные JSON-записи в очередь редакторской проверки."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Путь к JSON-файлу со списком мероприятий.")
        parser.add_argument(
            "--source",
            required=True,
            help="ID источника или его код парсера.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Проверить файл без изменения базы данных.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        source = self._get_source(options["source"])
        records = self._read_records(Path(options["file"]))

        self.stdout.write(f"MODE={'CHECK' if dry_run else 'APPLY'}")
        self.stdout.write("Импортированные записи не публикуются автоматически.")

        prepared = [
            self._prepare_record(record, position)
            for position, record in enumerate(records, start=1)
        ]
        failed_count = sum(bool(item["errors"]) for item in prepared)

        if dry_run:
            self._print_summary(len(prepared), 0, 0, failed_count, dry_run=True)
            return

        with transaction.atomic():
            run = ImportRun.objects.create(source=source, dry_run=False)
            staged_count = 0
            updated_count = 0

            for item in prepared:
                defaults = {
                    "import_run": run,
                    "title": item["normalized"].get("title", "")[:220],
                    "source_url": item["normalized"].get("source_url", ""),
                    "fingerprint": item["fingerprint"],
                    "raw_payload": item["raw"],
                    "normalized_payload": item["normalized"],
                    "validation_errors": item["errors"],
                    "status": (
                        ImportedEventStatus.ERROR
                        if item["errors"]
                        else ImportedEventStatus.NEW
                    ),
                }
                existing = ImportedEvent.objects.filter(
                    source=source,
                    external_id=item["external_id"],
                ).first()
                content_changed = existing and existing.fingerprint != item["fingerprint"]
                if existing and existing.event:
                    defaults["event"] = existing.event
                if existing and existing.status == ImportedEventStatus.IMPORTED and not content_changed:
                    defaults["status"] = ImportedEventStatus.IMPORTED
                elif existing and existing.status == ImportedEventStatus.IMPORTED:
                    defaults["status"] = ImportedEventStatus.REVIEW

                _, created = ImportedEvent.objects.update_or_create(
                    source=source,
                    external_id=item["external_id"],
                    defaults=defaults,
                )
                if created:
                    staged_count += 1
                else:
                    updated_count += 1

            run.status = ImportRunStatus.PARTIAL if failed_count else ImportRunStatus.COMPLETED
            run.finished_at = timezone.now()
            run.found_count = len(prepared)
            run.staged_count = staged_count
            run.updated_count = updated_count
            run.failed_count = failed_count
            run.message = "Все записи сохранены только в очереди импорта и требуют проверки редактором."
            run.save()
            source.last_import_at = run.finished_at
            source.save(update_fields=("last_import_at",))

        self._print_summary(len(prepared), staged_count, updated_count, failed_count, dry_run=False)

    def _get_source(self, identifier):
        queryset = (
            Source.objects.filter(pk=int(identifier))
            if identifier.isdigit()
            else Source.objects.filter(parser_code=identifier)
        )
        try:
            source = queryset.get()
        except Source.DoesNotExist as exc:
            raise CommandError(f"Источник {identifier!r} не найден.") from exc
        except Source.MultipleObjectsReturned as exc:
            raise CommandError(f"Код источника {identifier!r} должен быть уникальным.") from exc
        if not source.is_active:
            raise CommandError(f"Источник {identifier!r} отключён.")
        return source

    def _read_records(self, path):
        if not path.is_file():
            raise CommandError(f"Файл не найден: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Не удалось прочитать JSON: {exc}") from exc

        records = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise CommandError('Ожидается JSON-массив или объект с массивом в поле "events".')
        return records

    def _prepare_record(self, record, position):
        if not isinstance(record, dict):
            raw = {"value": record}
            errors = [f"Запись {position}: ожидается JSON-объект."]
            external_id = f"invalid-{position}"
            normalized = {}
        else:
            raw = record
            external_id = str(record.get("external_id") or "").strip()
            normalized = {field: record[field] for field in NORMALIZED_FIELDS if field in record}
            errors = []
            if not external_id:
                external_id = f"invalid-{position}"
                errors.append("Не указан external_id.")
            if not str(normalized.get("title") or "").strip():
                errors.append("Не указано название.")
            source_url = str(normalized.get("source_url") or "").strip()
            if source_url:
                try:
                    URLValidator()(source_url)
                except ValidationError:
                    errors.append("Некорректная ссылка на первоисточник.")

        canonical = json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return {
            "external_id": external_id[:255],
            "raw": raw,
            "normalized": normalized,
            "errors": errors,
            "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }

    def _print_summary(self, found, staged, updated, failed, *, dry_run):
        self.stdout.write(
            "SUMMARY: "
            f"found={found}, staged={staged}, updated={updated}, errors={failed}, "
            f"rolled_back={'yes' if dry_run else 'no'}"
        )
