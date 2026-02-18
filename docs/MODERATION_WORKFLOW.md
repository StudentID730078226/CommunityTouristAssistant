# Moderation Workflow

## Place Submissions

1. Authenticated user submits a place.
2. New place is stored with `moderation_status = pending`.
3. Admin reviews pending entries in Django Admin.
4. Admin approves or rejects selected places via bulk actions.

## Review Reporting

1. User reports a review from the place detail page.
2. A `ReviewReport` is created with status `pending`.
3. Admin handles reports in `Review` and `ReviewReport` admin screens.
4. Admin can:
   - Uphold reports (hide review + apply user penalty rules)
   - Dismiss reports (keep review visible)

## Penalty Rules

- Upheld report can reduce contribution points.
- Repeated upheld reports can activate review posting restrictions.

## Anti-Spam Controls

- Endpoint rate limits for review/report/place submission actions
- Honeypot trap field in review forms
- CAPTCHA escalation after suspicious activity
- Duplicate/similarity checks for review text
