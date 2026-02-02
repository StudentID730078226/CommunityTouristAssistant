"""Forms for creating and editing places and their opening hours."""

from datetime import datetime

from django import forms

from .models import ActivityPlace, BeachPlace, FoodPlace, HeritagePlace, Place


DAY_CHOICES = [
    ("mon", "Mon"),
    ("tue", "Tue"),
    ("wed", "Wed"),
    ("thu", "Thu"),
    ("fri", "Fri"),
    ("sat", "Sat"),
    ("sun", "Sun"),
]


def _build_time_choices():
    """Build selectable time choices in 30-minute increments.

    :return: List of (value, label) tuples for time selection.
    :rtype: list[tuple[str, str]]
    """
    choices = [("", "Select time")]
    for hour in range(24):
        for minute in (0, 30):
            value = f"{hour:02d}:{minute:02d}"
            choices.append((value, value))
    return choices


TIME_CHOICES = _build_time_choices()


def _parse_time_value(value):
    """Parse a time string into a time object.

    :param value: Time string in HH:MM format or empty string.
    :return: datetime.time instance or None for empty input.
    :rtype: datetime.time | None
    """
    return datetime.strptime(value, "%H:%M").time() if value else None


class PlaceForm(forms.ModelForm):
    """Base form for creating a Place with shared fields and opening hours."""
    opening_days_list = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    opening_time = forms.ChoiceField(
        choices=TIME_CHOICES, required=False, widget=forms.Select(attrs={"id": "id_opening_time", "class": "form-select"})
    )
    closing_time = forms.ChoiceField(
        choices=TIME_CHOICES, required=False, widget=forms.Select(attrs={"id": "id_closing_time", "class": "form-select"})
    )

    class Meta:
        model = Place
        fields = [
            "name",
            "description",
            "category",
            "location_text",
            "address_line_1",
            "address_line_2",
            "town_city",
            "postcode",
            "website_url",
            "phone_number",
            "accessibility_info",
            "transport_info",
            "parking_info",
            "best_time_to_visit",
            "child_friendly",
            "pet_friendly",
            "estimated_visit_minutes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"id": "id_name", "class": "form-control"}),
            "description": forms.Textarea(attrs={"id": "id_description", "rows": 3, "class": "form-control"}),
            "category": forms.Select(attrs={"id": "id_category"}),
            "location_text": forms.TextInput(
                attrs={
                    "id": "id_location_text",
                    "placeholder": "Postcode or address",
                    "aria-describedby": "location-help",
                    "class": "form-control",
                }
            ),
            "address_line_1": forms.TextInput(attrs={"id": "id_address_line_1", "placeholder": "Address line 1", "class": "form-control"}),
            "address_line_2": forms.TextInput(attrs={"id": "id_address_line_2", "placeholder": "Address line 2 (optional)", "class": "form-control"}),
            "town_city": forms.TextInput(attrs={"id": "id_town_city", "placeholder": "Town / City", "class": "form-control"}),
            "postcode": forms.TextInput(attrs={"id": "id_postcode", "placeholder": "Postcode", "class": "form-control"}),
            "website_url": forms.URLInput(attrs={"id": "id_website_url", "placeholder": "https://", "class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"id": "id_phone_number", "placeholder": "+44 ...", "class": "form-control"}),
            "accessibility_info": forms.Textarea(attrs={"id": "id_accessibility_info", "rows": 2, "class": "form-control"}),
            "transport_info": forms.Textarea(attrs={"id": "id_transport_info", "rows": 2, "class": "form-control"}),
            "parking_info": forms.TextInput(attrs={"id": "id_parking_info", "placeholder": "On-site, street parking, none...", "class": "form-control"}),
            "best_time_to_visit": forms.TextInput(attrs={"id": "id_best_time_to_visit", "placeholder": "Early morning, sunset, summer", "class": "form-control"}),
            "child_friendly": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "pet_friendly": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "estimated_visit_minutes": forms.NumberInput(attrs={"id": "id_estimated_visit_minutes", "min": "1", "class": "form-control"}),
        }

    def clean(self):
        """Validate place submission, including location and opening hours rules.

        :return: Cleaned form data with normalized opening hour fields.
        :rtype: dict
        :raises forms.ValidationError: If location data or hours are incomplete.
        """
        cleaned_data = super().clean()
        place_type = self.data.get("place_type")
        location_text = cleaned_data.get("location_text")
        postcode = cleaned_data.get("postcode")
        town_city = cleaned_data.get("town_city")
        days = cleaned_data.get("opening_days_list") or []
        opening_time_raw = cleaned_data.get("opening_time")
        closing_time_raw = cleaned_data.get("closing_time")

        if not location_text and not postcode and not town_city:
            raise forms.ValidationError("Please provide at least one location field (postcode, town/city, or location text).")

        if place_type == "beach":
            cleaned_data["opening_days"] = ""
            cleaned_data["opening_time"] = None
            cleaned_data["closing_time"] = None
            return cleaned_data

        has_hours_input = bool(days or opening_time_raw or closing_time_raw)
        if has_hours_input and (not opening_time_raw or not closing_time_raw):
            raise forms.ValidationError("Please provide both opening and closing times.")

        cleaned_data["opening_days"] = ",".join(days)
        cleaned_data["opening_time"] = _parse_time_value(opening_time_raw)
        cleaned_data["closing_time"] = _parse_time_value(closing_time_raw)
        return cleaned_data


class PlaceOpeningHoursForm(forms.ModelForm):
    """Form for editing only the opening hours fields on a Place."""
    opening_days_list = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    opening_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        required=False,
        widget=forms.Select(attrs={"id": "id_opening_time_edit", "class": "form-select"}),
    )
    closing_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        required=False,
        widget=forms.Select(attrs={"id": "id_closing_time_edit", "class": "form-select"}),
    )

    class Meta:
        model = Place
        fields = []

    def __init__(self, *args, **kwargs):
        """Initialize the form with existing opening hour values.

        :param args: Positional arguments passed to ModelForm.
        :param kwargs: Keyword arguments passed to ModelForm.
        :return: None
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.opening_days:
                self.fields["opening_days_list"].initial = [d for d in self.instance.opening_days.split(",") if d]
            if self.instance.opening_time:
                self.fields["opening_time"].initial = self.instance.opening_time.strftime("%H:%M")
            if self.instance.closing_time:
                self.fields["closing_time"].initial = self.instance.closing_time.strftime("%H:%M")

    def clean(self):
        """Validate opening hours and normalize fields.

        :return: Cleaned form data with opening hour fields normalized.
        :rtype: dict
        :raises forms.ValidationError: If one time is missing.
        """
        cleaned_data = super().clean()
        days = cleaned_data.get("opening_days_list") or []
        opening_time_raw = cleaned_data.get("opening_time")
        closing_time_raw = cleaned_data.get("closing_time")
        has_hours_input = bool(days or opening_time_raw or closing_time_raw)

        if has_hours_input and (not opening_time_raw or not closing_time_raw):
            raise forms.ValidationError("Please provide both opening and closing times.")

        cleaned_data["opening_days"] = ",".join(days)
        cleaned_data["opening_time"] = _parse_time_value(opening_time_raw)
        cleaned_data["closing_time"] = _parse_time_value(closing_time_raw)
        return cleaned_data

    def save(self, commit=True):
        """Persist opening hours to the associated Place.

        :param commit: Whether to save changes to the database.
        :return: Updated Place instance.
        :rtype: Place
        """
        self.instance.opening_days = self.cleaned_data.get("opening_days", "")
        self.instance.opening_time = self.cleaned_data.get("opening_time")
        self.instance.closing_time = self.cleaned_data.get("closing_time")
        if commit:
            self.instance.save(update_fields=["opening_days", "opening_time", "closing_time"])
        return self.instance


class MultipleFileInput(forms.ClearableFileInput):
    """File input widget allowing multiple file selection."""
    allow_multiple_selected = True


class PlaceImageUploadForm(forms.Form):
    """Form for uploading multiple place images."""
    images = forms.FileField(
        widget=MultipleFileInput(),
        required=False,
        help_text="You may upload up to 30 images. Each image must be under 5MB.",
    )


class HeritagePlaceForm(forms.ModelForm):
    """Form for heritage place-specific fields."""
    class Meta:
        model = HeritagePlace
        fields = ["period", "is_listed", "entry_fee", "guided_tours_available"]


class FoodPlaceForm(forms.ModelForm):
    """Form for food place-specific fields."""
    class Meta:
        model = FoodPlace
        fields = ["cuisine", "price_range", "vegetarian_options", "vegan_options", "takeaway_available"]


class ActivityPlaceForm(forms.ModelForm):
    """Form for activity place-specific fields."""
    class Meta:
        model = ActivityPlace
        fields = ["activity_type", "min_age", "duration_minutes", "booking_required"]


class BeachPlaceForm(forms.ModelForm):
    """Form for beach place-specific fields."""
    class Meta:
        model = BeachPlace
        fields = ["dog_friendly", "lifeguard_present", "water_quality", "facilities_available"]
