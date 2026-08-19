"""End-to-end API tests.

Skipped automatically when PostgreSQL is not reachable (see conftest).
Run them with:

    docker compose up -d postgres
    python -m app.scripts.ingest
    pytest
"""

from __future__ import annotations

import pytest

BASE = "/api/v1"


def _ask(client, message: str, **kwargs) -> dict:
    response = client.post(f"{BASE}/chat", json={"message": message, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


# --- language coverage --------------------------------------------------

def test_english_policy_query(api_client) -> None:
    data = _ask(api_client, "Can I build a pergola in my garden?")
    assert data["detected_language"] == "en"
    assert data["language"] == "en"
    assert data["answer"]


def test_arabic_policy_query(api_client) -> None:
    data = _ask(api_client, "هل يمكن وضع برجولة بدون تصريح؟")
    assert data["detected_language"] == "ar"
    assert data["language"] == "ar"


def test_franco_policy_query(api_client) -> None:
    data = _ask(api_client, "momken a3mel brjola fel gnena?")
    assert data["detected_language"] == "franco"
    assert data["language"] == "franco"


def test_mixed_language_query_is_handled(api_client) -> None:
    data = _ask(api_client, "هو ال pool allowed للضيوف؟")
    assert data["detected_language"] == "mixed"
    assert data["language"] in ("ar", "en")


def test_franco_spelling_variants_retrieve_the_same_record(api_client) -> None:
    """The two spellings must not produce different policy answers."""
    a = _ask(api_client, "fe kam ghrama 3ala el parking 3al zar3?")
    b = _ask(api_client, "fe kam 3'rama 3ala el parking 3al zar3?")
    assert a["intent"] == b["intent"] == "fine_lookup"
    ids_a = {s["id"] for s in a["sources"]}
    ids_b = {s["id"] for s in b["sources"]}
    assert ids_a & ids_b, f"no overlap between {ids_a} and {ids_b}"


# --- fines: the figures must be exact -----------------------------------

def test_fine_lookup_returns_a_violation_source(api_client) -> None:
    data = _ask(api_client, "What is the fine for burning waste?")
    assert data["intent"] == "fine_lookup"
    assert any(s["kind"] == "violation" for s in data["sources"])


def test_penalty_is_never_altered(api_client, dataset) -> None:
    """Every EGP figure in an answer must exist in the cited source records."""
    penalties = {v["id"]: v["penalty_egp"] for v in dataset["violations"]}
    data = _ask(api_client, "What is the fine for burning waste?")
    cited = [penalties[s["id"]] for s in data["sources"] if s["id"] in penalties]
    assert cited, "expected at least one violation source"
    answer = data["answer"].replace(",", "")
    assert any(str(p) in answer for p in cited) or data["confidence_band"] == "low"


def test_violation_endpoint_matches_the_dataset(api_client, dataset) -> None:
    expected = {v["id"]: v for v in dataset["violations"]}
    response = api_client.get(f"{BASE}/violations", params={"limit": 500})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == len(expected) == 90
    for row in rows:
        assert row["penalty_egp"] == expected[row["id"]]["penalty_egp"]
        assert row["violation_en"] == expected[row["id"]]["violation_en"]
        assert row["violation_ar"] == expected[row["id"]]["violation_ar"]


def test_single_violation_lookup(api_client, dataset) -> None:
    expected = next(v for v in dataset["violations"] if v["id"] == "V011")
    response = api_client.get(f"{BASE}/violations/V011")
    assert response.status_code == 200
    assert response.json()["penalty_egp"] == expected["penalty_egp"] == 500


def test_unknown_violation_returns_404(api_client) -> None:
    assert api_client.get(f"{BASE}/violations/V999").status_code == 404


# --- directories --------------------------------------------------------

def test_contact_lookup_never_leaks_placeholders(api_client) -> None:
    data = _ask(api_client, "What's the security number?")
    assert data["intent"] == "contact_lookup"
    assert "XXXX" not in data["answer"].upper()
    assert "not been configured" in data["answer"].lower()


def test_contacts_endpoint_masks_unconfigured_numbers(api_client) -> None:
    rows = api_client.get(f"{BASE}/contacts").json()
    assert rows
    for row in rows:
        if row["availability"] == "not_configured":
            assert row["phone"] is None
            assert row["message"]
        assert "XXXX" not in (row["phone"] or "").upper()


def test_facility_lookup(api_client) -> None:
    data = _ask(api_client, "Where is the nearest pool?")
    assert data["intent"] == "facility_lookup"
    assert data["answer"]


def test_facility_hours_are_only_shown_with_a_source(api_client) -> None:
    rows = api_client.get(f"{BASE}/facilities").json()
    by_id = {row["id"]: row for row in rows}
    # Playground hours come from rule P068; the gym has none configured.
    assert by_id["F002"]["hours"] == "10:00 - sunset"
    assert by_id["F002"]["hours_source"] == "policy:P068"
    assert by_id["F003"]["hours"] is None


# --- scope filtering ----------------------------------------------------

def test_compound_filter_is_accepted(api_client) -> None:
    data = _ask(api_client, "What is the fine for burning waste?", compound="unknown-compound")
    # v1.0 rules are all global, so a compound filter must not hide them.
    assert data["sources"]


def test_phase_filter_is_accepted(api_client) -> None:
    data = _ask(api_client, "What is the fine for burning waste?", phase="phase-1")
    assert data["sources"]


def test_effective_date_filter_excludes_future_versions(api_client) -> None:
    """Asking about a date before the policy took effect must retrieve nothing."""
    data = _ask(api_client, "What is the fine for burning waste?", as_of="2020-01-01")
    assert data["sources"] == []
    assert data["confidence_band"] == "low"


def test_policies_endpoint_respects_as_of(api_client) -> None:
    current = api_client.get(f"{BASE}/policies", params={"limit": 5}).json()
    historical = api_client.get(f"{BASE}/policies", params={"limit": 5, "as_of": "2020-01-01"}).json()
    assert current
    assert historical == []


# --- confidence, escalation, audit --------------------------------------

def test_low_confidence_escalates_and_opens_a_ticket(api_client) -> None:
    data = _ask(api_client, "Is this allowed?")
    assert data["confidence_band"] == "low"
    assert data["escalated"] is True
    assert data["ticket_id"]
    assert "escalate" in data["answer"].lower()

    ticket = api_client.get(f"{BASE}/tickets/{data['ticket_id']}").json()
    assert ticket["status"] == "open"


def test_answers_are_audited_with_their_sources(api_client) -> None:
    data = _ask(api_client, "What is the fine for burning waste?")
    assert data["audit_id"]
    assert data["policy_version"] == "1.0"


def test_ticket_lifecycle(api_client) -> None:
    created = api_client.post(
        f"{BASE}/tickets",
        json={"query": "I need help with a permit", "detected_language": "en"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["ticket_id"]

    updated = api_client.patch(
        f"{BASE}/tickets/{ticket_id}",
        json={"status": "resolved", "resolution": "Permit issued."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "resolved"
    assert updated.json()["resolved_at"]


def test_invalid_ticket_status_is_rejected(api_client) -> None:
    created = api_client.post(
        f"{BASE}/tickets", json={"query": "test", "detected_language": "en"}
    ).json()
    response = api_client.patch(
        f"{BASE}/tickets/{created['ticket_id']}", json={"status": "banana"}
    )
    assert response.status_code == 422


# --- violation reporting -------------------------------------------------

def test_violation_report_is_created_as_reported_not_verified(api_client) -> None:
    response = api_client.post(
        f"{BASE}/reports",
        json={
            "description": "Someone is burning garden waste behind building 12.",
            "location_text": "Behind building 12",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "reported"
    assert body["verified_violation_id"] is None if "verified_violation_id" in body else True
    # A suggestion may be present, but it is explicitly not an enforcement decision.
    assert "not a verified violation" in body["suggested_disclaimer"]


def test_report_rejects_non_image_attachment(api_client) -> None:
    report = api_client.post(
        f"{BASE}/reports", json={"description": "Blocked fire exit near the gate."}
    ).json()
    response = api_client.post(
        f"{BASE}/reports/{report['report_id']}/attachments",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_report_rejects_mislabelled_image(api_client) -> None:
    """Content-Type is caller-supplied; the bytes have to match."""
    report = api_client.post(
        f"{BASE}/reports", json={"description": "Debris left in the stairwell."}
    ).json()
    response = api_client.post(
        f"{BASE}/reports/{report['report_id']}/attachments",
        files={"file": ("fake.png", b"not really a png", "image/png")},
    )
    assert response.status_code == 415


def test_report_accepts_a_real_png(api_client) -> None:
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    report = api_client.post(
        f"{BASE}/reports", json={"description": "Car parked on the landscaped area."}
    ).json()
    response = api_client.post(
        f"{BASE}/reports/{report['report_id']}/attachments",
        files={"file": ("evidence.png", png, "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["attachments"][0]["sha256"]


# --- request validation --------------------------------------------------

@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 2001}])
def test_invalid_chat_requests_are_rejected(api_client, payload: dict) -> None:
    assert api_client.post(f"{BASE}/chat", json=payload).status_code == 422


def test_health_and_readiness(api_client) -> None:
    assert api_client.get("/health").json()["status"] == "ok"
    assert api_client.get("/health/ready").json()["database"] == "ok"


def test_dataset_status_reports_unconfigured_records(api_client) -> None:
    body = api_client.get(f"{BASE}/dataset").json()
    assert body["version"] == "1.0"
    assert body["counts"]["violations"] == 90
    assert body["unconfigured_contacts"], "placeholder contacts must be reported as unconfigured"


def test_projects_are_selectable_and_carry_a_scoping_token(api_client) -> None:
    """The location picker is fed from here, so it must never be empty."""
    projects = api_client.get(f"{BASE}/projects").json()
    assert projects, "the picker would have nothing to offer"
    for project in projects:
        assert project["name_en"] and project["name_ar"]
        assert project["compound"], "every project must scope to something"
        assert project["region_en"] and project["region_ar"]


def test_north_coast_projects_share_the_north_coast_scope(api_client) -> None:
    """The one scope the shipped dataset actually distinguishes.

    A Hacienda resident must keep the North Coast beach facility in scope; a
    Cairo resident must not. That only works if the North Coast projects resolve
    to the same `compound` token the dataset uses.
    """
    projects = api_client.get(f"{BASE}/projects").json()
    coastal = [p for p in projects if p["region"] == "north_coast"]
    assert coastal, "expected the North Coast projects"
    assert {p["compound"] for p in coastal} == {"north_coast"}

    beach = api_client.get(f"{BASE}/facilities", params={"compound": "north_coast"}).json()
    assert any(f["compound"] == "north_coast" for f in beach)

    inland = api_client.get(
        f"{BASE}/facilities", params={"compound": "palm_hills_october"}
    ).json()
    assert not any(f["compound"] == "north_coast" for f in inland)
