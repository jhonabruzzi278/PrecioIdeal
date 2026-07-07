from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

_INPUT_CLASS = "form-control"


class SignupForm(UserCreationForm):
    """Registration form: username + email + password, Bootstrap-styled.

    On save the user is created; the 30-day Pro trial is provisioned by the
    view via the billing access service.
    """

    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(attrs={"class": _INPUT_CLASS}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": _INPUT_CLASS})
        self.fields["password1"].widget.attrs.update({"class": _INPUT_CLASS})
        self.fields["password2"].widget.attrs.update({"class": _INPUT_CLASS})

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
