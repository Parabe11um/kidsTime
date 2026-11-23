from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.categories import seed_categories


class Command(BaseCommand):
    help = "Добавляет категории и подразделы из макетов, сохраняя мероприятия и пользовательские категории."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Проверить наполнение и отменить изменения.")

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        categories, created = seed_categories()
        if dry_run:
            transaction.set_rollback(True)
        self.stdout.write("MODE=DRY-RUN" if dry_run else "MODE=APPLY")
        self.stdout.write(
            f"CATEGORIES={len(categories)} CREATED={created} rolled_back={'yes' if dry_run else 'no'}"
        )
