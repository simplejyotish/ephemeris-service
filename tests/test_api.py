import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from ephemeris_service.main import DEFAULT_SOURCE_URL, create_app

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
    assert set(res[0]["Sun"]) == {"longitude", "speed", "latitude"}
    assert 0 <= res[0]["Sun"]["longitude"] < 360


def test_unknown_planet_422(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [JD], "planets": ["Chiron"], "ayanamsha": "lahiri"})
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
    assert body["service_version"] == "0.2.0"
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


def test_rise_set_body_and_hindu_rising(client):
    base = {"jd_start": 2461114.5, "lat": 28.6139, "lon": 77.2090}
    r = client.post("/v1/rise-set", headers=H, json={**base, "event": "sunrise", "hindu_rising": True})
    assert abs(r.json()["jd"] - 2461114.5451218807) < 1e-9
    r = client.post("/v1/rise-set", headers=H, json={**base, "event": "sunrise", "body": "Moon"})
    assert abs(r.json()["jd"] - 2461115.4703247305) < 1e-9
    r = client.post("/v1/rise-set", headers=H, json={**base, "event": "sunrise", "body": "Mars"})
    assert r.status_code == 422


def test_swe_error_is_422_with_message(client):
    r = client.post("/v1/rise-set", headers=H, json={
        "jd_start": 1.5, "lat": 28.6, "lon": 77.2, "event": "sunrise"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("swisseph.")


@pytest.mark.parametrize("env", ["dev", "development", "test", " DEV "])
def test_no_key_configured_skips_auth_in_dev(monkeypatch, env):
    monkeypatch.delenv("EPHEMERIS_API_KEY", raising=False)
    monkeypatch.setenv("ENV", env)
    with TestClient(create_app()) as c:
        r = c.post("/v1/ayanamsha", json={"jd": JD, "ayanamsha": "lahiri"})
        assert r.status_code == 200


def test_unset_env_without_key_refuses_to_start(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("EPHEMERIS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="EPHEMERIS_API_KEY"):
        create_app()


@pytest.mark.parametrize("env", ["staging", " production ", "", "prod"])
def test_non_dev_env_without_key_refuses_to_start(monkeypatch, env):
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv("SOURCE_URL", "https://example.org/src")
    monkeypatch.delenv("EPHEMERIS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="EPHEMERIS_API_KEY"):
        create_app()


@pytest.mark.parametrize("source_url", [None, "", "https://example.invalid/set-SOURCE_URL",
                                        "https://example.invalid/src"])
def test_production_requires_real_source_url(monkeypatch, source_url):
    monkeypatch.setenv("ENV", " Production ")
    monkeypatch.setenv("EPHEMERIS_API_KEY", KEY)
    if source_url is None:
        monkeypatch.delenv("SOURCE_URL", raising=False)
    else:
        monkeypatch.setenv("SOURCE_URL", source_url)
    with pytest.raises(RuntimeError, match="SOURCE_URL"):
        create_app()


def test_dev_keeps_placeholder_source_url(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("EPHEMERIS_API_KEY", KEY)
    monkeypatch.delenv("SOURCE_URL", raising=False)
    with TestClient(create_app()) as c:
        assert c.get("/version", headers=H).json()["source_url"] == DEFAULT_SOURCE_URL


def test_module_import_does_not_build_app():
    # The ASGI app is built lazily on first access of ``main.app`` so that importing
    # the module (e.g. in tests) does not depend on the process environment.
    env = {k: v for k, v in os.environ.items()
           if k not in ("ENV", "EPHEMERIS_API_KEY", "SOURCE_URL")}
    code = ("import ephemeris_service.main as m\n"
            "try:\n    m.app\nexcept RuntimeError as e:\n    print('refused:', e)\n")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                         text=True, check=True).stdout
    assert out.startswith("refused:") and "EPHEMERIS_API_KEY" in out


def test_production_without_key_refuses_to_start(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("EPHEMERIS_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


@pytest.mark.parametrize("env", ["production", " production ", "PROD"])
def test_production_disables_docs(monkeypatch, env):
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv("EPHEMERIS_API_KEY", KEY)
    monkeypatch.setenv("SOURCE_URL", "https://github.com/example/ephemeris-service")
    with TestClient(create_app()) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404


def test_unknown_frame_422(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [JD], "planets": ["Sun"], "ayanamsha": "lahiri", "frame": "galactic"})
    assert r.status_code == 422


def test_existing_response_fields_unchanged(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [2451545.0], "planets": ["Sun"], "ayanamsha": "lahiri"})
    sun = r.json()["results"][0]["Sun"]
    assert set(sun) == {"longitude", "speed", "latitude"}  # old keys + additive latitude
    assert abs(sun["longitude"] - 256.51569718931427) < 1e-6
    assert abs(sun["speed"] - 1.0193918758618497) < 1e-6


def test_frame_and_new_names_over_http(client):
    r = client.post("/v1/positions", headers=H, json={
        "jds": [2451545.0], "planets": ["Pluto", "Sun"], "ayanamsha": "fagan", "frame": "tropical"})
    assert r.status_code == 200
    assert abs(r.json()["results"][0]["Sun"]["longitude"] - 280.36891967534336) < 1e-9
    for name in ("pushya", "raman", "fagan", "tropical"):
        assert client.post("/v1/ayanamsha", headers=H,
                           json={"jd": JD, "ayanamsha": name}).status_code == 200


def test_houses_system_field(client):
    base = {"jd": 2447753.5, "lat": 28.6139, "lon": 77.2090, "ayanamsha": "tropical"}
    default = client.post("/v1/houses", headers=H, json=base).json()
    equal = client.post("/v1/houses", headers=H, json={**base, "system": "equal"})
    assert equal.status_code == 200
    body = equal.json()
    assert abs(body["cusps"][1] - 166.98422935680756) < 1e-9
    assert body["ascendant"] == default["ascendant"]
    assert abs(default["cusps"][1] - 161.78541038039478) < 1e-9


def test_unknown_system_422(client):
    r = client.post("/v1/houses", headers=H, json={
        "jd": JD, "lat": 28.6, "lon": 77.2, "ayanamsha": "lahiri", "system": "whole_sign"})
    assert r.status_code == 422


@pytest.mark.parametrize("system", ["koch", "equal"])
def test_houses_polar_latitude_422(client, system):
    r = client.post("/v1/houses", headers=H, json={
        "jd": 2447753.5, "lat": 80, "lon": 77.2, "ayanamsha": "lahiri", "system": system})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and "swisseph.houses_ex" in r.json()["detail"]


def test_houses_omitted_system_equals_placidus(client):
    base = {"jd": 2447753.5, "lat": 28.6139, "lon": 77.2090, "ayanamsha": "lahiri"}
    a = client.post("/v1/houses", headers=H, json=base)
    b = client.post("/v1/houses", headers=H, json={**base, "system": "placidus"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
