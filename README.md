# Palm Hills Resident AI Assistant

A verified, multilingual (English / Arabic / Egyptian Franco-Arabic) assistant for
Palm Hills residents. It answers questions about community regulations, violations
and their **exact** penalties, facilities, and contacts — always from the verified
dataset, never from the model's own knowledge.

```
Flutter app (not built yet)
      |
      v
FastAPI backend  ──▶  PostgreSQL + pgvector   (policies, violations, contacts,
      |                                        facilities, audit, tickets, reports)
      └──────────▶  LLM provider (Claude | template)
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
db/init/                       Postgres extension bootstrap
docker-compose.yml             api + postgres(pgvector)
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

### Run it

```bash
cp .env.example .env          # then edit
docker compose up -d          # postgres + api
docker compose exec api python -m app.scripts.ingest
curl localhost:8000/health/ready
```

Without Docker:

```bash
cd backend
python -m venv .venv && ./.venv/Scripts/pip install -r requirements.txt
# point DATABASE_URL at any Postgres 16 with the vector + pg_trgm extensions
./.venv/Scripts/python -m app.scripts.ingest
./.venv/Scripts/python -m uvicorn app.main:app --reload
```

Interactive docs: `http://localhost:8000/docs`

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
| `EMBEDDING_PROVIDER` | `hash` | `hash` (offline, deterministic, **lexical-ish**) / `local` (sentence-transformers) / `voyage` |
| `LLM_PROVIDER` | `template` | `template` (deterministic, no network) / `claude` |
| `LLM_MODEL` | `claude-opus-5` | |
| `LLM_EFFORT` | `low` | thinking is on by default on this model; `LLM_MAX_TOKENS` covers thinking + text |
| `API_KEYS` | *(empty)* | comma-separated; empty disables auth — local development only |
| `RATE_LIMIT_PER_MINUTE` | `60` | in-process; see open items |

Anthropic serves no embeddings endpoint, which is why the LLM and embedding
providers are configured independently.

### Tests

```bash
cd backend && ./.venv/Scripts/python -m pytest -q
```

56 logic tests (language detection, Franco variants, intent routing, integrity
guard, deterministic rendering in all three languages) run anywhere. 31 API tests
cover fine lookup, exact-penalty preservation against the dataset, facility and
contact lookup, placeholder protection, low-confidence escalation, compound/phase
filtering, effective-date filtering, audit logging, invalid requests, and
violation reporting; they **skip automatically** when PostgreSQL is unreachable.

---

## Status

**Done:** dataset (Step 1, rebuilt from the PDF), backend (Step 2) — schema,
ingestion, hybrid retrieval, language/intent layers, confidence and escalation,
audit logging, directories, ticketing, violation reporting, Docker Compose, tests.

**Verified locally:** the 56 logic tests, dataset build and validation, application
wiring and OpenAPI generation.

**Not verified locally:** anything requiring PostgreSQL or the Anthropic API —
Docker is not installed on this machine and no API key is configured. The 31 API
tests exist and will run against a live database; they have not been executed yet.

## Open items

1. **Real Palm Hills data** — security / maintenance / emergency / community
   management / beach office numbers, actual compound and phase names, facility
   locations and hours. Everything stays `not_configured` until supplied.
2. **Embeddings** — the default `hash` provider is deterministic and offline but
   its similarity is lexical, not semantic. Set `EMBEDDING_PROVIDER=local` and
   re-ingest before judging retrieval quality.
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
8. **Flutter frontend** — not started; the backend contract above is what it will
   consume.

Push notifications are deliberately out of scope.
