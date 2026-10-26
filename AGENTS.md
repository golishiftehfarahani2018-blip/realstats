# Project guidance

Read README.md, docs/status.md, docs/architecture-decisions.md, docs/phase2.md and docs/runbook.md before changing this project. The current user request overrides the four historical source documents summarized in docs/sources.md.

This is an independent installable product, not a Sites or browser-storage prototype. Preserve the Django 5.2 LTS/DRF + Next.js/TypeScript architecture and PostgreSQL for development and integration tests. Do not introduce SQLite fallback, mocked integration success, public deployment, fixed credentials, or previous-customer branding.

All access decisions must be enforced server-side using the authenticated active membership, organization, office, operation and record relationship. Historical introducer is separate from assignee. Only an authorized office manager or that offering's introducer can retrieve private owner fields. A senior role does not grant private contact access. Never add private fields to list/search/public serializers, logs or notifications.

Preserve the database composite foreign keys, immutable offering identity, append-only audit/price history, version checks and session auth_epoch. New mutations require CSRF and appropriate service checks. If migrations or integration tests cannot run, report the exact blocker and do not mark them passed.

Before delivery, run the relevant commands from docs/runbook.md, update docs/status.md with actual evidence, and keep .env, encryption keys, database/media contents and generated passwords out of Git and source archives. New dependencies must be exactly pinned with lockfiles updated. Financial, public publication, real SMS and operational multi-office features require their own stages; do not add nonfunctional UI placeholders.


Current release: business implements office settings, approved-offering revisions, consent/public snapshots/reviewed images, separate customer sessions, invitations, financial agreements and immutable ledger, reports and reminders. Read docs/release-v1.md. Financial or public-publication workflows are no longer future placeholders; preserve their scope checks, consent gate, share-only advisor output, row locks, stable integer rounding, version checks, idempotency and append-only triggers. Customer session credentials must never grant staff membership. Keep real tariffs unset. Run tests for core crm business against real PostgreSQL and S3; worker must restart in new tasks. Public deployment and external SMS/provider integration still require actual infrastructure/configuration; never claim these exist merely because the software runs locally.
