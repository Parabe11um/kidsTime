from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_source_automated_collection_allowed_source_feed_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="available_from",
            field=models.DateField(blank=True, null=True, verbose_name="Доступно с"),
        ),
        migrations.AddField(
            model_name="event",
            name="available_until",
            field=models.DateField(blank=True, null=True, verbose_name="Доступно по"),
        ),
    ]
