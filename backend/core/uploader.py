"""GeoTIFF, PNG, and JPG upload, validation, metadata extraction, preview generation, and scene registration."""

from __future__ import annotations

import io
import json
import pathlib
import re
import shutil
import time
from typing import BinaryIO

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from PIL import Image

from .bandstack import normalise_role, BAND_ORDERINGS

ROOT = pathlib.Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "data" / "uploads"
PREVIEWS_DIR = UPLOAD_DIR / "previews"
MANIFEST_PATH = UPLOAD_DIR / "uploaded_manifest.json"


def init_upload_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_id(filename: str) -> str:
    base = pathlib.Path(filename).stem
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", base).strip("_").lower()
    if not cleaned:
        cleaned = "uploaded_scene"
    timestamp = int(time.time())
    return f"{cleaned}_{timestamp % 1000000}"


def _stretch_channel(ch: np.ndarray) -> np.ndarray:
    valid = ch[np.isfinite(ch)]
    if len(valid) == 0:
        return np.zeros(ch.shape, dtype=np.uint8)
    p2, p98 = np.percentile(valid, (2, 98))
    if p98 > p2:
        norm = np.clip((ch - p2) / (p98 - p2), 0.0, 1.0)
    else:
        norm = np.zeros(ch.shape, dtype=np.float32)
    norm = np.power(norm, 0.85)
    return (norm * 255).astype(np.uint8)


def _render_preview(data: np.ndarray, band_indices: tuple[int, int, int], out_path: pathlib.Path) -> None:
    h, w = data.shape[1], data.shape[2]
    r_idx, g_idx, b_idx = band_indices
    r = _stretch_channel(data[r_idx])
    g = _stretch_channel(data[g_idx])
    b = _stretch_channel(data[b_idx])
    rgb = np.stack([r, g, b], axis=-1)
    img = Image.fromarray(rgb, mode="RGB")
    if max(h, w) > 1024:
        ratio = 1024.0 / max(h, w)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.BILINEAR)
    img.save(out_path, format="PNG", optimize=True)


def _ingest_rgb_image(file_obj: BinaryIO, filename: str,
                      label: str | None = None,
                      sensor: str | None = None) -> dict:
    """Ingest standard RGB raster (PNG, JPG, JPEG) and synthesize 4-band GeoTIFF."""
    init_upload_dirs()
    scene_id = _sanitize_id(filename)
    target_tif = UPLOAD_DIR / f"{scene_id}.tif"

    # Open image with PIL
    pil_img = Image.open(file_obj).convert("RGB")
    rgb_arr = np.array(pil_img)
    height, width, _ = rgb_arr.shape

    r = rgb_arr[:, :, 0].astype(np.float32)
    g = rgb_arr[:, :, 1].astype(np.float32)
    b = rgb_arr[:, :, 2].astype(np.float32)

    # Spectral pseudo-NIR synthesis:
    # Water has very low NIR absorption; vegetation has high NIR reflectance.
    is_water = (b >= r) & (g >= r) & ((r + g + b) < 220)
    is_veg = (g > r) & (g > b)

    nir = np.where(
        is_water,
        np.clip(0.25 * g, 0, 255),
        np.where(
            is_veg,
            np.clip(1.45 * g - 0.25 * r, 0, 255),
            np.clip(0.6 * r + 0.4 * g, 0, 255)
        )
    ).astype(np.float32)

    data_4band = np.stack([r, g, b, nir], axis=0)
    roles = ["RED", "GREEN", "BLUE", "NIR"]

    # Write as standardized GeoTIFF
    # Default 10m GSD (Sentinel-2 baseline)
    gsd_m = 10.0
    pixel_area_m2 = gsd_m * gsd_m
    crs_str = "EPSG:32645"
    transform = (gsd_m, 0.0, 86.85, 0.0, -gsd_m, 26.05)
    wgs84_bounds = [86.85, 26.05 - (height * gsd_m) / 111000.0,
                    86.85 + (width * gsd_m) / 100000.0, 26.05]

    with rasterio.open(
        target_tif,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=4,
        dtype=rasterio.uint8,
        crs=crs_str,
        transform=rasterio.transform.Affine(transform[0], transform[1], transform[2],
                                            transform[3], transform[4], transform[5]),
    ) as dst:
        for i in range(4):
            dst.write(data_4band[i].astype(np.uint8), i + 1)
        dst.update_tags(
            SATQUERY_BANDS="RED,GREEN,BLUE,NIR",
            SATQUERY_SCALE="255.0",
            SATQUERY_SOURCE="Standard RGB Image"
        )

    false_path = PREVIEWS_DIR / f"{scene_id}_false.png"
    nat_path = PREVIEWS_DIR / f"{scene_id}_natural.png"

    # Natural color: RED, GREEN, BLUE
    _render_preview(data_4band, (0, 1, 2), nat_path)
    # False color CIR: NIR, RED, GREEN
    _render_preview(data_4band, (3, 0, 1), false_path)

    display_label = label or pathlib.Path(filename).stem.replace("_", " ").title()
    sensor_display = sensor or "Aerial / Optical Photo (RGB+NIR)"

    entry = {
        "id": scene_id,
        "label": display_label,
        "sensor": sensor_display,
        "acquired": time.strftime("%Y-%m-%d"),
        "place": "Custom Uploaded Scene",
        "cloud_hint": 0.0,
        "pair": None,
        "path": str(target_tif.relative_to(ROOT)).replace("\\", "/"),
        "preview_false": str(false_path.relative_to(ROOT)).replace("\\", "/"),
        "preview_natural": str(nat_path.relative_to(ROOT)).replace("\\", "/"),
        "width": width,
        "height": height,
        "crs": crs_str,
        "transform": list(transform),
        "bands": [r.lower() for r in roles],
        "dtype": "uint8",
        "scale_factor": 255.0,
        "nodata": 0.0,
        "pixel_area_m2": pixel_area_m2,
        "bounds_wgs84": wgs84_bounds,
        "synthetic": False,
        "description": f"Custom uploaded image ({width}x{height}, bands: {', '.join(roles)}).",
        "ground_truth": {},
    }

    manifest_data = load_uploaded_manifest()
    manifest_data[scene_id] = entry
    save_uploaded_manifest(manifest_data)
    return entry


def ingest_upload(file_obj: BinaryIO, filename: str,
                  label: str | None = None,
                  sensor: str | None = None) -> dict:
    """Validate, save, extract metadata, generate previews, and register an uploaded image (GeoTIFF, PNG, JPG)."""
    ext = pathlib.Path(filename).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg"):
        return _ingest_rgb_image(file_obj, filename, label=label, sensor=sensor)

    init_upload_dirs()
    scene_id = _sanitize_id(filename)
    target_tif = UPLOAD_DIR / f"{scene_id}.tif"

    with target_tif.open("wb") as dst:
        shutil.copyfileobj(file_obj, dst)

    try:
        with rasterio.open(target_tif) as src:
            num_bands = src.count
            width = src.width
            height = src.height
            crs_str = str(src.crs) if src.crs else "EPSG:32645"
            transform = tuple(src.transform)[:6] if src.transform else (10.0, 0.0, 0.0, 0.0, -10.0, 0.0)
            dtypes = list(src.dtypes)
            descriptions = list(src.descriptions or [])
            tags = src.tags()
            bounds = src.bounds
            data = src.read().astype(np.float32)

            if src.crs:
                try:
                    wgs84_bounds = list(transform_bounds(src.crs, "EPSG:4326", *bounds))
                except Exception:
                    wgs84_bounds = [86.80, 25.90, 87.10, 26.20]
            else:
                wgs84_bounds = [86.80, 25.90, 87.10, 26.20]

    except Exception as e:
        if target_tif.exists():
            target_tif.unlink()
        raise ValueError(f"Invalid GeoTIFF format: {e}")

    # Determine band roles
    roles: list[str] = []
    tagged = tags.get("SATQUERY_BANDS")
    if tagged:
        roles = [normalise_role(b) for b in tagged.split(",") if normalise_role(b)]
    elif any(descriptions):
        roles = [normalise_role(d) for d in descriptions if normalise_role(d)]

    if len(roles) != num_bands:
        if sensor and sensor in BAND_ORDERINGS:
            roles = list(BAND_ORDERINGS[sensor])
        elif num_bands == 4:
            roles = ["GREEN", "RED", "NIR", "SWIR1"]
        elif num_bands == 3:
            roles = ["RED", "GREEN", "BLUE"]
        elif num_bands == 2:
            roles = ["VV", "VH"]
        elif num_bands >= 12:
            roles = ["COASTAL", "BLUE", "GREEN", "RED", "REDEDGE1", "REDEDGE2", "REDEDGE3", "NIR", "NIR08", "WATERVAPOUR", "SWIR1", "SWIR2"]
        else:
            roles = [f"BAND_{i+1}" for i in range(num_bands)]

    # Update GeoTIFF tags with SATQUERY_BANDS so load_geotiff recognizes them
    with rasterio.open(target_tif, "r+") as dst:
        dst.update_tags(SATQUERY_BANDS=",".join(roles))
        if "scale_factor" not in tags:
            scale = 10000.0 if dtypes[0].startswith("uint16") else 1.0
            dst.update_tags(SATQUERY_SCALE=str(scale))

    pixel_area_m2 = abs(transform[0] * transform[4]) if transform else 100.0

    false_path = PREVIEWS_DIR / f"{scene_id}_false.png"
    nat_path = PREVIEWS_DIR / f"{scene_id}_natural.png"

    roles_upper = [r.upper() for r in roles]
    role_to_idx = {r: i for i, r in enumerate(roles_upper)}

    if "NIR" in role_to_idx and "RED" in role_to_idx and "GREEN" in role_to_idx:
        false_indices = (role_to_idx["NIR"], role_to_idx["RED"], role_to_idx["GREEN"])
    elif num_bands >= 3:
        false_indices = (0, 1, 2)
    else:
        false_indices = (0, 0, 0)
    _render_preview(data, false_indices, false_path)

    if "RED" in role_to_idx and "GREEN" in role_to_idx and "BLUE" in role_to_idx:
        nat_indices = (role_to_idx["RED"], role_to_idx["GREEN"], role_to_idx["BLUE"])
    elif "RED" in role_to_idx and "GREEN" in role_to_idx:
        nat_indices = (role_to_idx["RED"], role_to_idx["GREEN"], role_to_idx["GREEN"])
    elif num_bands >= 3:
        nat_indices = (0, 1, 2)
    else:
        nat_indices = (0, 0, 0)
    _render_preview(data, nat_indices, nat_path)

    display_label = label or pathlib.Path(filename).stem.replace("_", " ").title()
    sensor_display = sensor or ("Sentinel-2 (custom)" if num_bands >= 4 else "Multispectral GeoTIFF")

    entry = {
        "id": scene_id,
        "label": display_label,
        "sensor": sensor_display,
        "acquired": time.strftime("%Y-%m-%d"),
        "place": "Custom Uploaded Scene",
        "cloud_hint": 0.0,
        "pair": None,
        "path": str(target_tif.relative_to(ROOT)).replace("\\", "/"),
        "preview_false": str(false_path.relative_to(ROOT)).replace("\\", "/"),
        "preview_natural": str(nat_path.relative_to(ROOT)).replace("\\", "/"),
        "width": width,
        "height": height,
        "crs": crs_str,
        "transform": list(transform),
        "bands": [r.lower() for r in roles],
        "dtype": dtypes[0],
        "scale_factor": 10000 if dtypes[0].startswith("uint16") else 1.0,
        "nodata": 0.0,
        "pixel_area_m2": pixel_area_m2,
        "bounds_wgs84": wgs84_bounds,
        "synthetic": False,
        "description": f"Custom uploaded satellite scene ({width}x{height}, {len(roles)} bands: {', '.join(roles)}).",
        "ground_truth": {},
    }

    manifest_data = load_uploaded_manifest()
    manifest_data[scene_id] = entry
    save_uploaded_manifest(manifest_data)

    return entry


def load_uploaded_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_uploaded_manifest(data: dict[str, dict]) -> None:
    init_upload_dirs()
    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remove_uploaded_scene(scene_id: str) -> bool:
    """Delete an uploaded scene and its previews from disk and manifest."""
    manifest_data = load_uploaded_manifest()
    if scene_id not in manifest_data:
        return False
    entry = manifest_data.pop(scene_id)
    save_uploaded_manifest(manifest_data)

    # Remove files
    tif_file = ROOT / entry.get("path", "")
    if tif_file.exists() and tif_file.is_file():
        try:
            tif_file.unlink()
        except OSError:
            pass

    for prev_key in ("preview_false", "preview_natural"):
        prev_file = ROOT / entry.get(prev_key, "")
        if prev_file.exists() and prev_file.is_file():
            try:
                prev_file.unlink()
            except OSError:
                pass

    from ..pipeline import unregister_uploaded_scene
    unregister_uploaded_scene(scene_id)
    return True
