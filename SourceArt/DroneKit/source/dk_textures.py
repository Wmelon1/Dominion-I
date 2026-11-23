# Dominion I - DroneKit texture generator (system Python: numpy + Pillow). Reuses the BuildingKit noise helpers.
#   python dk_textures.py [names...]   -> ../textures/T_<Name>_BaseColor.png, _Normal.png, _ORM.png
# Composite drone paint (orange-peel clear coat, mottling, chipped edges toward the panel seams), a 2x2 twill
# carbon-fibre weave, brushed anodised aluminium, moulded rubber, and an alpha rotor-blur disc.
import os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'BuildingKit', 'source'))
import bk_textures as bk
from bk_textures import fbm, band, blur, smooth, grid, colorize

OUT = os.path.join(os.path.dirname(HERE), 'textures')
os.makedirs(OUT, exist_ok=True)
bk.OUT = OUT
save = bk.save


def paint():
    """Matte military composite: mottled, slightly orange-peeled, with fine scuffs and a few chips to bare primer."""
    n = 1024
    mottle = fbm(n, 2.4, 1101)
    peel = band(n, 210, 70, 1102)
    scuff = fbm(n, 1.1, 1103, ax=0.15, ay=4.0)            # fine directional scuffs
    chips = smooth(0.80, 0.86, fbm(n, 1.8, 1104, fmin=10))
    grime = smooth(0.55, 0.9, fbm(n, 2.0, 1105))
    base = colorize(mottle, (196, 198, 192), (226, 226, 220))          # light neutral: tinted per drone in the material
    base *= (1.0 - 0.10 * grime[..., None]) * (0.97 + 0.05 * scuff[..., None])
    primer = colorize(fbm(n, 2.0, 1106), (92, 96, 98), (118, 122, 124))
    base = base * (1 - chips[..., None]) + primer * chips[..., None]
    h = peel * 0.25 + scuff * 0.1 - chips * 0.6
    rough = 0.52 + 0.14 * grime + 0.08 * scuff - 0.06 * peel
    metal = chips * 0.0
    save('DronePaint', base, h, rough, metal, 1.6, ao=np.ones((n, n)) - 0.12 * chips)


def carbon():
    """2x2 twill weave: 32 tows across the tile, each tow a rounded bundle with lengthwise fibre streaks."""
    n = 1024
    x, y = grid(n)
    tows = 32
    u, v = x / n * tows, y / n * tows
    iu, iv = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - iu, v - iv
    warp_on_top = ((iu + iv) // 2) % 2 == 0                         # twill: the over/under shifts one tow per row
    across = np.where(warp_on_top, fu, fv)                           # position across the tow on top
    along = np.where(warp_on_top, fv, fu)
    bulge = np.sin(np.pi * across) ** 0.6
    dip = 0.75 + 0.25 * np.sin(np.pi * along)                        # tows dip where they pass under
    streak_w = fbm(n, 1.0, 1201, ax=0.03, ay=6.0)
    streak_h = fbm(n, 1.0, 1202, ax=6.0, ay=0.03)
    streak = np.where(warp_on_top, streak_w, streak_h)
    h = bulge * dip
    sheen = np.where(warp_on_top, 1.0, 0.72)                         # the two tow directions catch light differently
    t = np.clip(0.25 + 0.5 * h * sheen + 0.25 * streak, 0, 1)
    base = colorize(t, (14, 15, 17), (58, 60, 64))
    rough = 0.28 + 0.12 * (1 - h) + 0.05 * streak
    save('Carbon', base, h * 0.7 + streak * 0.15, rough, 0.0, 3.0, ao_sigma=2, ao_k=2.0)


def anodized():
    """Brushed, dark gunmetal anodised aluminium (motor bells, hinges, gimbal yokes)."""
    n = 512
    brush = fbm(n, 1.0, 1301, ax=0.02, ay=8.0)
    blot = fbm(n, 2.2, 1302)
    base = colorize(brush * 0.55 + blot * 0.45, (58, 62, 68), (86, 90, 96))
    save('Anodized', base, brush * 0.2, 0.30 + 0.12 * blot, 0.95, 1.0, ao=np.ones((n, n)))


def rubber():
    """Moulded rubber with a light stipple (landing feet, bumpers, cable sleeves)."""
    n = 512
    stip = band(n, 120, 40, 1401)
    dust = smooth(0.5, 0.95, fbm(n, 2.0, 1402))
    base = colorize(stip * 0.4 + dust * 0.6, (24, 24, 24), (52, 50, 46))
    save('Rubber', base, stip * 0.5, 0.86, 0.0, 2.0, ao_k=1.5)


def rotor_blur():
    """Spinning-prop disc: polar-mapped (UV centre 0.5, 0.5); a faint translucent sweep with blade-tip banding."""
    n = 512
    x, y = grid(n)
    dx, dy = x / n - 0.5, y / n - 0.5
    r = np.sqrt(dx * dx + dy * dy) * 2.0                             # 0 at the hub, 1 at the tip
    ang = np.arctan2(dy, dx)
    hub = smooth(0.10, 0.18, r)
    tip = 1.0 - smooth(0.93, 1.0, r)
    sweep = 0.55 + 0.45 * np.cos(ang * 2.0) ** 2                     # two blades leave two denser sweeps
    rings = 0.85 + 0.15 * np.sin(r * 60.0)
    tipband = np.exp(-((r - 0.9) / 0.035) ** 2) * 0.6                 # painted tips show as a bright ring
    alpha = np.clip((0.16 * sweep * rings + tipband * 0.5) * hub * tip, 0, 1)
    rgb = np.ones((n, n, 3)) * 0.12
    rgb += tipband[..., None] * np.array([0.75, 0.55, 0.15])
    to8 = lambda a: (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(np.concatenate([to8(rgb), to8(alpha)[..., None]], -1), 'RGBA').save(
        os.path.join(OUT, 'T_RotorBlur_BaseColor.png'), optimize=True)
    print('wrote RotorBlur', n)


ALL = {f.__name__: f for f in (paint, carbon, anodized, rubber, rotor_blur)}

if __name__ == '__main__':
    for nm in (sys.argv[1:] or list(ALL)):
        ALL[nm]()
