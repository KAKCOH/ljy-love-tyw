"""Generate beautiful heart PWA icons using Pillow."""
import math
import os
from PIL import Image, ImageDraw, ImageFilter

def heart_points(cx, cy, scale):
    """Return list of (x, y) points tracing a heart outline using parametric equations."""
    pts = []
    for i in range(360):
        t = i * math.pi / 180
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
        pts.append((cx + x * scale, cy + y * scale))
    return pts

def gradient_radial(size):
    """Create a radial gradient from warm center to deep edges."""
    img = Image.new('RGBA', (size, size))
    cx = cy = size / 2
    max_dist = size * 0.72
    for y in range(size):
        for x in range(size):
            d = math.sqrt((x - cx)**2 + (y - cy)**2) / max_dist
            d = min(d, 1.0)
            # Deep burgundy edge → soft rose → warm pink center
            r = int(120 + 135 * (1 - d))
            g = int(15 + 85 * (1 - d))
            b = int(40 + 95 * (1 - d))
            img.putpixel((x, y), (r, g, b, 255))
    return img

def draw_heart_icon(size):
    """Draw a beautifully shaded heart icon."""
    # --- Background: radial gradient ---
    bg = gradient_radial(size)
    draw = ImageDraw.Draw(bg)

    # --- Heart shadow (darker, offset, blurred) ---
    shadow_size = size * 2  # render larger for blur downscale
    scale_s = shadow_size * 0.026
    cx_s = shadow_size / 2 + shadow_size * 0.01
    cy_s = shadow_size / 2 + shadow_size * 0.04
    shadow_img = Image.new('RGBA', (shadow_size, shadow_size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_img)
    pts_s = heart_points(cx_s, cy_s, scale_s)
    sdraw.polygon(pts_s, fill=(60, 5, 20, 180))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=size * 0.06))
    shadow_img = shadow_img.resize((size, size), Image.LANCZOS)
    bg.paste(shadow_img, (0, 0), shadow_img)

    # --- Main heart ---
    cx = size / 2
    cy = size / 2 - size * 0.015
    scale = size * 0.026
    pts = heart_points(cx, cy, scale)

    # Heart gradient layer: top warm pink → bottom deep rose
    heart_grad = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(heart_grad)
    hdraw.polygon(pts, fill=(255, 255, 255, 255))

    # Create vertical gradient strip to blend onto heart
    grad_strip = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    for y in range(size):
        t = y / size
        # Light warm pink → deeper rose
        r = int(255 - 20 * t)
        g = int(200 - 90 * t)
        b = int(180 - 80 * t)
        for x in range(size):
            # Add horizontal warmth (light from top-left)
            lt = x / size
            gr = min(255, r + int(15 * (1 - lt)))
            gg = min(255, g + int(10 * (1 - lt)))
            gb = min(255, b + int(5 * (1 - lt)))
            grad_strip.putpixel((x, y), (gr, gg, gb, 255))

    # Apply gradient only within heart shape
    for y in range(size):
        for x in range(size):
            if heart_grad.getpixel((x, y))[3] > 0:
                bg.putpixel((x, y), grad_strip.getpixel((x, y)))

    # --- Glossy highlight (white, semi-transparent, on upper heart) ---
    gloss = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gloss)
    gloss_pts = heart_points(cx - size * 0.02, cy - size * 0.04, scale * 0.85)
    gdraw.polygon(gloss_pts, fill=(255, 255, 255, 50))
    gloss = gloss.filter(ImageFilter.GaussianBlur(radius=size * 0.04))
    bg.paste(gloss, (0, 0), gloss)

    # --- Subtle sparkle dots ---
    sparkle = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    sdraw2 = ImageDraw.Draw(sparkle)
    sparkle_positions = [
        (size * 0.28, size * 0.28, size * 0.018),
        (size * 0.73, size * 0.22, size * 0.012),
        (size * 0.20, size * 0.55, size * 0.010),
        (size * 0.78, size * 0.50, size * 0.008),
    ]
    for sx, sy, sr in sparkle_positions:
        sdraw2.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(255, 240, 245, 200))
    sparkle = sparkle.filter(ImageFilter.GaussianBlur(radius=size * 0.008))
    bg.paste(sparkle, (0, 0), sparkle)

    # --- Subtle rounded corners (iOS style) ---
    # Create a rounded rectangle mask
    mask = Image.new('L', (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    corner_r = int(size * 0.18)
    mdraw.rounded_rectangle([0, 0, size-1, size-1], radius=corner_r, fill=255)
    bg.putalpha(mask)

    return bg

base = os.path.dirname(os.path.abspath(__file__))
for size in [192, 512]:
    icon = draw_heart_icon(size)
    path = os.path.join(base, 'static', f'icon-{size}.png')
    icon.save(path, 'PNG')
    print(f'Created {path} ({size}x{size})')
