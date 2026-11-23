"""Release 5 categories; existing slugs keep bookmarks and event assignments intact."""

from django.db.models import Prefetch

from .models import Category


# slug, label, color, subcategories. Items annotated as undecided in Figma are omitted.
CATEGORY_SPECS = (
    ("camps", "Детский лагерь", "#F2B84B", ()),
    ("cycle-paths", "Велодорожка", "#72C89A", ()),
    ("ice-rinks", "Каток", "#4E97D1", ()),
    ("water-activities", "Морские и водные развлечения", "#4E97D1", (
        ("water-parks", "Аквапарк"), ("aquariums", "Океанариум"), ("beaches", "Пляж"),
    )),
    ("museums", "Музеи", "#8A7BEF", ()),
    ("animals", "Общение с животными", "#4E97D1", (
        ("animal-rides", "Катание на животных"), ("zoos", "Зоопарк"),
        ("farms", "Ферма"), ("animal-cafes", "Антикафе с животными"),
    )),
    ("parks", "Парки", "#72C89A", ()),
    ("entertainment", "Развлекательные центры", "#FF766E", (
        ("attractions", "Аттракционы"), ("quests", "Квест, Полоса препятствий"),
        ("play-centres", "Игровые центры"),
    )),
    ("events", "События", "#F2B84B", (
        ("exhibitions", "Выставка"), ("new-year-shows", "НГ ёлка"),
        ("performances", "Спектакль"), ("workshops", "Мастер-класс"),
        ("festivals", "Фестиваль"), ("excursions", "Экскурсия"),
    )),
    ("theatre", "Театр", "#FF766E", ()),
    ("circus", "Цирк", "#FF766E", ()),
)


MOBILE_CATEGORY_ORDER = (
    "camps", "ice-rinks", "circus", "water-activities", "museums",
    "animals", "parks", "theatre", "entertainment", "events",
)


def mobile_home_categories(categories):
    order = {slug: index for index, slug in enumerate(MOBILE_CATEGORY_ORDER)}
    return sorted(
        (category for category in categories if category.slug != "cycle-paths"),
        key=lambda category: order.get(category.slug, len(order)),
    )


def seed_categories():
    categories, created_count = {}, 0
    for order, (slug, name, color, children) in enumerate(CATEGORY_SPECS, start=1):
        category, created = Category.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "accent_color": color, "sort_order": order * 10, "parent": None},
        )
        categories[slug] = category
        created_count += int(created)
        for child_order, (child_slug, child_name) in enumerate(children, start=1):
            child, created = Category.objects.update_or_create(
                slug=child_slug,
                defaults={
                    "name": child_name, "accent_color": color,
                    "sort_order": child_order * 10, "parent": category,
                },
            )
            categories[child_slug] = child
            created_count += int(created)
    return categories, created_count


def public_categories():
    return Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related(
        Prefetch("children", queryset=Category.objects.filter(is_active=True), to_attr="subcategories"),
    )
