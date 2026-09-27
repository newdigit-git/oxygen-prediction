from datetime import datetime, timedelta, timezone


def telemetry_payload(**overrides):
    payload = {
        "id": "DEVICE-001",
        "t": 1778918224,
        "b": 94,
        "p": 142.3,
        "f": 12.5,
        "c": -72,
        "l": "6.46667N, 3.63333E",
    }
    payload.update(overrides)
    return payload


def test_health_and_readiness(client):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").json()["status"] == "ready"


def test_telemetry_requires_device_key(client):
    response = client.post("/api/v1/telemetry", json=telemetry_payload())
    assert response.status_code == 401


def test_telemetry_ingest_and_history(client, device_headers):
    response = client.post(
        "/api/v1/telemetry",
        headers=device_headers,
        json=telemetry_payload(),
    )
    assert response.status_code == 201, response.text
    assert response.json()["device_id"] == "DEVICE-001"

    history = client.get(
        "/api/v1/telemetry/device/DEVICE-001?limit=10",
        headers=device_headers,
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert "X-Request-ID" in history.headers


def test_telemetry_rejects_invalid_values(client, device_headers):
    response = client.post(
        "/api/v1/telemetry",
        headers=device_headers,
        json=telemetry_payload(b=101),
    )
    assert response.status_code == 422


def test_session_ingest_is_idempotent(client, device_headers):
    payload = {
        "id": "DEVICE-001",
        "sid": "SESSION-001",
        "lc": "6.46667N, 3.63333E",
        "t_start": datetime.now(timezone.utc).isoformat(),
        "t_end": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "i_p": 200.0,
        "f_p": 150.0,
        "f_r": 5.0,
        "fb_pct": 90,
        "hf_log": 0,
        "c_st": -70,
    }
    first = client.post("/api/v1/sessions", headers=device_headers, json=payload)
    second = client.post("/api/v1/sessions", headers=device_headers, json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["sid"] == second.json()["sid"]
