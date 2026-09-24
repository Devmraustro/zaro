# ZARO — Intended But Unwired Features: Completion Report

Date: 2026-09-24
Branch: `main` (no commit/push performed per scope)

## Files changed in this delivery (and why)

**Phase 1 — References (wilaya/commune) publicly served**
- `apps/zaro-api/app/api/v1/router.py` — included `references.router` under the public storefront; included `dashboard.router`.
- `apps/zaro-api/app/api/v1/endpoints/references.py` — moved `Wilaya`/`Commune` imports to module top (removed lazy `# type: ignore[import-not-found]`); fixed the latent cross-join in the communes query (explicit `Commune.wilaya_id == Wilaya.id` join, filter `Wilaya.code == wilaya`, ordering by `Wilaya.code, Commune.code, Commune.name_en`).

**Phase 2 — Custom-request location submission**
- `apps/zaro-api/app/schemas/custom_requests.py` — added `wilaya` (`^\d{2}$`), `commune` (max 100), `address` (max 1000) to `CustomRequestSubmit`.
- `apps/zaro-api/app/api/v1/endpoints/custom_requests.py` — passes `wilaya`/`commune`/`address` to the service; `_serialize_public` now returns them.
- `apps/zaro-api/app/services/custom_requests_service.py` — persists `wilaya`/`commune`/`address` on the model; location validation raises `ValidationFailedError` (not `InvalidStateTransition`); added "commune requires a wilaya" rule.

**Phase 3 — Dashboard**
- `apps/zaro-api/app/api/v1/router.py` — wired the existing `dashboard.router` (no duplicate routes added).

**Phase 4 — Catalog localization (CRUD + public resolution)**
- `apps/zaro-api/app/schemas/catalog.py` — added `ProductLocalizationUpsert`, `CategoryLocalizationUpsert`, `LocalizationResponse`, `LOCALES`.
- `apps/zaro-api/app/api/v1/endpoints/catalog_admin.py` — added product/category localization PUT/GET/DELETE routes (permission-gated `PRODUCTS_UPDATE`/`PRODUCTS_READ`, `extra="forbid"` payloads, locale path pattern, 404 semantics, audit events); `_serialize_product_admin` now includes media via `_serialize_asset`.
- `apps/zaro-api/app/services/catalog_service.py` — attach `admin_media` in admin reads; localized search (`lang != "en"` matches `ProductLocalization.name` via parameterized subquery); public media attach.
- `apps/zaro-api/app/api/v1/endpoints/catalog_public.py` — rewritten public resolution: `lang` query param + `Accept-Language` fallback, localized name/description with canonical-en fallback, `locale` key in responses, localized category listing.

**Phase 5 — Product media PATCH/DELETE**
- `apps/zaro-api/app/schemas/files.py` — added `ProductMediaUpdate` (`extra="forbid"`, media_kind pattern, alt_text/sort_order bounds).
- `apps/zaro-api/app/models/audit_enums.py` — added `FILE_UPDATED`.
- `apps/zaro-api/app/api/v1/endpoints/files.py` — added `_load_product_media` (404 for missing/wrong-product/non-PRODUCT_MEDIA); PATCH (PRODUCTS_UPDATE, audit `FILE_UPDATED`) and DELETE (PRODUCTS_UPDATE, storage delete via `backend.delete`, audit `FILE_DELETED`, 204); fixed a stray `if False else` expression.

**Phase 6 — Telegram — INTENTIONALLY NOT WIRED**
No documented ZARO workflow requires Telegram; it stays an additive service (no-op when credentials unset) with its unit test green. No fictional wiring added.

**Test infrastructure**
- `apps/zaro-api/tests/conftest.py` — seed 3 wilayas (16/19/31) + 4 communes (1601/1602/1901/3101) after `create_all` (the integration DB has no Alembic seed data).
- `apps/zaro-api/tests/integration/test_references_api.py` (new, 5 tests) and `test_custom_requests_location.py` (new, 7 tests).
- `apps/zaro-api/tests/integration/test_product_media_api.py` — fixed one test-file bug: `await db_session.add(...)` (AsyncSession.add is synchronous). Two `await` occurrences corrected; no assertion weakened.

## Test results

**Previously failing integration suites — now green**
- `test_dashboard_api.py` — 3 passed
- `test_catalog_localizations.py` — 10 passed
- `test_product_media_api.py` — 9 passed

**Full backend gates**
- unit + non-PG integration: 522 passed
- migrations (SQLite, full up/down/up chain): 3 passed
- PostgreSQL concurrency + QC: 10 passed
- ruff check: 0 errors; ruff format: 0 unformatted; mypy: 0 errors

**Frontend gates** (no files changed for this delivery)
- typecheck: 4/4 tasks; lint: 2/2; web tests: 61 passed; build: 2/2

## Security scan
- No secrets or credentials added. No broad `# type: ignore` added. Storage keys/purpose/visibility/ownership remain server-set (extra="forbid"). Permissions/ownership checks preserved; no cross-tenant signals (404 rather than 403).

## Git status
Working tree modified only; **no commit, no push**. Untracked changes also include pre-existing work (payment removal, migrations 0008–0015, web UI/i18n) from earlier deliveries — none committed by this task.