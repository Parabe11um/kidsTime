from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="account",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Email подтверждён"),
        ),
        migrations.AddField(
            model_name="account",
            name="email_verification_digest",
            field=models.CharField(blank=True, default="", editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="account",
            name="email_verification_sent_at",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Письмо подтверждения отправлено"),
        ),
    ]
