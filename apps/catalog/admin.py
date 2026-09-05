from django import forms
from django.contrib import admin
from django.contrib.gis.geos import Point

from .models import Category, Event, EventSession, Organizer, Source, Venue


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
    list_display = ("name", "url", "last_checked_at")
    search_fields = ("name", "url")


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    form = VenueAdminForm
    list_display = ("name", "district", "metro", "has_coordinates", "is_published", "last_verified_at")
    list_filter = ("district", "stroller_access", "accessible", "is_published")
    search_fields = ("name", "address", "metro")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(boolean=True, description="Координаты")
    def has_coordinates(self, obj):
        return bool(obj.location)


class EventSessionInline(admin.TabularInline):
    model = EventSession
    extra = 1
    fields = ("starts_at", "ends_at", "price", "availability", "booking_url")


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
    inlines = (EventSessionInline,)

    @admin.display(description="Возраст")
    def age_range(self, obj):
        return f"{obj.age_from}–{obj.age_to} лет"


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ("event", "starts_at", "ends_at", "price", "availability")
    list_filter = ("availability", "starts_at")
    search_fields = ("event__title", "event__venue__name")

admin.site.site_header = "KidsTime — управление каталогом"
admin.site.site_title = "KidsTime"
admin.site.index_title = "Места, мероприятия и расписание"
