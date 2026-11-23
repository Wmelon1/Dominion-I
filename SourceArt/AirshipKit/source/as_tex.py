# Airship Kit - tileable texture sets generated with numpy (BaseColor sRGB, ORM, Normal).
# All maps wrap seamlessly; arrays are (rows=v, cols=u), row 0 = bottom of the image (Blender order).
import numpy as np


def _vnoise(w, h, cx, cy, rng):
    lat = rng.random((cy, cx)).astype(np.float32)
    xs = np.arange(w, dtype=np.float32) * cx / w
    ys = np.arange(h, dtype=np.float32) * cy / h
    x0 = np.floor(xs).astype(np.int64); fx = xs - x0; fx = fx * fx * (3 - 2 * fx); x1 = (x0 + 1) % cx
    y0 = np.floor(ys).astype(np.int64); fy = ys - y0; fy = fy * fy * (3 - 2 * fy); y1 = (y0 + 1) % cy
    a = lat[y0][:, x0]; b = lat[y0][:, x1]; c = lat[y1][:, x0]; d = lat[y1][:, x1]
    fx = fx[None, :]; fy = fy[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(w, h, cx, cy, octaves=4, seed=0, pers=0.5):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32); amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += amp * _vnoise(w, h, cx * 2 ** o, cy * 2 ** o, rng)
        tot += amp; amp *= pers
    return out / tot


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def blur(a, r=2):
    out = a.copy()
    for _ in range(2):
        acc = np.zeros_like(out)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                acc += np.roll(np.roll(out, dy, 0), dx, 1)
        out = acc / (2 * r + 1) ** 2
    return out


def normal_from_height(H, strength):
    dx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * 0.5 * strength
    dy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * 0.5 * strength
    n = np.stack([-dx, -dy, np.ones_like(H)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def ao_from_height(H, r=3, k=4.0):
    return np.clip(1.0 - np.maximum(blur(H, r) - H, 0) * k, 0.35, 1.0)


def lerp(a, b, t):
    t = t[..., None] if np.ndim(t) == 2 else t
    return a + (np.asarray(b, np.float32) - a) * t


def solid(h, w, c):
    out = np.empty((h, w, 3), np.float32)
    out[:] = c
    return out


def pack(col, ao, rough, metal, H, nstrength):
    orm = np.stack([ao, rough, metal], -1)
    return np.clip(col, 0, 1), np.clip(orm, 0, 1), normal_from_height(H, nstrength)


# --------------------------------------------------------------------------- envelope fabric
def tex_envelope(w=512, h=2048):
    """u = one gore (seams at u=0/1), v = 10 m between ring frames (tape at v=0, lacing at v=0.5)."""
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    u /= w; v /= h
    col = solid(h, w, (0.46, 0.48, 0.42))
    panel = np.floor(v * 4).astype(int)
    tint = np.array([1.0, 0.965, 1.02, 0.985], np.float32)[panel % 4]
    col *= tint[..., None]
    big = fbm(w, h, 2, 10, 5, 11)
    col *= (0.9 + 0.2 * big)[..., None]
    dirt = sstep(0.55, 0.8, fbm(w, h, 4, 24, 4, 12))
    col = lerp(col, (0.28, 0.29, 0.25), dirt * 0.45)
    weave = 0.5 + 0.25 * np.sin(u * np.pi * 2 * 120) * np.sin(v * np.pi * 2 * 960)
    du = np.minimum(u, 1 - u) * w                      # pixels to the gore seam
    seam = 1 - sstep(4, 7, du)
    stitch = (np.sin(v * np.pi * 2 * 600) > 0.6) * (np.abs(du - 5.5) < 1.2)
    dv = np.minimum(v, 1 - v) * h
    frame = 1 - sstep(14, 20, dv)
    dl = np.abs(v - 0.5) * h
    lacing = 1 - sstep(5, 8, dl)
    lace_dots = lacing * (np.sin(u * np.pi * 2 * 24) > 0.7)
    pucker = sstep(0, 40, du) * 0.6 + 0.4
    H = weave * 0.08 + seam * 0.9 + frame * 1.0 + lacing * 0.5 + lace_dots * 0.3 - (1 - pucker) * 0.3
    H += fbm(w, h, 8, 32, 3, 13) * 0.25
    col = lerp(col, (0.36, 0.37, 0.32), np.clip(seam + frame * 0.9 + lacing * 0.6, 0, 1))
    col = lerp(col, (0.22, 0.2, 0.17), stitch.astype(np.float32) * 0.8 + lace_dots * 0.6)
    ao = ao_from_height(H, 4, 3.0)
    col *= (0.75 + 0.25 * ao)[..., None]
    rough = 0.74 + 0.08 * fbm(w, h, 8, 32, 3, 14) - frame * 0.1
    return pack(col, ao, rough, np.zeros_like(H), H, 6.0)


# --------------------------------------------------------------------------- hull plating
def tex_plating(n=1024):
    """3 m x 2 m tile: 2 x 2 lapped plates, rivet rows, chipped paint, streaks."""
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    P = n // 2
    px, py = u % P, v % P
    pid = (u // P) + 2 * (v // P)
    rng = np.random.default_rng(3)
    tints = rng.uniform(0.94, 1.06, 4).astype(np.float32)
    base = np.array((0.34, 0.38, 0.34), np.float32)
    col = solid(n, n, base) * tints[pid.astype(int)][..., None]
    col *= (0.93 + 0.14 * fbm(n, n, 4, 4, 5, 31))[..., None]
    edge_d = np.minimum(np.minimum(px, P - 1 - px), np.minimum(py, P - 1 - py))
    groove = 1 - sstep(1.5, 3.5, edge_d)
    lap = (px / P) * 0.35
    riv = np.zeros_like(u)
    for c in (14.0, P - 15.0):
        d = np.sqrt((px - c) ** 2 + ((py % 22) - 11) ** 2)
        riv = np.maximum(riv, np.clip(1 - (d / 4.5) ** 2, 0, 1))
        d = np.sqrt((py - c) ** 2 + ((px % 22) - 11) ** 2)
        riv = np.maximum(riv, np.clip(1 - (d / 4.5) ** 2, 0, 1))
    H = lap - groove * 1.2 + riv * 0.9 + fbm(n, n, 16, 16, 3, 32) * 0.12
    near = 1 - sstep(10, 40, edge_d)
    chips = sstep(0.62, 0.66, fbm(n, n, 24, 24, 4, 33)) * (0.35 + 0.65 * near)
    streak = sstep(0.45, 0.75, fbm(n, n, 48, 2, 3, 34)) * (1 - py / P) ** 1.5
    rust = sstep(0.55, 0.75, fbm(n, n, 40, 3, 3, 35)) * (1 - py / P) ** 2 * 0.6
    col = lerp(col, (0.22, 0.23, 0.2), streak * 0.5)
    col = lerp(col, (0.33, 0.2, 0.11), rust)
    col = lerp(col, (0.2, 0.2, 0.19), groove * 0.7)
    col = lerp(col, (0.52, 0.52, 0.5), chips)
    ao = ao_from_height(H, 3, 3.0)
    col *= (0.7 + 0.3 * ao)[..., None]
    rough = 0.55 + 0.1 * fbm(n, n, 8, 8, 3, 36) + streak * 0.1 - chips * 0.25
    metal = chips * 0.9
    return pack(col, ao, rough, metal, H, 5.0)


# --------------------------------------------------------------------------- wooden deck planks
def tex_planks(n=1024, planks=11):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    pw = n / planks
    pid = np.floor(u / pw).astype(int)
    lx = (u - pid * pw) / pw
    rng = np.random.default_rng(5)
    joint = rng.uniform(0, n, planks).astype(np.float32)[pid]
    tone = rng.uniform(0.85, 1.12, planks).astype(np.float32)[pid]
    dj = np.abs(((v - joint + n / 2) % n) - n / 2)
    gap = np.maximum(1 - sstep(0.0, 0.035, np.minimum(lx, 1 - lx)), 1 - sstep(1.0, 3.0, dj))
    warp = fbm(n, n, 4, 2, 4, 51) * 6
    grain = 0.5 + 0.5 * np.sin((lx * 9 + warp + pid * 1.7) * np.pi * 2)
    fine = fbm(n, n, 64, 4, 3, 52)
    col = solid(n, n, (0.50, 0.36, 0.22)) * tone[..., None]
    col = lerp(col, (0.36, 0.24, 0.14), grain * 0.35 + fine * 0.2)
    wear = sstep(0.4, 0.8, fbm(n, n, 3, 3, 4, 53))
    col = lerp(col, (0.6, 0.47, 0.32), wear * 0.25)
    nails = np.zeros_like(u)
    for off in (-1, 1):
        for xo in (0.25, 0.75):
            d = np.sqrt(((lx - xo) * pw) ** 2 + (dj - 8 + off * 0) ** 2)
            nails = np.maximum(nails, 1 - sstep(1.5, 3.0, d))
    col = lerp(col, (0.12, 0.1, 0.08), np.clip(gap + nails * 0.8, 0, 1))
    H = -gap * 1.2 + grain * 0.15 + fine * 0.2 - nails * 0.3
    ao = ao_from_height(H, 3, 3.0)
    col *= (0.75 + 0.25 * ao)[..., None]
    rough = 0.68 + 0.1 * fine - wear * 0.12
    return pack(col, ao, rough, np.zeros_like(H), H, 4.0)


# --------------------------------------------------------------------------- interior wall panels
def tex_wall(n=1024):
    """2 m (u) x 3 m (v) tile: kick plate, green lower panel, chair rail, cream upper, top band."""
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    m = v / n * 3.0
    col = solid(n, n, (0.80, 0.76, 0.64))
    lower = m < 1.0
    col[lower] = (0.24, 0.33, 0.25)
    col[m < 0.12] = (0.2, 0.21, 0.2)
    rail = (m >= 1.0) & (m < 1.08)
    col[rail] = (0.32, 0.21, 0.12)
    col[m > 2.86] = (0.32, 0.32, 0.29)
    lx = (u % (n / 2)) / (n / 2)
    seam = 1 - sstep(0.004, 0.01, np.minimum(lx, 1 - lx))
    riv = np.zeros_like(u)
    for c in (0.02, 0.98):
        d = np.sqrt(((lx - c) * n / 2) ** 2 + ((v % 24) - 12) ** 2)
        riv = np.maximum(riv, np.clip(1 - (d / 3.5) ** 2, 0, 1))
    grime = sstep(0.45, 0.8, fbm(n, n, 6, 9, 4, 61)) * (0.4 + 0.6 * (1 - np.clip(m / 3, 0, 1)))
    scuff = sstep(0.7, 0.75, fbm(n, n, 40, 12, 3, 62)) * (m < 0.9)
    col *= (0.94 + 0.12 * fbm(n, n, 8, 12, 3, 63))[..., None]
    col = lerp(col, (0.25, 0.23, 0.19), grime * 0.35)
    col = lerp(col, (0.45, 0.45, 0.42), scuff * 0.6)
    col = lerp(col, (0.2, 0.2, 0.18), seam * 0.6)
    H = -seam + riv * 0.8 + rail * 0.8 + (m < 0.12) * 0.4 + fbm(n, n, 32, 48, 3, 64) * 0.06
    ao = ao_from_height(H, 3, 3.0)
    col *= (0.75 + 0.25 * ao)[..., None]
    rough = 0.6 + grime * 0.15 - rail * 0.15
    metal = (m < 0.12) * 0.6 + scuff * 0.5
    return pack(col, ao, rough, metal, H, 4.0)


# --------------------------------------------------------------------------- dark metal
def tex_darkmetal(n=1024):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    brushed = fbm(n, n, 2, 128, 3, 71)
    col = solid(n, n, (0.17, 0.175, 0.18)) * (0.85 + 0.3 * brushed)[..., None]
    oil = sstep(0.55, 0.8, fbm(n, n, 5, 5, 5, 72))
    scratches = sstep(0.82, 0.86, fbm(n, n, 3, 96, 2, 73)) + sstep(0.82, 0.86, fbm(n, n, 96, 3, 2, 74))
    riv = np.zeros_like(u)
    for c in (32.0, n - 33.0):
        d = np.sqrt((u - c) ** 2 + ((v % 32) - 16) ** 2)
        riv = np.maximum(riv, np.clip(1 - (d / 5) ** 2, 0, 1))
    col = lerp(col, (0.08, 0.075, 0.07), oil * 0.6)
    col = lerp(col, (0.42, 0.42, 0.42), np.clip(scratches, 0, 1) * 0.6)
    H = brushed * 0.2 + riv + scratches * -0.2
    ao = ao_from_height(H, 3, 3.0)
    rough = 0.48 + oil * 0.15 - np.clip(scratches, 0, 1) * 0.2
    metal = 0.8 - oil * 0.3
    return pack(col, ao, rough, metal, H, 4.0)


def tex_brass(n=256):
    tar = fbm(n, n, 4, 4, 5, 81)
    col = lerp(solid(n, n, (0.74, 0.54, 0.25)), (0.38, 0.33, 0.2), sstep(0.45, 0.85, tar) * 0.7)
    H = fbm(n, n, 16, 16, 3, 82) * 0.3
    return pack(col, np.ones_like(tar) * 0.95, 0.28 + tar * 0.3, np.ones_like(tar) * 0.95, H, 2.0)


def tex_canvas(n=512):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    weave = 0.5 + 0.25 * np.sin(u * np.pi * 2 * 140) + 0.25 * np.sin(v * np.pi * 2 * 140)
    stitch = (np.abs(u - 0.5) < 0.004) * (np.sin(v * np.pi * 2 * 60) > 0.3)
    col = solid(n, n, (0.38, 0.36, 0.25)) * (0.9 + 0.2 * fbm(n, n, 6, 6, 4, 91))[..., None]
    col = lerp(col, (0.22, 0.2, 0.14), stitch * 0.8 + sstep(0.6, 0.85, fbm(n, n, 8, 8, 3, 92)) * 0.3)
    H = weave * 0.3 - stitch * 0.4 + fbm(n, n, 12, 12, 3, 93) * 0.3
    return pack(col, ao_from_height(H, 2, 2.0), 0.85 + 0.0 * H, np.zeros_like(H), H, 3.0)


def tex_emblem(n=1024):
    """fictional faction emblem: ring, red field, white wings, gold star (RGBA)."""
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    x, y = (u - n / 2) / (n / 2), (v - n / 2) / (n / 2)
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    col = solid(n, n, (0.55, 0.08, 0.06))
    ring = (r > 0.84) & (r < 0.98)
    col[ring] = (0.09, 0.11, 0.18)
    col[(r > 0.80) & (r <= 0.84)] = (0.82, 0.7, 0.36)
    ax = np.abs(x)
    f = np.clip((ax - 0.13) / 0.72, 0, 1)
    top = 0.04 + 0.34 * f ** 0.8
    bot = top - (0.07 + 0.22 * (1 - f) ** 1.1) - 0.06 * np.abs(np.sin(f * np.pi * 7))
    wings = (ax > 0.13) & (ax < 0.85) & (y < top) & (y > bot)
    col[wings] = (0.92, 0.9, 0.84)
    fl = wings & (np.abs(np.sin(f * np.pi * 7)) < 0.12) & (y < top - 0.05)
    col[fl] = (0.55, 0.52, 0.47)
    R, ri, k = 0.30, 0.13, 5
    a = (th - np.pi / 2) % (2 * np.pi / k)
    a = np.minimum(a, 2 * np.pi / k - a)
    s5 = np.sin(np.pi / k)
    edge = R * ri * s5 / (R * np.sin(a) + ri * np.sin(np.pi / k - a) + 1e-6)
    star = r < edge
    col[star] = (0.92, 0.75, 0.3)
    col[star & (r < edge - 0.025)] = (0.98, 0.84, 0.4)
    alpha = (r < 0.98).astype(np.float32)
    grime = fbm(n, n, 6, 6, 4, 101)
    col *= (0.85 + 0.2 * grime)[..., None]
    return np.clip(col, 0, 1), alpha
