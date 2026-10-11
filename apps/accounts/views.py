import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, PasswordResetView
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from .forms import EmailLoginForm, EmailPasswordResetForm, RegistrationForm
from .limits import rate_limited
from .policy import registration_policy_url

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
                user = form.save()
            except IntegrityError:
                form.add_error("email", "Этот email уже зарегистрирован. Войдите или восстановите пароль.")
            else:
                login(request, user, backend="apps.accounts.backends.EmailBackend")
                return redirect("core:profile")
    return render(request, "accounts/register.html", {
        "form": form,
        "privacy_policy_url": registration_policy_url(),
        "test_registration_enabled": settings.TEST_REGISTRATION_ENABLED,
    }, status=status)


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
