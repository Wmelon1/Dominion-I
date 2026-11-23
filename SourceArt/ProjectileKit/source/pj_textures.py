# Dominion I - ProjectileKit textures (system Python: numpy + Pillow), reusing the BuildingKit noise helpers.
#   python pj_textures.py   -> ../textures/T_PJPaint_*, T_PJMetal_*, T_PJBrass_*, T_PJCopper_*
# Direction-neutral detail (the rounds are box-projected), each a neutral base the materials tint:
#   PJPaint  - stoved military paint: orange-peel, handling scuffs, chips down to bare steel at the edges
#   PJMetal  - machined steel: fine tool marks, oil sheen, darker blotches
#   PJBrass  - cartridge brass: brushed, warm tarnish, finger marks
#   PJCopper - gilding metal / driving-band copper: engraving scratches, oxidised patches
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'BuildingKit', 'source'))
import bk_textures as bk
from bk_textures import fbm, band, colorize, smooth

OUT = os.path.join(os.path.dirname(HERE), 'textures')
os.makedirs(OUT, exist_ok=True)
bk.OUT = OUT
N = 512


def paint():
    peel = band(N, 120, 40, 3101)
    mottle = fbm(N, 2.2, 3102)
    scuff = fbm(N, 1.2, 3103)
    chips = smooth(0.78, 0.84, fbm(N, 1.7, 3104, fmin=6))
    grime = smooth(0.5, 0.9, fbm(N, 2.0, 3105))
    base = colorize(mottle, (205, 205, 200), (232, 232, 226)) * (1 - 0.12 * grime[..., None]) * (0.96 + 0.06 * scuff[..., None])
    bare = colorize(fbm(N, 1.5, 3106), (120, 122, 126), (160, 162, 166))
    base = base * (1 - chips[..., None]) + bare * chips[..., None]
    h = peel * 0.25 + scuff * 0.1 - chips * 0.5
    bk.save('PJPaint', base, h, 0.5 + 0.15 * grime - 0.25 * chips, chips * 0.9, 1.4, ao=np.ones((N, N)) - 0.1 * chips)


def metal():
    marks = band(N, 200, 60, 3201)
    blot = fbm(N, 2.0, 3202)
    sheen = fbm(N, 2.6, 3203)
    base = colorize(marks * 0.35 + blot * 0.65, (118, 120, 124), (168, 170, 174))
    bk.save('PJMetal', base, marks * 0.3, 0.28 + 0.15 * blot - 0.08 * sheen, 0.95, 0.8, ao=np.ones((N, N)))


def brass():
    brush = band(N, 240, 80, 3301)
    tarnish = smooth(0.45, 0.85, fbm(N, 2.2, 3302))
    prints = smooth(0.7, 0.8, fbm(N, 1.6, 3303, fmin=8))
    base = colorize(brush * 0.4 + fbm(N, 2.0, 3304) * 0.6, (198, 156, 72), (232, 192, 102))
    base = base * (1 - 0.35 * tarnish[..., None]) + np.array([0.33, 0.24, 0.12]) * 0.35 * tarnish[..., None]
    base *= (1 - 0.08 * prints[..., None])
    bk.save('PJBrass', base, brush * 0.25, 0.22 + 0.25 * tarnish + 0.1 * prints, 1.0, 0.7, ao=np.ones((N, N)))


def copper():
    scratch = band(N, 300, 50, 3401)
    ox = smooth(0.55, 0.9, fbm(N, 2.0, 3402))
    base = colorize(fbm(N, 2.2, 3403) * 0.6 + scratch * 0.4, (176, 104, 62), (214, 136, 86))
    base = base * (1 - 0.4 * ox[..., None]) + np.array([0.28, 0.2, 0.15]) * 0.4 * ox[..., None]
    bk.save('PJCopper', base, scratch * 0.35, 0.3 + 0.3 * ox, 1.0, 1.0, ao=np.ones((N, N)))


if __name__ == '__main__':
    paint()
    metal()
    brass()
    copper()
