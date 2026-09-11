"""End-to-end test for custom GeoTIFF upload, preview, query, and mask rendering."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app import app
from backend.core.uploader import load_uploaded_manifest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAMPLE_TIF = ROOT / "data" / "demo" / "bihar_post_flood.tif"

def main():
    client = TestClient(app)
    print("1. Testing health check...")
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok", h
    initial_scenes = client.get("/api/v1/scenes").json()["scenes"]
    print(f"   Initial scene count: {len(initial_scenes)}")

    print("\n2. Testing POST /api/v1/scenes/upload with sample GeoTIFF...")
    with open(SAMPLE_TIF, "rb") as f:
        res = client.post(
            "/api/v1/scenes/upload",
            files={"file": ("custom_field_survey.tif", f, "image/tiff")},
            data={"label": "Custom Field Survey Flood", "sensor": "Sentinel-2 L2A (field)"},
        )
    assert res.status_code == 200, res.text
    scene = res.json()["scene"]
    sid = scene["id"]
    print(f"   Uploaded successfully! ID: {sid}")
    print(f"   Resolution: {scene['pixel_area_m2']} m2/px, Bands: {scene['bands']}")
    print(f"   Preview False: {scene['preview_false']}")
    print(f"   Preview Natural: {scene['preview_natural']}")

    print("\n3. Testing GET /api/v1/scenes to verify dynamic registration...")
    all_scenes = client.get("/api/v1/scenes").json()["scenes"]
    found = next((s for s in all_scenes if s["id"] == sid), None)
    assert found is not None, f"Uploaded scene {sid} not in /scenes response!"
    print(f"   Found uploaded scene in scene list. Total scenes: {len(all_scenes)}")

    print("\n4. Testing GET /api/v1/scenes/{scene_id}...")
    detail = client.get(f"/api/v1/scenes/{sid}").json()
    assert "bandstack" in detail, detail
    print(f"   Bandstack verified: {detail['bandstack']['bands']} bands")

    print("\n5. Testing POST /api/v1/query (Kernel Measurement) on uploaded scene...")
    qr = client.post(
        "/api/v1/query",
        json={"query": "How much area is flooded in this image?", "scene_id": sid},
    ).json()
    assert qr["verdict"] == "ANSWER", qr
    assert qr["headline"] and qr["headline"]["value"] > 0
    print(f"   Verdict: {qr['verdict']}")
    print(f"   Measured Flood Area: {qr['headline']['value']} {qr['headline']['unit']}")
    print(f"   Evidence rows: {len(qr['evidence'])}")

    print("\n6. Testing POST /api/v1/query (RAG Methodology) on uploaded scene...")
    rag_res = client.post(
        "/api/v1/query",
        json={"query": "how does masking done", "scene_id": sid},
    ).json()
    assert rag_res["verdict"] == "ANSWER", rag_res
    assert rag_res["intent"] == "method_explain"
    assert len(rag_res["citations"]) > 0
    print(f"   Verdict: {rag_res['verdict']} | Intent: {rag_res['intent']}")
    print(f"   Citations: {len(rag_res['citations'])} | Top: {rag_res['citations'][0]['title']}")

    print("\n7. Testing GET /api/v1/scenes/{scene_id}/mask.png on uploaded scene...")
    png = client.get(f"/api/v1/scenes/{sid}/mask.png?intent=flood_extent")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    print(f"   Mask PNG rendered successfully ({len(png.content)} bytes)")

    print("\n8. Testing invalid file extension rejection...")
    bad_res = client.post(
        "/api/v1/scenes/upload",
        files={"file": ("fake_file.txt", b"not a geotiff", "text/plain")},
    )
    assert bad_res.status_code == 400
    print("   Rejected non-geotiff with HTTP 400 as expected.")

    print("\n==========================================")
    print("ALL UPLOAD INTEGRATION TESTS PASSED (100%)")
    print("==========================================")

if __name__ == "__main__":
    main()
