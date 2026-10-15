from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from . import views
from .forms import StyledSetPasswordForm

app_name = "accounts"
urlpatterns = [
    path("login/", views.EmailLoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("email/sent/", never_cache(TemplateView.as_view(template_name="accounts/email_verification_sent.html")), name="email_verification_sent"),
    path("email/resend/", views.resend_verification, name="email_verification_resend"),
    path("email/confirmed/", never_cache(TemplateView.as_view(template_name="accounts/email_verified.html")), name="email_verified"),
    path("email/verify/<uidb64>/<token>/", views.verify_email, name="email_verify"),
    path("logout/", auth_views.LogoutView.as_view(next_page="core:profile"), name="logout"),
    path("password/reset/", views.EmailPasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_confirm.html", form_class=StyledSetPasswordForm, success_url=reverse_lazy("accounts:password_reset_complete")), name="password_reset_confirm"),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
]
