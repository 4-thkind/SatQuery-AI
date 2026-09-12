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

    print("\n8b. Testing PNG/RGB upload path...")
    # _ingest_rgb_image is a separate branch from the GeoTIFF path: it
    # synthesises a 4-band stack from RGB and labels the scene
    # "Aerial / Optical Photo (RGB+NIR)". Untested, it leaked a permanent
    # scene into the sidebar every time someone tried a PNG.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (34, 90, 60)).save(buf, format="PNG")
    buf.seek(0)
    rgb = client.post(
        "/api/v1/scenes/upload",
        files={"file": ("aerial_test.png", buf, "image/png")},
    )
    assert rgb.status_code == 200, rgb.text
    rgb_sid = rgb.json()["scene"]["id"]
    print(f"   Registered {rgb_sid} from PNG")

    rgb_listed = [s["id"] for s in client.get("/api/v1/scenes").json()["scenes"]]
    assert rgb_sid in rgb_listed, "PNG scene not listed"

    rgb_gone = client.delete(f"/api/v1/scenes/{rgb_sid}")
    assert rgb_gone.status_code == 200, rgb_gone.text
    rgb_after = [s["id"] for s in client.get("/api/v1/scenes").json()["scenes"]]
    assert rgb_sid not in rgb_after, f"{rgb_sid} survived delete"
    print(f"   Removed {rgb_sid}; PNG path leaves nothing behind.")

    print("\n9. Cleaning up the uploaded test scene...")
    # Without this the test leaves a permanent phantom scene in the
    # sidebar: every run registered a "Custom Field Survey Flood" card
    # that outlived it, because the manifest is durable state and nothing
    # removed the row. remove_uploaded_scene drops the manifest entry, the
    # .tif and both previews, so a run leaves the tree as it found it.
    gone = client.delete(f"/api/v1/scenes/{sid}")
    assert gone.status_code == 200, gone.text
    listed = [s["id"] for s in client.get("/api/v1/scenes").json()["scenes"]]
    assert sid not in listed, f"{sid} still listed after delete"
    print(f"   Removed {sid}; sidebar back to {len(listed)} bundled scenes.")

    print("\n==========================================")
    print("ALL UPLOAD INTEGRATION TESTS PASSED (100%)")
    print("==========================================")

if __name__ == "__main__":
    main()
