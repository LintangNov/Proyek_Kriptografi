"""Membuat assets/aegisvault.ico dari bentuk logo perisai A pada file Figma."""
import os

from PIL import Image, ImageDraw

SCALE = 16  # digambar 16 kali lebih besar pada kanvas 64 satuan agar tepinya halus
INK = (26, 29, 36, 255)
AMBER = (249, 174, 31, 255)


def cubic(p0, p1, p2, p3, steps=48):
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        points.append(tuple(u**3 * a + 3 * u**2 * t * b + 3 * u * t**2 * c + t**3 * d for a, b, c, d in zip(p0, p1, p2, p3)))
    return points


shield = [(32, 3), (56, 11.5), (56, 31)]
shield += cubic((56, 31), (56, 45), (46.5, 55.5), (32, 61))
shield += cubic((32, 61), (17.5, 55.5), (8, 45), (8, 31))
shield += [(8, 11.5)]
chevron = [(32, 16), (47, 48), (39.5, 48), (32, 31.5), (24.5, 48), (17, 48)]

canvas = Image.new("RGBA", (64 * SCALE, 64 * SCALE), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)
scaled = lambda pts: [(x * SCALE, y * SCALE) for x, y in pts]
draw.polygon(scaled(shield), fill=INK)
draw.polygon(scaled(chevron), fill=AMBER)
r = 3.5 * SCALE
cx, cy = 32 * SCALE, 44.5 * SCALE
draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=AMBER)

root = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(root, exist_ok=True)
canvas.resize((256, 256), Image.LANCZOS).save(os.path.join(root, "aegisvault.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("assets/aegisvault.ico")
