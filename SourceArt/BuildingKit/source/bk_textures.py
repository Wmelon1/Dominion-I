# Dominion I - BuildingKit texture generator (system Python: numpy + Pillow)
#   python bk_textures.py            -> writes ../textures/T_<Name>_BaseColor.png, _Normal.png, _ORM.png
# Every texture is seamless (built from periodic FFT noise and integer-count patterns), so one small shared
# material library covers every building. ORM = R ambient occlusion, G roughness, B metallic (Blender);
# Tools/convert_textures.py repacks ORM into the HDRP mask map for Unity. Normals are OpenGL (+Y up), as Unity wants.
import os, sys
import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures')
os.makedirs(OUT, exist_ok=True)


# ------------------------------------------------------------------ periodic noise helpers
def _freqs(n, ax=1.0, ay=1.0):
    fy = np.fft.fftfreq(n)[:, None] * n * ay
    fx = np.fft.fftfreq(n)[None, :] * n * ax
    return fx, fy


def norm01(a):
    a = a - a.min()
    m = a.max()
    return a / m if m > 0 else a


def fbm(n, beta=2.0, seed=0, ax=1.0, ay=1.0, fmin=1.0, fmax=None):
    """Seamless fractal noise with a 1/f^beta power spectrum. ax/ay > 1 squash features along that axis."""
    rng = np.random.default_rng(seed)
    F = np.fft.fft2(rng.standard_normal((n, n)))
    fx, fy = _freqs(n, ax, ay)
    f = np.sqrt(fx * fx + fy * fy)
    amp = 1.0 / np.maximum(f, fmin) ** (beta * 0.5)
    if fmax:
        amp *= np.exp(-(f / fmax) ** 2)
    amp[0, 0] = 0
    return norm01(np.real(np.fft.ifft2(F * amp)))


def band(n, f0, width, seed=0, ax=1.0, ay=1.0):
    """Seamless noise concentrated around f0 cycles per tile (features of one size)."""
    rng = np.random.default_rng(seed)
    F = np.fft.fft2(rng.standard_normal((n, n)))
    fx, fy = _freqs(n, ax, ay)
    f = np.sqrt(fx * fx + fy * fy)
    amp = np.exp(-((f - f0) / width) ** 2)
    amp[0, 0] = 0
    return norm01(np.real(np.fft.ifft2(F * amp)))


def blur(a, sigma):
    n0, n1 = a.shape
    fy = np.fft.fftfreq(n0)[:, None]
    fx = np.fft.fftfreq(n1)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def grid(n):
    y = (np.arange(n) + 0.5)[:, None] * np.ones((1, n))
    x = (np.arange(n) + 0.5)[None, :] * np.ones((n, 1))
    return x, y


def hash_table(count, seed):
    return np.random.default_rng(seed).random(count)


def lerp(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) == 2 and np.ndim(a) == 1 else t
    return a + (b - a) * t


def colorize(t, c0, c1):
    """Blend two sRGB colours (0-255) by t (HxW) -> HxWx3 float 0-1."""
    c0 = np.array(c0, float) / 255
    c1 = np.array(c1, float) / 255
    return c0 + (c1 - c0) * t[..., None]


# ------------------------------------------------------------------ output
def normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * 0.5      # image rows go down; +Y (green) is up
    nx, ny, nz = -dx * strength, -dy * strength, np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / l, ny / l, nz / l], -1) * 0.5 + 0.5


def cavity_ao(h, sigma, k):
    return np.clip(1.0 - np.maximum(blur(h, sigma) - h, 0) * k, 0.35, 1.0)


def save(name, base, height, rough, metal, nstrength, ao=None, ao_sigma=6, ao_k=3.0):
    n = base.shape[0]
    if ao is None:
        ao = cavity_ao(height, ao_sigma, ao_k)
    if np.ndim(rough) == 0:
        rough = np.full((n, n), float(rough))
    if np.ndim(metal) == 0:
        metal = np.full((n, n), float(metal))
    to8 = lambda a: (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(to8(base), 'RGB').save(os.path.join(OUT, f'T_{name}_BaseColor.png'), optimize=True)
    Image.fromarray(to8(normal_from_height(height, nstrength)), 'RGB').save(os.path.join(OUT, f'T_{name}_Normal.png'), optimize=True)
    Image.fromarray(to8(np.stack([ao, rough, metal], -1)), 'RGB').save(os.path.join(OUT, f'T_{name}_ORM.png'), optimize=True)
    print('wrote', name, n)


# ------------------------------------------------------------------ textures
def brick():
    """1.8 m tile: 8 bricks x 24 courses (215x65 mm brick, 10 mm mortar), running bond."""
    n = 1024
    x, y = grid(n)
    ch, bl = n / 24, n / 8
    row = np.floor(y / ch)
    bx = x / bl + (row % 2) * 0.5
    col = np.floor(bx) % 8
    fu, fv = bx - np.floor(bx), y / ch - row
    mort = 0.010 / 1.8 * n * 0.5
    d = np.minimum(np.minimum(fu, 1 - fu) * bl, np.minimum(fv, 1 - fv) * ch) - mort
    chip = fbm(n, 1.6, 11, fmin=8)
    m = smooth(-0.8, 1.6, d + (chip - 0.5) * 3.0)
    idx = (row * 8 + col).astype(int)
    hv = hash_table(24 * 8, 3)[idx]
    hv2 = hash_table(24 * 8, 4)[idx]
    grain = fbm(n, 1.2, 12, fmin=30)
    spots = band(n, 140, 50, 13)
    brickc = colorize(hv, (128, 56, 40), (176, 88, 60))
    brickc = brickc * (0.82 + 0.3 * grain[..., None]) * (0.9 + 0.2 * spots[..., None])
    burnt = (hv2 > 0.86)[..., None]
    brickc = np.where(burnt, brickc * np.array([0.62, 0.58, 0.6]), brickc)
    mortc = colorize(fbm(n, 1.5, 14, fmin=20), (150, 145, 136), (190, 184, 172))
    dirt = fbm(n, 2.2, 15)[..., None]
    base = (mortc + (brickc - mortc) * m[..., None]) * (0.88 + 0.16 * dirt)
    h = m * (0.8 + 0.2 * smooth(0, 6, d)) + (grain - 0.5) * 0.08 + (spots - 0.5) * 0.05
    rough = 0.9 - 0.08 * m
    save('Brick', base, h, rough, 0.0, 6.0, ao_sigma=5, ao_k=2.2)


def plaster():
    """3 m tile of exterior render: near-white so per-building materials can tint it."""
    n = 1024
    bumps = band(n, 220, 90, 21)
    fine = fbm(n, 1.1, 22, fmin=60)
    blot = fbm(n, 2.4, 23)
    streak = fbm(n, 2.0, 24, ax=0.15, ay=2.5)                  # vertical rain streaks
    base = colorize(blot, (214, 210, 200), (238, 235, 226))
    base *= (0.94 + 0.08 * fine[..., None]) * (1 - 0.1 * smooth(0.55, 0.95, streak)[..., None])
    h = bumps * 0.6 + fine * 0.4
    save('Plaster', base, h, 0.88, 0.0, 2.2, ao_k=1.5)


def concrete():
    """3 m tile: 1.5 m precast panels with grooved joints, form-tie holes and water stains."""
    n = 1024
    x, y = grid(n)
    pp = n / 2
    fu, fv = (x / pp) % 1, (y / pp) % 1
    d = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)) * pp
    joint = smooth(2.5, 5.0, d)
    ties = np.ones((n, n))
    for cu in (0.2, 0.8):
        for cv in (0.25, 0.75):
            r = np.sqrt(((fu - cu) * pp) ** 2 + ((fv - cv) * pp) ** 2)
            ties = np.minimum(ties, smooth(4.0, 6.5, r))
    pid = (np.floor(x / pp) + 2 * np.floor(y / pp)).astype(int)
    pv = hash_table(4, 31)[pid]
    mott = fbm(n, 2.0, 32)
    pores = band(n, 300, 120, 33)
    streak = fbm(n, 2.0, 34, ax=0.12, ay=3.0)
    t = np.clip(mott * 0.7 + pv * 0.3, 0, 1)
    base = colorize(t, (150, 148, 142), (188, 186, 180))
    base *= (0.92 + 0.1 * pores[..., None])
    base *= (1 - 0.18 * smooth(0.5, 0.95, streak)[..., None])
    base *= (0.55 + 0.45 * joint[..., None]) * (0.45 + 0.55 * ties[..., None])
    h = joint * 0.8 + ties * 0.2 + (pores - 0.5) * 0.12 + (mott - 0.5) * 0.06
    save('Concrete', base, h, 0.86, 0.0, 4.0, ao_k=2.5)


def siding():
    """2 m tile of painted lap siding: 10 boards of 0.2 m, each overlapping the one below."""
    n = 1024
    x, y = grid(n)
    bh = n / 10
    fv = (y / bh) % 1                                       # 0 at top of board, 1 at bottom lip
    h = 0.25 + 0.75 * fv                                    # board leans out toward its lower edge
    lip = smooth(0.0, 0.04, fv)
    h = h * lip
    grain = fbm(n, 1.4, 41, ax=6.0, ay=0.25)
    seams = np.ones((n, n))
    row = np.floor(y / bh).astype(int)
    off = hash_table(10, 42)[row]
    su = ((x / (n / 1.0)) + off) % 1                         # one butt joint per board per tile
    seams = smooth(0.0, 3.0, np.minimum(su, 1 - su) * n)
    base = colorize(grain, (226, 224, 218), (246, 245, 240))
    shade = 0.62 + 0.38 * lip * (0.85 + 0.15 * fv)
    base *= shade[..., None] * (0.75 + 0.25 * seams[..., None])
    dirt = fbm(n, 2.2, 43)
    base *= (0.94 + 0.08 * dirt[..., None])
    h = h * seams + (grain - 0.5) * 0.05
    save('Siding', base, h, 0.62, 0.0, 9.0, ao_k=2.0)


def shingle():
    """2 m tile of asphalt shingles: 10 courses of 0.2 m, 6 tabs per course, staggered (v runs up the roof)."""
    n = 1024
    x, y = grid(n)
    ch = n / 10
    row = np.floor(y / ch)
    tx = x / (n / 6) + (row % 2) * 0.5
    col = np.floor(tx) % 6
    fu, fv = tx - np.floor(tx), y / ch - row                # fv 0 at top (up-roof), 1 at exposed lower edge
    edge = smooth(0, 3, np.minimum(fu, 1 - fu) * (n / 6))
    h = (0.3 + 0.7 * fv) * smooth(0.0, 0.05, fv) * (0.6 + 0.4 * edge)
    idx = (row * 6 + col).astype(int)
    hv = hash_table(60, 51)[idx]
    grit = band(n, 360, 140, 52)
    base = colorize(hv, (66, 64, 62), (98, 94, 90))
    base *= (0.8 + 0.35 * grit[..., None])
    base *= (0.55 + 0.45 * smooth(0.0, 0.08, fv))[..., None] * (0.7 + 0.3 * edge[..., None])
    weather = fbm(n, 2.0, 53)
    base *= (0.9 + 0.15 * weather[..., None])
    h = h + (grit - 0.5) * 0.1
    save('Shingle', base, h, 0.92, 0.0, 7.0, ao_k=2.5)


def gravel():
    """4 m tile of a ballasted flat roof: grey gravel over membrane."""
    n = 1024
    stones = band(n, 420, 160, 61)
    big = band(n, 180, 60, 62)
    blot = fbm(n, 2.2, 63)
    t = np.clip(stones * 0.6 + big * 0.4, 0, 1)
    base = colorize(t, (92, 90, 86), (168, 164, 156)) * (0.85 + 0.2 * blot[..., None])
    h = smooth(0.35, 0.8, stones) * 0.6 + big * 0.4
    save('Gravel', base, h, 0.95, 0.0, 5.0, ao_k=3.0)


def corrugated():
    """2 m tile of painted corrugated cladding, ribs vertical (76 mm pitch), near-white for tinting."""
    n = 1024
    x, y = grid(n)
    ribs = 26
    ph = x / n * ribs * 2 * np.pi
    h = 0.5 + 0.5 * np.sin(ph)
    streak = fbm(n, 2.0, 71, ax=0.1, ay=3.0)
    rust = smooth(0.72, 0.9, fbm(n, 1.8, 72)) * smooth(0.4, 0.9, streak)
    paint = fbm(n, 1.6, 73, fmin=10)
    base = colorize(paint, (214, 216, 214), (232, 234, 232))
    base *= (0.86 + 0.14 * h[..., None]) * (1 - 0.12 * smooth(0.5, 0.95, streak)[..., None])
    base = base * (1 - rust[..., None] * 0.55) + np.array([0.42, 0.24, 0.14]) * rust[..., None] * 0.55
    rough = 0.5 + 0.35 * rust
    metal = 0.25 * (1 - rust)
    save('Corrugated', base, h, rough, metal, 14.0, ao_k=1.0)


def trim():
    n = 512
    f = fbm(n, 1.4, 81, fmin=12)
    base = colorize(f, (232, 230, 224), (246, 245, 240))
    save('Trim', base, f * 0.3, 0.42, 0.0, 1.0, ao=np.ones((n, n)))


def metal_dark():
    n = 512
    brush = fbm(n, 1.0, 91, ax=0.02, ay=8.0)
    blot = fbm(n, 2.2, 92)
    base = colorize(brush * 0.5 + blot * 0.5, (44, 46, 50), (64, 66, 70))
    save('MetalDark', base, brush * 0.2, 0.38 + 0.12 * blot, 0.9, 1.0, ao=np.ones((n, n)))


def metal_galv():
    n = 512
    spangle = band(n, 40, 18, 101)
    blot = fbm(n, 2.0, 102)
    base = colorize(spangle * 0.6 + blot * 0.4, (150, 152, 154), (190, 192, 194))
    save('Galvanized', base, spangle * 0.15, 0.36 + 0.2 * blot, 1.0, 0.8, ao=np.ones((n, n)))


def interior_wall():
    n = 1024
    roll = band(n, 90, 40, 111)
    fine = fbm(n, 1.2, 112, fmin=40)
    blot = fbm(n, 2.4, 113)
    base = colorize(blot, (232, 230, 224), (244, 242, 237)) * (0.97 + 0.04 * fine[..., None])
    save('InteriorWall', base, roll * 0.5 + fine * 0.5, 0.86, 0.0, 1.2, ao_k=1.0)


def wood_floor():
    """2 m tile of oak boards: 16 rows of 125 mm, two 1 m boards per row with random end joints."""
    n = 1024
    x, y = grid(n)
    rh = n / 16
    row = np.floor(y / rh).astype(int)
    off = hash_table(16, 121)[row]
    bu = (x / (n / 2) + off) % 2
    bid = (row * 2 + np.floor(bu)).astype(int)
    fu, fv = bu % 1, (y / rh) % 1
    gap = smooth(0.0, 2.0, np.minimum(fv, 1 - fv) * rh) * smooth(0.0, 2.0, np.minimum(fu, 1 - fu) * (n / 2))
    grain = fbm(n, 1.5, 122, ax=12.0, ay=0.6)
    rings = 0.5 + 0.5 * np.sin(grain * 40.0 + hash_table(32, 123)[bid] * 6)
    hv = hash_table(32, 124)[bid]
    base = colorize(np.clip(hv * 0.6 + rings * 0.4, 0, 1), (130, 88, 54), (184, 136, 92))
    base *= (0.85 + 0.15 * grain[..., None])
    base *= (0.35 + 0.65 * gap[..., None])
    h = gap * 0.9 + rings * 0.1
    save('WoodFloor', base, h, 0.48 + 0.1 * (1 - gap), 0.0, 3.0, ao_k=1.5)


def floor_tile():
    """2.4 m tile of 0.6 m porcelain/stone tiles with soft veining and grout lines."""
    n = 1024
    x, y = grid(n)
    tp = n / 4
    fu, fv = (x / tp) % 1, (y / tp) % 1
    d = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)) * tp
    grout = smooth(1.5, 3.0, d)
    tid = (np.floor(x / tp) + 4 * np.floor(y / tp)).astype(int)
    tv = hash_table(16, 131)[tid]
    vein = fbm(n, 2.0, 132)
    vein = 1 - smooth(0.0, 0.04, np.abs(vein - 0.5))
    cloud = fbm(n, 2.2, 133)
    base = colorize(np.clip(cloud * 0.6 + tv * 0.4, 0, 1), (196, 192, 184), (226, 222, 214))
    base *= (1 - 0.2 * vein[..., None])
    gc = np.array([0.45, 0.44, 0.42])
    base = gc + (base - gc) * grout[..., None]
    save('FloorTile', base, grout, 0.22 + 0.5 * (1 - grout), 0.0, 3.0, ao_k=1.0)


def carpet():
    n = 512
    fib = band(n, 200, 80, 141)
    blot = fbm(n, 2.0, 142)
    base = colorize(np.clip(fib * 0.5 + blot * 0.5, 0, 1), (70, 78, 90), (98, 106, 118))
    save('Carpet', base, fib, 0.97, 0.0, 2.0, ao_k=1.0)


def ceiling_tile():
    """1.2 m tile: 2 x 2 mineral-fibre ceiling tiles of 0.6 m in a white T-bar grid."""
    n = 512
    x, y = grid(n)
    tp = n / 2
    fu, fv = (x / tp) % 1, (y / tp) % 1
    d = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)) * tp
    bar = 1 - smooth(4.0, 5.5, d)
    fiss = band(n, 120, 60, 151)
    base = colorize(fiss, (220, 220, 216), (236, 236, 232))
    base = base * (1 - bar[..., None]) + np.array([0.93, 0.93, 0.92]) * bar[..., None]
    h = 1 - bar * 0.6 - smooth(0.6, 0.9, fiss) * 0.1
    save('CeilingTile', base, h, 0.9 - 0.4 * bar, 0.0, 2.0, ao_k=1.5)


def wood():
    """2 m tile of stained hardwood for doors, stair treads and furniture (grain along U)."""
    n = 1024
    grain = fbm(n, 1.6, 161, ax=10.0, ay=0.5)
    rings = 0.5 + 0.5 * np.sin(grain * 55.0)
    pores = band(n, 300, 120, 162, ax=6.0, ay=0.5)
    base = colorize(np.clip(rings * 0.5 + grain * 0.5, 0, 1), (96, 62, 38), (142, 98, 62))
    base *= (0.9 + 0.1 * pores[..., None])
    save('Wood', base, rings * 0.3 + pores * 0.2, 0.55, 0.0, 1.5, ao=np.ones((n, n)))


def fabric():
    n = 512
    x, y = grid(n)
    weave = 0.5 + 0.25 * np.sin(x / n * 2 * np.pi * 96) + 0.25 * np.sin(y / n * 2 * np.pi * 96)
    blot = fbm(n, 2.0, 171)
    base = colorize(np.clip(weave * 0.4 + blot * 0.6, 0, 1), (196, 196, 192), (236, 236, 232))
    save('Fabric', base, weave, 0.95, 0.0, 2.0, ao=np.ones((n, n)))


# ------------------------------------------------------------------ windows
def _interior(n, rng, kind):
    """One fake-interior window image (n x n, sRGB 0-1) seen through glass, plus a smoothness map."""
    x, y = grid(n)
    u, v = x / n, y / n                                    # v = 0 at top
    room = np.array(rng.choice([(46, 44, 42), (38, 40, 46), (50, 46, 40), (34, 36, 38)])) / 255
    img = room * (0.75 + 0.5 * (1 - v))[..., None]           # ceiling lit, floor dark
    ceil = smooth(0.0, 0.02, 0.16 - np.abs(v - 0.08) * 1.0)
    img = img + 0.08 * ceil[..., None]
    # silhouettes of furniture against the back wall
    for _ in range(rng.integers(1, 4)):
        x0, w = rng.uniform(0, 0.8), rng.uniform(0.1, 0.35)
        top = rng.uniform(0.55, 0.8)
        m = (u > x0) & (u < x0 + w) & (v > top)
        img[m] *= rng.uniform(0.45, 0.75)
    if kind == 'lit':
        warm = np.array([1.0, 0.86, 0.62])
        img = img * 1.4 + warm * 0.22 * (1 - v)[..., None]
    if kind in ('curtains', 'sheer'):
        col = np.array(rng.choice([(150, 40, 36), (60, 80, 120), (190, 170, 130), (90, 110, 80), (200, 196, 186)])) / 255
        folds = 0.75 + 0.25 * np.sin(u * 2 * np.pi * rng.uniform(9, 15))
        if kind == 'sheer':
            img = img * 0.45 + col * 0.55 * folds[..., None] * 0.9
        else:
            gap = rng.uniform(0.1, 0.4)
            c0 = 0.5 - gap / 2 + rng.uniform(-0.1, 0.1)
            m = (u < c0) | (u > c0 + gap)
            img = np.where(m[..., None], col * folds[..., None] * (0.8 + 0.2 * (1 - v))[..., None], img)
    if kind == 'blinds':
        drop = rng.uniform(0.25, 1.0)
        slat = 0.6 + 0.4 * smooth(0.2, 0.5, (v * 48) % 1)
        bc = np.array(rng.choice([(210, 206, 196), (180, 182, 184), (150, 130, 100)])) / 255
        m = v < drop
        img = np.where(m[..., None], bc * slat[..., None], img)
        rail = (np.abs(v - drop) < 0.012)
        img[rail] = bc * 0.6
    if kind == 'shade':
        drop = rng.uniform(0.3, 0.9)
        sc = np.array(rng.choice([(222, 216, 200), (120, 120, 116), (200, 160, 110)])) / 255
        img = np.where((v < drop)[..., None], sc * (0.9 + 0.1 * u)[..., None], img)
    # sky reflection on the glass: a soft diagonal sheen, stronger at the top
    sheen = smooth(0.0, 1.0, 1.2 - v - u * 0.5) * 0.10 + smooth(0.5, 0.0, np.abs(u + v * 0.6 - rng.uniform(0.3, 1.1))) * 0.05
    img = img + np.array([0.55, 0.65, 0.78]) * sheen[..., None]
    return np.clip(img, 0, 1)


def window_atlas():
    """2048 atlas, 4 x 4 window interiors (curtains, blinds, shades, dark and lit rooms) for sealed floors."""
    n, c = 2048, 512
    kinds = ['curtains', 'blinds', 'dark', 'shade', 'lit', 'curtains', 'sheer', 'blinds',
             'dark', 'curtains', 'blinds', 'lit', 'shade', 'dark', 'sheer', 'curtains']
    base = np.zeros((n, n, 3))
    rng = np.random.default_rng(201)
    for i, k in enumerate(kinds):
        r, q = divmod(i, 4)
        base[r * c:(r + 1) * c, q * c:(q + 1) * c] = _interior(c, rng, k)
    h = np.zeros((n, n))
    save('WindowFake', base, h, 0.08, 0.1, 0.0, ao=np.ones((n, n)))


def curtain_wall():
    """2048 tile = 8 bays (1.5 m) x 4 floors (3.6 m) of a glass curtain wall: vision glass with interiors,
    back-painted spandrel bands and painted mullion lines (the 3D fins sit on top in LOD0)."""
    n = 2048
    bw, fh = n // 8, n // 4
    base = np.zeros((n, n, 3))
    rough = np.zeros((n, n))
    metal = np.zeros((n, n))
    rng = np.random.default_rng(301)
    glass = np.array([0.20, 0.30, 0.36])
    kinds = ['dark', 'blinds', 'dark', 'lit', 'blinds', 'dark', 'shade', 'dark']
    spand_h = int(fh * 0.25)
    for f in range(4):
        y0 = f * fh
        for b in range(8):
            x0 = b * bw
            cell = _interior(bw, rng, kinds[rng.integers(0, len(kinds))])
            cell = np.repeat(cell[np.linspace(0, bw - 1, fh - spand_h).astype(int)], 1, axis=0)
            vis = cell * 0.55 + glass * 0.45
            base[y0:y0 + fh - spand_h, x0:x0 + bw] = vis
            rough[y0:y0 + fh - spand_h, x0:x0 + bw] = 0.05
            metal[y0:y0 + fh - spand_h, x0:x0 + bw] = 0.35
            sp = glass * 0.55 + rng.uniform(-0.01, 0.01)
            base[y0 + fh - spand_h:y0 + fh, x0:x0 + bw] = sp
            rough[y0 + fh - spand_h:y0 + fh, x0:x0 + bw] = 0.12
            metal[y0 + fh - spand_h:y0 + fh, x0:x0 + bw] = 0.5
    x, y = grid(n)
    mull = (np.minimum((x % bw), bw - (x % bw)) < 3) | (np.minimum((y % fh), fh - (y % fh)) < 3) | \
           (np.abs((y % fh) - (fh - spand_h)) < 2)
    base[mull] = np.array([0.16, 0.17, 0.18])
    rough[mull] = 0.4
    metal[mull] = 0.9
    h = (~mull).astype(float)
    save('CurtainWall', base, h, rough, metal, 2.0, ao=np.ones((n, n)))


ALL = {f.__name__: f for f in (brick, plaster, concrete, siding, shingle, gravel, corrugated, trim, metal_dark, metal_galv,
                                interior_wall, wood_floor, floor_tile, carpet, ceiling_tile, wood, fabric, window_atlas,
                                curtain_wall)}

if __name__ == '__main__':
    names = sys.argv[1:] or list(ALL)
    for nm in names:
        ALL[nm]()
