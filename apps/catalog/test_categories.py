import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .categories import CATEGORY_SPECS, MOBILE_CATEGORY_ORDER, public_categories
from .models import Category, Event


class CategorySeedTests(TestCase):
    def test_category_refresh_preserves_existing_assignments_and_custom_data(self):
        call_command("seed_demo", stdout=io.StringIO())
        assignments = dict(Event.objects.values_list("pk", "category_id"))
        event_data = list(Event.objects.order_by("pk").values())
        workshop = Category.objects.get(slug="workshops")
        # A deployed catalog starts with five flat categories.
        Category.objects.filter(pk=workshop.pk).update(parent=None, name="Мастер-классы")
        custom = Category.objects.create(name="Своя категория", slug="custom", is_active=False)
        Category.objects.filter(slug="camps").update(is_active=False)
        categories = dict(Category.objects.values_list("slug", "pk"))

        call_command("seed_categories", stdout=io.StringIO())
        call_command("seed_categories", stdout=io.StringIO())

        workshop.refresh_from_db()
        custom.refresh_from_db()
        self.assertEqual(workshop.parent.slug, "events")
        self.assertEqual(workshop.name, "Мастер-класс")
        self.assertEqual(dict(Category.objects.values_list("slug", "pk")), categories)
        self.assertEqual(dict(Event.objects.values_list("pk", "category_id")), assignments)
        self.assertEqual(list(Event.objects.order_by("pk").values()), event_data)
        self.assertEqual(custom.name, "Своя категория")
        self.assertFalse(custom.is_active)
        self.assertFalse(Category.objects.get(slug="camps").is_active)

    def test_fresh_catalog_has_eleven_roots_and_sixteen_subcategories(self):
        call_command("seed_categories", stdout=io.StringIO())
        self.assertEqual(
            list(Category.objects.filter(parent=None).values_list("name", flat=True)),
            [spec[1] for spec in CATEGORY_SPECS],
        )
        self.assertEqual(Category.objects.exclude(parent=None).count(), 16)
        self.assertFalse(Event.objects.exists())

    def test_dry_run_rolls_back_new_and_existing_categories(self):
        output = io.StringIO()
        call_command("seed_categories", dry_run=True, stdout=output)
        self.assertFalse(Category.objects.exists())
        self.assertIn("CATEGORIES=27", output.getvalue())
        self.assertIn("rolled_back=yes", output.getvalue())

        category = Category.objects.create(name="Животные", slug="animals", sort_order=50)
        call_command("seed_categories", dry_run=True, stdout=io.StringIO())
        category.refresh_from_db()
        self.assertEqual(category.name, "Животные")
        self.assertEqual(category.sort_order, 50)
        self.assertEqual(Category.objects.count(), 1)


class CategoryNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())

    def test_home_shows_root_categories_and_filter_groups_have_subcategories(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(len(response.context["categories"]), 11)
        self.assertEqual(
            [category.slug for category in response.context["mobile_categories"]],
            list(MOBILE_CATEGORY_ORDER),
        )
        for slug, name, *_ in CATEGORY_SPECS:
            self.assertContains(response, f'?category={slug}"')
            self.assertContains(response, name)
        self.assertNotIn("workshops", {category.slug for category in response.context["categories"]})

        response = self.client.get(reverse("catalog:event_list"), {"category": "workshops"})
        self.assertContains(response, '<optgroup label="События">')
        self.assertContains(response, '<option value="workshops" selected>Мастер-класс</option>')
        self.assertContains(response, '<optgroup label="Общение с животными">')

    def test_parent_filter_includes_own_and_child_events_on_list_and_map(self):
        original = Event.objects.get(slug="creative-weekend")
        root = Category.objects.get(slug="events")
        direct = Event.objects.get(slug="family-day-zaryadye")
        direct.category = root
        direct.save(update_fields=["category"])
        expected = set(Event.objects.filter(category__parent=root).values_list("pk", flat=True)) | {direct.pk}
        self.assertIn(original.pk, expected)

        response = self.client.get(reverse("catalog:event_list"), {"category": "events"})
        self.assertEqual({event.pk for event in response.context["events"]}, expected)
        markers = self.client.get(reverse("catalog:map_events_api"), {"category": "events"})
        self.assertEqual({event["id"] for event in markers.json()["results"]}, expected)

        response = self.client.get(reverse("catalog:event_list"), {"category": "workshops"})
        self.assertIn(original, response.context["events"])
        self.assertNotIn(direct, response.context["events"])
        self.assertEqual(self.client.get(reverse("catalog:event_list"), {"category": "unknown"}).context["result_count"], 0)

    def test_inactive_categories_and_their_children_are_not_offered(self):
        Category.objects.filter(slug__in=("animals", "water-parks")).update(is_active=False)
        roots = list(public_categories())
        self.assertNotIn("animals", {category.slug for category in roots})
        water = next(category for category in roots if category.slug == "water-activities")
        self.assertNotIn("water-parks", {child.slug for child in water.subcategories})

    def test_admin_rejects_cycles_and_deeper_nesting(self):
        root = Category.objects.get(slug="events")
        child = Category.objects.get(slug="workshops")
        for category, parent in ((root, root), (root, child), (Category(name="Вложенная", slug="nested"), child)):
            with self.subTest(category=category.slug, parent=parent.slug):
                category.parent = parent
                with self.assertRaises(ValidationError):
                    category.clean()
                category.parent = None
        root.parent = Category.objects.get(slug="parks")
        with self.assertRaises(ValidationError):
            root.clean()
