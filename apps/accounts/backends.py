from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        if email is None or password is None:
            return None
        users = list(get_user_model().objects.filter(email__iexact=email.strip())[:2])
        if len(users) != 1:
            # Match Django's dummy hashing for a missing or ambiguous account.
            get_user_model()().set_password(password)
            return None
        user = users[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
