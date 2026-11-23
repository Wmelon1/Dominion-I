# Procedural VFX textures for Dominion I (smoke, fire, sparks, rings, debris, ground cracks decal).
import numpy as np, math, os
from PIL import Image, ImageDraw, ImageFilter
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Assets', 'Dominion', 'Resources', 'Dominion', 'VFX')
rng = np.random.default_rng(11)

def noise(n, octaves=5, seed=0, base=4):
    r = np.random.default_rng(seed); out = np.zeros((n, n), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        c = base * 2 ** o
        g = r.random((c + 1, c + 1)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)
        out += np.asarray(img, np.float32) / 255.0 * amp; tot += amp; amp *= 0.55
    return out / tot

def save(a, name, mode='RGBA'):
    Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), mode).save(os.path.join(OUT, name))

S = 256
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
u = (xx + 0.5) / S * 2 - 1
v = 1 - (yy + 0.5) / S * 2            # +v = up in the image (top)
r = np.sqrt(u * u + v * v)

def puff(seed, lumpy=0.45):
    n = noise(S, 5, seed, 3)
    n2 = noise(S, 4, seed + 7, 6)
    edge = 1 - r / (0.92 - lumpy * 0.35 * (n - 0.5))
    a = np.clip(edge * 1.6, 0, 1) ** 1.3 * (0.55 + 0.6 * n2)
    a = np.clip(a, 0, 1)
    # fake volumetric shading: height field -> light from the top-left (sun side), soft self-shadow underneath
    h = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)), np.float32) / 255
    gy, gx = np.gradient(h)
    nz = 0.08
    nrm = np.dstack([-gx, gy, np.full_like(h, nz)]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    L = np.array([-0.45, 0.75, 0.5]); L /= np.linalg.norm(L)
    lit = np.clip((nrm * L).sum(2), 0, 1)
    shade = 0.5 + 0.5 * lit + 0.1 * (n2 - 0.5)
    shade *= 0.85 + 0.15 * np.clip(v * 0.5 + 0.5, 0, 1)
    return np.dstack([shade, shade, shade, a])

def sheet(tiles):
    top = np.concatenate([tiles[0], tiles[1]], axis=1)
    bot = np.concatenate([tiles[2], tiles[3]], axis=1)
    return np.concatenate([top, bot], axis=0)

save(sheet([puff(s) for s in (1, 2, 3, 4)]), 'T_FX_Smoke.png')

def fire(seed):
    n = noise(S, 5, seed, 4)
    n2 = noise(S, 3, seed + 3, 8)
    d = r / (0.85 + 0.25 * (n - 0.5))
    I = np.clip(1 - d, 0, 1) ** 1.2 * (0.6 + 0.7 * n2)
    I = np.clip(I * 1.4, 0, 1)
    hot = np.array([1.0, 0.95, 0.75]); mid = np.array([1.0, 0.55, 0.12]); cold = np.array([0.55, 0.12, 0.02])
    t = I[..., None]
    col = np.where(t > 0.5, mid + (hot - mid) * ((t - 0.5) * 2), cold + (mid - cold) * (t * 2))
    return np.dstack([col * I[..., None], I])      # premultiplied for additive blending
save(sheet([fire(s) for s in (5, 6, 7, 8)]), 'T_FX_Fire.png')

dot = np.clip(1 - r, 0, 1) ** 2.2
save(np.dstack([dot, dot * 0.9, dot * 0.7, dot]), 'T_FX_Spark.png')

ring_n = noise(S * 2, 4, 21, 8)
Y2, X2 = np.mgrid[0:S * 2, 0:S * 2].astype(np.float32)
U2 = (X2 + 0.5) / (S * 2) * 2 - 1; V2 = (Y2 + 0.5) / (S * 2) * 2 - 1
R2 = np.sqrt(U2 * U2 + V2 * V2)
ring = np.exp(-((R2 - 0.85) / 0.06) ** 2) * (0.6 + 0.6 * ring_n) + np.exp(-((R2 - 0.7) / 0.18) ** 2) * 0.25 * ring_n
ring = np.clip(ring, 0, 1) * (R2 < 1)
save(np.dstack([ring, ring, ring, ring]), 'T_FX_Ring.png')
dustring = np.clip(np.exp(-((R2 - 0.78) / 0.16) ** 2) * (0.4 + 0.9 * ring_n), 0, 1) * (R2 < 1)
save(np.dstack([np.full_like(dustring, 0.62), np.full_like(dustring, 0.55), np.full_like(dustring, 0.45), dustring]), 'T_FX_DustRing.png')

# debris chunk (irregular polygon, rough shading)
deb = np.zeros((S, S, 4), np.float32)
img = Image.new('L', (S, S), 0); d = ImageDraw.Draw(img)
pts = [(S / 2 + math.cos(a) * S * (0.32 + 0.12 * rng.random()), S / 2 + math.sin(a) * S * (0.32 + 0.12 * rng.random()))
       for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
d.polygon(pts, fill=255)
m = np.asarray(img.filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
sh = 0.35 + 0.4 * noise(S, 4, 31, 6)
deb[..., 0] = sh * 0.95; deb[..., 1] = sh * 0.9; deb[..., 2] = sh * 0.82; deb[..., 3] = m
save(deb, 'T_FX_Debris.png')

# ground cracks + scorch decal (1024): branching fractures from the centre, ring fractures, scorched burn
N = 1024
crack = Image.new('L', (N, N), 0); cd = ImageDraw.Draw(crack)
def branch(x, y, ang, length, width, depth):
    seg = 14
    for i in range(int(length / seg)):
        ang += rng.normal(0, 0.28)
        nx, ny = x + math.cos(ang) * seg, y + math.sin(ang) * seg
        cd.line([(x, y), (nx, ny)], fill=255, width=max(1, int(width)))
        x, y = nx, ny
        width *= 0.985
        if depth < 3 and rng.random() < 0.07:
            branch(x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.4, 1.0), length * rng.uniform(0.25, 0.5), width * 0.7, depth + 1)
c = N / 2
for k in range(11):
    a = k / 11 * 2 * math.pi + rng.normal(0, 0.18)
    branch(c + math.cos(a) * 30, c + math.sin(a) * 30, a, rng.uniform(300, 480), rng.uniform(13, 20), 0)
for rr in (130, 230):
    a0 = rng.uniform(0, 6.28)
    for k in range(5):
        a1 = a0 + k * 1.25 + rng.uniform(0, 0.5); span = rng.uniform(0.3, 0.7)
        pts = [(c + math.cos(a1 + t * span) * (rr + rng.normal(0, 6)), c + math.sin(a1 + t * span) * (rr + rng.normal(0, 6))) for t in np.linspace(0, 1, 12)]
        cd.line(pts, fill=255, width=7)
cm = np.asarray(crack.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
Yc, Xc = np.mgrid[0:N, 0:N].astype(np.float32)
Rc = np.sqrt((Xc - c) ** 2 + (Yc - c) ** 2) / (N / 2)
nn = noise(N, 6, 41, 4)
scorch = np.clip(1 - Rc / (0.42 + 0.25 * (nn - 0.5)), 0, 1) ** 1.4
scorch = np.clip(scorch * 1.35, 0, 1)
alpha = np.clip(np.maximum(cm * 1.0, scorch * 0.95) * np.clip((1 - Rc) * 4, 0, 1), 0, 1)
col = np.dstack([0.09 + 0.08 * nn, 0.08 + 0.06 * nn, 0.07 + 0.05 * nn])
col = col * (1 - cm[..., None] * 0.85)
save(np.dstack([col, alpha]), 'T_FX_Cracks.png')
hgt = 1 - cm * 0.9 - scorch * 0.15 + 0.05 * nn
gy, gx = np.gradient(np.asarray(Image.fromarray((np.clip(hgt, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255)
nrm = np.dstack([-gx * 18, gy * 18, np.ones_like(gx)]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
save(nrm * 0.5 + 0.5, 'T_FX_Cracks_Normal.png', 'RGB')
print('vfx textures written to', OUT)
