"""Render PNG previews of each demo scene for the frontend and documentation.

Two per scene: false-colour (NIR-red-green, the standard remote-sensing composite
where vegetation is red and water is near-black) and a natural-ish composite.

There is no blue band in these scenes (S2 subset is B03/B04/B08/B11), so natural
colour is synthesised: blue is estimated from green and red, which is what any
pan-sharpening or band-synthesis routine does when a channel is missing. It is
labelled approximate for exactly that reason.

Run:  python scripts/make_previews.py
"""

import pathlib

import numpy as np
import rasterio
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "data" / "demo"
OUT = DEMO / "previews"


def stretch(band, lo, hi, gamma=1.0):
    """Clip to an explicit reflectance range, then gamma. Deliberately NOT a
    per-band percentile stretch: stretching each channel to its own extremes
    decorrelates the channels and turns a natural scene into saturated primaries.
    A shared physical range keeps the relative band brightness that carries the
    actual colour."""
    v = (band - lo) / (hi - lo)
    # Soft shoulder instead of a hard clip. The visible range is tuned for
    # vegetation (~0.02-0.18 reflectance) but cloud sits near 0.75, so a plain
    # clip drove every cloud pixel to pure white and threw away all its internal
    # structure. Compressing everything above 1.0 asymptotically keeps the
    # highlights inside the display range while preserving their relative
    # differences -- the same job a film shoulder or a tone-mapping curve does.
    hi_part = v > 1.0
    v = np.where(hi_part, 1.0 + np.log1p(np.maximum(v - 1.0, 0.0)) * 0.22, v)
    v = np.clip(v / max(1.0, float(v.max())), 0.0, 1.0)
    if gamma != 1.0:
        v = v ** (1.0 / gamma)
    return v


def tone(rgb):
    """Mild S-curve plus desaturation toward luminance.

    Real satellite composites are muted: atmospheric scattering and mixed pixels
    pull everything toward grey. Full-saturation output is the single strongest
    'this is not imagery' cue, so pull 22% back toward luminance."""
    lum = (0.30 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2])[..., None]
    rgb = rgb * 0.88 + lum * 0.12
    # Smoothstep: lifts shadows slightly, rolls off highlights, no clipping.
    rgb = rgb * rgb * (3.0 - 2.0 * rgb)
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for tif in sorted(DEMO.glob("*.tif")):
        with rasterio.open(tif) as src:
            b = dict(zip(src.descriptions, src.read().astype(np.float64) / 10000.0))

        # Synthetic blue. Over vegetation, chlorophyll absorbs blue harder than
        # red, so the ordering is green > red > blue and a linear fit works.
        # That fit breaks
        # on bright targets: clouds are spectrally flat -- which is precisely why
        # they look white -- but the vegetation coefficients drove their blue to
        # half their green and rendered every cloud edge yellow.
        #
        # So blend by brightness: the vegetation fit where the scene is dark,
        # flat (blue = green) where it is bright. Purely a preview concern; the
        # measurement path never sees this channel.
        veg_blue = 0.55 * b["green"] - 0.05 * b["red"] + 0.004
        bright = np.clip((b["green"] - 0.16) / 0.22, 0.0, 1.0)
        blue = veg_blue * (1 - bright) + b["green"] * bright

        # Vegetation absorbs visible light, so the visible bands here really do span
        # only ~0.02-0.20 reflectance. Stretching them against a NIR-sized range
        # crushes the whole scene into dark grey, so the visible channels get their
        # own range -- shared across R, G and B, which is what preserves colour.
        vis = dict(lo=0.015, hi=0.175, gamma=1.35)
        natural = np.dstack([stretch(b["red"], **vis),
                             stretch(b["green"], **vis),
                             stretch(blue, **vis)])

        # False colour needs its OWN visible range, wider than the natural one.
        # Sharing the natural range lifts green to mid-grey while NIR saturates
        # red, and mid-grey green under full red is magenta -- which is why this
        # composite came out hot pink. A real NIR-R-G composite reads deep crimson
        # because green stays dark: vegetation reflects ~5x more NIR than green,
        # and the render has to preserve that ratio, not equalise it.
        vis_fc = dict(lo=0.010, hi=0.330, gamma=1.25)
        nir_fc = dict(lo=0.010, hi=0.400, gamma=1.45)
        false = np.dstack([stretch(b["nir"], **nir_fc),
                           stretch(b["red"], **vis_fc),
                           stretch(b["green"], **vis_fc)])

        Image.fromarray(tone(natural)).save(OUT / f"{tif.stem}_natural.png")
        Image.fromarray(tone(false)).save(OUT / f"{tif.stem}_false.png")
        n += 2
    print(f"wrote {n} previews -> {OUT}")


if __name__ == "__main__":
    main()
