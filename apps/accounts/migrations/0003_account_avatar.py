from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_account_email_verification")]

    operations = [
        migrations.AddField(
            model_name="account",
            name="avatar",
            field=models.ImageField(blank=True, upload_to="avatars/", verbose_name="Фото профиля"),
        ),
    ]
