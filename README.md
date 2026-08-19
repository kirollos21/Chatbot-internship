# Palm Hills Resident AI Assistant

A verified, multilingual (English / Arabic / Egyptian Franco-Arabic) assistant for
Palm Hills residents. It answers questions about community regulations, violations
and their **exact** penalties, facilities, and contacts — always from the verified
dataset, never from the model's own knowledge.

```
Flutter app (web / Windows)
      |
      v
FastAPI backend  ──▶  PostgreSQL + pgvector   (policies, violations, contacts,
      |                                        facilities, audit, tickets, reports)
      └──────────▶  LLM provider (Gemini | Claude | template)
```

**Authority order: verified data > retrieval > LLM phrasing.** The model rewrites
retrieved records into natural language; it is never the source of a fact.

---

## Repository layout

```
data/
  parts/                       hand-verified extraction, one file per entity
  build_dataset.py             assembles + validates the canonical dataset
  palm_hills_regulations_v1.0.json   generated — the source of truth for the backend
docs/source/                   the original regulations PDF
backend/                       FastAPI service
frontend/                      Flutter app (lib/core, lib/screens, lib/widgets)
db/init/                       Postgres extension bootstrap
docker-compose.yml             api + postgres(pgvector)
run.bat                        Windows launcher for the whole stack
```

---

## Step 1 — the dataset

Built directly from `docs/source/Community_Living_standards_regulations_and_penalties.pdf`
(27 pages: Arabic regulations + violations table on pp. 1–14, English on pp. 15–27).

```bash
python data/build_dataset.py
# categories=10 rules=117 violations=90 contacts=5 facilities=4
```

The build script is also a validator — it fails on duplicate IDs, non-integer
penalties, dangling `related_policy_ids`, or a masked placeholder phone number
that isn't `null`. Wire it into CI ahead of any ingestion.

**Provenance is recorded per field.** Every rule carries `src_en` / `src_ar`:

| value | meaning |
|---|---|
| `pdf` | the rule appears in that language in the source document |
| `derived` | that language was translated during data preparation because the source section is abridged in it |

12 of the 117 rules are `derived` (the English regulations section is shorter than
the Arabic one — e.g. Maintenance has 28 Arabic rules vs 20 English). Those 12
should get a human translation review before launch; `GET /api/v1/policies`
exposes the flags so reviewers can filter for them.

The **90 violations and their penalties are transcribed verbatim** from the source
tables, and the two language tables are row-aligned in the PDF, so each record
pairs the same row.

---

## Step 2 — the backend

### Run it (Windows)

`run.bat` drives the whole flow. With no argument it does setup → dataset →
database → ingest → serve:

```bat
run.bat            :: full first run
run.bat check      :: report what is installed / configured
run.bat setup      :: venv + dependencies + .env
run.bat dataset    :: rebuild and validate the dataset
run.bat db         :: start PostgreSQL and wait for it
run.bat ingest     :: load the dataset, build embeddings
run.bat serve      :: API on http://localhost:8000
run.bat test       :: run the test suite
run.bat app        :: Flutter web app in Chrome
run.bat android    :: Flutter app on an Android emulator
run.bat app-build  :: release web bundle into frontend/build/web
```

The backend serves no HTML of its own - `/` is a 404 by design and the only
browser page is `/docs`. The UI is the Flutter app, so run the API in one
terminal and `run.bat app` (or `android`) in another.

Set `GEMINI_API_KEY` in `.env` before serving. Without it the API still runs —
it just answers from the deterministic renderer instead of the model.

### Run it (other platforms)

```bash
cp .env.example .env          # then edit
docker compose up -d          # postgres + api
docker compose exec api python -m app.scripts.ingest
curl localhost:8000/health/ready
```

Interactive docs: `http://localhost:8000/docs`

### Running the app on Android

`run.bat android` boots the first available AVD, waits for
`sys.boot_completed`, then runs the app against it. It needs the Android SDK -
Android Studio's default location (`%LOCALAPPDATA%\Android\Sdk`) is found
automatically, otherwise set `ANDROID_HOME`.

Two Android-specific details, both already handled in the repo:

- **The API base URL is `http://10.0.2.2:8000`, not `localhost`.** Inside the
  emulator `localhost` is the emulator itself; `10.0.2.2` is its alias for the
  host machine's loopback. `run.bat android` passes it via `--dart-define`.
- **Cleartext HTTP is allowed for loopback hosts in debug builds only.**
  Android 9+ blocks plain HTTP by default, which would kill every request to
  the dev backend. `frontend/android/app/src/debug/res/xml/network_security_config.xml`
  permits it for `10.0.2.2`, `localhost` and `127.0.0.1` and nothing else, and
  it lives in the `debug` source set so release builds are unaffected.

For a physical device over USB, run `adb reverse tcp:8000 tcp:8000` and pass
`API_BASE_URL=http://localhost:8000` instead.

#### One toolchain quirk worth knowing

`cmdline-tools` **23.0** replaced `sdkmanager` with a new `android` CLI and made
`sdkmanager.bat` a thin deprecation shim. The shim breaks two things the Android
Gradle Plugin relies on:

- it splits `;`-separated package paths into separate arguments, so
  `sdkmanager "ndk;28.2.13676358"` becomes a lookup for `ndk` and for
  `28.2.13676358`, both of which fail;
- it then exits with `0xC0000409` (stack buffer overrun) rather than an error,
  so AGP reports only "finished with non-zero exit value".

The result is that AGP cannot auto-install the NDK, and `flutter build apk`
fails while configuring `:app`. The fix in place here: `cmdline-tools/latest`
holds the pre-deprecation **19.0** tools, which AGP drives correctly, and 23.0
is kept alongside at `cmdline-tools/23.0`. The new CLI's native downloader also
failed repeatedly on the larger archives (`java.io.IOException`, message
elided), so the classic `sdkmanager` did the system-image and NDK installs.

If a future Android Studio needs 23.0 as `latest`, swap the two directories
back and pre-install any package AGP would otherwise fetch itself.

### Running the database on Windows

The backend needs PostgreSQL with **pg_trgm** (bundled with PostgreSQL) and,
for semantic search, **pgvector**. pgvector publishes no Windows binaries, so
there are three routes:

| Route | pgvector | Admin needed | Retrieval |
|---|---|---|---|
| Container (`docker compose up -d postgres`) | yes, prebuilt | yes, to install the runtime | vector + trigram |
| Compile pgvector into an existing PostgreSQL | yes | yes (MSVC + superuser) | vector + trigram |
| Portable PostgreSQL + `VECTOR_ENABLED=false` | no | **no** | trigram only |

`run.bat db` picks a container runtime when one is installed and otherwise
starts the portable cluster.

**Portable route (what this machine uses).** A self-contained PostgreSQL 16.10
runs from `D:\PHD	ools\pgsql` with its data in `D:\PHD	ools\pgdata`, on
**port 5433** so it does not collide with an already-installed PostgreSQL on
5432. It listens on 127.0.0.1 only and uses scram-sha-256. Dev credentials:
role `palmhills` / `palmhills`, superuser `postgres` / `palmhills_dev_admin`.

With `VECTOR_ENABLED=false` the embedding column and HNSW index are never
created and retrieval ranks on trigram similarity alone. **This is materially
weaker than the vector path**, especially for Arabic and Franco queries — the
assistant answers exact-match questions well but falls back to "I could not
verify this" more often, which is the safe failure but not a helpful one. Use it
for development and the UI, not for judging retrieval quality.

**Compile route** — MSVC C++ build tools, then from an *x64 Native Tools Command
Prompt* as administrator:

```bat
set "PGROOT=C:\Program Files\PostgreSQL"
git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

Then `CREATE EXTENSION vector;` in the target database and set
`VECTOR_ENABLED=true`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/chat` | the assistant |
| POST | `/api/v1/chat/language` | diagnostic: what the detector and router saw |
| GET | `/api/v1/categories` `/policies` `/violations` `/violations/{id}` | regulation browsing (`as_of`, `compound`, `phase` filters) |
| GET | `/api/v1/contacts` `/facilities` `/facilities/{id}` | directories (placeholder-safe) |
| GET | `/api/v1/dataset` | what's loaded + what still needs real Palm Hills data |
| POST/GET/PATCH | `/api/v1/tickets` | human escalation |
| POST/GET | `/api/v1/reports`, `/reports/{id}/attachments` | resident violation reporting |
| GET | `/health`, `/health/ready` | liveness / readiness |

### How a question is answered

1. **Language detection** — `en` / `ar` / `franco` / `mixed`. Franco is matched on a
   **consonant skeleton** (`7abibi` → `hbb` ← `7abeby`), so spelling variation is
   tolerated by construction rather than by an exhaustive variant list.
2. **Intent routing** — contact questions go to the contacts directory, facility
   questions to the facilities directory, greetings get a canned reply. Only policy
   and fine questions enter retrieval. Not everything goes through RAG.
3. **Hybrid retrieval** — pgvector cosine + pg_trgm lexical + category agreement.
   Version, effective date, compound and phase are filtered **in SQL before
   ranking**, so an out-of-scope or superseded rule can't be ranked at all.
4. **Confidence** — top score, margin over the runner-up, intent/route agreement,
   topic signal, and a heavy penalty for deictic questions ("Is this allowed?").
5. **Answer** — the LLM rewrites the retrieved records. Then the **integrity guard**
   re-reads every number in the generated text and rejects the answer unless each
   one appears in the retrieved sources, falling back to a deterministic rendering
   of the same records. An invented fine is structurally unable to ship.
6. **Escalation** — low confidence never guesses: it opens a ticket and says so.
7. **Audit** — every answer is written to `audit_logs` with the record IDs,
   confidence, policy version, provider, and whether the guard fired.

### Placeholder safety

Contacts and facilities are placeholders until Palm Hills supplies real data.
Unconfigured fields are `null` with an explicit `availability: "not_configured"`
marker and a resident-facing message ("This number has not been configured in the
system yet."). `XXXXXXXXXX` is never loaded into the database and never returned;
the integrity guard rejects it as a second line of defence.

Facility hours are shown only when their origin can be named — `F002` (playground,
10:00–sunset) and `F004` (beach, 11:00 to 30 min before sunset) come from rules
P068 and P110, flagged via `hours_source`. `F003` (gym) has no hours and returns
`null` rather than a guess.

### Configuration

| Variable | Default | Notes |
|---|---|---|
| `VECTOR_ENABLED` | `true` | false drops the vector column/index and ranks on trigram alone (no pgvector needed) |
| `EMBEDDING_PROVIDER` | `hash` | `hash` (offline, deterministic, **lexical-ish**) / `gemini` / `local` / `voyage` |
| `LLM_PROVIDER` | `gemini` | `gemini` / `claude` / `template` (deterministic, no network) |
| `GEMINI_API_KEY` | *(unset)* | without it the assistant serves deterministic answers rather than failing |
| `LLM_MODEL` | *(per provider)* | unset → `gemini-2.5-flash` for Gemini, `claude-opus-5` for Claude |
| `LLM_THINKING_BUDGET` | `0` | `gemini-2.5-flash` thinks by default; disabled here (see below) |
| `LLM_TEMPERATURE` | `0.2` | low: the task is a grounded rewrite, not composition |
| `API_KEYS` | *(empty)* | comma-separated; empty disables auth — local development only |
| `RATE_LIMIT_PER_MINUTE` | `60` | in-process; see open items |

The LLM and embedding providers are configured **independently** — they need not
be the same vendor, and some LLM vendors serve no embeddings endpoint at all.
Setting `EMBEDDING_PROVIDER=gemini` reuses `GEMINI_API_KEY` and is the cheapest
way to replace the lexical-only default with real semantic retrieval.

Two Gemini-specific choices worth knowing:

- **Thinking is disabled** (`LLM_THINKING_BUDGET=0`). `gemini-2.5-flash` thinks by
  default, but this call only rephrases records the retriever already chose. Leaving
  thinking on risks the documented 2.5 failure mode where reasoning consumes
  `max_output_tokens` and the response returns empty with `finish_reason=MAX_TOKENS`.
- **`generateContent`, not the newer Interactions API.** Google documents
  generateContent as the recommended path for stable production deployments, and
  this call is single-turn with no tools or server-side state.

A blocked prompt, a safety-stopped candidate, an empty response and a transport
failure are all treated the same way: the provider declines and the deterministic
renderer answers instead. The assistant never surfaces a truncated half-answer.

### Tests

```bash
cd backend && ./.venv/Scripts/python -m pytest -q
```

70 logic tests (language detection, Franco variants, intent routing, integrity
guard, deterministic rendering in all three languages, provider selection and
degradation) run anywhere. 31 API tests
cover fine lookup, exact-penalty preservation against the dataset, facility and
contact lookup, placeholder protection, low-confidence escalation, compound/phase
filtering, effective-date filtering, audit logging, invalid requests, and
violation reporting; they **skip automatically** when PostgreSQL is unreachable.

---

## Step 3 — the Flutter frontend

```bat
run.bat app          :: run in Chrome against http://localhost:8000
run.bat app-build    :: release web bundle in frontend/build/web
```

Or directly: `cd frontend && flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000`.
The API base URL and key come from `--dart-define`, so nothing is baked into the
source.

Screens: Home, Assistant, Rules, Fines, Facilities, Contacts, Report a
Violation, My Requests — a navigation rail on wide layouts, a bottom bar plus
the Home grid on phones.

Three things the UI is deliberately strict about:

- **Answers are rendered verbatim.** The assistant screen prints the backend's
  `answer` string as-is. No client-side truncation, summarising or reformatting
  — that text already passed the integrity guard, and editing it here would put
  unverified wording on screen.
- **Placeholders stay visibly absent.** A contact with no configured number shows
  the backend's "not configured" notice and a *disabled* call button. There is no
  code path that renders `XXXXXXXXXX` or a stand-in number. Facility hours appear
  only when `hours_source` can name the rule they came from.
- **A report is not an accusation.** The AI's suggested violation is never shown
  to the reporting resident; the report stays `reported` until staff verify it,
  and the backend's disclaimer is displayed with the confirmation.

Franco-Arabic is a full UI language, not just a reply language — the interface,
placeholders and example prompts all switch with it. Arabic flips the whole app
to RTL via `Directionality`; Franco stays LTR because it is Latin script.

> Franco is not a real locale (no BCP-47 code, no `intl` support), so the strings
> live in a plain `S` class rather than ARB/`flutter_localizations`. Arabic still
> gets correct RTL.

`flutter test` covers penalty formatting (exact amounts, separators only),
placeholder safety, per-language text direction, and the low-confidence /
escalation flags.

---

## Status

**Done:** dataset (Step 1, rebuilt from the PDF), backend (Step 2) — schema,
ingestion, hybrid retrieval, language/intent layers, confidence and escalation,
audit logging, directories, ticketing, violation reporting, Docker Compose, tests
— and the Flutter frontend (Step 3), all eight screens in three languages.

**Verified locally:** the 70 backend logic tests, dataset build and validation,
application wiring and OpenAPI generation, a live Gemini call (a deliberately
invalid key returned HTTP 400 and degraded to a deterministic answer rather than
raising), and on the frontend `flutter analyze` clean, 6 tests passing and a
successful release web build.

**Verified against a live database:** all **114 tests pass with none skipped**,
including the 31 API tests, running against the portable PostgreSQL on port 5433.
The dataset ingests (117 policies, 90 violations) and the assistant answers
end-to-end in English, Arabic and Franco.

**Not verified:** the vector retrieval path — this machine has no pgvector, so
everything above ran in `trigram-only` mode. No Gemini key is configured either,
so answers currently come from the deterministic renderer rather than the model.

## Open items

1. **Real Palm Hills data** — security / maintenance / emergency / community
   management / beach office numbers, actual compound and phase names, facility
   locations and hours. Everything stays `not_configured` until supplied.
2. **Embeddings** — the default `hash` provider is deterministic and offline but
   its similarity is lexical, not semantic. Set `EMBEDDING_PROVIDER=gemini`
   (same key as the LLM) and re-ingest before judging retrieval quality.
3. **Translation review** — the 12 `derived` rules.
4. **Rate limiting** is per-process; move to Redis or the reverse proxy behind
   more than one replica.
5. **Attachment storage** — uploads are validated (type, size, magic bytes) and
   hashed, but the bytes are not persisted yet (`"storage": "not_persisted"`).
   Needs an object-storage decision, which follows the deployment decision.
6. **Auth** is a static API key. Resident identity (and therefore per-resident
   compound inference) needs the real Palm Hills identity provider.
7. **Migrations** — schema is created idempotently at boot. Introduce Alembic
   before the first production schema change.
8. **Frontend gaps** — auth/resident identity, offline caching, and push-free
   status refresh are not implemented. Evidence upload works end-to-end but the
   backend still discards the bytes (item 5).
9. **Semantic retrieval is off locally.** Trigram-only ranking misses queries
   that need meaning rather than shared characters — an Arabic "fine for parking
   on the grass" currently retrieves waste violations and escalates instead of
   answering. Installing pgvector (container or MSVC) and setting
   `VECTOR_ENABLED=true` plus `EMBEDDING_PROVIDER=gemini` is the fix, and is the
   highest-value next step for answer quality.

Push notifications are deliberately out of scope.
