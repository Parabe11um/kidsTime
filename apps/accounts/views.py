import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.views import LoginView, PasswordResetView
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from .forms import EmailLoginForm, EmailPasswordResetForm, RegistrationForm, ResendVerificationForm
from .limits import rate_limited
from .policy import registration_policy_url
from .models import Account
from .verification import RESEND_INTERVAL, mail_configured, pending_verification, send_verification, valid_verification

logger = logging.getLogger(__name__)
LIMIT_MESSAGE = "Слишком много попыток. Попробуйте позже."


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if rate_limited(request, "login", request.POST.get("email", "")):
            form = EmailLoginForm(request=request, data={"email": request.POST.get("email", "")})
            form.add_error(None, LIMIT_MESSAGE)
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)


@sensitive_post_parameters("password1", "password2")
@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("core:profile")
    form = RegistrationForm(request.POST or None)
    status = 200
    if request.method == "POST":
        if rate_limited(request, "register", request.POST.get("email", "")):
            form.is_valid()
            form.add_error(None, LIMIT_MESSAGE)
            status = 429
        elif form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    send_verification(request, user.account)
            except IntegrityError:
                form.add_error("email", "Этот email уже зарегистрирован. Войдите или восстановите пароль.")
            except (SMTPException, OSError):
                logger.error("Registration verification email delivery failed")
                form.add_error(None, "Не удалось отправить письмо подтверждения. Попробуйте зарегистрироваться ещё раз позже.")
            else:
                return redirect("accounts:email_verification_sent")
    return render(request, "accounts/register.html", {
        "form": form,
        "privacy_policy_url": registration_policy_url(),
        "test_registration_enabled": settings.TEST_REGISTRATION_ENABLED,
        "registration_mail_configured": mail_configured(),
    }, status=status)


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def resend_verification(request):
    form = ResendVerificationForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        if rate_limited(request, "verify-resend", email):
            form.add_error(None, LIMIT_MESSAGE)
            status = 429
        elif not mail_configured():
            form.add_error(None, "Отправка писем временно недоступна. Попробуйте позже.")
        else:
            try:
                with transaction.atomic():
                    account = Account.objects.select_for_update().select_related("user").filter(email=email).first()
                    if pending_verification(account) and timezone.now() - account.email_verification_sent_at >= RESEND_INTERVAL:
                        send_verification(request, account)
            except (SMTPException, OSError):
                logger.error("Resend verification email delivery failed")
                form.add_error(None, "Не удалось отправить письмо. Попробуйте позже.")
            else:
                return redirect("accounts:email_verification_sent")
    return render(request, "accounts/email_verification_resend.html", {"form": form}, status=status)


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def verify_email(request, uidb64, token):
    try:
        user_id = int(urlsafe_base64_decode(uidb64).decode())
    except (ValueError, TypeError, UnicodeDecodeError, OverflowError):
        user_id = None
    with transaction.atomic():
        account = Account.objects.select_for_update().select_related("user").filter(user_id=user_id).first()
        validlink = valid_verification(account, token)
        if request.method == "POST" and validlink:
            account.user.is_active = True
            account.user.save(update_fields=["is_active"])
            account.email_verified_at = timezone.now()
            account.email_verification_digest = ""
            account.save(update_fields=["email_verified_at", "email_verification_digest"])
            response = redirect("accounts:email_verified")
            response["Referrer-Policy"] = "no-referrer"
            return response
    response = render(request, "accounts/email_verification_confirm.html", {"validlink": validlink})
    response["Referrer-Policy"] = "no-referrer"
    return response


@method_decorator(never_cache, name="dispatch")
class EmailPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = EmailPasswordResetForm
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        if rate_limited(self.request, "reset", form.cleaned_data["email"]):
            form.add_error(None, LIMIT_MESSAGE)
            return self.render_to_response(self.get_context_data(form=form), status=429)
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            form.add_error(None, "Восстановление пароля временно недоступно. Попробуйте позже.")
            return self.form_invalid(form)
        try:
            return super().form_valid(form)
        except (SMTPException, OSError):
            logger.error("Password reset email delivery failed")
            form.add_error(None, "Не удалось отправить письмо. Попробуйте позже.")
            return self.form_invalid(form)
