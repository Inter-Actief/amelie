# Based loosely on https://github.com/arcarson/palette-generator/blob/master/src/palette_generator.js


def hsl_string(h: int, s: int, l: int) -> str:
    return f"hsl({h} {s}% {l}%)"


def opposite_hue(h: int):
    return (h + 180) % 360


def get_shade(h: int, s: int, l: int, percentage: int):
    base_lightness = l
    difference_to_white = 100 - l
    tint = round((percentage / 100) * difference_to_white)
    adjusted_lightness = base_lightness + tint
    return hsl_string(h, s, adjusted_lightness)


def generate_shades(h: int, s: int, l: int, shade_variation: int):
    names = ['darker', 'dark', 'base', 'light', 'lighter']
    variation_multiplier = -2
    shades = {}

    for name in names:
        variation_percentage = shade_variation * variation_multiplier
        shades[name] = get_shade(h, s, l, variation_percentage)
        variation_multiplier += 1

    return shades


def generate_triadic_scheme(h: int, s: int, l: int, hue_increment: int):
    return [
        [h, s, l],
        [opposite_hue(h) - hue_increment, s, l],
        [opposite_hue(h) + hue_increment, s, l],
    ]


def generate_palette(h: int, s: int, l: int, hue_increment: int = 20, shade_variation: int = 20):
  color_group_names = ['alpha', 'beta', 'delta', 'gamma', 'epsilon']
  color_values = generate_triadic_scheme(h, s, l, hue_increment)

  colors = {}
  for i, color in enumerate(color_values):
      h, s, l = color
      colors[color_group_names[i]] = generate_shades(h, s, l, shade_variation)

  colors['grey'] = generate_shades(color_values[0][0], 10, 50, shade_variation + 10)

  return colors
