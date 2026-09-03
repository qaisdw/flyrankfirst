# Verification Evidence

## 1. Multi-Tenant Isolation
- Tenant A (`tenant_a@example.com`) attempts to access Tenant B's widget:
  `GET /api/widgets/<tenant_b_widget_id>` -> Returns `404 Not Found`.

## 2. Public Config & Cache Control
- `GET /widgets/<widget_id>/config`
  Response Header: `Cache-Control: public, max-age=60`

## 3. Boundary Validation (4xx Errors)
- `POST /submissions` with invalid payload `{ "invalid_field": 123 }`
  Returns `422 Unprocessable Entity` JSON response.

## 4. Rate Limiting (429 Too Many Requests)
- Fired 15 rapid POST requests from `127.0.0.1`:
  Request #11+ returns HTTP `429 Too Many Requests`.

## 5. Geo Enrichment Fallback Chain
- Disabled Provider A (`ip-api.com` mock failure):
  Provider B (`ipapi.co`) responded. Submission stored with enriched country/city.
- Disabled both providers:
  Submission succeeded with `geo_data = null`.

## 6. Harmless Side Effect Failure
- Forced email service to throw `ConnectionError`:
  `POST /submissions` returned HTTP `201 Created` and row persisted safely in DB.