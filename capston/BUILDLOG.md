# Build Log

## Initial Setup & Architecture
- Configured FastAPI with SQLAlchemy SQLite for zero-config persistence.
- Implemented multi-tenant data model (Users -> Widgets -> Submissions).

## Boundary Validation & CORS
- Added public `/submissions` route allowing cross-origin requests (`CORS`).
- Implemented Pydantic schema validation for form field payloads.

## Abuse Protection & Resiliency
- Built IP and widget rate-limiting middleware returning HTTP 429 upon bursts.
- Added honeypot field (`hp_field`) checks to silently reject automated spam.
- Integrated `httpx` async fallback chain for Geo IP enrichment (`ip-api.com` -> `ipapi.co`).
- Wrapped confirmation email side effect in safe `BackgroundTasks` so failures do not abort submissions.