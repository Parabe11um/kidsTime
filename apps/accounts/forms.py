from uuid import uuid4

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Account


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "Email"}))
    password = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Пароль"}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("email") and data.get("password"):
            self.user_cache = authenticate(self.request, email=data["email"], password=data["password"])
            if self.user_cache is None:
                raise ValidationError("Не удалось войти. Проверьте email и пароль.")
        return data

    def get_user(self):
        return self.user_cache


class RegistrationForm(forms.Form):
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "Email"}))
    password1 = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Пароль"}), help_text="Не менее 8 символов. Не используйте распространённый пароль или только цифры.")
    password2 = forms.CharField(label="Повторите пароль", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Повторите пароль"}))
    privacy = forms.BooleanField(label="Ознакомлен с Политикой конфиденциальности", error_messages={"required": "Необходимо ознакомиться с Политикой конфиденциальности."})
    newsletter = forms.BooleanField(label="Согласен получать рассылку с акциями", required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists() or Account.objects.filter(email=email).exists():
            raise ValidationError("Этот email уже зарегистрирован. Войдите или восстановите пароль.")
        return email

    def clean(self):
        data = super().clean()
        if not settings.PRIVACY_POLICY_URL:
            raise ValidationError("Регистрация временно недоступна: политика конфиденциальности ещё не опубликована.")
        if data.get("password1") and data.get("password2"):
            if data["password1"] != data["password2"]:
                self.add_error("password2", "Пароли не совпадают.")
            user = get_user_model()(email=data.get("email", ""))
            try:
                password_validation.validate_password(data["password1"], user)
            except ValidationError as error:
                self.add_error("password1", error)
        return data

    @transaction.atomic
    def save(self):
        email = self.cleaned_data["email"]
        user = get_user_model().objects.create_user(username="kidstime_" + uuid4().hex, email=email, password=self.cleaned_data["password1"])
        now = timezone.now()
        Account.objects.create(user=user, email=email, privacy_accepted_at=now, privacy_policy_url=settings.PRIVACY_POLICY_URL, newsletter_accepted_at=now if self.cleaned_data["newsletter"] else None)
        return user


class EmailPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "Email"}))

    def get_users(self, email):
        # Existing admin accounts may share an email; don't reset an ambiguous identity.
        if get_user_model().objects.filter(email__iexact=email).count() != 1:
            return []
        return super().get_users(email)


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, label in (("new_password1", "Новый пароль"), ("new_password2", "Повторите пароль")):
            self.fields[name].widget.attrs.update({"autocomplete": "new-password", "placeholder": label})
