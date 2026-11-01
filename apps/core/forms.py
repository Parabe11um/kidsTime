import io
import warnings
from uuid import uuid4

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


class ProfileSettingsForm(forms.Form):
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    newsletter = forms.BooleanField(label="Получать рассылку с акциями", required=False)


class ProfileAvatarForm(forms.Form):
    avatar = forms.ImageField(label="Фото профиля")

    def clean_avatar(self):
        upload = self.cleaned_data["avatar"]
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Выберите фото размером до 5 МБ.")
        try:
            upload.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as source:
                    if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "is_animated", False):
                        raise forms.ValidationError("Выберите обычное фото в формате JPEG, PNG или WebP.")
                    if source.width * source.height > 16_000_000:
                        raise forms.ValidationError("Разрешение фото должно быть не больше 16 мегапикселей.")
                    image = ImageOps.exif_transpose(source)
                    image.thumbnail((512, 512))
                    # Re-encoding removes metadata and any bytes appended to the upload.
                    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                        rgba = image.convert("RGBA")
                        image = Image.new("RGB", rgba.size, "white")
                        image.paste(rgba, mask=rgba.getchannel("A"))
                    else:
                        image = image.convert("RGB")
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=88)
        except forms.ValidationError:
            raise
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise forms.ValidationError("Не удалось прочитать фото. Выберите другой файл.") from error
        return ContentFile(output.getvalue(), name=f"{uuid4().hex}.jpg")
