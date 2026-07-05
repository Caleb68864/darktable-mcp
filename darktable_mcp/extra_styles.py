"""15 additional starter-style recipes for darktable-mcp (name -> nudge sequence).

Each nudge is (control, direction, amount). Controls: brightness, warmth, tint, contrast,
filmic_contrast, saturation, vibrance, shadows, highlights, whites, blacks.
"""

EXTRA_STYLES: dict[str, list[tuple[str, str, int]]] = {
    # Warm highlights + cool shadows: the classic blockbuster split-tone.
    "Teal & Orange": [("warmth", "up", 3), ("shadows", "down", 3), ("saturation", "up", 2), ("contrast", "up", 2)],
    # Cool cast, gentle contrast, restrained color: crisp Scandinavian daylight.
    "Nordic Cool": [("warmth", "down", 4), ("saturation", "down", 2), ("contrast", "up", 1), ("highlights", "up", 1)],
    # Lifted blacks + flatter, muted tones: dusty aged-print fade.
    "Vintage Matte": [("blacks", "up", 3), ("contrast", "down", 3), ("saturation", "down", 3), ("warmth", "up", 1)],
    # Bright, open, low-contrast, gently warm: clean and airy portraits.
    "Bright & Airy": [("brightness", "up", 3), ("shadows", "up", 3), ("contrast", "down", 2), ("warmth", "up", 1)],
    # Dark base, crushed shadows, hard curve: brooding low-key drama.
    "Low Key": [("brightness", "down", 3), ("shadows", "down", 4), ("filmic_contrast", "up", 3), ("blacks", "down", 2)],
    # Warm push with recovered highlights + richer color: fallen-leaf autumn.
    "Autumn Warmth": [("warmth", "up", 4), ("saturation", "up", 2), ("highlights", "down", 2), ("vibrance", "up", 2)],
    # Bright, desaturated, soft contrast, faint warmth: delicate pastel skin.
    "Pastel Portrait": [("brightness", "up", 2), ("saturation", "down", 3), ("contrast", "down", 2), ("warmth", "up", 1)],
    # Punchy vibrance + contrast with deep shadows: postcard landscape snap.
    "Landscape Pop": [("vibrance", "up", 4), ("contrast", "up", 3), ("shadows", "down", 2), ("highlights", "down", 1)],
    # Strong warmth, glowing lifted highlights, extra color: golden sunset haze.
    "Sunset Glow": [("warmth", "up", 5), ("highlights", "up", 2), ("saturation", "up", 2), ("blacks", "up", 1)],
    # Neutral white balance, balanced tones, honest color: true-to-life clean.
    "Clean Neutral": [("contrast", "up", 1), ("highlights", "down", 1), ("shadows", "up", 1), ("saturation", "up", 1)],
    # Cool, hard filmic contrast, tamed highlights: heavy overcast storm sky.
    "Stormy Sky": [("warmth", "down", 3), ("filmic_contrast", "up", 4), ("highlights", "down", 3), ("contrast", "up", 2)],
    # Faded blacks, warm cast, softened color and contrast: nostalgic film stock.
    "Retro Film": [("blacks", "up", 2), ("warmth", "up", 3), ("saturation", "down", 2), ("contrast", "down", 1), ("tint", "up", 1)],
    # High contrast, bold vibrance, deep shadows: gritty high-energy street.
    "Punchy Street": [("contrast", "up", 4), ("vibrance", "up", 3), ("shadows", "down", 3), ("filmic_contrast", "up", 2)],
    # Brightened, low contrast, glowing highlights, muted color: hazy dreamscape.
    "Dreamy Soft": [("brightness", "up", 2), ("contrast", "down", 3), ("highlights", "up", 3), ("saturation", "down", 2)],
    # Deep blacks, strong filmic contrast, saturated color: luxurious and moody-rich.
    "Rich & Deep": [("blacks", "down", 3), ("filmic_contrast", "up", 3), ("saturation", "up", 3), ("shadows", "down", 2)],
}
