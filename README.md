# Community Tourist Assistant

A Django-based crowd-sourced tourism platform where visitors can discover places, submit content, review locations, and help moderate quality through reporting workflows.

## Key Features

- Public place browsing and advanced search/filtering
- Polymorphic place types (heritage, food, activity, beach, generic)
- Place submission workflow with moderation statuses
- Review posting, reporting, and moderation actions
- Contribution points and trust/restriction mechanics
- Like system with dedicated `PlaceLike` model
- Anti-spam protections (rate limits, honeypot, CAPTCHA escalation, similarity checks)

## Tech Stack

- Python 3.12+
- Django 4.2
- django-polymorphic
- django-ratelimit
- Bootstrap 5
- Pytest + pytest-django + pytest-cov

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Configure environment variables (copy `.env.example` to `.env` and adjust values).
4. Run migrations:
   `python manage.py migrate`
5. Start development server:
   `python manage.py runserver`

## Database Options

This project supports both SQLite and PostgreSQL via environment variables.

- SQLite (default): no extra setup required.
- PostgreSQL: set these variables in `.env`:
  - `DB_ENGINE=django.db.backends.postgresql`
  - `DB_NAME=community_tourism`
  - `DB_USER=your_user`
  - `DB_PASSWORD=your_password`
  - `DB_HOST=localhost`
  - `DB_PORT=5432`

## Testing

- Run all tests:
  `pytest -q`
- Run with coverage:
  `pytest --cov=accounts --cov=community_tourism --cov=places --cov=reviews --cov-report=term-missing -q`

## Sphinx Documentation

- Install docs dependencies (already included in `requirements.txt`):
  `pip install -r requirements.txt`
- Build HTML docs:
  `sphinx-build -b html docs/sphinx/source docs/sphinx/_build/html`
- Build PDF docs with rinohtype:
  `sphinx-build -b rinoh docs/sphinx/source docs/sphinx/_build/rinoh`

## Public Policy Pages

- Contribution Guidelines: `/policies/contribution-guidelines/`
- Moderation Policy: `/policies/moderation-policy/`
- Acceptable Use Policy: `/policies/acceptable-use/`

## Project Structure

- `accounts/` user auth, profile, contribution tracking
- `places/` core place models, add/search/detail workflows, likes
- `reviews/` reviews, reports, moderation actions, anti-spam helpers
- `templates/` frontend templates
- `tests/` unit + integration test suites
