"""Integration test for Genesis Inference API."""

from genesis_ai.main import GenesisAI
from genesis_ai.ui.app import create_app

def test_integration():
    genesis = GenesisAI()
    genesis.db.init_db()
    print("[OK] Genesis initialized")

    app = create_app(genesis)
    print("[OK] App created with Inference API")

    with app.test_client() as client:
        resp = client.get("/v1/health")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["status"] in ("healthy", "degraded")
        print("[OK] Health: " + data["status"])

        resp = client.get("/v1/models")
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) >= 1
        print("[OK] Models: " + str(len(data["data"])) + " model(s)")

        resp = client.post("/v1/chat", json={"message": "hello"})
        assert resp.status_code == 401
        print("[OK] Chat without auth: 401")

        resp = client.get("/v1/status")
        assert resp.status_code == 401
        print("[OK] Status without auth: 401")

        resp = client.get("/api/status")
        assert resp.status_code == 200
        print("[OK] UI /api/status still works: 200")

    print()
    print("ALL INTEGRATION TESTS PASSED")

if __name__ == "__main__":
    test_integration()
