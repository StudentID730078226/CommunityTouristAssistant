import re

from django.core.exceptions import ValidationError

BANNED_WORDS = [
    "badword1",
    "badword2",
    "offensiveword",
]

def validate_review_language(value):
    """Validate review text against banned words and spam patterns.

    :param value: Raw review text.
    :return: None if valid.
    :raises ValidationError: When content is inappropriate or spam-like.
    """
    text = value.lower()

    for word in BANNED_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text):
            raise ValidationError(
                "Your review contains inappropriate language."
            )

    # Basic anti-spam safeguards.
    if len(re.findall(r"https?://|www\.", text)) > 2:
        raise ValidationError("Please do not include excessive links in reviews.")
    if len(text) > 1200:
        raise ValidationError("Review is too long. Please keep it under 1200 characters.")
