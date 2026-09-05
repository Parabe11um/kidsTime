from django import forms
from django.contrib import admin, messages
from django.contrib.gis.geos import Point

from .models import (
    Category,
    Event,
    EventImage,
    EventSession,
    ImportedEvent,
    ImportedEventStatus,
    ImportRun,
    Organizer,
    Source,
    Venue,
)
from .services.imports import ImportPromotionError, promote_imported_event


class VenueAdminForm(forms.ModelForm):
    latitude = forms.DecimalField(label="Широта", max_digits=9, decimal_places=6, required=False)
    longitude = forms.DecimalField(label="Долгота", max_digits=9, decimal_places=6, required=False)

    class Meta:
        model = Venue
        exclude = ("location",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.location:
            self.fields["latitude"].initial = self.instance.location.y
            self.fields["longitude"].initial = self.instance.location.x

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if (latitude is None) != (longitude is None):
            raise forms.ValidationError("Укажите и широту, и долготу либо оставьте оба поля пустыми.")
        if latitude is not None and not -90 <= latitude <= 90:
            self.add_error("latitude", "Широта должна быть от −90 до 90.")
        if longitude is not None and not -180 <= longitude <= 180:
            self.add_error("longitude", "Долгота должна быть от −180 до 180.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")
        instance.location = Point(float(longitude), float(latitude), srid=4326) if latitude is not None else None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Organizer)
class OrganizerAdmin(admin.ModelAdmin):
    list_display = ("name", "website", "is_partner")
    list_filter = ("is_partner",)
    search_fields = ("name", "email", "phone")


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "parser_code",
        "is_active",
        "automated_collection_allowed",
        "last_import_at",
    )
    list_filter = ("is_active", "automated_collection_allowed")
    search_fields = ("name", "url", "feed_url", "parser_code")


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    form = VenueAdminForm
    change_form_template = "admin/catalog/venue/change_form.html"
    list_display = ("name", "district", "metro", "has_coordinates", "is_published", "last_verified_at")
    list_filter = ("district", "stroller_access", "accessible", "is_published")
    search_fields = ("name", "address", "metro")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Основное", {"fields": ("name", "slug", "address", "district", "metro")}),
        ("Координаты", {"fields": (("latitude", "longitude"),)}),
        (
            "Доступность",
            {
                "fields": (
                    "entrance_notes",
                    "parking_notes",
                    ("stroller_access", "accessible"),
                )
            },
        ),
        ("Публикация", {"fields": ("is_published", "last_verified_at")}),
    )

    @admin.display(boolean=True, description="Координаты")
    def has_coordinates(self, obj):
        return bool(obj.location)


class EventSessionInline(admin.TabularInline):
    model = EventSession
    extra = 1
    fields = ("starts_at", "ends_at", "price", "availability", "booking_url")


class EventImageInline(admin.TabularInline):
    model = EventImage
    extra = 1
    fields = (
        "image",
        "alt_text",
        "is_cover",
        "sort_order",
        "source_url",
        "rights_note",
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "venue",
        "age_range",
        "display_price",
        "status",
        "last_verified_at",
    )
    list_filter = ("status", "category", "activity_format", "is_free", "is_featured", "is_recommended")
    search_fields = ("title", "short_description", "venue__name", "venue__address")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("venue", "organizer", "source")
    readonly_fields = ("created_at", "updated_at")
    inlines = (EventImageInline, EventSessionInline)
    save_on_top = True
    fieldsets = (
        ("Основное", {"fields": ("title", "slug", "short_description", "description")}),
        ("Место и тип", {"fields": ("category", "venue", "organizer", "activity_format")}),
        (
            "Возраст и стоимость",
            {
                "fields": (
                    ("age_from", "age_to"),
                    ("price_from", "price_to", "is_free"),
                    "duration_minutes",
                )
            },
        ),
        (
            "Публикация",
            {
                "fields": (
                    "status",
                    ("is_featured", "is_recommended"),
                    "published_until",
                    "last_verified_at",
                )
            },
        ),
        (
            "Первоисточник",
            {
                "fields": ("source", "source_url", "cover_url"),
                "description": "Внешняя обложка используется только если загруженного изображения нет.",
            },
        ),
        (
            "Служебные данные",
            {"classes": ("collapse",), "fields": ("created_at", "updated_at")},
        ),
    )

    @admin.display(description="Возраст")
    def age_range(self, obj):
        return f"{obj.age_from}–{obj.age_to} лет"


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ("event", "starts_at", "ends_at", "price", "availability")
    list_filter = ("availability", "starts_at")
    search_fields = ("event__title", "event__venue__name")


@admin.register(EventImage)
class EventImageAdmin(admin.ModelAdmin):
    list_display = ("event", "is_cover", "sort_order", "rights_note", "created_at")
    list_filter = ("is_cover", "created_at")
    search_fields = ("event__title", "alt_text", "rights_note", "source_url")
    autocomplete_fields = ("event",)


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "status",
        "dry_run",
        "started_at",
        "found_count",
        "staged_count",
        "updated_count",
        "failed_count",
    )
    list_filter = ("status", "dry_run", "source")
    readonly_fields = (
        "source",
        "status",
        "dry_run",
        "started_at",
        "finished_at",
        "found_count",
        "staged_count",
        "updated_count",
        "failed_count",
        "message",
    )

    def has_add_permission(self, request):
        return False


@admin.action(description="Передать выбранные записи на проверку")
def mark_imports_for_review(modeladmin, request, queryset):
    queryset.exclude(status=ImportedEventStatus.IMPORTED).update(status=ImportedEventStatus.REVIEW)


@admin.action(description="Пропустить выбранные записи")
def skip_imports(modeladmin, request, queryset):
    queryset.exclude(status=ImportedEventStatus.IMPORTED).update(status=ImportedEventStatus.SKIPPED)


@admin.action(description="Создать или обновить черновики из выбранных записей")
def promote_imports_to_drafts(modeladmin, request, queryset):
    created_count = 0
    failed_count = 0
    for item in queryset.exclude(
        status__in=(ImportedEventStatus.SKIPPED, ImportedEventStatus.IMPORTED)
    ):
        try:
            promote_imported_event(item)
            created_count += 1
        except ImportPromotionError as exc:
            item.status = ImportedEventStatus.ERROR
            item.validation_errors = [str(exc)]
            item.save(update_fields=("status", "validation_errors", "updated_at"))
            failed_count += 1

    if created_count:
        modeladmin.message_user(
            request,
            f"Подготовлено черновиков: {created_count}. Проверьте их перед публикацией.",
            level=messages.SUCCESS,
        )
    if failed_count:
        modeladmin.message_user(
            request,
            f"Не удалось подготовить записей: {failed_count}. Ошибки сохранены в очереди импорта.",
            level=messages.WARNING,
        )


@admin.register(ImportedEvent)
class ImportedEventAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "status", "source_url", "event", "updated_at")
    list_filter = ("status", "source", "updated_at")
    search_fields = ("title", "external_id", "source_url")
    autocomplete_fields = ("event",)
    readonly_fields = (
        "source",
        "import_run",
        "external_id",
        "fingerprint",
        "raw_payload",
        "created_at",
        "updated_at",
    )
    actions = (mark_imports_for_review, promote_imports_to_drafts, skip_imports)
    fieldsets = (
        ("Проверка", {"fields": ("status", "title", "source_url", "event")}),
        (
            "Нормализованные данные",
            {"fields": ("normalized_payload", "validation_errors")},
        ),
        (
            "Технические данные",
            {
                "classes": ("collapse",),
                "fields": (
                    "source",
                    "import_run",
                    "external_id",
                    "fingerprint",
                    "raw_payload",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return False


admin.site.site_header = "KidsTime — управление каталогом"
admin.site.site_title = "KidsTime"
admin.site.index_title = "Места, мероприятия и расписание"
