# Dominion I - BuildingKit geometry library (Blender 5.x). Executed with exec() from a driver that defines KIT_DIR.
#
# Every building is generated into three builders at once:
#   g0  LOD0  - full detail: window frames, glass, sills, reveals, doors, interiors where a floor is "open"
#   g1  LOD1  - exterior shell: flat walls with window quads, roofs, big roof props (no interior)
#   gc  Collider - closed boxes only: walls with door and open-window holes, slabs, stair ramps, roofs, big furniture
# UVs are planar in world metres divided by each material's tile size (v runs up walls and up roof slopes),
# so the shared tiling materials line up across the whole kit with a material tiling of 1.
import bpy, bmesh, math, os, json, random
from mathutils import Vector, Matrix

KIT_DIR = globals().get('KIT_DIR')
TEX_DIR = os.path.join(KIT_DIR, 'textures')
Z = Vector((0.0, 0.0, 1.0))

# name: (texture stem or None, sRGB tint, tile metres (u, v) or None for explicit UVs, kind)
MATS = {
    'BLD_Brick': ('Brick', 'ffffff', 1.8, 'lit'),
    'BLD_BrickDark': ('Brick', '9a9290', 1.8, 'lit'),
    'BLD_Plaster_Cream': ('Plaster', 'f0e2c4', 3.0, 'lit'),
    'BLD_Plaster_Sage': ('Plaster', 'c4cfb6', 3.0, 'lit'),
    'BLD_Plaster_White': ('Plaster', 'ffffff', 3.0, 'lit'),
    'BLD_Plaster_Terracotta': ('Plaster', 'd8a07e', 3.0, 'lit'),
    'BLD_Concrete': ('Concrete', 'ffffff', 3.0, 'lit'),
    'BLD_ConcreteDark': ('Concrete', 'a4a29e', 3.0, 'lit'),
    'BLD_Stone': ('Concrete', 'efe6d2', 3.0, 'lit'),
    'BLD_Siding_White': ('Siding', 'ffffff', 2.0, 'lit'),
    'BLD_Siding_Blue': ('Siding', 'a9bccd', 2.0, 'lit'),
    'BLD_Siding_Yellow': ('Siding', 'e8d79e', 2.0, 'lit'),
    'BLD_Shingle': ('Shingle', 'ffffff', 2.0, 'lit'),
    'BLD_Shingle_Red': ('Shingle', 'c98670', 2.0, 'lit'),
    'BLD_Gravel': ('Gravel', 'ffffff', 4.0, 'lit'),
    'BLD_Corrugated': ('Corrugated', 'b9c3c9', 2.0, 'lit'),
    'BLD_Corrugated_Red': ('Corrugated', 'b86a56', 2.0, 'lit'),
    'BLD_Trim': ('Trim', 'ffffff', 1.0, 'lit'),
    'BLD_TrimGreen': ('Trim', '4f6a58', 1.0, 'lit'),
    'BLD_TrimRed': ('Trim', '8e3a32', 1.0, 'lit'),
    'BLD_MetalDark': ('MetalDark', 'ffffff', 1.0, 'lit'),
    'BLD_Galvanized': ('Galvanized', 'ffffff', 1.5, 'lit'),
    'BLD_InteriorWall': ('InteriorWall', 'ffffff', 3.0, 'lit'),
    'BLD_InteriorWall_Warm': ('InteriorWall', 'eadcc0', 3.0, 'lit'),
    'BLD_InteriorWall_Blue': ('InteriorWall', 'c6d4e0', 3.0, 'lit'),
    'BLD_InteriorWall_Green': ('InteriorWall', 'cddabf', 3.0, 'lit'),
    'BLD_WoodFloor': ('WoodFloor', 'ffffff', 2.0, 'lit'),
    'BLD_FloorTile': ('FloorTile', 'ffffff', 2.4, 'lit'),
    'BLD_Carpet': ('Carpet', 'ffffff', 2.0, 'lit'),
    'BLD_CeilingTile': ('CeilingTile', 'ffffff', 1.2, 'lit'),
    'BLD_Wood': ('Wood', 'ffffff', 2.0, 'lit'),
    'BLD_Fabric': ('Fabric', '7d90a8', 1.0, 'lit'),
    'BLD_Fabric_Red': ('Fabric', 'a85448', 1.0, 'lit'),
    'BLD_Fabric_Beige': ('Fabric', 'cfc2a8', 1.0, 'lit'),
    'BLD_WindowFake': ('WindowFake', 'ffffff', None, 'lit'),
    'BLD_CurtainWall': ('CurtainWall', 'ffffff', (12.0, 14.4), 'lit'),
    'BLD_Glass': (None, 'a9c4cc', 1.0, 'glass'),
}
ATLAS = 4                                   # WindowFake is 4 x 4 cells
DARK_CELLS = [2, 8, 13]                     # empty dark rooms (used for doorways in LOD1)
ROUGH = {'BLD_Glass': 0.04}


def srgb_to_lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def tile_of(m):
    t = MATS[m][2]
    if t is None:
        return None
    return (t, t) if isinstance(t, (int, float)) else t


def newell(pts):
    n = Vector()
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n.x += (p.y - q.y) * (p.z + q.z)
        n.y += (p.z - q.z) * (p.x + q.x)
        n.z += (p.x - q.x) * (p.y + q.y)
    return n


def planar_uv(pts, mat):
    n = newell(pts)
    if n.length < 1e-12:
        return [(0, 0)] * len(pts)
    n.normalize()
    tu, tv = tile_of(mat) or (1.0, 1.0)
    if abs(n.z) > 0.999:
        eu, ev = Vector((1, 0, 0)), Vector((0, 1 if n.z > 0 else -1, 0))
    else:
        ev = (Z - n * n.z).normalized()
        eu = ev.cross(n)
    return [(p.dot(eu) / tu, p.dot(ev) / tv) for p in pts]


# ------------------------------------------------------------------ mesh builder
class G:
    def __init__(self):
        self.V, self.F = [], []

    def poly(self, pts, mat, uv=None, smooth=False, normal=None):
        pts = [Vector(p) for p in pts]
        nn = newell(pts)
        if nn.length < 1e-9:
            return
        if normal is not None and nn.dot(Vector(normal)) < 0:
            pts.reverse()
            if uv:
                uv = list(reversed(uv))
        b = len(self.V)
        self.V.extend(pts)
        self.F.append((list(range(b, b + len(pts))), mat, uv, smooth))

    def quad(self, p0, p1, p2, p3, mat, normal=None, uv=None):
        self.poly([p0, p1, p2, p3], mat, uv, normal=normal)

    def obox(self, o, ax, ay, az, mat, skip=(), mats=None, smooth=False):
        """Box from corner o along edge vectors ax, ay, az. Faces named by local axis: -x +x -y +y -z +z."""
        o = Vector(o)
        c = [o + ax * i + ay * j + az * k for k in (0, 1) for j in (0, 1) for i in (0, 1)]
        faces = {'-x': (0, 2, 6, 4), '+x': (1, 3, 7, 5), '-y': (0, 1, 5, 4), '+y': (2, 6, 7, 3),
                 '-z': (0, 2, 3, 1), '+z': (4, 5, 7, 6)}
        ctr = o + (ax + ay + az) * 0.5
        for k, idx in faces.items():
            if k in skip:
                continue
            pts = [c[i] for i in idx]
            fc = sum(pts, Vector()) / 4
            self.poly(pts, (mats or {}).get(k, mat), normal=fc - ctr, smooth=smooth)

    def box(self, x0, y0, z0, x1, y1, z1, mat, skip=(), mats=None):
        if x1 - x0 < 1e-5 or y1 - y0 < 1e-5 or z1 - z0 < 1e-5:
            return
        self.obox(Vector((x0, y0, z0)), Vector((x1 - x0, 0, 0)), Vector((0, y1 - y0, 0)), Vector((0, 0, z1 - z0)),
                  mat, skip, mats)

    def cyl(self, cx, cy, z0, z1, r, segs, mat, top=True, bottom=False, mat_cap=None, r1=None):
        r1 = r if r1 is None else r1
        ring = [(math.cos(i / segs * math.tau), math.sin(i / segs * math.tau)) for i in range(segs)]
        for i in range(segs):
            a, b = ring[i], ring[(i + 1) % segs]
            pts = [(cx + a[0] * r, cy + a[1] * r, z0), (cx + b[0] * r, cy + b[1] * r, z0),
                   (cx + b[0] * r1, cy + b[1] * r1, z1), (cx + a[0] * r1, cy + a[1] * r1, z1)]
            mid = Vector(((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, 0))
            u0, u1 = i / segs * math.tau * r / 1.0, (i + 1) / segs * math.tau * r / 1.0
            tu, tv = tile_of(mat) or (1, 1)
            uv = [(u0 / tu, z0 / tv), (u1 / tu, z0 / tv), (u1 / tu, z1 / tv), (u0 / tu, z1 / tv)]
            self.poly(pts, mat, uv=uv, smooth=True, normal=mid)
        if top:
            self.poly([(cx + a[0] * r1, cy + a[1] * r1, z1) for a in ring], mat_cap or mat, normal=Z)
        if bottom:
            self.poly([(cx + a[0] * r, cy + a[1] * r, z0) for a in ring], mat_cap or mat, normal=-Z)

    def merge(self, other, M=None):
        b = len(self.V)
        self.V.extend([(M @ v) if M else v.copy() for v in other.V])
        for idx, mat, uv, sm in other.F:
            self.F.append(([i + b for i in idx], mat, uv, sm))

    def tris(self):
        return sum(len(f[0]) - 2 for f in self.F)


class B3:
    """The three outputs of one building."""
    def __init__(self, seed=0):
        self.g0, self.g1, self.gc = G(), G(), G()
        self.rng = random.Random(seed)
        self.doors = []          # (centre at floor level, outward normal, width, height) of every walk-through opening
        self.paths = []          # walking routes [(x, y), ...] that must be climbable (stairs)

    def cell(self, dark=False):
        return self.rng.choice(DARK_CELLS) if dark else self.rng.randrange(ATLAS * ATLAS)


def curtain_uv(o):
    """Ribbon-window strip mapped onto the vision-glass part of one floor row of the CurtainWall texture."""
    row = o.kw.get('row', 0) % 4
    off = o.kw.get('uoff', 0.0)
    top = 1 - row / 4 - 0.004
    bot = 1 - (row + 1) / 4 + 0.0625 + 0.004
    a, b = o.u0 / 12 + off, o.u1 / 12 + off
    return [(a, bot), (b, bot), (b, top), (a, top)]


def atlas_uv(cell, pad=0.012):
    r, q = divmod(cell, ATLAS)
    u0, u1 = q / ATLAS + pad, (q + 1) / ATLAS - pad
    v0, v1 = 1 - (r + 1) / ATLAS + pad, 1 - r / ATLAS - pad
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


# ------------------------------------------------------------------ walls
class WF:
    """Wall frame: outer face line a->b at height z0. u along the wall, v up, d inward (0 = outer face)."""
    def __init__(self, a, b, z0, t):
        self.a = Vector((a[0], a[1], z0))
        d = Vector((b[0] - a[0], b[1] - a[1], 0.0))
        self.L = d.length
        self.e = d / self.L
        self.n = self.e.cross(Z)            # outward (interior is on the left of a->b)
        self.t = t

    def P(self, u, v, d=0.0):
        return self.a + self.e * u + Z * v - self.n * d

    def box(self, g, u0, u1, v0, v1, d0, d1, mat, skip=(), mats=None):
        if u1 - u0 < 1e-5 or v1 - v0 < 1e-5 or d1 - d0 < 1e-5:
            return
        g.obox(self.P(u0, v0, d0), self.e * (u1 - u0), -self.n * (d1 - d0), Z * (v1 - v0), mat, skip, mats)

    def rect(self, g, u0, u1, v0, v1, d, mat, normal, uv=None):
        if u1 - u0 < 1e-5 or v1 - v0 < 1e-5:
            return
        g.poly([self.P(u0, v0, d), self.P(u1, v0, d), self.P(u1, v1, d), self.P(u0, v1, d)], mat, uv=uv, normal=normal)


class Op:
    """Wall opening. kind: open (window, glass), door (doorway), hole (no frame), store (shopfront glass),
    blind (recessed fake window), panel (recessed closed panel/door). v is measured from the wall band's z0."""
    THROUGH = ('open', 'door', 'hole', 'store')

    def __init__(self, u0, u1, v0, v1, kind='open', **kw):
        self.u0, self.u1, self.v0, self.v1, self.kind, self.kw = u0, u1, v0, v1, kind, kw
        self.cell = kw.get('cell')

    def through(self):
        return self.kind in Op.THROUGH


def grid_face(g, W, U0, U1, H, holes, mat, d, normal, extra_u=(), extra_v=()):
    us = {U0, U1}
    vs = {0.0, H}
    for h in holes:
        for u in (h[0], h[1]):
            if U0 < u < U1:
                us.add(u)
        for v in (h[2], h[3]):
            if 0 < v < H:
                vs.add(v)
    us.update(u for u in extra_u if U0 < u < U1)
    vs.update(v for v in extra_v if 0 < v < H)
    if isinstance(mat, tuple) and mat and mat[0] == 'v':
        vs.update(ve for ve, _ in mat[1] if 0 < ve < H)
    elif not isinstance(mat, str) and mat is not None:
        us.update(ue for ue, _ in mat if U0 < ue < U1)
    us, vs = sorted(us), sorted(vs)
    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            u0, u1, v0, v1 = us[i], us[i + 1], vs[j], vs[j + 1]
            if u1 - u0 < 1e-4 or v1 - v0 < 1e-4:
                continue
            cu, cv = (u0 + u1) * 0.5, (v0 + v1) * 0.5
            if any(h[0] < cu < h[1] and h[2] < cv < h[3] for h in holes):
                continue
            m = seg_mat(mat, cu, cv)
            if m:
                W.rect(g, u0, u1, v0, v1, d, m, normal)


def seg_mat(mat, u, v=0.0):
    if isinstance(mat, str) or mat is None:
        return mat
    if isinstance(mat, tuple) and mat and mat[0] == 'v':
        for ve, m in mat[1]:
            if v < ve:
                return m
        return mat[1][-1][1]
    for ue, m in mat:
        if u < ue:
            return m
    return mat[-1][1]


def col_wall(gc, W, U0, U1, H, holes, d0, d1):
    us, vs = {U0, U1}, {0.0, H}
    for h in holes:
        us.update(u for u in (h[0], h[1]) if U0 < u < U1)
        vs.update(v for v in (h[2], h[3]) if 0 < v < H)
    us, vs = sorted(us), sorted(vs)
    for j in range(len(vs) - 1):
        v0, v1 = vs[j], vs[j + 1]
        run = None
        for i in range(len(us) - 1):
            u0, u1 = us[i], us[i + 1]
            cu, cv = (u0 + u1) * 0.5, (v0 + v1) * 0.5
            solid = not any(h[0] < cu < h[1] and h[2] < cv < h[3] for h in holes)
            if solid:
                run = [u0, u1] if run is None else [run[0], u1]
            elif run:
                W.box(gc, run[0], run[1], v0, v1, d0, d1, 'COL')
                run = None
        if run:
            W.box(gc, run[0], run[1], v0, v1, d0, d1, 'COL')


STYLE = {
    # frame material, frame width, mullions (n vertical, transom fraction or None), sill mat, lintel mat
    'house': dict(fm='BLD_Trim', fw=0.06, mv=1, tr=0.62, sill='BLD_Trim', lintel=None, trimw=0.09),
    'cottage': dict(fm='BLD_Trim', fw=0.06, mv=1, tr=0.62, sill='BLD_Trim', lintel=None, trimw=0.09,
                    shutter='BLD_TrimGreen'),
    'brick': dict(fm='BLD_Trim', fw=0.06, mv=1, tr=0.7, sill='BLD_Stone', lintel='BLD_Stone', trimw=0.0),
    'modern': dict(fm='BLD_MetalDark', fw=0.05, mv=0, tr=None, sill='BLD_MetalDark', lintel=None, trimw=0.0),
    'apartment': dict(fm='BLD_Trim', fw=0.06, mv=1, tr=None, sill='BLD_ConcreteDark', lintel=None, trimw=0.0),
    'adoor': dict(fm='BLD_Trim', fw=0.06, mv=0, tr=0.8, sill=None, lintel=None, trimw=0.0),
    'ribbon': dict(fm='BLD_MetalDark', fw=0.05, mv=-1.5, tr=None, sill=None, lintel=None, trimw=0.0),
    'store': dict(fm='BLD_MetalDark', fw=0.07, mv=-1.6, tr=0.78, sill=None, lintel=None, trimw=0.0),
    'industrial': dict(fm='BLD_MetalDark', fw=0.05, mv=-1.0, tr=0.5, sill='BLD_Galvanized', lintel=None, trimw=0.0),
}


def window_frame(g, W, op, dfr, style, glass):
    s = STYLE[style]
    fm, fw = s['fm'], s['fw']
    u0, u1, v0, v1 = op.u0, op.u1, op.v0, op.v1
    a, b = dfr - 0.035, dfr + 0.035
    bottom = op.kind not in ('door', 'store') or v0 > 0.05
    W.box(g, u0, u0 + fw, v0, v1, a, b, fm, skip=('-x',))
    W.box(g, u1 - fw, u1, v0, v1, a, b, fm, skip=('+x',))
    W.box(g, u0 + fw, u1 - fw, v1 - fw, v1, a, b, fm, skip=('+z',))
    if bottom:
        W.box(g, u0 + fw, u1 - fw, v0, v0 + fw, a, b, fm, skip=('-z',))
    # mullions: mv > 0 = that many evenly spaced, mv < 0 = one every |mv| metres
    mv = s['mv']
    n = mv if mv >= 0 else max(0, int(round((u1 - u0) / -mv)) - 1)
    for i in range(1, n + 1):
        um = u0 + (u1 - u0) * i / (n + 1)
        W.box(g, um - fw * 0.4, um + fw * 0.4, v0 + (fw if bottom else 0), v1 - fw, a + 0.01, b - 0.01, fm)
    if s['tr'] and v1 - v0 > 1.0:
        vt = v0 + (v1 - v0) * s['tr']
        W.box(g, u0 + fw, u1 - fw, vt - fw * 0.4, vt + fw * 0.4, a + 0.01, b - 0.01, fm)
    if glass:
        W.rect(g, u0 + fw, u1 - fw, v0 + (fw if bottom else 0), v1 - fw, dfr, 'BLD_Glass', W.n)
    if s['sill'] and op.kind in ('open', 'blind'):
        W.box(g, u0 - 0.04, u1 + 0.04, v0 - 0.05, v0 + 0.012, -0.06, a, s['sill'], skip=('+y',))
    if s['lintel'] and op.kind in ('open', 'blind'):
        W.box(g, u0 - 0.1, u1 + 0.1, v1, v1 + 0.17, -0.025, 0.0, s['lintel'], skip=('+y',))
    if s.get('shutter') and op.kind in ('open', 'blind'):
        sw = (u1 - u0) * 0.5
        for a0, a1 in ((u0 - s['trimw'] - sw, u0 - s['trimw'] - 0.02), (u1 + s['trimw'] + 0.02, u1 + s['trimw'] + sw)):
            W.box(g, a0, a1, v0, v1, -0.05, 0.0, s['shutter'], skip=('+y',))
            for k in range(1, 6):                 # louvre lines
                vv = v0 + (v1 - v0) * k / 6
                W.box(g, a0 + 0.04, a1 - 0.04, vv - 0.012, vv + 0.012, -0.065, -0.05, s['shutter'], skip=('+y',))
    if s['trimw'] > 0:                       # flat casing around the opening (houses)
        tw = s['trimw']
        W.box(g, u0 - tw, u0, v0 - (0.05 if op.kind == 'open' else 0), v1 + tw, -0.025, 0.0, 'BLD_Trim', skip=('+y',))
        W.box(g, u1, u1 + tw, v0 - (0.05 if op.kind == 'open' else 0), v1 + tw, -0.025, 0.0, 'BLD_Trim', skip=('+y',))
        W.box(g, u0, u1, v1, v1 + tw, -0.025, 0.0, 'BLD_Trim', skip=('+y',))


def door_leaf(g, W, op, mat, ang=100.0, inward=True, side=0):
    """Open door leaf hinged at the inner jamb (side 0 = u0 jamb, 1 = u1 jamb)."""
    w = op.u1 - op.u0 - 0.1
    hgt = min(op.v1 - op.v0 - 0.05, 2.1)
    th = 0.045
    hu = op.u0 + 0.05 if side == 0 else op.u1 - 0.05
    hinge = W.P(hu, op.v0, W.t - 0.02 if inward else 0.02)
    a = math.radians(ang)
    sgn = 1 if side == 0 else -1
    into = -W.n if inward else W.n
    dirv = W.e * (math.cos(a) * sgn) + into * math.sin(a)
    thick = dirv.cross(Z).normalized() * th
    g.obox(hinge, dirv * w, thick, Z * hgt, mat)


def reveal(g, W, o, d0, d1, rm, bottom=True, sillmat=None):
    """The four faces lining an opening between depths d0 and d1."""
    if bottom:
        g.poly([W.P(o.u0, o.v0, d0), W.P(o.u1, o.v0, d0), W.P(o.u1, o.v0, d1), W.P(o.u0, o.v0, d1)], sillmat or rm, normal=Z)
    g.poly([W.P(o.u0, o.v1, d0), W.P(o.u1, o.v1, d0), W.P(o.u1, o.v1, d1), W.P(o.u0, o.v1, d1)], rm, normal=-Z)
    g.poly([W.P(o.u0, o.v0, d0), W.P(o.u0, o.v1, d0), W.P(o.u0, o.v1, d1), W.P(o.u0, o.v0, d1)], rm, normal=W.e)
    g.poly([W.P(o.u1, o.v0, d0), W.P(o.u1, o.v1, d0), W.P(o.u1, o.v1, d1), W.P(o.u1, o.v0, d1)], rm, normal=-W.e)


def wall(B, a, b, z0, H, t, ops=(), mo='BLD_Brick', mi=None, mr=None, inner=None, caps=(False, False),
         top=None, style='brick', lod1=True, col=True, mi_ext=None):
    """One wall band. Outer face a->b (building interior on the left).
    mo = outer face material (None: hidden outside, e.g. a stair shaft inside a sealed floor - no outer face, no LOD1).
    mi = interior face material (None: sealed floor, no inner face; through-openings not allowed).
    inner = (start, end) trim of the inner face (default (t, t) for the corners of a closed footprint).
    top = material for a cap face on the wall top (parapets, garden walls)."""
    W = WF(a, b, z0, t)
    L = W.L
    i0, i1 = inner if inner is not None else (t, t)
    mr = mr or (mo if isinstance(mo, str) else None) or (mi if isinstance(mi, str) else None) or 'BLD_Concrete'
    g0 = B.g0
    outer_ops = [o for o in ops if o.kind != 'ipanel'] if mo else [o for o in ops if o.through()]
    inner_ops = [o for o in ops if o.through() or o.kind == 'ipanel']
    if mo:
        grid_face(g0, W, 0.0, L, H, [(o.u0, o.u1, o.v0, o.v1) for o in outer_ops], mo, 0.0, W.n)
    if mi:
        grid_face(g0, W, i0, L - i1, H, [(o.u0, o.u1, o.v0, o.v1) for o in inner_ops], mi, t, -W.n)
    for o in ops:
        st = o.kw.get('style', style)
        rm = o.kw.get('reveal', mr)
        if o.through():
            assert mi, 'through-opening in a sealed wall'
            reveal(g0, W, o, 0.0, t, rm, bottom=o.v0 > 0.001 or o.kind in ('open', 'store') or o.kw.get('floor'),
                   sillmat=o.kw.get('sillmat'))
            if o.kind in ('open', 'store'):
                window_frame(g0, W, o, t * 0.4, st, True)
            elif o.kind == 'door':
                df = o.kw.get('frame', 'BLD_Trim')
                if df:
                    fd0, fd1 = t - 0.06, t
                    W.box(g0, o.u0, o.u0 + 0.06, o.v0, o.v1, fd0, fd1, df, skip=('-x',))
                    W.box(g0, o.u1 - 0.06, o.u1, o.v0, o.v1, fd0, fd1, df, skip=('+x',))
                    W.box(g0, o.u0 + 0.06, o.u1 - 0.06, o.v1 - 0.06, o.v1, fd0, fd1, df, skip=('+z',))
                if o.kw.get('leaf'):
                    door_leaf(g0, W, o, o.kw['leaf'], o.kw.get('ang', 100.0), o.kw.get('inward', True), o.kw.get('side', 0))
                if o.kw.get('glassdoor'):
                    window_frame(g0, W, o, t * 0.5, 'store', True)
        elif o.kind == 'ipanel':
            if not mi:
                continue
            rd = o.kw.get('depth', 0.04)
            reveal(g0, W, o, t - rd, t, mi, bottom=o.v0 > 0.001)
            W.rect(g0, o.u0, o.u1, o.v0, o.v1, t - rd, o.kw.get('mat', 'BLD_Wood'), -W.n)
            fm = o.kw.get('frame')
            if fm:
                W.box(g0, o.u0 - 0.06, o.u0, o.v0, o.v1 + 0.06, t, t + 0.02, fm, skip=('-y',))
                W.box(g0, o.u1, o.u1 + 0.06, o.v0, o.v1 + 0.06, t, t + 0.02, fm, skip=('-y',))
                W.box(g0, o.u0, o.u1, o.v1, o.v1 + 0.06, t, t + 0.02, fm, skip=('-y',))
                W.box(g0, o.u1 - 0.2, o.u1 - 0.08, o.v0 + 1.0, o.v0 + 1.04, t - rd - 0.06, t - rd, fm)  # handle
        elif mo and o.kind == 'cblind':
            rd = o.kw.get('depth', 0.1)
            reveal(g0, W, o, 0.0, rd, rm, bottom=o.v0 > 0.001)
            W.rect(g0, o.u0, o.u1, o.v0, o.v1, rd, 'BLD_CurtainWall', W.n, uv=curtain_uv(o))
        elif mo:
            rd = o.kw.get('depth', 0.14 if o.kind == 'blind' else 0.05)
            reveal(g0, W, o, 0.0, rd, rm, bottom=o.v0 > 0.001)
            if o.kind == 'blind':
                if o.cell is None:
                    o.cell = B.cell()
                W.rect(g0, o.u0, o.u1, o.v0, o.v1, rd, 'BLD_WindowFake', W.n, uv=atlas_uv(o.cell))
                window_frame(g0, W, o, 0.06, st, False)
            else:
                W.rect(g0, o.u0, o.u1, o.v0, o.v1, rd, o.kw.get('mat', 'BLD_Wood'), W.n)
                fm = o.kw.get('frame')
                if fm:
                    W.box(g0, o.u0, o.u0 + 0.05, o.v0, o.v1, 0.0, rd, fm, skip=('-x',))
                    W.box(g0, o.u1 - 0.05, o.u1, o.v0, o.v1, 0.0, rd, fm, skip=('+x',))
                    W.box(g0, o.u0 + 0.05, o.u1 - 0.05, o.v1 - 0.05, o.v1, 0.0, rd, fm, skip=('+z',))
    for k, (cap, u) in enumerate(((caps[0], 0.0), (caps[1], L))):
        if cap:
            g0.poly([W.P(u, 0, 0), W.P(u, H, 0), W.P(u, H, t), W.P(u, 0, t)], mi_ext or mo or mi,
                    normal=(-W.e if k == 0 else W.e))
    if top:
        g0.poly([W.P(0, H, 0), W.P(L, H, 0), W.P(L - i1, H, t), W.P(i0, H, t)], top, normal=Z)
    if lod1 and mo:
        g1 = B.g1
        if isinstance(mo, tuple):
            prev = 0.0
            for ve, m in mo[1]:
                top_v = min(ve, H)
                W.rect(g1, 0.0, L, prev, top_v, 0.0, m, W.n)
                prev = top_v
                if prev >= H:
                    break
        else:
            W.rect(g1, 0.0, L, 0, H, 0.0, mo, W.n)
        for o in outer_ops:
            if o.kind == 'cblind':
                W.rect(g1, o.u0, o.u1, o.v0, o.v1, -0.004, 'BLD_CurtainWall', W.n, uv=curtain_uv(o))
                continue
            if o.kind == 'panel':
                W.rect(g1, o.u0, o.u1, o.v0, o.v1, -0.004, o.kw.get('mat', 'BLD_Wood'), W.n)
                continue
            if o.cell is None:
                o.cell = B.cell(dark=o.kind in ('door', 'hole'))
            W.rect(g1, o.u0, o.u1, o.v0, o.v1, -0.004, 'BLD_WindowFake', W.n, uv=atlas_uv(o.cell))
        if top:
            g1.poly([W.P(0, H, 0), W.P(L, H, 0), W.P(L - i1, H, t), W.P(i0, H, t)], top, normal=Z)
    if col:
        col_wall(B.gc, W, 0.0, L, H, [(o.u0, o.u1, o.v0, o.v1) for o in ops if o.through()], 0.0, t)
    for o in ops:
        if o.kind in ('door', 'hole') and o.v0 < 0.3:
            h = 99.0 if o.v1 >= H - 0.02 else o.v1 - o.v0          # open to the sky (parapet gap)
            B.doors.append((W.P((o.u0 + o.u1) / 2, o.v0, t / 2), W.n.copy(), o.u1 - o.u0, h, t))
    return W


def rect_walls(B, x0, y0, x1, y1, z0, H, t, ops=None, **kw):
    """Four walls of an axis-aligned footprint, counter-clockwise from the front (-Y) side.
    ops: dict with keys 'front', 'right', 'back', 'left' -> list of Op (u measured from each wall's start corner:
    front from x0, right from y0, back from x1, left from y1)."""
    ops = ops or {}
    sides = [('front', (x0, y0), (x1, y0)), ('right', (x1, y0), (x1, y1)),
             ('back', (x1, y1), (x0, y1)), ('left', (x0, y1), (x0, y0))]
    per = kw.pop('per', {})
    out = {}
    for name, a, b in sides:
        k = dict(kw)
        k.update(per.get(name, {}))
        out[name] = wall(B, a, b, z0, H, t, ops.get(name, ()), **k)
    return out


def spaced(L, count, w, margin=None, centers=None):
    """u-ranges of 'count' openings of width w spread evenly along a wall of length L."""
    if centers is None:
        m = margin if margin is not None else 0.0
        step = (L - 2 * m) / count
        centers = [m + step * (i + 0.5) for i in range(count)]
    return [(c - w / 2, c + w / 2) for c in centers]


def win_row(L, count, w, v0, v1, kind='blind', margin=None, centers=None, **kw):
    return [Op(a, b, v0, v1, kind, **kw) for a, b in spaced(L, count, w, margin, centers)]


# ------------------------------------------------------------------ slabs, floors, ceilings
def hslab(g, x0, y0, x1, y1, z, mat, up=True, holes=()):
    xs, ys = {x0, x1}, {y0, y1}
    for h in holes:
        xs.update(v for v in (h[0], h[2]) if x0 < v < x1)
        ys.update(v for v in (h[1], h[3]) if y0 < v < y1)
    xs, ys = sorted(xs), sorted(ys)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            a, b, c, d = xs[i], xs[i + 1], ys[j], ys[j + 1]
            if b - a < 1e-4 or d - c < 1e-4:
                continue
            cx, cy = (a + b) * 0.5, (c + d) * 0.5
            if any(h[0] < cx < h[2] and h[1] < cy < h[3] for h in holes):
                continue
            g.poly([(a, c, z), (b, c, z), (b, d, z), (a, d, z)], mat, normal=Z if up else -Z)


def col_slab(gc, x0, y0, x1, y1, z0, z1, holes=()):
    xs, ys = {x0, x1}, {y0, y1}
    for h in holes:
        xs.update(v for v in (h[0], h[2]) if x0 < v < x1)
        ys.update(v for v in (h[1], h[3]) if y0 < v < y1)
    xs, ys = sorted(xs), sorted(ys)
    for j in range(len(ys) - 1):
        run = None
        for i in range(len(xs) - 1):
            cx, cy = (xs[i] + xs[i + 1]) * 0.5, (ys[j] + ys[j + 1]) * 0.5
            solid = not any(h[0] < cx < h[2] and h[1] < cy < h[3] for h in holes)
            if solid:
                run = [xs[i], xs[i + 1]] if run is None else [run[0], xs[i + 1]]
            elif run:
                gc.box(run[0], ys[j], z0, run[1], ys[j + 1], z1, 'COL')
                run = None
        if run:
            gc.box(run[0], ys[j], z0, run[1], ys[j + 1], z1, 'COL')


def room(B, x0, y0, x1, y1, zf, zc, mf, mc, holes=(), slab=0.25, col_floor=True):
    """Floor face at zf and ceiling face at zc over a rectangle (holes = (x0, y0, x1, y1) list)."""
    hslab(B.g0, x0, y0, x1, y1, zf, mf, True, holes)
    hslab(B.g0, x0, y0, x1, y1, zc, mc, False, holes)
    if col_floor:
        col_slab(B.gc, x0, y0, x1, y1, zf - slab, zf, holes)


# ------------------------------------------------------------------ partitions (interior walls, both faces)
def partition(B, a, b, z0, H, t=0.12, ops=(), ml='BLD_InteriorWall', mr_='BLD_InteriorWall', caps=(True, True),
              mcap=None, rev='BLD_InteriorWall'):
    """Free-standing interior wall whose left face (interior side of a->b) gets ml and right face mr_."""
    W = WF(a, b, z0, t)
    L = W.L
    holes = [(o.u0, o.u1, o.v0, o.v1) for o in ops]
    grid_face(B.g0, W, 0.0, L, H, holes, mr_, 0.0, W.n)
    grid_face(B.g0, W, 0.0, L, H, holes, ml, t, -W.n)
    for o in ops:
        B.g0.poly([W.P(o.u0, o.v1, 0), W.P(o.u1, o.v1, 0), W.P(o.u1, o.v1, t), W.P(o.u0, o.v1, t)], rev, normal=-Z)
        B.g0.poly([W.P(o.u0, o.v0, 0), W.P(o.u0, o.v1, 0), W.P(o.u0, o.v1, t), W.P(o.u0, o.v0, t)], rev, normal=W.e)
        B.g0.poly([W.P(o.u1, o.v0, 0), W.P(o.u1, o.v1, 0), W.P(o.u1, o.v1, t), W.P(o.u1, o.v0, t)], rev, normal=-W.e)
        if o.v0 > 0.01:
            B.g0.poly([W.P(o.u0, o.v0, 0), W.P(o.u1, o.v0, 0), W.P(o.u1, o.v0, t), W.P(o.u0, o.v0, t)], rev, normal=Z)
        fr = o.kw.get('frame', 'BLD_Trim')
        if fr:
            for d0, d1 in ((-0.015, 0.0), (t, t + 0.015)):
                W.box(B.g0, o.u0 - 0.07, o.u0, o.v0, o.v1 + 0.07, d0, d1, fr)
                W.box(B.g0, o.u1, o.u1 + 0.07, o.v0, o.v1 + 0.07, d0, d1, fr)
                W.box(B.g0, o.u0, o.u1, o.v1, o.v1 + 0.07, d0, d1, fr)
        if o.kw.get('leaf'):
            door_leaf(B.g0, W, o, o.kw['leaf'], o.kw.get('ang', 95.0), o.kw.get('inward', True), o.kw.get('side', 0))
    for k, (cap, u) in enumerate(((caps[0], 0.0), (caps[1], L))):
        if cap:
            B.g0.poly([W.P(u, 0, 0), W.P(u, H, 0), W.P(u, H, t), W.P(u, 0, t)], mcap or ml, normal=(-W.e if k == 0 else W.e))
    col_wall(B.gc, W, 0.0, L, H, holes, 0.0, t)
    for o in ops:
        if o.kind in ('door', 'hole') and o.v0 < 0.3:
            B.doors.append((W.P((o.u0 + o.u1) / 2, o.v0, t / 2), W.n.copy(), o.u1 - o.u0, o.v1 - o.v0, t))
    return W


# ------------------------------------------------------------------ roofs
def gable_roof(B, x0, y0, x1, y1, ze, pitch, oh, mroof='BLD_Shingle', mgable='BLD_Siding_White',
               mfascia='BLD_Trim', msoffit='BLD_Trim', rt=0.2, axis='x', gable_t=0.3, gable_inner=None, solid=True):
    """Gable roof over a footprint whose walls top out at ze. axis = ridge direction."""
    if axis == 'y':        # build along x in a rotated frame
        M = Matrix.Rotation(math.pi / 2, 4, 'Z')
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hw, hd = (y1 - y0) / 2, (x1 - x0) / 2
        tmp = B3()
        tmp.rng = B.rng
        gable_roof(tmp, -hw, -hd, hw, hd, ze, pitch, oh, mroof, mgable, mfascia, msoffit, rt, 'x', gable_t, gable_inner, solid)
        T = Matrix.Translation((cx, cy, 0)) @ M
        B.g0.merge(tmp.g0, T)
        B.g1.merge(tmp.g1, T)
        B.gc.merge(tmp.gc, T)
        return
    tp = math.tan(math.radians(pitch))
    yc = (y0 + y1) / 2
    D = (y1 - y0) / 2
    zr = ze + D * tp
    zE = ze - oh * tp
    X0, X1 = x0 - oh, x1 + oh
    for g, detail in ((B.g0, True), (B.g1, False)):
        for s in (-1, 1):
            ye = yc + s * (D + oh)
            top = [(X0, ye, zE + rt), (X1, ye, zE + rt), (X1, yc, zr + rt), (X0, yc, zr + rt)]
            out = Vector((0, s * tp, 1))
            g.poly(top, mroof, normal=out)
            if detail:
                bot = [(X0, ye, zE), (X1, ye, zE), (X1, yc, zr), (X0, yc, zr)]
                g.poly(bot, msoffit, normal=-out)
                g.poly([(X0, ye, zE), (X1, ye, zE), (X1, ye, zE + rt), (X0, ye, zE + rt)], mfascia, normal=(0, s, 0))
                for xe, sx in ((X0, -1), (X1, 1)):
                    g.poly([(xe, ye, zE), (xe, yc, zr), (xe, yc, zr + rt), (xe, ye, zE + rt)], mfascia, normal=(sx, 0, 0))
            else:
                g.poly([(X0, ye, zE + rt), (X1, ye, zE + rt), (X1, ye, zE), (X0, ye, zE)], mfascia, normal=(0, s, 0))
        # gable triangles (wall continues up to the roof underside)
        for xg, sx in ((x0, -1), (x1, 1)):
            g.poly([(xg, y0, ze), (xg, y1, ze), (xg, yc, zr)], mgable, normal=(sx, 0, 0))
    if gable_inner:
        t = gable_t
        k = t / max(D, 1e-6)
        for xg, sx in ((x0 + t, 1), (x1 - t, -1)):
            B.g0.poly([(xg, y0 + t, ze), (xg, y1 - t, ze), (xg, y1 - t, ze + t * tp), (xg, yc, zr), (xg, y0 + t, ze + t * tp)],
                      gable_inner, normal=(sx, 0, 0))
    gc = B.gc
    if not solid:
        # open interior up to the roof: two sloped slabs instead of a solid attic
        for s in (-1, 1):
            ye = yc + s * (D + oh)
            a = Vector((X0, ye, zE))
            gc.obox(a, Vector((X1 - X0, 0, 0)), Vector((0, yc - ye, zr - zE)), Vector((0, 0, rt)), 'COL')
        for xg in (x0, x1 - gable_t):
            gc.poly([(xg, y0, ze), (xg, y1, ze), (xg, yc, zr)], 'COL', normal=(-1, 0, 0))
            gc.poly([(xg + gable_t, y0, ze), (xg + gable_t, y1, ze), (xg + gable_t, yc, zr)], 'COL', normal=(1, 0, 0))
        return
    # collider: closed prism of attic + roof
    for s in (-1, 1):
        ye = yc + s * (D + oh)
        gc.poly([(X0, ye, zE + rt), (X1, ye, zE + rt), (X1, yc, zr + rt), (X0, yc, zr + rt)], 'COL', normal=(0, s * tp, 1))
        gc.poly([(X0, ye, zE), (X1, ye, zE), (X1, ye, zE + rt), (X0, ye, zE + rt)], 'COL', normal=(0, s, 0))
    for xe, sx in ((X0, -1), (X1, 1)):
        gc.poly([(xe, y0 - oh, zE), (xe, y1 + oh, zE), (xe, y1 + oh, zE + rt), (xe, yc, zr + rt), (xe, y0 - oh, zE + rt)],
                'COL', normal=(sx, 0, 0))
    gc.poly([(X0, y0 - oh, zE), (X1, y0 - oh, zE), (X1, y1 + oh, zE), (X0, y1 + oh, zE)], 'COL', normal=-Z)


def shed_roof(B, x0, y0, x1, y1, z_hi, z_lo, mroof='BLD_Shingle', mfascia='BLD_Trim', msoffit='BLD_Trim', rt=0.14,
              down='-y'):
    """Single-slope roof slab over a rectangle, high edge on the side opposite 'down' (-y or +y)."""
    if down == '-y':
        hi_y, lo_y = y1, y0
    else:
        hi_y, lo_y = y0, y1
    pts_top = [(x0, lo_y, z_lo + rt), (x1, lo_y, z_lo + rt), (x1, hi_y, z_hi + rt), (x0, hi_y, z_hi + rt)]
    pts_bot = [(x0, lo_y, z_lo), (x1, lo_y, z_lo), (x1, hi_y, z_hi), (x0, hi_y, z_hi)]
    sgn = -1 if down == '-y' else 1
    up = Vector((0, sgn * (z_hi - z_lo), abs(hi_y - lo_y)))
    for g, detail in ((B.g0, True), (B.g1, False)):
        g.poly(pts_top, mroof, normal=up)
        if detail:
            g.poly(pts_bot, msoffit, normal=-up)
        g.poly([pts_bot[0], pts_bot[1], pts_top[1], pts_top[0]], mfascia, normal=(0, sgn, 0))
        g.poly([pts_bot[0], pts_bot[3], pts_top[3], pts_top[0]], mfascia, normal=(-1, 0, 0))
        g.poly([pts_bot[1], pts_bot[2], pts_top[2], pts_top[1]], mfascia, normal=(1, 0, 0))
    gc = B.gc
    gc.poly(pts_top, 'COL', normal=up)
    gc.poly(pts_bot, 'COL', normal=-up)
    gc.poly([pts_bot[0], pts_bot[1], pts_top[1], pts_top[0]], 'COL', normal=(0, sgn, 0))
    gc.poly([pts_bot[3], pts_bot[2], pts_top[2], pts_top[3]], 'COL', normal=(0, -sgn, 0))
    gc.poly([pts_bot[0], pts_bot[3], pts_top[3], pts_top[0]], 'COL', normal=(-1, 0, 0))
    gc.poly([pts_bot[1], pts_bot[2], pts_top[2], pts_top[1]], 'COL', normal=(1, 0, 0))


def hip_roof(B, x0, y0, x1, y1, ze, pitch, oh, mroof='BLD_Shingle', mfascia='BLD_Trim', msoffit='BLD_Trim', rt=0.2):
    """Hip roof, ridge along the longer side (same pitch on all four slopes)."""
    tp = math.tan(math.radians(pitch))
    X0, Y0, X1, Y1 = x0 - oh, y0 - oh, x1 + oh, y1 + oh
    zE = ze - oh * tp
    w, d = X1 - X0, Y1 - Y0
    h = min(w, d) / 2
    zr = zE + h * tp
    if w >= d:
        r0, r1 = Vector((X0 + h, (Y0 + Y1) / 2, zr)), Vector((X1 - h, (Y0 + Y1) / 2, zr))
    else:
        r0, r1 = Vector(((X0 + X1) / 2, Y0 + h, zr)), Vector(((X0 + X1) / 2, Y1 - h, zr))
    c00, c10, c11, c01 = Vector((X0, Y0, zE)), Vector((X1, Y0, zE)), Vector((X1, Y1, zE)), Vector((X0, Y1, zE))
    up = Vector((0, 0, rt))
    if w >= d:
        planes = [((c00, c10, r1, r0), (0, -tp, 1)), ((c11, c01, r0, r1), (0, tp, 1)),
                  ((c01, c00, r0), (-tp, 0, 1)), ((c10, c11, r1), (tp, 0, 1))]
    else:
        planes = [((c10, c11, r1, r0), (tp, 0, 1)), ((c01, c00, r0, r1), (-tp, 0, 1)),
                  ((c00, c10, r0), (0, -tp, 1)), ((c11, c01, r1), (0, tp, 1))]
    for g, detail in ((B.g0, True), (B.g1, False)):
        for pts, nrm in planes:
            g.poly([p + up for p in pts], mroof, normal=nrm)
            if detail:
                g.poly(list(pts), msoffit, normal=-Vector(nrm))
        for a, b, nrm in ((c00, c10, (0, -1, 0)), (c10, c11, (1, 0, 0)), (c11, c01, (0, 1, 0)), (c01, c00, (-1, 0, 0))):
            g.poly([a, b, b + up, a + up], mfascia, normal=nrm)
    gc = B.gc
    for pts, nrm in planes:
        gc.poly([p + up for p in pts], 'COL', normal=nrm)
    for a, b, nrm in ((c00, c10, (0, -1, 0)), (c10, c11, (1, 0, 0)), (c11, c01, (0, 1, 0)), (c01, c00, (-1, 0, 0))):
        gc.poly([a, b, b + up, a + up], 'COL', normal=nrm)
    gc.poly([c00, c10, c11, c01], 'COL', normal=-Z)


def flat_roof(B, x0, y0, x1, y1, zr, t, ph, mo, mroof='BLD_Gravel', mpar='BLD_Concrete', mcope='BLD_Stone', holes=(),
              lod_holes=None, gap_back=None):
    """Roof surface at zr over the inner footprint, parapet walls of height ph above it with a coping cap."""
    hslab(B.g0, x0 + t, y0 + t, x1 - t, y1 - t, zr, mroof, True, holes)
    hslab(B.g1, x0 + t, y0 + t, x1 - t, y1 - t, zr, mroof, True, holes if lod_holes is None else lod_holes)
    col_slab(B.gc, x0, y0, x1, y1, zr - 0.3, zr, holes)
    if ph > 0:
        pops = {}
        if gap_back:
            pops['back'] = [Op(x1 - gap_back[1], x1 - gap_back[0], 0.0, ph + 0.01, 'hole', floor=True)]
        rect_walls(B, x0, y0, x1, y1, zr, ph, t, pops, mo=mo, mi=mpar, col=True)
        cw = 0.04
        for g in (B.g0, B.g1):
            # coping: a frame of four boxes overhanging both faces of the parapet
            zc0, zc1 = zr + ph, zr + ph + 0.08
            g.box(x0 - cw, y0 - cw, zc0, x1 + cw, y0 + t + cw, zc1, mcope)
            if gap_back:
                g.box(x0 - cw, y1 - t - cw, zc0, gap_back[0], y1 + cw, zc1, mcope)
                g.box(gap_back[1], y1 - t - cw, zc0, x1 + cw, y1 + cw, zc1, mcope)
            else:
                g.box(x0 - cw, y1 - t - cw, zc0, x1 + cw, y1 + cw, zc1, mcope)
            g.box(x0 - cw, y0 + t + cw, zc0, x0 + t + cw, y1 - t - cw, zc1, mcope, skip=('-y', '+y'))
            g.box(x1 - t - cw, y0 + t + cw, zc0, x1 + cw, y1 - t - cw, zc1, mcope, skip=('-y', '+y'))


# ------------------------------------------------------------------ stairs
RISE, RUN = 0.175, 0.28


def flight(B, x0, x1, ys, ye, zs, ze, mt='BLD_Concrete', ms='BLD_Concrete', mso='BLD_Plaster_White', sides=(True, True),
           thick=0.3, col=True):
    """Straight flight along Y from (ys, zs) to (ye, ze); its last riser lands on the floor/landing that starts at ye.
    sides: draw the side faces at x0 / x1 (False when the flight runs against a wall)."""
    n = max(2, int(round((ze - zs) / RISE)))
    rise = (ze - zs) / n
    run = (ye - ys) / (n - 1)
    sgn = 1 if ye > ys else -1
    g = B.g0
    fwd = Vector((0, sgn, 0))
    soff = lambda y: zs + (y - ys) / (ye - ys) * (ze - thick - zs)
    for i in range(n - 1):
        ya, yb = ys + run * i, ys + run * (i + 1)
        zt = zs + rise * (i + 1)
        g.poly([(x0, ya, zt), (x1, ya, zt), (x1, yb, zt), (x0, yb, zt)], mt, normal=Z)
        g.poly([(x0, ya, zt - rise), (x1, ya, zt - rise), (x1, ya, zt), (x0, ya, zt)], ms, normal=-fwd)
        for side, xs, nx in ((0, x0, -1), (1, x1, 1)):
            if sides[side]:
                g.poly([(xs, ya, soff(ya)), (xs, yb, soff(yb)), (xs, yb, zt), (xs, ya, zt)], ms, normal=(nx, 0, 0))
    g.poly([(x0, ye, ze - rise), (x1, ye, ze - rise), (x1, ye, ze), (x0, ye, ze)], ms, normal=-fwd)
    g.poly([(x0, ye, ze - thick), (x1, ye, ze - thick), (x1, ye, ze - rise), (x0, ye, ze - rise)], mso, normal=fwd)
    g.poly([(x0, ys, zs), (x1, ys, zs), (x1, ye, ze - thick), (x0, ye, ze - thick)], mso,
           normal=Vector((0, (ze - zs) * sgn, -abs(ye - ys))))
    if col:
        col_ramp(B.gc, x0, x1, ys, zs, ye, ze)


def col_ramp(gc, x0, x1, ys, zs, ye, ze, thick=0.3):
    top = [Vector((x0, ys, zs)), Vector((x1, ys, zs)), Vector((x1, ye, ze)), Vector((x0, ye, ze))]
    bot = [p - Vector((0, 0, thick)) for p in top]
    sgn = 1 if ye > ys else -1
    gc.poly(top, 'COL', normal=Z)
    gc.poly(bot, 'COL', normal=-Z)
    gc.poly([bot[0], bot[3], top[3], top[0]], 'COL', normal=(-1, 0, 0))
    gc.poly([bot[1], bot[2], top[2], top[1]], 'COL', normal=(1, 0, 0))
    gc.poly([bot[0], bot[1], top[1], top[0]], 'COL', normal=(0, -sgn, 0))
    gc.poly([bot[3], bot[2], top[2], top[3]], 'COL', normal=(0, sgn, 0))


def railing(B, pts, z, h=1.0, mat='BLD_MetalDark', post=1.2, bar=0.04, col=True):
    """Handrail along a polyline of (x, y) points at floor height z (with posts every 'post' metres)."""
    g = B.g0
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        a, b = Vector((ax, ay, z)), Vector((bx, by, z))
        d = b - a
        L = d.length
        if L < 1e-4:
            continue
        e = d / L
        s = e.cross(Z) * bar
        g.obox(a + Z * (h - bar) - s * 0.5, d, s, Z * bar, mat)
        g.obox(a + Z * (h * 0.5 - bar * 0.5) - s * 0.5, d, s * 0.6, Z * bar * 0.6, mat)
        cnt = max(1, int(math.ceil(L / post)))
        for i in range(cnt + 1):
            p = a + d * (i / cnt)
            g.obox(p - s * 0.5 - e * bar * 0.5, e * bar, s, Z * (h - bar), mat)
        if col:
            B.gc.obox(a - s * 1.5, d, s * 3, Z * h, 'COL')


def sloped_rail(B, x, ys, zs, ye, ze, h=0.95, mat='BLD_MetalDark', col=False):
    g = B.g0
    a, b = Vector((x, ys, zs + h)), Vector((x, ye, ze + h))
    d = b - a
    s = Vector((0.04, 0, 0))
    g.obox(a - s * 0.5, d, s, Vector((0, 0, 0.05)), mat)
    n = max(2, int(abs(ye - ys) / 1.0) + 1)
    for i in range(n + 1):
        p = Vector((x, ys + (ye - ys) * i / n, zs + (ze - zs) * i / n))
        g.obox(p - Vector((0.02, 0.02, 0)), Vector((0.04, 0, 0)), Vector((0, 0.04, 0)), Vector((0, 0, h)), mat)


# ------------------------------------------------------------------ stair core (switch-back stairs up a shaft)
def stair_core(B, x0, y0, x1, levels, open_levels, wall_mat='BLD_Concrete', inner_mat='BLD_Plaster_White',
               floor_mat='BLD_Concrete', t=0.2, bulkhead=3.0, lw=1.3, run_len=3.0, outer_mat=None,
               door_mat='BLD_TrimGreen', roof_door=True):
    """Switch-back stair shaft. Inside spans x0..x1 (two flights + a 0.15 m centre wall) from y0 (the door end).
    levels = floor heights [ground, ..., roof]; the shaft rises 'bulkhead' above the roof with a door out.
    open_levels = level indices with an open doorway to the floor (and visible outer walls); the rest get a
    closed door seen only from inside the shaft. Returns the shaft's outer footprint (x0, y0, x1, y1)."""
    xm = (x0 + x1) / 2
    cw = 0.15
    y1 = y0 + lw * 2 + run_len
    yA, yB = y0 + lw, y1 - lw
    outer_mat = outer_mat or wall_mat
    top = levels[-1]
    ztop = top + bulkhead
    zs = levels[0]
    X0, Y0, X1, Y1 = x0 - t, y0 - t, x1 + t, y1 + t
    bands = list(zip(levels[:-1], levels[1:])) + [(top, ztop)]
    dc = (X1 - X0) / 2
    for k, (za, zb) in enumerate(bands):
        roof = k == len(bands) - 1
        visible = roof or k in open_levels
        if roof and not roof_door:
            fops = []
        elif visible:
            fops = [Op(dc - 0.5, dc + 0.5, 0.0, 2.15, 'door', frame='BLD_MetalDark', leaf=door_mat, ang=100,
                       inward=False, side=1, reveal=inner_mat)]
        else:
            fops = [Op(dc - 0.5, dc + 0.5, 0.0, 2.1, 'ipanel', mat=door_mat, frame='BLD_MetalDark')]
        rect_walls(B, X0, Y0, X1, Y1, za, zb - za, t, {'front': fops},
                   mo=(wall_mat if roof else outer_mat) if visible else None, mi=inner_mat, mr=inner_mat, lod1=roof)
    # bulkhead roof
    for g in (B.g0, B.g1):
        g.box(X0 - 0.05, Y0 - 0.05, ztop, X1 + 0.05, Y1 + 0.05, ztop + 0.15, wall_mat)
    hslab(B.g0, x0, y0, x1, y1, ztop - 0.001, inner_mat, up=False)
    B.gc.box(X0, Y0, ztop, X1, Y1, ztop + 0.15, 'COL')
    # centre wall between the flights
    B.g0.box(xm - cw / 2, yA, zs, xm + cw / 2, yB, top + 0.1, inner_mat, skip=('-z',))
    B.gc.box(xm - cw / 2, yA, zs, xm + cw / 2, yB, top + 0.1, 'COL')
    hslab(B.g0, x0, y0, x1, y1, zs, floor_mat, True)
    B.gc.box(x0, y0, zs - 0.2, x1, y1, zs, 'COL')
    for k in range(len(levels) - 1):
        za, zb = levels[k], levels[k + 1]
        zm = (za + zb) / 2
        # mid landing (far end) and the next floor landing (door end); faces toward the flights are drawn
        # only on the half where a flight leaves the landing (the arriving flight's riser covers the other half)
        B.g0.box(x0, yB, zm - 0.2, x1, y1, zm, floor_mat, skip=('-y',), mats={'-z': inner_mat})
        B.g0.poly([(xm, yB, zm - 0.2), (x1, yB, zm - 0.2), (x1, yB, zm), (xm, yB, zm)], inner_mat, normal=(0, -1, 0))
        B.gc.box(x0, yB, zm - 0.2, x1, y1, zm, 'COL')
        B.g0.box(x0, y0, zb - 0.2, x1, yA, zb, floor_mat, skip=('+y',), mats={'-z': inner_mat})
        if k < len(levels) - 2:
            B.g0.poly([(x0, yA, zb - 0.2), (xm, yA, zb - 0.2), (xm, yA, zb), (x0, yA, zb)], inner_mat, normal=(0, 1, 0))
        B.gc.box(x0, y0, zb - 0.2, x1, yA, zb, 'COL')
        flight(B, x0, xm - cw / 2, yA, yB, za, zm, sides=(False, False))
        flight(B, xm + cw / 2, x1, yB, yA, zm, zb, sides=(False, False))
    xa, xb = (x0 + xm - cw / 2) / 2, (xm + cw / 2 + x1) / 2
    route = [(xm, y0 + 0.5)]
    for k in range(len(levels) - 1):
        route += [(xa, y0 + 0.6), (xa, y1 - 0.6), (xb, y1 - 0.6), (xb, y0 + 0.6)]
    route.append((xm, y0 - t - 1.0))          # out through the roof door
    B.paths.append(route)
    # guard rail where the last flight drops away below the roof landing
    railing(B, [(x0, yA), (xm, yA)], top, h=1.05)
    B.g0.poly([(x0, yA, top - 0.2), (xm, yA, top - 0.2), (xm, yA, top), (x0, yA, top)], inner_mat, normal=(0, 1, 0))
    return (X0, Y0, X1, Y1)


# ------------------------------------------------------------------ furniture & props (LOD0 + collider)
def furn(B, x0, y0, z0, x1, y1, z1, mat, col=True, skip=('-z',), mats=None):
    B.g0.box(x0, y0, z0, x1, y1, z1, mat, skip=skip, mats=mats)
    if col:
        B.gc.box(x0, y0, z0, x1, y1, z1, 'COL')


def table(B, cx, cy, z, w, d, h=0.75, mat='BLD_Wood', col=True):
    x0, y0, x1, y1 = cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2
    B.g0.box(x0, y0, z + h - 0.04, x1, y1, z + h, mat)
    for lx, ly in ((x0 + 0.04, y0 + 0.04), (x1 - 0.09, y0 + 0.04), (x0 + 0.04, y1 - 0.09), (x1 - 0.09, y1 - 0.09)):
        B.g0.box(lx, ly, z, lx + 0.05, ly + 0.05, z + h - 0.04, mat, skip=('-z', '+z'))
    if col:
        B.gc.box(x0, y0, z, x1, y1, z + h, 'COL')


def chair(B, cx, cy, z, rot=0.0, mat='BLD_Wood'):
    M = Matrix.Translation((cx, cy, z)) @ Matrix.Rotation(rot, 4, 'Z')
    g = G()
    g.box(-0.22, -0.22, 0.42, 0.22, 0.22, 0.46, mat)
    g.box(-0.22, 0.17, 0.46, 0.22, 0.22, 0.92, mat)
    for lx, ly in ((-0.21, -0.21), (0.17, -0.21), (-0.21, 0.17), (0.17, 0.17)):
        g.box(lx, ly, 0, lx + 0.04, ly + 0.04, 0.42, mat, skip=('-z', '+z'))
    B.g0.merge(g, M)


def sofa(B, x0, y0, x1, y1, z, back='+y', mat='BLD_Fabric'):
    g = B.g0
    g.box(x0, y0, z, x1, y1, z + 0.42, mat, skip=('-z',))
    t = 0.2
    if back == '+y':
        g.box(x0, y1 - t, z + 0.42, x1, y1, z + 0.85, mat)
    elif back == '-y':
        g.box(x0, y0, z + 0.42, x1, y0 + t, z + 0.85, mat)
    elif back == '+x':
        g.box(x1 - t, y0, z + 0.42, x1, y1, z + 0.85, mat)
    else:
        g.box(x0, y0, z + 0.42, x0 + t, y1, z + 0.85, mat)
    B.gc.box(x0, y0, z, x1, y1, z + 0.85, 'COL')


def bed(B, x0, y0, x1, y1, z, head='+y', mat='BLD_Fabric_Beige'):
    g = B.g0
    g.box(x0, y0, z, x1, y1, z + 0.3, 'BLD_Wood', skip=('-z',))
    g.box(x0 + 0.03, y0 + 0.03, z + 0.3, x1 - 0.03, y1 - 0.03, z + 0.52, mat, skip=('-z',))
    if head == '+y':
        g.box(x0, y1 - 0.06, z, x1, y1, z + 1.0, 'BLD_Wood')
        g.box(x0 + 0.1, y1 - 0.5, z + 0.52, x1 - 0.1, y1 - 0.1, z + 0.62, 'BLD_Fabric_Beige')
    else:
        g.box(x0, y0, z, x1, y0 + 0.06, z + 1.0, 'BLD_Wood')
        g.box(x0 + 0.1, y0 + 0.1, z + 0.52, x1 - 0.1, y0 + 0.5, z + 0.62, 'BLD_Fabric_Beige')
    B.gc.box(x0, y0, z, x1, y1, z + 0.55, 'COL')


def shelf(B, x0, y0, x1, y1, z, h, mat='BLD_Wood', shelves=4, goods=None):
    """Open shelving unit; goods = list of materials for boxes on the shelves (shop stock)."""
    g = B.g0
    th = 0.03
    g.box(x0, y0, z, x0 + th, y1, z + h, mat)
    g.box(x1 - th, y0, z, x1, y1, z + h, mat)
    deep_x = (x1 - x0) < (y1 - y0)
    for i in range(shelves + 1):
        zz = z + 0.1 + (h - 0.15) * i / shelves
        g.box(x0, y0, zz, x1, y1, zz + th, mat)
        if goods and i < shelves:
            rng = random.Random(hash((round(x0, 2), round(y0, 2), i)))
            L = (y1 - y0) if deep_x else (x1 - x0)
            p = 0.05
            while p < L - 0.15:
                w = rng.uniform(0.12, 0.3)
                hh = rng.uniform(0.12, (h - 0.15) / shelves - 0.06)
                m = rng.choice(goods)
                if deep_x:
                    g.box(x0 + 0.04, y0 + p, zz + th, x1 - 0.04, y0 + p + w - 0.02, zz + th + hh, m, skip=('-z',))
                else:
                    g.box(x0 + p, y0 + 0.04, zz + th, x0 + p + w - 0.02, y1 - 0.04, zz + th + hh, m, skip=('-z',))
                p += w
    B.gc.box(x0, y0, z, x1, y1, z + h, 'COL')


def counter(B, x0, y0, x1, y1, z, h=0.92, body='BLD_Trim', top='BLD_Stone'):
    B.g0.box(x0, y0, z, x1, y1, z + h - 0.04, body, skip=('-z',))
    B.g0.box(x0 - 0.02, y0 - 0.02, z + h - 0.04, x1 + 0.02, y1 + 0.02, z + h, top)
    B.gc.box(x0, y0, z, x1, y1, z + h, 'COL')


def desk(B, cx, cy, z, rot=0.0, w=1.6, d=0.8):
    M = Matrix.Translation((cx, cy, z)) @ Matrix.Rotation(rot, 4, 'Z')
    g = G()
    g.box(-w / 2, -d / 2, 0.72, w / 2, d / 2, 0.75, 'BLD_Trim')
    g.box(-w / 2, -d / 2, 0, -w / 2 + 0.04, d / 2, 0.72, 'BLD_MetalDark', skip=('-z',))
    g.box(w / 2 - 0.04, -d / 2, 0, w / 2, d / 2, 0.72, 'BLD_MetalDark', skip=('-z',))
    g.box(-w / 2 + 0.04, d / 2 - 0.04, 0.3, w / 2 - 0.04, d / 2, 0.72, 'BLD_MetalDark')
    g.box(-0.3, 0.05, 0.75, 0.3, 0.09, 1.1, 'BLD_MetalDark')               # monitor
    g.box(-0.05, 0.09, 0.75, 0.05, 0.2, 0.85, 'BLD_MetalDark')
    g.box(0.25, -0.5, 0, 0.75, 0.0, 0.48, 'BLD_Fabric')                     # chair seat block
    g.box(0.25, -0.62, 0.48, 0.75, -0.52, 1.0, 'BLD_Fabric')
    B.g0.merge(g, M)
    c = G()
    c.box(-w / 2, -d / 2, 0, w / 2, d / 2, 0.75, 'COL')
    B.gc.merge(c, M)


def hvac(B, x, y, z, w=2.2, d=1.4, h=1.3, rot=0.0):
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
    g = G()
    g.box(-w / 2, -d / 2, 0, w / 2, d / 2, 0.15, 'BLD_MetalDark', skip=('-z',))
    g.box(-w / 2 + 0.05, -d / 2 + 0.05, 0.15, w / 2 - 0.05, d / 2 - 0.05, h, 'BLD_Galvanized', skip=('-z',))
    for fx in (-w / 4, w / 4):
        g.cyl(fx, 0, h, h + 0.12, min(w / 4, d / 2) - 0.12, 12, 'BLD_MetalDark')
    B.g0.merge(g, M)
    B.g1.merge(g, M)
    c = G()
    c.box(-w / 2, -d / 2, 0, w / 2, d / 2, h + 0.12, 'COL')
    B.gc.merge(c, M)


def water_tank(B, x, y, z, r=1.6, h=3.0, legs=2.2):
    g = G()
    for a in range(4):
        ang = a * math.pi / 2 + math.pi / 4
        lx, ly = math.cos(ang) * r * 0.8, math.sin(ang) * r * 0.8
        g.box(lx - 0.1, ly - 0.1, 0, lx + 0.1, ly + 0.1, legs, 'BLD_MetalDark', skip=('-z',))
    g.cyl(0, 0, legs, legs + h, r, 16, 'BLD_Wood', top=False, bottom=True)
    g.cyl(0, 0, legs + h, legs + h + r * 0.45, r + 0.05, 16, 'BLD_MetalDark', top=False, r1=0.08)
    g.box(-r, -r, legs - 0.12, r, r, legs, 'BLD_MetalDark')
    M = Matrix.Translation((x, y, z))
    B.g0.merge(g, M)
    B.g1.merge(g, M)
    c = G()
    c.box(-r, -r, legs - 0.12, r, r, legs + h, 'COL')
    B.gc.merge(c, M)


def antenna(B, x, y, z, h=8.0, r=0.06):
    g = G()
    g.cyl(0, 0, 0, h, r, 6, 'BLD_Galvanized')
    g.cyl(0, 0, h * 0.6, h * 0.6 + 0.6, r * 2.5, 6, 'BLD_Galvanized')
    B.g0.merge(g, Matrix.Translation((x, y, z)))
    B.g1.merge(g, Matrix.Translation((x, y, z)))


# ------------------------------------------------------------------ materials
def load_img(stem, kind, noncolor):
    name = f'T_{stem}_{kind}.png'
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(os.path.join(TEX_DIR, name), check_existing=True)
        img.name = name
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    return img


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m is not None and m.get('bk_ver') == 3:
        return m
    if m is None:
        m = bpy.data.materials.new(name)
    m['bk_ver'] = 3
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.location = (200, 0)
    nt.links.new(bs.outputs[0], out.inputs[0])
    if name == 'COL':
        bs.inputs['Base Color'].default_value = (1, 0, 1, 1)
        return m
    stem, tint, tile, kind = MATS[name]
    tl = srgb_to_lin(tint) + [1.0]
    if kind == 'glass':
        bs.inputs['Base Color'].default_value = tl
        bs.inputs['Roughness'].default_value = 0.03
        bs.inputs['Transmission Weight'].default_value = 1.0
        bs.inputs['IOR'].default_value = 1.45
        bs.inputs['Alpha'].default_value = 0.35
        m.surface_render_method = 'BLENDED'
        m.use_backface_culling = False
        m.diffuse_color = tl[:3] + [0.35]
        return m
    bc = nt.nodes.new('ShaderNodeTexImage')
    bc.image = load_img(stem, 'BaseColor', False)
    bc.location = (-600, 200)
    orm = nt.nodes.new('ShaderNodeTexImage')
    orm.image = load_img(stem, 'ORM', True)
    orm.location = (-600, -100)
    nm = nt.nodes.new('ShaderNodeTexImage')
    nm.image = load_img(stem, 'Normal', True)
    nm.location = (-600, -400)
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    mix.location = (-250, 200)
    nt.links.new(bc.outputs['Color'], mix.inputs[6])
    mix.inputs[7].default_value = tl
    nt.links.new(mix.outputs[2], bs.inputs['Base Color'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    sep.location = (-250, -100)
    nt.links.new(orm.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[1], bs.inputs['Roughness'])
    nt.links.new(sep.outputs[2], bs.inputs['Metallic'])
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nmap.location = (-250, -400)
    nt.links.new(nm.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bs.inputs['Normal'])
    m.diffuse_color = tl[:3] + [1.0]
    return m


MAT_ORDER = list(MATS) + ['COL']


def build_obj(g, name, coll, weld=True):
    me = bpy.data.meshes.get(name)
    if me:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    used = sorted({f[1] for f in g.F}, key=MAT_ORDER.index)
    me.from_pydata([tuple(v) for v in g.V], [], [f[0] for f in g.F])
    for m in used:
        me.materials.append(get_mat(m))
    mi = {m: i for i, m in enumerate(used)}
    me.polygons.foreach_set('material_index', [mi[f[1]] for f in g.F])
    me.polygons.foreach_set('use_smooth', [bool(f[3]) for f in g.F])
    uvl = me.uv_layers.new(name='UVMap')
    flat = []
    for idx, mat, uv, sm in g.F:
        if uv is None:
            uv = planar_uv([g.V[i] for i in idx], mat) if mat != 'COL' else [(0, 0)] * len(idx)
        for p in uv:
            flat += [p[0], p[1]]
    uvl.data.foreach_set('uv', flat)
    if weld:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
        bm.to_mesh(me)
        bm.free()
    me.validate()
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def finish(B, name, parent_coll, info=None):
    """Create <name> (empty root) with <name>_LOD0, <name>_LOD1 and <name>_Collider children."""
    coll = get_coll(name, parent_coll)
    for o in list(coll.objects):
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 2.0
    coll.objects.link(root)
    o0 = build_obj(B.g0, name + '_LOD0', coll)
    o1 = build_obj(B.g1, name + '_LOD1', coll)
    oc = build_obj(B.gc, name + '_Collider', coll, weld=False)
    oc.data.materials.clear()                     # collision only: no material, the renderer is removed in Unity
    for o in (o0, o1, oc):
        o.parent = root
    oc.display_type = 'WIRE'
    oc.hide_render = True
    oc.hide_set(True)
    o1.hide_render = True
    o1.hide_set(True)
    if info:
        root['bk_info'] = json.dumps(info)
    stats = dict(lod0=B.g0.tris(), lod1=B.g1.tris(), col=B.gc.tris(), mats0=len(o0.data.materials),
                 mats1=len(o1.data.materials))
    root['bk_stats'] = json.dumps(stats)
    return root, stats


# ------------------------------------------------------------------ transforms
def sub(B):
    T = B3()
    T.rng = B.rng
    return T


def put(B, T, M):
    B.g0.merge(T.g0, M)
    B.g1.merge(T.g1, M)
    B.gc.merge(T.gc, M)
    for c, n, w, h, t in T.doors:
        B.doors.append((M @ c, (M.to_3x3() @ n), w, h, t))


def flight_x(B, y0, y1, xs, xe, zs, ze, **kw):
    """flight() running along X (from xs to xe) across y0..y1."""
    T = sub(B)
    if xe < xs:
        flight(T, y0, y1, -xs, -xe, zs, ze, **kw)
        put(B, T, Matrix.Rotation(math.pi / 2, 4, 'Z'))
    else:
        flight(T, -y1, -y0, xs, xe, zs, ze, **kw)
        put(B, T, Matrix.Rotation(-math.pi / 2, 4, 'Z'))


def sloped_rail_x(B, y, xs, zs, xe, ze, h=0.95, mat='BLD_MetalDark', posts=None):
    g = B.g0
    a, b = Vector((xs, y, zs + h)), Vector((xe, y, ze + h))
    d = b - a
    g.obox(a - Vector((0, 0.02, 0)), d, Vector((0, 0.04, 0)), Vector((0, 0, 0.05)), mat)
    m = Vector((xs, y, zs + h * 0.5)), Vector((xe, y, ze + h * 0.5))
    g.obox(m[0] - Vector((0, 0.015, 0)), m[1] - m[0], Vector((0, 0.03, 0)), Vector((0, 0, 0.03)), mat)
    n = posts or max(2, int(abs(xe - xs) / 1.2) + 1)
    for i in range(n + 1):
        p = Vector((xs + (xe - xs) * i / n, y, zs + (ze - zs) * i / n))
        g.obox(p - Vector((0.02, 0.02, 0)), Vector((0.04, 0, 0)), Vector((0, 0.04, 0)), Vector((0, 0, h)), mat)
    B.gc.obox(Vector((xs, y - 0.06, zs)), Vector((xe - xs, 0, ze - zs)), Vector((0, 0.12, 0)), Vector((0, 0, h)), 'COL')


def band(B, x0, y0, x1, y1, z0, z1, mat, out=0.05, lod1=True):
    """Horizontal decorative band (belt course / cornice) wrapped around a rectangular footprint."""
    gs = (B.g0, B.g1) if lod1 else (B.g0,)
    for g in gs:
        g.box(x0 - out, y0 - out, z0, x1 + out, y0, z1, mat, skip=('+y',))
        g.box(x0 - out, y1, z0, x1 + out, y1 + out, z1, mat, skip=('-y',))
        g.box(x0 - out, y0, z0, x0, y1, z1, mat, skip=('+x', '-y', '+y'))
        g.box(x1, y0, z0, x1 + out, y1, z1, mat, skip=('-x', '-y', '+y'))


def door_on(B, W, u0, u1, side, mat='BLD_Wood', frame='BLD_Trim', h=2.05):
    """A closed door slab (with casing) mounted on one face of a partition: side 'r' = the d=0 face, 'l' = d=t face."""
    d0, d1 = (-0.035, 0.0) if side == 'r' else (W.t, W.t + 0.035)
    W.box(B.g0, u0, u1, 0.0, h, d0, d1, mat)
    e0, e1 = (-0.05, 0.0) if side == 'r' else (W.t, W.t + 0.05)
    W.box(B.g0, u0 - 0.07, u0, 0.0, h + 0.07, e0, e1, frame)
    W.box(B.g0, u1, u1 + 0.07, 0.0, h + 0.07, e0, e1, frame)
    W.box(B.g0, u0, u1, h, h + 0.07, e0, e1, frame)
    hd = (-0.09, -0.035) if side == 'r' else (W.t + 0.035, W.t + 0.09)
    W.box(B.g0, u1 - 0.18, u1 - 0.06, 1.0, 1.04, hd[0], hd[1], 'BLD_MetalDark')


def crates(B, x, y, z, rng, count=3, mat='BLD_Wood', size=(1.0, 1.2)):
    """A small stack of crates (cover)."""
    zz = z
    for i in range(count):
        s = rng.uniform(*size)
        ox, oy = rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15)
        furn(B, x + ox - s / 2, y + oy - s / 2, zz, x + ox + s / 2, y + oy + s / 2, zz + s, mat, skip=('-z',) if i == 0 else ())
        zz += s
        if rng.random() < 0.4:
            break


def curtain(B, a, b, zb, ze, z_ref, uoff=0.0, lod1=True):
    """Full-height glass curtain wall quad along a->b (outward = right of a->b), UV-locked to the CurtainWall texture
    (12 m x 4 floors of 3.6 m per tile) with floors counted from z_ref."""
    W = WF(a, b, 0.0, 0.3)
    L = W.L
    pts = [W.P(0, zb), W.P(L, zb), W.P(L, ze), W.P(0, ze)]
    uv = [(uoff, (zb - z_ref) / 14.4), (uoff + L / 12, (zb - z_ref) / 14.4), (uoff + L / 12, (ze - z_ref) / 14.4),
          (uoff, (ze - z_ref) / 14.4)]
    for g in ((B.g0, B.g1) if lod1 else (B.g0,)):
        g.poly(pts, 'BLD_CurtainWall', uv=uv, normal=W.n)
    return W


def rect_sides(x0, y0, x1, y1):
    return [('front', (x0, y0), (x1, y0)), ('right', (x1, y0), (x1, y1)), ('back', (x1, y1), (x0, y1)),
            ('left', (x0, y1), (x0, y0))]


def column(B, cx, cy, z0, z1, w=0.7, mat='BLD_Concrete', round_=False):
    if round_:
        B.g0.cyl(cx, cy, z0, z1, w / 2, 16, mat, top=False)
    else:
        B.g0.box(cx - w / 2, cy - w / 2, z0, cx + w / 2, cy + w / 2, z1, mat, skip=('-z', '+z'))
    B.gc.box(cx - w / 2, cy - w / 2, z0, cx + w / 2, cy + w / 2, z1, 'COL')


def planter(B, x0, y0, x1, y1, z, h=0.8):
    furn(B, x0, y0, z, x1, y1, z + h, 'BLD_ConcreteDark')
    B.g0.box(x0 + 0.08, y0 + 0.08, z + h, x1 - 0.08, y1 - 0.08, z + h + 0.35, 'BLD_TrimGreen', skip=('-z',))
