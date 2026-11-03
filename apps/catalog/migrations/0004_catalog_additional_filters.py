from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_event_availability_period")]

    operations = [
        migrations.AddField(
            model_name="venue",
            name="has_children_room",
            field=models.BooleanField(blank=True, default=None, null=True, verbose_name="Детская комната"),
        ),
        migrations.AddField(
            model_name="venue",
            name="has_cafe",
            field=models.BooleanField(blank=True, default=None, null=True, verbose_name="Ресторан или кафе"),
        ),
        migrations.AddField(
            model_name="event",
            name="accepts_pushkin_card",
            field=models.BooleanField(blank=True, default=None, null=True, verbose_name="Принимает Пушкинскую карту"),
        ),
    ]
