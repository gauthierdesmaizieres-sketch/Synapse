"""Génère docs/icon-192.png et docs/icon-512.png (même dessin que icon.svg), sans dépendance."""
import math
import struct
import zlib
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
NODES = [(18, 40, 5), (30, 28, 6), (44, 34, 4), (46, 18, 4), (26, 16, 3)]
LINES = [((18, 40), (30, 28)), ((30, 28), (44, 34)), ((44, 34), (46, 18)), ((30, 28), (26, 16))]
C1, C2 = (0x63, 0x66, 0xF1), (0x0E, 0xA5, 0xE9)


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def coverage(x, y):
    """Blanc (1) sur le motif, 0 ailleurs. Coordonnées dans le repère 64x64 du SVG."""
    for cx, cy, r in NODES:
        if math.hypot(x - cx, y - cy) <= r:
            return 1
    for a, b in LINES:
        if seg_dist(x, y, a, b) <= 1.5:
            return 1
    return 0


def png(size, path, ss=3):
    rows = []
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            white = 0.0
            for sj in range(ss):
                for si in range(ss):
                    x = (i + (si + .5) / ss) * 64 / size
                    y = (j + (sj + .5) / ss) * 64 / size
                    white += coverage(x, y)
            white /= ss * ss
            t = (i + j) / (2 * size)
            base = [C1[k] + (C2[k] - C1[k]) * t for k in range(3)]
            row += bytes(round(base[k] + (255 - base[k]) * white) for k in range(3))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


if __name__ == "__main__":
    for s in (192, 512):
        png(s, DOCS / f"icon-{s}.png")
        print("écrit", f"icon-{s}.png")
