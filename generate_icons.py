"""Generate clean, minimal heart icons for PWA."""
import math
import os
from PIL import Image, ImageDraw

def heart_points(cx, cy, scale):
    """Parametric heart curve: smooth, anti-aliased polygon points."""
    pts = []
    for i in range(360):
        t = i * math.pi / 180
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2*t)
              - 2 * math.cos(3*t) - math.cos(4*t))
        pts.append((cx + x * scale, cy + y * scale))
    return pts


def make_icon(size):
    img = Image.new('RGBA', (size, size))

    # --- Background: warm romantic gradient (top→bottom) ---
    for y in range(size):
        t = y / size
        r = int(225 - 55 * t)
        g = int(82 + 5 * t)
        b = int(85 + 8 * t)
        for x in range(size):
            img.putpixel((x, y), (r, g, b, 255))

    # --- White heart ---
    cx = size / 2
    cy = size / 2 - size * 0.02
    scale = size * 0.027
    pts = heart_points(cx, cy, scale)

    draw = ImageDraw.Draw(img)
    draw.polygon(pts, fill=(255, 255, 255, 255))

    return img


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    for sz in [192, 512]:
        icon = make_icon(sz)
        path = os.path.join(base, 'static', f'icon-{sz}.png')
        icon.save(path, 'PNG')
        print(f'Created {path} ({sz}x{sz})')
