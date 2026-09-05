from decimal import Decimal

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone


class PublicationStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    REVIEW = "review", "На модерации"
    PUBLISHED = "published", "Опубликовано"
    ARCHIVED = "archived", "В архиве"


class ActivityFormat(models.TextChoices):
    INDOOR = "indoor", "В помещении"
    OUTDOOR = "outdoor", "На улице"
    BOTH = "both", "В помещении и на улице"


class AvailabilityStatus(models.TextChoices):
    AVAILABLE = "available", "Есть места"
    FEW = "few", "Мало мест"
    SOLD_OUT = "sold_out", "Мест нет"
    UNKNOWN = "unknown", "Нужно уточнить"


class ImportRunStatus(models.TextChoices):
    RUNNING = "running", "Выполняется"
    COMPLETED = "completed", "Завершён"
    PARTIAL = "partial", "Завершён с ошибками"
    FAILED = "failed", "Ошибка"


class ImportedEventStatus(models.TextChoices):
    NEW = "new", "Новая запись"
    REVIEW = "review", "На проверке"
    READY = "ready", "Готово к переносу"
    IMPORTED = "imported", "Перенесено"
    SKIPPED = "skipped", "Пропущено"
    ERROR = "error", "Ошибка"


class Category(models.Model):
    name = models.CharField("Название", max_length=120)
    slug = models.SlugField("Адрес", max_length=140, unique=True)
    accent_color = models.CharField("Цвет", max_length=7, default="#FF766E")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=100)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Organizer(models.Model):
    name = models.CharField("Название", max_length=180)
    website = models.URLField("Сайт", blank=True)
    email = models.EmailField("E-mail", blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    is_partner = models.BooleanField("Партнёр", default=False)

    class Meta:
        ordering = ("name",)
        verbose_name = "Организатор"
        verbose_name_plural = "Организаторы"

    def __str__(self):
        return self.name


class Source(models.Model):
    name = models.CharField("Название", max_length=180)
    url = models.URLField("Ссылка", blank=True)
    feed_url = models.URLField("Адрес ленты или раздела", blank=True)
    parser_code = models.SlugField(
        "Код парсера",
        max_length=80,
        blank=True,
        help_text="Технический идентификатор адаптера источника.",
    )
    is_active = models.BooleanField("Активен", default=True)
    automated_collection_allowed = models.BooleanField(
        "Автоматический сбор разрешён",
        default=False,
        help_text="Включайте только после проверки правил сайта и получения необходимых разрешений.",
    )
    usage_notes = models.TextField("Условия использования", blank=True)
    last_checked_at = models.DateTimeField("Последняя проверка", null=True, blank=True)
    last_import_at = models.DateTimeField("Последний импорт", null=True, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("parser_code",),
                condition=~models.Q(parser_code=""),
                name="unique_nonempty_parser_code",
            )
        ]
        verbose_name = "Источник"
        verbose_name_plural = "Источники"

    def __str__(self):
        return self.name


class Venue(models.Model):
    name = models.CharField("Название", max_length=180)
    slug = models.SlugField("Адрес страницы", max_length=200, unique=True)
    address = models.CharField("Адрес", max_length=255)
    district = models.CharField("Район", max_length=120, blank=True)
    metro = models.CharField("Метро", max_length=120, blank=True)
    location = models.PointField(
        "Координаты",
        srid=4326,
        geography=True,
        null=True,
        blank=True,
        help_text="Сохраняются собственные координаты или точка, выбранная редактором.",
    )
    entrance_notes = models.CharField("Как найти вход", max_length=255, blank=True)
    parking_notes = models.CharField("Парковка", max_length=255, blank=True)
    stroller_access = models.BooleanField("Можно с коляской", default=False)
    accessible = models.BooleanField("Безбарьерный доступ", default=False)
    is_published = models.BooleanField("Опубликовано", default=True)
    last_verified_at = models.DateTimeField("Проверено", null=True, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Место"
        verbose_name_plural = "Места"

    def __str__(self):
        return self.name


class EventQuerySet(models.QuerySet):
    def visible(self):
        today = timezone.localdate()
        return self.filter(status=PublicationStatus.PUBLISHED).filter(
            models.Q(published_until__isnull=True) | models.Q(published_until__gte=today)
        )


class Event(models.Model):
    title = models.CharField("Название", max_length=220)
    slug = models.SlugField("Адрес страницы", max_length=240, unique=True)
    short_description = models.CharField("Краткое описание", max_length=300)
    description = models.TextField("Описание")
    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        on_delete=models.PROTECT,
        related_name="events",
    )
    venue = models.ForeignKey(
        Venue,
        verbose_name="Место",
        on_delete=models.PROTECT,
        related_name="events",
    )
    organizer = models.ForeignKey(
        Organizer,
        verbose_name="Организатор",
        on_delete=models.PROTECT,
        related_name="events",
    )
    source = models.ForeignKey(
        Source,
        verbose_name="Источник",
        on_delete=models.PROTECT,
        related_name="events",
    )
    source_url = models.URLField("Страница первоисточника", blank=True)
    cover_url = models.URLField("Ссылка на обложку", blank=True)
    age_from = models.PositiveSmallIntegerField("Возраст от", default=0)
    age_to = models.PositiveSmallIntegerField("Возраст до", default=14)
    price_from = models.DecimalField("Цена от", max_digits=10, decimal_places=2, default=0)
    price_to = models.DecimalField("Цена до", max_digits=10, decimal_places=2, null=True, blank=True)
    is_free = models.BooleanField("Бесплатно", default=False)
    duration_minutes = models.PositiveIntegerField("Продолжительность, минут", null=True, blank=True)
    activity_format = models.CharField(
        "Формат",
        max_length=12,
        choices=ActivityFormat.choices,
        default=ActivityFormat.INDOOR,
    )
    status = models.CharField(
        "Статус",
        max_length=12,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    is_featured = models.BooleanField("Популярное", default=False)
    is_recommended = models.BooleanField("Рекомендуем", default=False)
    published_until = models.DateField("Показывать до", null=True, blank=True)
    last_verified_at = models.DateTimeField("Проверено", default=timezone.now)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ("title",)
        indexes = [
            models.Index(fields=("status", "published_until"), name="event_visibility_idx"),
            models.Index(fields=("category", "activity_format"), name="event_filter_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(age_to__gte=models.F("age_from")),
                name="event_age_range_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(price_from__gte=0),
                name="event_price_from_nonnegative",
            ),
        ]
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.age_to < self.age_from:
            errors["age_to"] = "Возраст «до» не может быть меньше возраста «от»."
        if self.price_to is not None and self.price_to < self.price_from:
            errors["price_to"] = "Цена «до» не может быть меньше цены «от»."
        if self.is_free:
            self.price_from = Decimal("0")
            self.price_to = Decimal("0")
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse("catalog:event_detail", kwargs={"slug": self.slug})

    @property
    def next_session(self):
        if hasattr(self, "upcoming_sessions"):
            return self.upcoming_sessions[0] if self.upcoming_sessions else None
        return self.sessions.filter(starts_at__gte=timezone.now()).order_by("starts_at").first()

    @property
    def display_price(self):
        if self.is_free:
            return "Бесплатно"
        if self.price_to and self.price_to != self.price_from:
            return f"{self.price_from:g}–{self.price_to:g} ₽"
        return f"от {self.price_from:g} ₽"

    @property
    def display_cover_url(self):
        prefetched_images = getattr(self, "prefetched_images", None)
        if prefetched_images is not None:
            primary = next((image for image in prefetched_images if image.is_cover), None)
            image = primary or (prefetched_images[0] if prefetched_images else None)
        else:
            image = self.images.order_by("-is_cover", "sort_order", "pk").first()
        return image.image.url if image else self.cover_url


class EventImage(models.Model):
    event = models.ForeignKey(
        Event,
        verbose_name="Мероприятие",
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField("Изображение", upload_to="events/%Y/%m/")
    alt_text = models.CharField("Описание изображения", max_length=255, blank=True)
    source_url = models.URLField("Источник изображения", blank=True)
    rights_note = models.CharField(
        "Права на использование",
        max_length=255,
        blank=True,
        help_text="Например: предоставлено организатором или собственная фотография.",
    )
    sort_order = models.PositiveSmallIntegerField("Порядок", default=100)
    is_cover = models.BooleanField("Обложка", default=False)
    created_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ("-is_cover", "sort_order", "pk")
        verbose_name = "Изображение мероприятия"
        verbose_name_plural = "Изображения мероприятия"

    def __str__(self):
        return self.alt_text or f"Изображение для {self.event}"


class EventSession(models.Model):
    event = models.ForeignKey(
        Event,
        verbose_name="Мероприятие",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    starts_at = models.DateTimeField("Начало")
    ends_at = models.DateTimeField("Окончание", null=True, blank=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(
        "Доступность",
        max_length=12,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.UNKNOWN,
    )
    booking_url = models.URLField("Ссылка на запись", blank=True)

    class Meta:
        ordering = ("starts_at",)
        indexes = [models.Index(fields=("starts_at", "availability"), name="session_search_idx")]
        verbose_name = "Сеанс"
        verbose_name_plural = "Сеансы"

    def __str__(self):
        return f"{self.event}: {timezone.localtime(self.starts_at):%d.%m.%Y %H:%M}"


class ImportRun(models.Model):
    source = models.ForeignKey(
        Source,
        verbose_name="Источник",
        on_delete=models.PROTECT,
        related_name="import_runs",
    )
    status = models.CharField(
        "Статус",
        max_length=12,
        choices=ImportRunStatus.choices,
        default=ImportRunStatus.RUNNING,
    )
    dry_run = models.BooleanField("Проверочный запуск", default=False)
    started_at = models.DateTimeField("Начало", auto_now_add=True)
    finished_at = models.DateTimeField("Окончание", null=True, blank=True)
    found_count = models.PositiveIntegerField("Найдено", default=0)
    staged_count = models.PositiveIntegerField("Добавлено в очередь", default=0)
    updated_count = models.PositiveIntegerField("Обновлено", default=0)
    failed_count = models.PositiveIntegerField("Ошибок", default=0)
    message = models.TextField("Сообщение", blank=True)

    class Meta:
        ordering = ("-started_at",)
        verbose_name = "Запуск импорта"
        verbose_name_plural = "Запуски импорта"

    def __str__(self):
        return f"{self.source} — {self.started_at:%d.%m.%Y %H:%M}"


class ImportedEvent(models.Model):
    source = models.ForeignKey(
        Source,
        verbose_name="Источник",
        on_delete=models.PROTECT,
        related_name="imported_events",
    )
    import_run = models.ForeignKey(
        ImportRun,
        verbose_name="Запуск импорта",
        on_delete=models.SET_NULL,
        related_name="items",
        null=True,
        blank=True,
    )
    external_id = models.CharField("ID в источнике", max_length=255)
    title = models.CharField("Название", max_length=220, blank=True)
    source_url = models.URLField("Страница первоисточника", blank=True)
    fingerprint = models.CharField("Отпечаток данных", max_length=64, blank=True)
    status = models.CharField(
        "Статус",
        max_length=12,
        choices=ImportedEventStatus.choices,
        default=ImportedEventStatus.NEW,
    )
    raw_payload = models.JSONField("Исходные данные", default=dict)
    normalized_payload = models.JSONField("Нормализованные данные", default=dict)
    validation_errors = models.JSONField("Ошибки проверки", default=list, blank=True)
    event = models.ForeignKey(
        Event,
        verbose_name="Созданное мероприятие",
        on_delete=models.SET_NULL,
        related_name="import_records",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("Получено", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(fields=("source", "external_id"), name="unique_source_external_event"),
        ]
        indexes = [models.Index(fields=("status", "updated_at"), name="import_review_idx")]
        verbose_name = "Импортированное мероприятие"
        verbose_name_plural = "Очередь импорта"

    def __str__(self):
        return self.title or self.external_id
