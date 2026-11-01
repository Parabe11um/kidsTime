from django import forms


class ProfileSettingsForm(forms.Form):
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    newsletter = forms.BooleanField(label="Получать рассылку с акциями", required=False)
