from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_account_profile_details")]

    operations = [
        migrations.AddField(
            model_name="account",
            name="use_geolocation",
            field=models.BooleanField(default=False, verbose_name="Подбирать места по геолокации"),
        ),
    ]
