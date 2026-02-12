"""Anti-spam helpers for review submissions."""

from __future__ import annotations

import random
import re
from difflib import SequenceMatcher
from typing import Tuple

from .models import Review


CAPTCHA_REQUIRED_KEY = "review_captcha_required"
CAPTCHA_ANSWER_KEY = "review_captcha_answer"
CAPTCHA_QUESTION_KEY = "review_captcha_question"


def normalize_text(text: str) -> str:
    """Normalize text for similarity comparison.

    :param text: Raw review text input.
    :return: Normalized text with punctuation removed and whitespace collapsed.
    :rtype: str
    """
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", (text or "").lower())).strip()


def get_or_create_captcha(request) -> Tuple[bool, str]:
    """Return the current CAPTCHA requirement and question for the session.

    :param request: Incoming HTTP request.
    :return: Tuple of (required flag, question text).
    :rtype: tuple[bool, str]
    """
    required = bool(request.session.get(CAPTCHA_REQUIRED_KEY))
    if not required:
        return False, ""

    question = request.session.get(CAPTCHA_QUESTION_KEY)
    if not question:
        a = random.randint(2, 9)
        b = random.randint(1, 8)
        request.session[CAPTCHA_ANSWER_KEY] = str(a + b)
        request.session[CAPTCHA_QUESTION_KEY] = f"What is {a} + {b}?"
        request.session.modified = True
        question = request.session[CAPTCHA_QUESTION_KEY]
    return True, question


def require_captcha(request) -> None:
    """Flag the session so CAPTCHA is required on the next submission.

    :param request: Incoming HTTP request.
    :return: None
    """
    request.session[CAPTCHA_REQUIRED_KEY] = True
    # Force a fresh challenge on the next render.
    request.session.pop(CAPTCHA_QUESTION_KEY, None)
    request.session.pop(CAPTCHA_ANSWER_KEY, None)
    request.session.modified = True


def validate_captcha(request, submitted_answer: str) -> bool:
    """Validate a submitted CAPTCHA answer and clear the requirement on success.

    :param request: Incoming HTTP request.
    :param submitted_answer: User's answer to the CAPTCHA question.
    :return: True if the answer matches the expected value.
    :rtype: bool
    """
    expected = str(request.session.get(CAPTCHA_ANSWER_KEY, "")).strip()
    if expected and str(submitted_answer or "").strip() == expected:
        request.session[CAPTCHA_REQUIRED_KEY] = False
        request.session.pop(CAPTCHA_QUESTION_KEY, None)
        request.session.pop(CAPTCHA_ANSWER_KEY, None)
        request.session.modified = True
        return True
    return False


def is_duplicate_or_similar_review(place, text: str) -> bool:
    """Check whether a review is a duplicate or too similar for a given place.

    :param place: Place instance to compare against.
    :param text: Review text to evaluate.
    :return: True if duplicate or highly similar review is detected.
    :rtype: bool
    """
    candidate = normalize_text(text)
    if not candidate:
        return False

    # Exact duplicate against any existing review text for this place.
    if Review.objects.filter(place=place, text__iexact=text, is_archived=False).exists():
        return True

    # Similarity check against recent texts for this place.
    for existing in (
        Review.objects.filter(place=place, is_archived=False).order_by("-created_at").values_list("text", flat=True)[:50]
    ):
        existing_normalized = normalize_text(existing)
        if not existing_normalized:
            continue
        similarity = SequenceMatcher(None, candidate, existing_normalized).ratio()
        if len(candidate) >= 25 and len(existing_normalized) >= 25 and similarity >= 0.85:
            return True
    return False
