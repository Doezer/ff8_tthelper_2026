"""Bitmap / pixel utilities. Ported from BitmapHelpers.fs.

The F# original hand-rolls per-pixel loops (`Seq.iter` over every x,y).
Here the same results are produced with vectorized numpy operations
instead, which is both less code and much faster - a deliberate deviation
from the F# implementation, not from its behavior.

Only what the runtime detection path (GameStateDetection's non-Bootstrap
functions) actually needs is ported: `Polygon`-based masking and
`blurBitmap` are only used by the offline `Bootstrap` module that
regenerates the template images under `images/` from raw screenshots.
Those images are already committed, so Bootstrap/Polygon were not ported.
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Tuple

import numpy as np
from PIL import Image

RGBA = Tuple[int, int, int, int]
PixelPredicate = Callable[[np.ndarray], np.ndarray]  # (H,W,4) uint8 -> (H,W) bool


class Rect(NamedTuple):
    x: int
    y: int
    width: int
    height: int


class SimpleBitmap:
    """RGBA image backed by a numpy uint8 array of shape (height, width, 4)."""

    __slots__ = ("pixels",)

    def __init__(self, pixels: np.ndarray):
        assert pixels.ndim == 3 and pixels.shape[2] == 4, "expected an (H, W, 4) RGBA array"
        self.pixels = pixels

    @property
    def width(self) -> int:
        return self.pixels.shape[1]

    @property
    def height(self) -> int:
        return self.pixels.shape[0]

    def get_pixel(self, x: int, y: int) -> RGBA:
        r, g, b, a = self.pixels[y, x]
        return int(r), int(g), int(b), int(a)

    def set_pixel(self, x: int, y: int, rgba: RGBA) -> None:
        self.pixels[y, x] = rgba

    def crop(self, rect: Rect) -> "SimpleBitmap":
        x, y, w, h = rect
        return SimpleBitmap(self.pixels[y:y + h, x:x + w].copy())

    def draw_from(self, source: "SimpleBitmap", source_rect: Rect, target_point: Tuple[int, int]) -> None:
        sx, sy, w, h = source_rect
        tx, ty = target_point
        self.pixels[ty:ty + h, tx:tx + w] = source.pixels[sy:sy + h, sx:sx + w]

    @staticmethod
    def from_file(path: str) -> "SimpleBitmap":
        with Image.open(path) as img:
            return SimpleBitmap(np.array(img.convert("RGBA"), dtype=np.uint8))

    @staticmethod
    def create_empty(width: int, height: int) -> "SimpleBitmap":
        return SimpleBitmap(np.zeros((height, width, 4), dtype=np.uint8))

    def save(self, path: str) -> None:
        Image.fromarray(self.pixels, mode="RGBA").save(path)


def is_whitish_pixel(min_br: int, max_diff: int) -> PixelPredicate:
    def predicate(pixels: np.ndarray) -> np.ndarray:
        r = pixels[..., 0].astype(np.int16)
        g = pixels[..., 1].astype(np.int16)
        b = pixels[..., 2].astype(np.int16)
        return (
            (r > min_br) & (g > min_br) & (b > min_br)
            & (np.abs(r - g) < max_diff) & (np.abs(r - b) < max_diff) & (np.abs(g - b) < max_diff)
        )

    return predicate


def is_pixel_between(lower: RGBA, upper: RGBA) -> PixelPredicate:
    def predicate(pixels: np.ndarray) -> np.ndarray:
        r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
        return (
            (r >= lower[0]) & (r <= upper[0])
            & (g >= lower[1]) & (g <= upper[1])
            & (b >= lower[2]) & (b <= upper[2])
        )

    return predicate


def pixel_diff(pixel1: RGBA, pixel2: RGBA) -> int:
    return sum(abs(int(pixel2[i]) - int(pixel1[i])) for i in range(3))


def bitmap_diff(bitmap1: SimpleBitmap, bitmap2: SimpleBitmap) -> float:
    """Normalized sum of per-channel abs differences over pixels opaque in both bitmaps.

    Pixels transparent (alpha=0) in either bitmap are excluded - this is how the
    irregularly-shaped digit/cursor/element template PNGs (masked when they were
    generated) ignore background pixels around the glyph.
    """
    a1 = bitmap1.pixels.astype(np.int32)
    a2 = bitmap2.pixels.astype(np.int32)
    valid = (a1[..., 3] != 0) & (a2[..., 3] != 0)

    max_abs_diff = int(np.count_nonzero(valid)) * 3 * 255
    if max_abs_diff == 0:
        return 0.0

    diffs = np.abs(a2[..., :3] - a1[..., :3]).sum(axis=-1)
    abs_diff = int(diffs[valid].sum())
    return abs_diff / max_abs_diff


def filtered_sub_bitmap(screenshot: SimpleBitmap, rect: Rect, pixel_filter: PixelPredicate) -> SimpleBitmap:
    """Crop `rect` out of `screenshot`, replacing pixels that fail `pixel_filter` with opaque black."""
    sub = screenshot.crop(rect)
    mask = pixel_filter(sub.pixels)
    out = sub.pixels.copy()
    out[~mask] = (0, 0, 0, 255)
    return SimpleBitmap(out)


def sub_bitmap(screenshot: SimpleBitmap, rect: Rect) -> SimpleBitmap:
    return screenshot.crop(rect)
