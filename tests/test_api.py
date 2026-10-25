import pytest
from fastapi.testclient import TestClient

from ephemeris_service.main import create_app

KEY = "secret-key"
H = {"X-Internal-Key": KEY}
JD = 2460000.5


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("EPHEMERIS_API_KEY", KEY)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("SOURCE_URL", "https://example.org/src")
    with TestClient(create_app()) as c:
        yield c


def test_health_needs_no_key(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_missing_key_401(client):
    assert client.post("/v1/ayanamsha", json={"jd": JD, "ayanamsha": "lahiri"}).status_code == 401


def test_wrong_key_401(client):
    r = client.post("/v1/ayanamsha", json={"jd": JD, "ayanamsha": "lahiri"},
                    headers={"X-Internal-Key": "nope"})
    assert r.status_code == 401


def test_positions_ok(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [JD, JD + 1], "planets": ["Sun", "Moon"], "ayanamsha": "lahiri"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert len(res) == 2
    assert set(res[0]) == {"Sun", "Moon"}
    assert set(res[0]["Sun"]) == {"longitude", "speed"}
    assert 0 <= res[0]["Sun"]["longitude"] < 360


def test_unknown_planet_422(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [JD], "planets": ["Pluto"], "ayanamsha": "lahiri"})
    assert r.status_code == 422


def test_unknown_ayanamsha_422(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [JD], "planets": ["Sun"], "ayanamsha": "bogus"})
    assert r.status_code == 422


def test_positions_over_2000_422(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [JD] * 2001, "planets": ["Sun"], "ayanamsha": "lahiri"})
    assert r.status_code == 422


def test_version_has_source_url(client):
    r = client.get("/version", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["source_url"] == "https://example.org/src"
    assert body["service_version"] == "0.1.0"
    assert body["swe_version"] and body["ephemeris_mode"] in ("moshier", "swieph")


def test_ayanamsha_houses_ok(client):
    r = client.post("/v1/ayanamsha", headers=H, json={"jd": JD, "ayanamsha": "krishnamurti"})
    assert r.status_code == 200 and isinstance(r.json()["value"], float)
    r = client.post("/v1/houses", headers=H, json={
        "jd": JD, "lat": 28.6, "lon": 77.2, "ayanamsha": "lahiri"})
    body = r.json()
    assert r.status_code == 200 and len(body["cusps"]) == 12
    assert {"ascendant", "midheaven"} <= set(body)


def test_rise_set_and_eclipse_ok(client):
    r = client.post("/v1/rise-set", headers=H, json={
        "jd_start": JD, "lat": 28.6, "lon": 77.2, "event": "sunrise"})
    assert r.status_code == 200 and r.json()["jd"] > JD
    r = client.post("/v1/eclipses", headers=H, json={"jd_start": JD, "kind": "solar"})
    assert r.status_code == 200 and r.json()["eclipse_type"] in (
        "total", "hybrid", "annular", "partial")
    assert client.post("/v1/eclipses", headers=H,
                       json={"jd_start": JD, "kind": "x"}).status_code == 422


def test_swe_error_is_422_with_message(client):
    r = client.post("/v1/rise-set", headers=H, json={
        "jd_start": 1.5, "lat": 28.6, "lon": 77.2, "event": "sunrise"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("swisseph.")


def test_no_key_configured_skips_auth_in_dev(monkeypatch):
    monkeypatch.delenv("EPHEMERIS_API_KEY", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    with TestClient(create_app()) as c:
        r = c.post("/v1/ayanamsha", json={"jd": JD, "ayanamsha": "lahiri"})
        assert r.status_code == 200


def test_production_without_key_refuses_to_start(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("EPHEMERIS_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


def test_production_disables_docs(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("EPHEMERIS_API_KEY", KEY)
    with TestClient(create_app()) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
