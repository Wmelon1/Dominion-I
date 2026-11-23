# Dominion I - CityKit texture generator (system Python: numpy + Pillow). Reuses the BuildingKit noise helpers.
#   python ck_textures.py [names...]   -> ../textures/T_<Name>_BaseColor.png, _Normal.png, _ORM.png
# Terrain layers (grass, meadow, dirt, rock, paving, lot gravel), road surfaces with baked lane markings (UV u runs
# across the road, v along it), sidewalk pavers, crosswalk paint (alpha), facade tiles for the procedural buildings
# (2 bays x 2 floors per tile, fake interiors behind glossy glass), bark and alpha leaf atlases for the trees.
import os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'BuildingKit', 'source'))
import bk_textures as bk
from bk_textures import fbm, band, blur, smooth, grid, hash_table, colorize, norm01, normal_from_height, cavity_ao

OUT = os.path.join(os.path.dirname(HERE), 'textures')
os.makedirs(OUT, exist_ok=True)
bk.OUT = OUT
save = bk.save


def save_rgba(name, rgb, alpha):
    to8 = lambda a: (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(np.concatenate([to8(rgb), to8(alpha)[..., None]], -1), 'RGBA').save(
        os.path.join(OUT, f'T_{name}_BaseColor.png'), optimize=True)


# ------------------------------------------------------------------ terrain
def grass():
    n = 1024
    blades = band(n, 330, 140, 401, ax=1.0, ay=0.35)
    clump = fbm(n, 2.2, 402)
    fine = band(n, 480, 160, 403)
    dry = smooth(0.62, 0.85, fbm(n, 2.4, 404))
    t = np.clip(blades * 0.5 + fine * 0.2 + clump * 0.3, 0, 1)
    base = colorize(t, (52, 78, 30), (104, 132, 56))
    base = base * (1 - dry[..., None] * 0.45) + colorize(t, (128, 118, 66), (168, 156, 96)) * dry[..., None] * 0.45
    base *= (0.8 + 0.3 * clump[..., None])
    h = blades * 0.6 + fine * 0.4
    save('Grass', base, h, 0.92, 0.0, 3.0, ao_k=2.0)


def meadow():
    n = 1024
    blades = band(n, 260, 120, 411, ax=1.0, ay=0.4)
    clump = fbm(n, 2.0, 412)
    flowers = smooth(0.82, 0.86, band(n, 200, 60, 413)) * smooth(0.5, 0.7, fbm(n, 2.0, 414))
    t = np.clip(blades * 0.6 + clump * 0.4, 0, 1)
    base = colorize(t, (92, 98, 48), (150, 146, 82))
    base *= (0.8 + 0.3 * clump[..., None])
    fl = np.where((fbm(n, 1.0, 415) > 0.5)[..., None], np.array([0.85, 0.82, 0.5]), np.array([0.8, 0.8, 0.86]))
    base = base * (1 - flowers[..., None]) + fl * flowers[..., None]
    save('Meadow', base, blades, 0.93, 0.0, 3.0, ao_k=2.0)


def dirt():
    n = 1024
    pebbles = smooth(0.62, 0.75, band(n, 160, 60, 421))
    soil = fbm(n, 2.0, 422)
    fine = band(n, 420, 160, 423)
    base = colorize(np.clip(soil * 0.7 + fine * 0.3, 0, 1), (88, 70, 52), (138, 112, 82))
    base = base * (1 - pebbles[..., None] * 0.6) + colorize(fine, (130, 124, 116), (176, 170, 160)) * pebbles[..., None] * 0.6
    h = soil * 0.3 + pebbles * 0.5 + fine * 0.2
    save('Dirt', base, h, 0.9, 0.0, 4.0, ao_k=2.5)


def rock():
    n = 1024
    big = fbm(n, 2.4, 431)
    cracks = 1 - smooth(0.0, 0.03, np.abs(fbm(n, 1.8, 432) - 0.5))
    strata = 0.5 + 0.5 * np.sin((grid(n)[1] / n * 2 * np.pi * 3) + big * 9)
    lichen = smooth(0.66, 0.8, fbm(n, 2.0, 433))
    blocks = band(n, 24, 10, 435)
    t = np.clip(big * 0.45 + blocks * 0.3 + strata * 0.08 + band(n, 300, 120, 434) * 0.17, 0, 1)
    base = colorize(t, (92, 88, 82), (158, 152, 142)) * (1 - cracks[..., None] * 0.5)
    base = base * (1 - lichen[..., None] * 0.35) + np.array([0.42, 0.46, 0.3]) * lichen[..., None] * 0.35
    h = big * 0.5 + blocks * 0.4 - cracks * 0.3
    save('Rock', base, h, 0.82, 0.0, 6.0, ao_k=3.0)


def paving():
    """4 m tile: 0.5 m concrete plaza slabs in a running bond, worn and stained."""
    n = 1024
    x, y = grid(n)
    sp = n / 8
    row = np.floor(y / sp)
    bx = x / sp + (row % 2) * 0.5
    fu, fv = bx % 1, (y / sp) % 1
    d = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)) * sp
    joint = smooth(1.0, 2.6, d)
    sid = (row * 8 + np.floor(bx) % 8).astype(int)
    sv = hash_table(64, 441)[sid]
    stain = fbm(n, 2.2, 442)
    base = colorize(np.clip(sv * 0.5 + stain * 0.5, 0, 1), (138, 134, 126), (184, 180, 170))
    base *= (0.92 + 0.1 * band(n, 300, 100, 443)[..., None])
    base *= (0.55 + 0.45 * joint[..., None])
    save('Paving', base, joint * 0.8 + stain * 0.2, 0.84, 0.0, 3.0, ao_k=2.0)


def lot_gravel():
    n = 1024
    stones = band(n, 380, 150, 451)
    patches = fbm(n, 2.2, 452)
    oil = smooth(0.7, 0.85, fbm(n, 2.0, 453))
    base = colorize(np.clip(stones * 0.6 + patches * 0.4, 0, 1), (96, 92, 86), (150, 146, 138)) * (1 - oil[..., None] * 0.35)
    save('LotGravel', base, stones, 0.93, 0.0, 4.0, ao_k=2.5)


# ------------------------------------------------------------------ roads
def asphalt_base(n, seed, w_m, l_m):
    """Asphalt for a patch w_m x l_m metres: aggregate, wear in the wheel paths, patches and cracks."""
    x, y = grid(n)
    agg = band(n, 520, 200, seed)
    blot = fbm(n, 2.2, seed + 1)
    cracks = 1 - smooth(0.0, 0.012, np.abs(fbm(n, 1.7, seed + 2) - 0.5))
    cracks *= smooth(0.55, 0.75, fbm(n, 2.0, seed + 3))
    patch = smooth(0.74, 0.76, fbm(n, 2.6, seed + 4))
    t = np.clip(agg * 0.5 + blot * 0.5, 0, 1)
    base = colorize(t, (44, 45, 47), (74, 75, 77))
    base = base * (1 - patch[..., None] * 0.25) + np.array([0.12, 0.12, 0.13]) * patch[..., None] * 0.25
    base *= (1 - cracks[..., None] * 0.55)
    h = agg * 0.5 + blot * 0.1 - cracks * 0.4
    rough = 0.86 - patch * 0.08
    return base, h, rough


def paint_lines(n, w_m, l_m, lines):
    """lines: list of (u_centre_m, width_m, dash_m or 0, gap_m, colour rgb 0-1). Returns (mask, colour)."""
    x, y = grid(n)
    um, vm = x / n * w_m, y / n * l_m
    mask = np.zeros((n, n))
    col = np.zeros((n, n, 3))
    wear = fbm(n, 1.2, 77, fmin=20)
    for uc, wd, dash, gap, c in lines:
        m = smooth(wd / 2 + 0.01, wd / 2 - 0.01, np.abs(um - uc))
        if dash > 0:
            per = dash + gap
            ph = vm % per
            m *= smooth(0.0, 0.04, ph) * smooth(dash, dash - 0.04, ph)
        m *= smooth(0.2, 0.45, wear)
        mask = np.maximum(mask, m)
        col = col * (1 - m[..., None]) + np.array(c) * m[..., None]
    return mask, col


def road(name, w_m, l_m, lines, seed):
    n = 1024
    base, h, rough = asphalt_base(n, seed, w_m, l_m)
    # darker oily wheel paths in each lane
    m, c = paint_lines(n, w_m, l_m, lines)
    base = base * (1 - m[..., None]) + c * m[..., None] * (0.85 + 0.1 * fbm(n, 1.5, seed + 9)[..., None])
    h = h + m * 0.15
    rough = rough * (1 - m) + 0.6 * m
    save(name, base, h, rough, 0.0, 2.5, ao_k=1.5)


W, Y = (0.9, 0.9, 0.86), (0.85, 0.66, 0.16)


def roads():
    # local street: 8 m wide, two lanes, dashed white centre line, thin edge lines
    road('RoadLocal', 8.0, 8.0, [(4.0, 0.12, 3.0, 5.0, W), (0.35, 0.12, 0, 0, W), (7.65, 0.12, 0, 0, W)], 501)
    # arterial / avenue: 14 m, four lanes, double yellow centre, dashed lane lines, edge lines
    road('RoadArterial', 14.0, 14.0, [(6.88, 0.12, 0, 0, Y), (7.12, 0.12, 0, 0, Y), (3.6, 0.12, 3.0, 6.0, W),
                                      (10.4, 0.12, 3.0, 6.0, W), (0.4, 0.15, 0, 0, W), (13.6, 0.15, 0, 0, W)], 511)
    # highway: 12 m, two lanes each way, solid centre double yellow, edge lines, shoulders
    road('RoadHighway', 12.0, 12.0, [(5.9, 0.12, 0, 0, Y), (6.1, 0.12, 0, 0, Y), (3.1, 0.14, 4.0, 8.0, W),
                                     (8.9, 0.14, 4.0, 8.0, W), (0.6, 0.18, 0, 0, W), (11.4, 0.18, 0, 0, W)], 521)
    n = 1024
    base, h, rough = asphalt_base(n, 531, 8.0, 8.0)
    save('Asphalt', base, h, rough, 0.0, 2.5, ao_k=1.5)


def sidewalk():
    """3 m tile of 0.6 m concrete sidewalk flags with scored joints."""
    n = 1024
    x, y = grid(n)
    sp = n / 5
    fu, fv = (x / sp) % 1, (y / sp) % 1
    d = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)) * sp
    joint = smooth(1.5, 3.5, d)
    sid = (np.floor(x / sp) + 5 * np.floor(y / sp)).astype(int)
    sv = hash_table(25, 541)[sid]
    gum = smooth(0.86, 0.9, band(n, 260, 90, 542)) * 0.6
    stain = fbm(n, 2.2, 543)
    base = colorize(np.clip(sv * 0.4 + stain * 0.6, 0, 1), (150, 148, 142), (196, 194, 186))
    base *= (0.6 + 0.4 * joint[..., None]) * (1 - gum[..., None] * 0.4)
    save('Sidewalk', base, joint * 0.7 + stain * 0.3, 0.86, 0.0, 3.0, ao_k=1.5)


def crosswalk():
    """Zebra crossing paint, alpha-tested: 6 bars across a 4 m deep crossing (u along the crossing, v across the road)."""
    n = 512
    x, y = grid(n)
    bars = ((x / n * 6) % 1) < 0.5
    wear = smooth(0.25, 0.5, fbm(n, 1.4, 551, fmin=8))
    a = bars * wear
    rgb = np.ones((n, n, 3)) * np.array([0.9, 0.9, 0.86])
    save_rgba('Crosswalk', rgb, a)
    h = np.zeros((n, n))
    Image.fromarray(np.full((n, n, 3), (128, 128, 255), np.uint8)).save(os.path.join(OUT, 'T_Crosswalk_Normal.png'))
    Image.fromarray(np.stack([np.full((n, n), 255), np.full((n, n), 160), np.zeros((n, n))], -1).astype(np.uint8)).save(
        os.path.join(OUT, 'T_Crosswalk_ORM.png'))


# ------------------------------------------------------------------ facades for procedural buildings
def facade(name, wall_fn, win_box, frame_col, sill, rng_seed, shutter=None):
    """One tile = 2 bays x 2 floors. win_box = (u0, u1, v0, v1) of the window in a bay (fractions, v from the floor up).
    wall_fn(n) -> (rgb, height). Windows get fake interiors from the building-kit window generator."""
    n = 1024
    wall, wh = wall_fn(n)
    rgb = wall.copy()
    h = wh.copy()
    rough = np.full((n, n), 0.85)
    metal = np.zeros((n, n))
    rng = np.random.default_rng(rng_seed)
    cw, ch = n // 2, n // 2
    kinds = ['curtains', 'blinds', 'dark', 'shade', 'lit', 'sheer']
    for by in range(2):
        for bx in range(2):
            u0, u1, v0, v1 = win_box
            x0 = bx * cw + int(u0 * cw)
            x1 = bx * cw + int(u1 * cw)
            y1 = (1 - by) * ch + ch - int(v0 * ch)          # image rows go down; v measured up from the floor line
            y0 = (1 - by) * ch + ch - int(v1 * ch)
            ww, hh = x1 - x0, y1 - y0
            inner = bk._interior(max(ww, hh), rng, kinds[rng.integers(0, len(kinds))])
            inner = inner[np.linspace(0, inner.shape[0] - 1, hh).astype(int)][:, np.linspace(0, inner.shape[1] - 1, ww).astype(int)]
            f = max(3, ww // 22)
            rgb[y0:y1, x0:x1] = frame_col
            rgb[y0 + f:y1 - f, x0 + f:x1 - f] = inner[f:hh - f, f:ww - f]
            mid = (x0 + x1) // 2
            rgb[y0:y1, mid - f // 2:mid + f // 2 + 1] = frame_col
            h[y0:y1, x0:x1] = 0.15
            h[y0 + f:y1 - f, x0 + f:x1 - f] = 0.0
            rough[y0 + f:y1 - f, x0 + f:x1 - f] = 0.06
            metal[y0 + f:y1 - f, x0 + f:x1 - f] = 0.1
            if sill is not None:
                s = max(4, hh // 14)
                rgb[y1:y1 + s, x0 - f:x1 + f] = sill
                h[y1:y1 + s, x0 - f:x1 + f] = 1.2
                rgb[y0 - s:y0, x0 - f:x1 + f] = sill * 0.95
                h[y0 - s:y0, x0 - f:x1 + f] = 1.1
            if shutter is not None:
                sw = ww // 2
                for xa in (x0 - sw - f, x1 + f):
                    rgb[y0:y1, max(0, xa):xa + sw] = shutter
                    slat = (np.arange(hh) % 10 < 5)[:, None]
                    h[y0:y1, max(0, xa):xa + sw] = 1.05
    save(name, rgb, h, rough, metal, 4.0, ao_k=2.0)


def wall_brick(n):
    from PIL import Image as I
    src = np.asarray(I.open(os.path.join(HERE, '..', '..', 'BuildingKit', 'textures', 'T_Brick_BaseColor.png')).convert('RGB')) / 255.0
    # brick tile is 1.8 m; the facade tile is 6.4 m -> repeat ~3.5x, resample
    reps = 6.4 / 1.8
    idx = (np.arange(n) * reps * src.shape[0] / n).astype(int) % src.shape[0]
    rgb = src[idx][:, idx]
    hsrc = np.asarray(I.open(os.path.join(HERE, '..', '..', 'BuildingKit', 'textures', 'T_Brick_Normal.png')).convert('RGB')) / 255.0
    hmap = 1 - np.abs(hsrc[idx][:, idx][..., 0] - 0.5) * 2
    return rgb, hmap * 0.3 + 0.6


def wall_plaster(n):
    blot = fbm(n, 2.4, 611)
    fine = fbm(n, 1.1, 612, fmin=60)
    streak = fbm(n, 2.0, 613, ax=0.15, ay=2.5)
    rgb = colorize(blot, (218, 214, 204), (240, 238, 230)) * (0.95 + 0.06 * fine[..., None])
    rgb *= (1 - 0.12 * smooth(0.55, 0.95, streak)[..., None])
    return rgb, np.full((n, n), 0.7) + fine * 0.1


def wall_concrete(n):
    x, y = grid(n)
    ch = n // 2
    band_ = (((y % ch) / ch) > 0.08) & (((y % ch) / ch) < 0.14)
    mott = fbm(n, 2.0, 621)
    rgb = colorize(mott, (150, 150, 146), (186, 186, 180))
    rgb[band_] *= 0.82
    streak = fbm(n, 2.0, 622, ax=0.12, ay=3.0)
    rgb *= (1 - 0.15 * smooth(0.5, 0.95, streak)[..., None])
    return rgb, np.where(band_, 0.6, 0.75) + mott * 0.05


def facades():
    facade('FacadeBrick', wall_brick, (0.22, 0.78, 0.28, 0.82), np.array([0.9, 0.9, 0.86]), np.array([0.78, 0.75, 0.68]), 701)
    facade('FacadePlaster', wall_plaster, (0.25, 0.75, 0.3, 0.8), np.array([0.92, 0.92, 0.9]), np.array([0.85, 0.84, 0.8]), 702)
    facade('FacadeConcrete', wall_concrete, (0.06, 0.94, 0.3, 0.86), np.array([0.16, 0.17, 0.18]), None, 703)
    storefront()


def storefront():
    """6.4 m x 4 m ground-floor tile: two shop windows, a door, a sign band (tinted per building)."""
    n = 1024
    x, y = grid(n)
    u, v = x / n, 1 - y / n                      # v up
    rgb = np.ones((n, n, 3)) * np.array([0.3, 0.3, 0.32])
    h = np.full((n, n), 0.8)
    rough = np.full((n, n), 0.5)
    metal = np.full((n, n), 0.6)
    rng = np.random.default_rng(801)
    sign = v > 0.8
    rgb[sign] = np.array([0.82, 0.8, 0.76])
    rough[sign] = 0.4
    metal[sign] = 0.0
    for a, b in ((0.04, 0.46), (0.54, 0.96)):
        win = (u > a) & (u < b) & (v > 0.12) & (v < 0.74)
        hh, ww = int(0.62 * n), int((b - a) * n)
        inner = bk._interior(max(hh, ww), rng, rng.choice(['lit', 'dark', 'blinds']))
        inner = inner[np.linspace(0, inner.shape[0] - 1, hh).astype(int)][:, np.linspace(0, inner.shape[1] - 1, ww).astype(int)]
        y0 = int((1 - 0.74) * n)
        x0 = int(a * n)
        rgb[y0:y0 + hh, x0:x0 + ww] = inner * 1.1 + 0.03
        h[win] = 0.0
        rough[win] = 0.05
        metal[win] = 0.1
    kick = (v < 0.12)
    rgb[kick] = np.array([0.22, 0.22, 0.23])
    save('Storefront', rgb, h, rough, metal, 3.0, ao_k=1.5)


# ------------------------------------------------------------------ trees
def bark():
    n = 512
    x, y = grid(n)
    ridges = band(n, 40, 16, 901, ax=5.0, ay=0.3)
    fine = fbm(n, 1.6, 902, ax=3.0, ay=0.5)
    rgb = colorize(np.clip(ridges * 0.6 + fine * 0.4, 0, 1), (54, 44, 36), (110, 96, 80))
    save('Bark', rgb, ridges * 0.8 + fine * 0.2, 0.92, 0.0, 6.0, ao_k=3.0)


def leaves(name, seed, broad=True, col0=(46, 78, 30), col1=(96, 128, 52)):
    """Alpha-tested foliage atlas: 2 x 2 cards of leaf clusters (broadleaf) or needle sprays (conifer)."""
    n = 1024
    rng = np.random.default_rng(seed)
    rgb = np.zeros((n, n, 3))
    a = np.zeros((n, n))
    x, y = grid(n)
    c = n // 2
    for q in range(4):
        ox, oy = (q % 2) * c, (q // 2) * c
        lx, ly = x[oy:oy + c, ox:ox + c] - ox, y[oy:oy + c, ox:ox + c] - oy
        cell_a = np.zeros((c, c))
        cell_c = np.zeros((c, c, 3))
        count = 230 if broad else 900
        for _ in range(count):
            # leaves scattered in a rough disc, denser in the middle
            r = rng.uniform(0, 0.42) ** 0.8 * c
            ang = rng.uniform(0, 2 * np.pi)
            cx, cy = c / 2 + np.cos(ang) * r, c / 2 + np.sin(ang) * r
            rot = rng.uniform(0, np.pi)
            dx, dy = lx - cx, ly - cy
            ex = dx * np.cos(rot) + dy * np.sin(rot)
            ey = -dx * np.sin(rot) + dy * np.cos(rot)
            if broad:
                L, Wd = rng.uniform(18, 30), rng.uniform(9, 14)
            else:
                L, Wd = rng.uniform(16, 34), rng.uniform(1.6, 2.6)
            m = (ex / L) ** 2 + (ey / Wd) ** 2 < 1
            shade = rng.uniform(0.0, 1.0)
            col = (np.array(col0) + (np.array(col1) - np.array(col0)) * shade) / 255
            light = 0.75 + 0.25 * (ex / L)
            cell_c[m] = col * light[m][..., None]
            cell_a[m] = 1
        if not broad:
            # twig spine
            spine = (np.abs(lx - c / 2) < 2.0) & (ly > c * 0.1) & (ly < c * 0.9)
            cell_c[spine] = np.array([0.25, 0.2, 0.14])
            cell_a[spine] = 1
        rgb[oy:oy + c, ox:ox + c] = cell_c
        a[oy:oy + c, ox:ox + c] = cell_a
    # bleed colour into transparent texels (no dark halos when mip-mapped)
    filled = rgb.copy()
    w = a.copy()
    for _ in range(6):
        filled = np.where(w[..., None] > 0, filled, (np.roll(filled, 1, 0) + np.roll(filled, -1, 0) + np.roll(filled, 1, 1) + np.roll(filled, -1, 1)) / 4)
        w = np.maximum(w, (np.roll(w, 1, 0) + np.roll(w, -1, 0) + np.roll(w, 1, 1) + np.roll(w, -1, 1)) / 4 > 0)
    save_rgba(name, filled, a)
    Image.fromarray(np.full((n, n, 3), (128, 128, 255), np.uint8)).save(os.path.join(OUT, f'T_{name}_Normal.png'))
    Image.fromarray(np.stack([np.full((n, n), 255), np.full((n, n), 200), np.zeros((n, n))], -1).astype(np.uint8)).save(
        os.path.join(OUT, f'T_{name}_ORM.png'))


def foliage():
    leaves('LeavesBroad', 911, True)
    leaves('LeavesConifer', 912, False, (26, 54, 30), (60, 92, 48))
    leaves('LeavesAutumn', 913, True, (120, 70, 22), (196, 140, 46))


# ------------------------------------------------------------------ vehicles / props
def car_paint():
    n = 512
    f = fbm(n, 1.4, 931, fmin=10)
    dirt = smooth(0.55, 0.9, fbm(n, 2.0, 932, ax=0.3, ay=2.0))
    rgb = np.ones((n, n, 3)) * (0.96 + 0.04 * f[..., None])
    rgb *= (1 - dirt[..., None] * 0.12)
    save('CarPaint', rgb, f * 0.02, 0.28 + dirt * 0.3, 0.45 * (1 - dirt * 0.5), 0.3, ao=np.ones((n, n)))


def burnt():
    n = 512
    rust = fbm(n, 2.0, 941)
    soot = fbm(n, 1.6, 942, fmin=8)
    rgb = colorize(rust, (40, 30, 26), (120, 64, 36)) * (0.5 + 0.5 * soot[..., None])
    save('Burnt', rgb, rust * 0.4 + soot * 0.2, 0.9, 0.3, 3.0, ao_k=2.0)


ALL = {f.__name__: f for f in (grass, meadow, dirt, rock, paving, lot_gravel, roads, sidewalk, crosswalk, facades, bark,
                                foliage, car_paint, burnt)}

if __name__ == '__main__':
    for nm in (sys.argv[1:] or list(ALL)):
        ALL[nm]()
