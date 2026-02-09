"""Forms for creating user reviews with lightweight anti-spam fields."""

from __future__ import annotations

from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    """Review form with rating, text, honeypot, and optional CAPTCHA."""
    rating = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={"class": "star-rating"}),
        label="Rating",
    )
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)
    captcha_answer = forms.CharField(required=False, label="Security check")

    class Meta:
        model = Review
        fields = ["rating", "text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Write your review...",
                }
            )
        }

    def __init__(self, *args, require_captcha: bool = False, captcha_question: str = "", **kwargs):
        """Initialize the form and configure CAPTCHA when required.

        :param args: Positional arguments passed to ModelForm.
        :param require_captcha: Whether the security question should be required.
        :param captcha_question: The question to display when CAPTCHA is required.
        :param kwargs: Keyword arguments passed to ModelForm.
        :return: None
        """
        super().__init__(*args, **kwargs)
        if require_captcha:
            self.fields["captcha_answer"].required = True
            self.fields["captcha_answer"].help_text = captcha_question
            self.fields["captcha_answer"].widget = forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Answer security question"}
            )
        else:
            self.fields["captcha_answer"].widget = forms.HiddenInput()

    def clean_honeypot(self):
        """Validate the hidden honeypot field to detect bots.

        :return: Empty string when no spam detected.
        :rtype: str
        :raises forms.ValidationError: If the honeypot field is filled.
        """
        honeypot = self.cleaned_data.get("honeypot", "")
        if honeypot:
            raise forms.ValidationError("Spam protection triggered.")
        return honeypot
