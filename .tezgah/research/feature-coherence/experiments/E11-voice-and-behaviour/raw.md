# E11 Sources — reachability of `behaviour` and `user-verbatim` in Ustam and aibim-app

Protocol: `experiments/E11-voice-and-behaviour/protocol.md`.
Question: can either audited repository produce the two evidence classes that came back
empty in every arm?
Verdict up front: **both halves of the protocol's prediction are falsified.**
Telemetry initialisation exists in both repositories (aibim-app ships PostHog + Sentry +
GTM; Ustam ships a provider-neutral observability seam in three clients), and a verbatim
user statement has a real, shipped source in both (Ustam: the customer portal's free-text
service request; aibim-app: the desktop tray's `security_user_feedback` message).
The real defect is not absence but **dark instrumentation**: in Ustam the admin and mobile
clients cannot be switched on by any configuration, and in aibim-app the whole analytics
stack is off outside a `saas`+`prod` build with `granted` consent.

Evidence class of every row below: `code` (source, migration or schema read in this
session). No row is `ui-observed` or `behaviour`: nothing was run.
Not looked at: runtime/DB contents, deployment secrets (`VITE_POSTHOG_KEY`,
`OBSERVABILITY_ENDPOINT`, `VITE_SENTRY_DSN`), vendor dashboards.

---

## 1. Ustam — `apps/admin` (Next.js 16) + `apps/api` (NestJS + Prisma/Postgres) + `apps/mobile` (Expo)

| Source | `path:line` | Measure it supports (window + definition) | Measure it cannot |
|---|---|---|---|
| Telemetry seam (API) | `apps/api/src/observability/api-observability-runtime.ts:13-17` | Nothing as shipped. `enabled: OBSERVABILITY_ADAPTER === 'remote'`; keys absent → no-op sink, `enabled:false`, "hiçbir sinyal yayınlanmaz" (`:12`) | Any product number unless a deployment sets `OBSERVABILITY_ADAPTER=remote` + `OBSERVABILITY_ENDPOINT` |
| Telemetry flag + sink | `packages/config/src/index.ts:336` (default `disabled`), `:847-860` (https enforced); `packages/domain/src/observability.ts:67-70` (`NoopObservabilitySink`), `:255` (product signals need `consent.analytics`, else `consent.diagnostics`) | A *switch*: `OBSERVABILITY_ADAPTER=remote` selects `RemoteObservabilitySink` (`api-observability-runtime.ts:15`) | Anything at rest — no sink means no rows, so no count and no funnel |
| Consent flag (admin) | `apps/admin/lib/observability.ts:36-39` (`analytics:false, diagnostics:false`), `:19-35` (`enabled===true`, `Noop` fallback at `:33`) | Nothing. Only `crash`/`metric`-class essential signals would pass | Every product/analytics event, forever, by default |
| Admin client wiring | `apps/admin/lib/observability-runtime.ts:9-12` (no `enabled` passed) + call sites `apps/admin/lib/api.ts:99,133,143,150` (`create.started`, `create.completed`, `workflow.transitioned`, `api.request`), reached by every admin page that calls `adminApi` — the users area does, `apps/admin/app/(dashboard)/users/page.tsx:8` | **Instrumented but dark.** The users area's own API seam is fully instrumented; no env var feeds `enabled`, so it is hardcoded off | Cannot be turned on by configuration at all — `createAdminObservability` has `enabled` only in its own test (`apps/admin/lib/observability.test.ts:9`) |
| Consent flow (mobile) | `apps/mobile/src/observability/mobile-observability.ts:19-41`, runtime `:12`; call sites `apps/mobile/src/api/client.ts:30,45,52`, `apps/mobile/src/app/CreateActionsScreen.tsx:67` | Nothing. `create.completed`, `api.request`, `create.started` are emitted into a disabled client | The mobile funnel (`create.started → create.completed`) and any screen-level usage |
| Telemetry catalog + retention | `packages/domain/src/telemetry.ts:111-114` (definition: `consent`, `retentionDays`), catalog e.g. `:130-134` (`navigation.opened`, `retentionDays: 90`) | Declares the **shape** of each event and its retention (30/90 d) | No stored row exists to apply 30/90 d to; retention is a schema constant, not a job |
| Audit-log table | `apps/api/prisma/schema.prisma:3432-3447` — `AuditLog` (`organizationId, actorUserId, action, resourceType, resourceId, requestId, reason, redactedDiff, metadata, createdAt`; indexes on `(org,resourceType,resourceId,createdAt)` and `(org,actorUserId,createdAt)`) | **Behaviour proxy.** `COUNT(*)` of `action` per `actorUserId`/`resourceType` per window — e.g. "user.invite actions per week per org". Append-only; window is per query | Funnels (no session id, no screen id, no sequence), per-user rates beyond the actor, and time-to-first-value |
| Audit-log query window | `apps/api/src/audit-logs/audit-logs.service.ts:11,17`; query contract `packages/domain/src/files-audit.ts:22-30` (`from`/`to` optional, `limit ≤ 100`) | An explicit `[from,to]` slice with a definition the caller supplies | No default window, no retention and **no TTL column**: retention is undefined (`OrganizationSettings.retentionPolicy` `schema.prisma:1029` is a `Json` field with **no reader** outside generated Prisma; `auditLog.deleteMany` appears only in test cleanup, never in product code) |
| Campaign interactions | `apps/api/prisma/schema.prisma:2987-3008` + enum `:421-428` (`IMPRESSION/CLICK/COMPLETE/DISMISS`), `dedupeKey` unique per `(org,campaign,user,type,dedupeKey)` | **The only funnel-shaped counter in the repo.** CTR = distinct users with `CLICK` / distinct users with `IMPRESSION` per campaign per window, deduped per key | Whether the user did anything *after* the click: the satisfaction-survey campaign's CTA lands outside the product and its answers are never stored |
| Support ticket / message (not a support export) | `apps/api/prisma/schema.prisma:2754-2815` (`SupportTicket`, `SupportMessage.body`, `SupportAttachment`, `SupportSlaEvent.occurredAt`); endpoints `apps/api/src/support/support.controller.ts:41,63,73,84,96` | **Behaviour proxy:** ticket volume and SLA events — e.g. "tickets opened per category per week", "median `first_response` from `SupportSlaEvent.occurredAt`". Messages are authored by platform `User`s (`authorUserId`), not by the end customer | A customer's own words, and any export: the controller has list/create/read/patch/messages only — no CSV/export route anywhere |
| Customer portal free-text request | `apps/api/prisma/schema.prisma:5299-5320` (field `description String @db.Text` at `:5308`); validation `packages/domain/src/field-customer-learning.ts:482-489` (`min(5).max(5000)`); public endpoint `apps/api/src/field-learning/field-learning.controller.ts:375`; write `apps/api/src/field-learning/field-learning.service.ts:2600,2621-2634`; UI `apps/admin/app/musteri/[token]/CustomerPortalScreen.tsx:322` (`<textarea maxLength={5000} name="description" required>`) | **`user-verbatim`, reachable today.** The customer's own typed sentences, up to 5000 chars, behind a portal grant with `SERVICE_REQUEST` scope | Anything about the admin users area — this is the customer portal surface; no funnel, no rating, no structured dimension beyond `equipmentId` |
| Survey campaign (pointer without a store) | `apps/admin/app/(dashboard)/announcements/campaign-model.ts:261-267` (`memnuniyet-anketi`, body "Kısa bir ankete katılarak…", `actionLabel: 'Ankete katıl'`) | Nothing but the `CLICK` interaction row | The survey answers: `Campaign.content` is a template and there is no response table |
| AI assistance requests | `apps/api/prisma/schema.prisma:2425-2461` (`inputKind: TEXT|VOICE|PHOTO|BOARD_PHOTO`, `requestFingerprint`, `resultPayload`, `mediaRetention`, `mediaDeleteAfter`) | Request volume/status by `inputKind` (`:2431`) — a behaviour count | The user's words: no prompt/transcript column exists (fingerprint + AI result only), so voice/text input is not a verbatim source even though it is accepted |
| Production doc | `docs/production-readiness.md:62-66` | Confirms the off-by-default state and that "vendor, region and retention behind that endpoint are a deployment decision and are not recorded here" | Any retention figure |

### Ustam — the two classes

- `behaviour` — **reachable, but only as append-only event counts with a caller-supplied
  window**: `audit_logs` (`schema.prisma:3432`) via `/audit-logs` with `from`/`to`
  (`files-audit.ts:22-30`), `campaign_interactions` (`:2987`, the single click/impression
  ratio), and `support_sla_events` (`:2805`). No funnel from the admin users area: the
  product events that would build one are emitted into a client that is off by default and,
  for `admin`/`mobile`, not switchable by configuration at all
  (`apps/admin/lib/observability-runtime.ts:9-12`, `apps/mobile/src/observability/mobile-observability-runtime.ts:12`).
- `user-verbatim` — **reachable, from the customer portal**: `customer_service_requests.description`
  (`schema.prisma:5308`), captured at `CustomerPortalScreen.tsx:322` through
  `POST /:token/service-requests` (`field-learning.controller.ts:375`). Second-order:
  `support_messages.body` (`schema.prisma:2786`) exists but is staff-authored.

---

## 2. aibim-app — `admin/frontend` (React) + `admin/backend` (axum) + `app/frontend` + `app/backend`

| Source | `path:line` | Measure it supports (window + definition) | Measure it cannot |
|---|---|---|---|
| PostHog init (product app) | `app/frontend/src/analytics/posthog.ts:50-51` (`if (!hasAnalyticsConsent()) return`), `:61-73` (`posthog.init`, `capture_pageview:false`, `persistence:'localStorage+cookie'`), `:87-88`, `:103` (capture gated again) | **A real funnel source.** `surface.view.*`, `*.click.*`, `*.create.*` events per user/tenant group with `$pageview` from the route listener | Nothing on the audited admin surface; and nothing at all until consent is `granted` |
| Consent gate | `app/frontend/src/analytics/consent.ts:9` (`VITE_APP_ENV==='prod' && VITE_MODE==='saas'`), `:30` (`hasAnalyticsConsent`), `:34`; banner `AnalyticsConsentBanner.tsx:84-87`; provider gate `PostHogProvider.tsx:81-89` (`consent !== 'granted'` → no init, 12 s delay) | Counts only for consented users in the SaaS production build; self-hosted/enterprise builds emit zero | Any denominator that includes non-consenting users — no funnel completion rate over the whole population |
| Event catalog | `app/frontend/src/analytics/events.ts:8-139` (`surface.action.target`) | Named intents with a stable vocabulary (per-monitoring/detection/governance sections) | Values: no duration, no outcome, no payload text |
| Sentry | `app/frontend/src/main.tsx:23-30` (init only when `VITE_SENTRY_DSN` present) + `analytics/sentry.ts:10` | Crash/error rate by environment, and non-PII user context (`App.tsx:147-149`) | Any product metric; and no error signal from either admin frontend |
| GTM/GA | `app/frontend/src/analytics/consent.ts:7-8` (hardcoded `GTM-KWVMNLQJ`, `G-8GYDEJM4ZR`), `:67-80` | Page/consent-mode signals once consent is `granted` in the SaaS prod build | Anything on the admin surface |
| Admin frontend analytics | `admin/frontend/package.json:10-21` (deps: react, axios, recharts, zustand — no analytics client); only match for the word anywhere in the admin UI is a policy label, `admin/frontend/src/pages/TenantDetail.tsx:42` | **Nothing.** The audited users area (`admin/frontend/src/pages/Users.tsx`) has no instrumentation of any kind | Every number about the admin users area, including its own funnel |
| `audit_log` (tenant audit) | `db/migrations/003_behavioral.sql:34-52` (`operation, actor_id, actor_role, resource_type, resource_id, action_details, source_ip, previous_hash, entry_hash, created_at`; hash-chained), `031_audit_log_tenant_id.sql:4-13` | **Behaviour proxy.** `COUNT(*)` per `operation`/`actor_id`/`resource_type` in an explicit `[from,to]`; also a tamper check via `previous_hash`/`entry_hash` pairs | Funnels; and any retention: the table is a plain B-tree table (not a hypertable) with **no TTL, no partition, and no delete path** other than the undocumented archive job below |
| Audit-log API window | `admin/backend/src/handlers/admin.rs:7199` (`GET /api/v1/admin/audit-logs`, route `admin/backend/src/main.rs:298-299`), filters `:7236-7247` (`tenant_id`, `operation`, `created_at` from/to, `actor_id`), data query `:7290`, `limit ≤ 500`, `offset` | A filtered, offset-paginated slice with a caller-supplied window and a filtered `total` (`:7273`) | Export: the CSV path belongs to the *enterprise* handler, not this one — `audit_log` has no export route |
| `enterprise_audit_events` | `db/migrations/081_enterprise_account_management.sql:391`; list `admin/backend/src/handlers/admin.rs:7338`; CSV `:7348,7497-7508` (`enterprise-audit.csv`, cap 5000); signed export `:7538`; routes `main.rs:469-474` | **The only audit export in aibim-app**: enterprise-scoped event counts and a signed CSV of the same | Tenant-level `audit_log` data (different table, different scope) |
| `detection_events` | `db/migrations/002_detection.sql:5-55` (metadata only: `prompt_hash` `:20`, `prompt_length`, `risk_score`, `action_taken` `:41`, `sentiment_polarity/score`, `sentiment_emotions`), hypertable `:58-63` 1-month chunks | **Behaviour proxy at production volume.** Rates over an explicit window: block ratio = `COUNT(action_taken='blocked') / COUNT(*)` per tenant/model/provider; sentiment distribution per 24 h (`app/frontend/src/pages/SentimentAnalytics/index.tsx:66-80`) | The prompt text itself (hash + length only), and retention: `add_retention_policy` appears nowhere in `db/migrations` |
| `ai_telemetry_events` | `db/migrations/088_ai_telemetry_events.sql:6-56` (`event_type` ∈ 9 families, `decision`, `risk_level`, `actor_type`, `redaction_state` default `metadata_only`, `prevent_hard_delete` trigger at the tail); writer `app/backend/src/db/event_logger.rs:46-50,361` | **A real telemetry table with a window and a definition**: decision mix = `COUNT(decision) / COUNT(*)` per `event_type` per tenant, e.g. policy allow/block ratio; `trace_id` joins a request across families | User behaviour *of the product UI* — this is AI-governance telemetry (model/agent/tool/policy/eval), not product analytics; no retention policy, only a no-hard-delete trigger |
| `agent_audit_log` | `db/migrations/009_agents.sql:6-24` (hypertable, 1-month chunks; `approved`, `constraint_violated`, `severity`, `estimated_cost_usd`) | Block ratio and violation mix for agent tool calls per window | The product UI, and any retention (`add_retention_policy` absent) |
| `review_queue` / `hitl_queue` | `db/migrations/008_governance.sql:6-30` (`prompt_snippet TEXT`, `detection_summary`, `review_notes`, `reviewed_at`, `ttl_expires_at`), `056_state_persistence.sql:23-41` (`request_json JSONB`, 5-minute TTL) | **Two things**: (a) behaviour — approve/reject/timeout mix and reviewer latency from `created_at → reviewed_at`; (b) **`user-verbatim`** — `prompt_snippet` / `request_json` hold the end user's own prompt that triggered quarantine | A statement *about the product*: the snippet is user content captured for a human decision, truncated, with a 5-minute TTL on the durable variant |
| Desktop setup events (feedback carrier) | `db/migrations/102_desktop_enterprise_control_plane.sql:39-48` (`event TEXT`, `error TEXT`, `metadata JSONB`, `is_deleted`); write `app/backend/src/proxy/api_handlers/desktop.rs:3166`; read `:3250` with `LIMIT/OFFSET` `:3273-3274,3277,3294` | **`user-verbatim` + behaviour.** Event counts per `tool_id` per window (setup/security), and the free-text `metadata.message` of user feedback | Nothing about the admin users area; feedback only from enrolled desktop agents |
| Desktop tray feedback form | `native-enforcement/windows-tray/src/feedback.rs:6-11` (category + `message: String`), `:28-52` (`metadata.message`, `category`, optional diagnostics), `:68-76` (`event: "security_user_feedback"`), `:88` (`POST /api/v1/desktop/setup-events`); mirrors `linux-tray/src/feedback.rs:74`, `macos-network-extension/Sources/AibimNetworkExtensionInstaller/main.swift:1248`; rendered at `app/frontend/src/pages/DesktopAgentDownload/index.tsx:220,1325` | **`user-verbatim`, reachable today**: the user's typed message, one of 5 fixed categories, sent only when the agent is enrolled | Any user who is not on an enrolled desktop agent — no web/mobile feedback path exists |
| Governed data export | `app/backend/src/proxy/api_handlers/data.rs:735-800` (`GET /api/v1/data/export`, governance-gated, `detection_events` metadata columns only, `max_export_records`) | An exportable behaviour slice (correlation id, model, risk, action, endpoint, timestamp) | Prompts/text: the export deliberately selects no content column |
| Retention, declared vs enforced | `app/backend/src/db/retention.rs:64-72` (`audit_logs` 365 d → archive, `event_details` 90 d, `prompt_hashes` 30 d), guarded by `:17-18` (`// FUTURE: Wire …` + `#![allow(dead_code)]`); `db/migrations/051_benchmark_retention_and_indexes.sql:5-6,20-24,57-60` (retention must be a manual job; `add_retention_policy` only works on hypertables); `db/migrations/090_tenant_data_governance_policies.sql:3-15` (`retention_days` per data domain); `db/migrations/105_commercial_entitlements_usage.sql:265,271,276,281` (`retention_days` 7/30/90/contractual per plan) | A **declared** window per source, each with a plan tier | An enforced one: the manager is dead code and applies only `prompt_hashes`/`event_details` in memory; its `audit_logs` policy name does not even match the table (`audit_log`), and no job in `app/backend/src/jobs/` sweeps audit or telemetry tables |

### aibim-app — the two classes

- `behaviour` — **reachable, from four independent stores, each with an explicit window**:
  `detection_events` (`002_detection.sql:7`, hypertable, block ratio / sentiment mix),
  `ai_telemetry_events` (`088_ai_telemetry_events.sql:6`, decision mix per event family),
  `audit_log` + `enterprise_audit_events` (`003_behavioral.sql:34`, `081_…:391`, the latter
  with a CSV export), `agent_audit_log` (`009_agents.sql:6`). The product-UI funnel is
  reachable **only** from `app/frontend` PostHog (`analytics/posthog.ts:61`) and only as
  `saas`+`prod`+`granted`; the audited admin users area has no instrumentation at all
  (`admin/frontend/package.json:10-21`, sole match `TenantDetail.tsx:42`).
- `user-verbatim` — **reachable, from two places**: (1) the desktop tray's
  `security_user_feedback` message, `native-enforcement/windows-tray/src/feedback.rs:46,74`
  → `desktop_agent_setup_events.metadata` (`102_…:39`) → read at
  `desktop.rs:3250` and rendered at `DesktopAgentDownload/index.tsx:1325`; (2) the
  quarantined prompt itself, `review_queue.prompt_snippet` (`008_governance.sql:16`) and
  `hitl_queue.request_json` (`056_state_persistence.sql:26`, 5-minute TTL).

---

## 3. Searches that show the gaps (negative evidence)

Each line is a search run in this session whose empty or single-sided result is the finding.

- Ustam has **no analytics dependency anywhere**: `grep -rniE "posthog|mixpanel|amplitude|segment|plausible|umami|matomo|gtag|google-analytics|hotjar|clarity|logrocket|firebase|vercel/(analytics|otel)" package.json apps/*/package.json packages/*/package.json` → no matches; `apps/admin/next.config.ts` has no analytics plugin. What exists is the in-house seam, off by default.
- Ustam's admin/mobile seams **cannot be enabled by config**: `grep -rn "createAdminObservability|createMobileObservability"` → only the runtime (which passes no `enabled`), the factory, and one test passing `enabled: true`. No `NEXT_PUBLIC_*`/`EXPO_PUBLIC_*` reads feed either flag.
- Ustam has **no audit-log retention**: `grep -rn "retentionPolicy" apps packages --include=*` excluding generated Prisma → no matches; `grep -rn "auditLog.deleteMany" apps --include=*.ts` → generated client + integration-test cleanup only.
- Ustam has **no support export and no review corpus**: `support.controller.ts` exposes `tickets`/`assignees`/`tickets/:id`/`tickets` POST/`PATCH`/`messages`/`read` only (lines 41,53,63,73,84,96); `grep -niE "rating|stars|yorum|reviewText|testimonial" apps/api/prisma/schema.prisma` → no matches; the only files matching `*review*` are engine review agents and the internal UX audit under `apps/admin/review/`.
- aibim-app has **no support-ticket table**: `grep -rniE "CREATE TABLE IF NOT EXISTS (support|ticket)" db/migrations/*.sql` → no matches; every `ticket` hit is a WebSocket auth ticket (`app/backend/src/proxy/ws_tickets.rs`).
- aibim-app's **admin users area is uninstrumented**: `grep -rniE "posthog|sentry|analytics|gtag|consent" admin/frontend/src admin/frontend/index.html` → one label, `TenantDetail.tsx:42`; `admin/frontend/package.json` has no analytics dependency.
- aibim-app has **no enforced retention**: `grep -rn "add_retention_policy" db/migrations/*.sql` → no matches (only `051_…` explaining why it cannot be used); `app/backend/src/db/retention.rs` is `#![allow(dead_code)]` with a `FUTURE:` note; no job in `app/backend/src/jobs/` touches `audit_log`, `ai_telemetry_events` or `desktop_agent_setup_events`.
- aibim-app has **no user review corpus**: `find . -iname "*review*"` → `app/frontend/src/pages/ReviewQueue` (HITL queue), `.claude/skills/security-review-owasp.md`, `.engineering/roles/security-reviewer.md`.

## 4. Consequence for the line

The empty classes in every arm were **not** forced by the products. Both repositories carry
a `user-verbatim` source and multiple `behaviour` stores; the arms that reported "no source"
reported a limit of their search, not a property of either product.

What is genuinely absent, and worth reporting as a finding in the product sense:

1. **Ustam — dark instrumentation.** `apps/admin` and `apps/mobile` emit product events at
   real call sites (`apps/admin/lib/api.ts:99-150`, `apps/mobile/src/api/client.ts:30-52`)
   into clients whose `enabled` flag is hardcoded `false` and whose analytics consent is
   hardcoded `false`, with no env plumbing to change either. The API client is the only one
   that a deployment can switch on. So the admin users area has a shipped funnel definition
   and zero rows.
2. **No retention is enforced anywhere.** Ustam's `audit_logs` has no TTL and an unread
   `retentionPolicy` field; aibim-app declares windows in three places
   (`retention.rs`, `tenant_data_governance_policies.retention_days`,
   `commercial_entitlements_usage`) and enforces none, and its `audit_logs` policy names a
   table that does not exist. Every behaviour number therefore has a caller-chosen window
   and no contractual one.
