from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_account_avatar")]

    operations = [
        migrations.AddField(
            model_name="account", name="patronymic",
            field=models.CharField(blank=True, max_length=150, verbose_name="Отчество"),
        ),
        migrations.AddField(
            model_name="account", name="birth_date",
            field=models.DateField(blank=True, null=True, verbose_name="Дата рождения"),
        ),
        migrations.AddField(
            model_name="account", name="phone",
            field=models.CharField(blank=True, max_length=40, verbose_name="Телефон"),
        ),
    ]
