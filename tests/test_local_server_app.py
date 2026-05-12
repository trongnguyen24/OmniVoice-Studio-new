import os

os.environ.setdefault("OMNIVOICE_DISABLE_FILE_LOG", "1")
os.environ.setdefault("OMNIVOICE_MODEL", "test")


def test_local_server_core_routes():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        system = client.get("/system/info")
        assert system.status_code == 200
        assert "data_dir" in system.json()

        status = client.get("/model/status")
        assert status.status_code == 200
        assert "status" in status.json()


def test_extension_engine_routes():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        engines = client.get("/api/ext/engines")
        assert engines.status_code == 200
        body = engines.json()
        ids = {engine["id"] for engine in body["engines"]}
        assert {"omnivoice", "kokoro", "gwen"}.issubset(ids)
        assert body["default_engine"] in ids

        unknown = client.post("/api/ext/engines/select", json={"engine": "missing"})
        assert unknown.status_code == 404

        placeholder = client.post("/api/ext/engines/kokoro/preload")
        assert placeholder.status_code == 501
