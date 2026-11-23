# Airship Kit - "Leviathan" troop airship: 160 m envelope, two-deck gondola, 200-seat troop deck.
# Needs tk_core.py, tk_tank.py, ak_core.py and as_tex.py exec'd first in the same namespace.
# Coordinates: X = left(+)/right(-), Y = back(+)/front(-), Z = up. Origin = lower troop-deck floor, gondola centre.

AS_DIR = globals().get('AS_DIR')
TEX_DIR = os.path.join(AS_DIR, 'textures')
GLB_DIR = os.path.join(AS_DIR, 'glb')

ENV, HUL, WOD, WAL, DMT, BRS, FAB, GLS, LMP, DEC, RED = range(11)
TILE = {ENV: (2.0, 10.0), HUL: (3.0, 2.0), WOD: (2.0, 2.0), WAL: (2.0, 3.0), DMT: (1.0, 1.0), BRS: (0.5, 0.5),
        FAB: (1.0, 1.0), GLS: (2.0, 2.0), LMP: (1.0, 1.0), RED: (1.0, 1.0), DEC: (1.0, 1.0)}
ZE = 22.5                                   # envelope axis height
FL0, CL0, FL1, CL1, ROOF = 0.0, 3.1, 3.3, 6.3, 7.2
WT = 0.25                                   # gondola wall thickness
HALF = [(0.0, -32.0), (1.5, -31.8), (3.2, -31.0), (4.6, -29.6), (5.6, -27.8), (6.0, -25.6), (6.0, 28.4),
        (5.5, 30.6), (4.2, 32.0)]
PLAN = HALF + [(-x, y) for x, y in reversed(HALF[1:])]
ENV_KEYS = [(-75.6, 2.2), (-74.5, 5.0), (-72.0, 8.4), (-68.0, 11.2), (-62.0, 13.2), (-54.0, 14.5), (-44.0, 15.0),
            (-20.0, 15.0), (10.0, 14.8), (30.0, 14.0), (48.0, 12.0), (62.0, 9.2), (74.0, 5.6), (81.0, 2.6),
            (83.5, 1.0)]


# ------------------------------------------------------------------------------ materials
def img_from(name, rgb, alpha=None, noncolor=False):
    h, w = rgb.shape[:2]
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=alpha is not None)
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb
    if alpha is not None:
        px[..., 3] = alpha
    img.pixels.foreach_set(px.ravel())
    save_image(img, name + '.png')
    return img


def tex_material(name, gen):
    col, orm, nrm = gen()
    return final_material(f'MAT_{name}', img_from(f'T_{name}_BaseColor', col),
                          img_from(f'T_{name}_ORM', orm, noncolor=True),
                          img_from(f'T_{name}_Normal', nrm, noncolor=True))


def flat_material(name, color, rough, metal=0.0, emit=0.0, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = NT(mat)
    b = nt.n('ShaderNodeBsdfPrincipled')
    out = nt.n('ShaderNodeOutputMaterial')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*color, 1)
        b.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        mat.surface_render_method = 'BLENDED'
        mat.use_backface_culling = False
    nt.L.new(b.outputs[0], out.inputs['Surface'])
    return mat


def decal_material():
    col, alpha = tex_emblem()
    img = img_from('T_Emblem', col, alpha)
    mat = bpy.data.materials.get('MAT_Emblem') or bpy.data.materials.new('MAT_Emblem')
    nt = NT(mat)
    ti = nt.n('ShaderNodeTexImage', image=img)
    b = nt.n('ShaderNodeBsdfPrincipled')
    gt = nt.n('ShaderNodeMath', operation='GREATER_THAN')
    gt.inputs[1].default_value = 0.5
    out = nt.n('ShaderNodeOutputMaterial')
    nt.L.new(ti.outputs['Color'], b.inputs['Base Color'])
    nt.L.new(ti.outputs['Alpha'], gt.inputs[0])
    nt.L.new(gt.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.7
    nt.L.new(b.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'DITHERED'
    return mat


def build_materials():
    M = [None] * 11
    M[ENV] = tex_material('Envelope', tex_envelope)
    M[HUL] = tex_material('HullPlating', tex_plating)
    M[WOD] = tex_material('DeckPlanks', tex_planks)
    M[WAL] = tex_material('InteriorWall', tex_wall)
    M[DMT] = tex_material('DarkMetal', tex_darkmetal)
    M[BRS] = tex_material('Brass', tex_brass)
    M[FAB] = tex_material('Canvas', tex_canvas)
    M[GLS] = flat_material('MAT_Glass', (0.10, 0.13, 0.14), 0.04, alpha=0.22)
    M[LMP] = flat_material('MAT_Lamp', (1.0, 0.78, 0.5), 0.3, emit=5.0)
    M[DEC] = decal_material()
    M[RED] = flat_material('MAT_RedPaint', (0.5, 0.07, 0.05), 0.45)
    return M


# ------------------------------------------------------------------------------ plan helpers
def env_r(y):
    k = ENV_KEYS
    if y <= k[0][0]:
        return k[0][1]
    if y >= k[-1][0]:
        return k[-1][1]
    for i in range(len(k) - 1):
        if k[i][0] <= y <= k[i + 1][0]:
            p0, p1, p2, p3 = k[max(i - 1, 0)], k[i], k[i + 1], k[min(i + 2, len(k) - 1)]
            t = (y - p1[0]) / (p2[0] - p1[0])
            return max(_cr(p0[1], p1[1], p2[1], p3[1], t), 0.3)


def offset_poly(poly, t):
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = Vector(poly[i]), Vector(poly[(i + 1) % n])
        d = (b - a).normalized()
        nrm = Vector((-d.y, d.x))
        lines.append((a + nrm * t, d))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1.x * d2.y - d1.y * d2.x
        if abs(den) < 1e-9:
            out.append(tuple(p2))
            continue
        s = ((p2.x - p1.x) * d2.y - (p2.y - p1.y) * d2.x) / den
        out.append(tuple(p1 + d1 * s))
    return out


def ring(poly, z, sx=1.0, sy=1.0):
    return [(x * sx, y * sy, z) for x, y in poly]


# ------------------------------------------------------------------------------ walls & slabs
def wall(mb, A, B, z0, z1, t, openings=(), zbreaks=(), mo=HUL, mi=WAL, rev=DMT):
    """thick wall from A to B (2D outer line), interior on the left side. openings: (u0,u1,za,zb,kind)."""
    A, B = Vector(A), Vector(B)
    L = (B - A).length
    d = (B - A) / L
    n = Vector((-d.y, d.x))
    us = sorted({0.0, L} | {o[0] for o in openings} | {o[1] for o in openings})
    zs = sorted({z0, z1} | {o[2] for o in openings} | {o[3] for o in openings} | {z for z in zbreaks if z0 < z < z1})
    cache = {}

    def V(i, j, s):
        k = (i, j, s)
        if k not in cache:
            p = A + d * us[i] + (n * t if s else Vector((0, 0)))
            cache[k] = mb.bm.verts.new((p.x, p.y, zs[j]))
        return cache[k]

    def inside(uc, zc):
        return any(o[0] < uc < o[1] and o[2] < zc < o[3] for o in openings)
    for i in range(len(us) - 1):
        for j in range(len(zs) - 1):
            if inside((us[i] + us[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2):
                continue
            mb.face((V(i, j, 0), V(i + 1, j, 0), V(i + 1, j + 1, 0), V(i, j + 1, 0)), mo)
            mb.face((V(i, j + 1, 1), V(i + 1, j + 1, 1), V(i + 1, j, 1), V(i, j, 1)), mi)
    for o in openings:
        i0, i1 = us.index(o[0]), us.index(o[1])
        j0, j1 = zs.index(o[2]), zs.index(o[3])
        for i in range(i0, i1):
            mb.face((V(i, j0, 0), V(i + 1, j0, 0), V(i + 1, j0, 1), V(i, j0, 1)), rev)
            mb.face((V(i + 1, j1, 0), V(i, j1, 0), V(i, j1, 1), V(i + 1, j1, 1)), rev)
        for j in range(j0, j1):
            mb.face((V(i0, j + 1, 0), V(i0, j, 0), V(i0, j, 1), V(i0, j + 1, 1)), rev)
            mb.face((V(i1, j, 0), V(i1, j + 1, 0), V(i1, j + 1, 1), V(i1, j, 1)), rev)
        if o[4] == 'win':
            pm = A + d * ((o[0] + o[1]) / 2) + n * (t * 0.45)
            hw = (o[1] - o[0]) / 2
            q = [mb.bm.verts.new((pm.x + d.x * su * hw, pm.y + d.y * su * hw, z))
                 for su, z in ((-1, o[2]), (1, o[2]), (1, o[3]), (-1, o[3]))]
            mb.face(q, GLS)
            mid = A + d * ((o[0] + o[1]) / 2) + n * (t * 0.45)
            mb.box((0, 0, 0), (0.05, 0.06, o[3] - o[2]), DMT,
                   M=Mt(mid.x, mid.y, (o[2] + o[3]) / 2) @ Mrz(math.atan2(d.y, d.x)))
    for j in range(len(zs) - 1):
        mb.face((V(0, j, 1), V(0, j + 1, 1), V(0, j + 1, 0), V(0, j, 0)), mo)
        last = len(us) - 1
        mb.face((V(last, j, 0), V(last, j + 1, 0), V(last, j + 1, 1), V(last, j, 1)), mo)
    for i in range(len(us) - 1):
        mb.face((V(i + 1, 0, 0), V(i, 0, 0), V(i, 0, 1), V(i + 1, 0, 1)), mo)
        top = len(zs) - 1
        mb.face((V(i, top, 0), V(i + 1, top, 0), V(i + 1, top, 1), V(i, top, 1)), mo)


def slab(mb, x0, x1, y0, y1, zb, zt, holes=(), mt=WOD, mbot=WAL, side=DMT):
    xs = sorted({x0, x1} | {h[0] for h in holes} | {h[1] for h in holes})
    ys = sorted({y0, y1} | {h[2] for h in holes} | {h[3] for h in holes})
    cache = {}

    def V(i, j, s):
        k = (i, j, s)
        if k not in cache:
            cache[k] = mb.bm.verts.new((xs[i], ys[j], zt if s else zb))
        return cache[k]

    def inside(xc, yc):
        return any(h[0] < xc < h[1] and h[2] < yc < h[3] for h in holes)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if inside((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2):
                continue
            mb.face((V(i, j, 1), V(i + 1, j, 1), V(i + 1, j + 1, 1), V(i, j + 1, 1)), mt)
            mb.face((V(i, j + 1, 0), V(i + 1, j + 1, 0), V(i + 1, j, 0), V(i, j, 0)), mbot)
    for h in holes:
        i0, i1, j0, j1 = xs.index(h[0]), xs.index(h[1]), ys.index(h[2]), ys.index(h[3])
        for i in range(i0, i1):
            mb.face((V(i, j0, 1), V(i + 1, j0, 1), V(i + 1, j0, 0), V(i, j0, 0)), side)
            mb.face((V(i + 1, j1, 1), V(i, j1, 1), V(i, j1, 0), V(i + 1, j1, 0)), side)
        for j in range(j0, j1):
            mb.face((V(i0, j + 1, 1), V(i0, j, 1), V(i0, j, 0), V(i0, j + 1, 0)), side)
            mb.face((V(i1, j, 1), V(i1, j + 1, 1), V(i1, j + 1, 0), V(i1, j, 0)), side)
    for i in range(len(xs) - 1):
        mb.face((V(i, 0, 0), V(i + 1, 0, 0), V(i + 1, 0, 1), V(i, 0, 1)), side)
        mb.face((V(i + 1, len(ys) - 1, 0), V(i, len(ys) - 1, 0), V(i, len(ys) - 1, 1), V(i + 1, len(ys) - 1, 1)), side)


def deck(mb, zb, zt, holes=(), mt=WOD, mbot=WAL):
    ins = offset_poly(PLAN, WT)
    nh = len(HALF)
    cf, cr = ins[5], ins[6]                     # inset corners at the straight side
    slab(mb, -cf[0], cf[0], cf[1], cr[1], zb, zt, holes, mt, mbot)
    nose = [p for p in ins if p[1] <= cf[1] + 1e-3]
    tail = [p for p in ins if p[1] >= cr[1] - 1e-3]
    for poly in (nose, tail):
        c = Vector((sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)))
        poly = sorted(poly, key=lambda p: math.atan2(p[1] - c.y, p[0] - c.x))
        mb.loft([ring(poly, zb), ring(poly, zt)], DMT, cap_mats=(mbot, mt))


def bulkhead(mb, y, z0, z1, door=None, t=0.12):
    xw = 6.0 - WT
    ops = []
    if door:
        x0, x1, h = door
        ops = [(xw - x1, xw - x0, z0, z0 + h, 'door')]
    wall(mb, (xw, y - t / 2), (-xw, y - t / 2), z0, z1, t, ops, mo=WAL, mi=WAL)
    if door:
        x0, x1, h = door
        for x in (x0, x1):
            mb.box((x, y, z0 + h / 2), (0.08, t + 0.06, h), DMT)
        mb.box(((x0 + x1) / 2, y, z0 + h + 0.04), (x1 - x0 + 0.16, t + 0.06, 0.08), DMT)


# ------------------------------------------------------------------------------ props & furniture
def lamp(S, mb, c, hang=0.0):
    x, y, z = c
    mb.cyl(0.1, 0.05, 8, DMT, M=frame((x, y, z), (0, 0, -1)), x0=0.0)
    if hang:
        mb.cyl(0.012, hang, 4, DMT, M=frame((x, y, z), (0, 0, -1)), x0=0.0)
    zb = z - hang - 0.05
    mb.lathe([(0, 0), (0.07, 0.0), (0.09, 0.08), (0.07, 0.16), (0, 0.17)], 8, LMP, M=frame((x, y, zb), (0, 0, -1)))
    for k in range(4):
        a = k * math.pi / 2
        p0 = Vector((x + 0.1 * math.cos(a), y + 0.1 * math.sin(a), zb))
        beam(mb, p0, p0 + Vector((0, 0, -0.17)), 0.012, 0.012, DMT)
    S.lights.append((x, y, zb - 0.12))


def chair(mb, c, yaw=0.0):
    M = Mt(*c) @ Mrz(yaw)
    for sx in (-0.2, 0.2):
        for sy in (-0.18, 0.18):
            mb.box((sx, sy, 0.23), (0.04, 0.04, 0.46), DMT, M=M)
    mb.box((0, 0, 0.48), (0.46, 0.44, 0.06), FAB, M=M)
    mb.box((0, 0.2, 0.8), (0.44, 0.04, 0.5), FAB, M=M)


def table(mb, c, w, d, h=0.76, top=WOD):
    x, y, z = c
    mb.box((x, y, z + h - 0.025), (w, d, 0.05), top)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((x + sx * (w / 2 - 0.06), y + sy * (d / 2 - 0.06), z + (h - 0.05) / 2), (0.05, 0.05, h - 0.05), DMT)


def crate(mb, c, s, yaw=0.0):
    M = Mt(*c) @ Mrz(yaw)
    mb.box((0, 0, s[2] / 2), s, WOD, M=M)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * (s[0] / 2), sy * (s[1] / 2), s[2] / 2), (0.05, 0.05, s[2] + 0.01), DMT, M=M)
    mb.box((0, -s[1] / 2 - 0.005, s[2] * 0.6), (s[0] * 0.4, 0.01, s[2] * 0.2), RED, M=M)


def barrel(mb, c, r=0.3, h=0.9, mat=DMT):
    mb.lathe([(0, 0), (r * 0.95, 0), (r, 0.05), (r * 1.04, h * 0.3), (r * 1.04, h * 0.7), (r, h - 0.05),
              (r * 0.95, h), (0, h)], 12, mat, M=frame(c, (0, 0, 1)))


def rifle(mb, base, yaw, lean=0.12):
    M = Mt(*base) @ Mrz(yaw) @ Mrx(-lean)
    mb.box((0, 0, 0.18), (0.05, 0.12, 0.36), WOD, M=M, top=(1, 0.6))
    mb.box((0, 0.01, 0.55), (0.045, 0.06, 0.4), WOD, M=M)
    mb.box((0, 0.0, 0.5), (0.05, 0.09, 0.12), DMT, M=M)
    mb.cyl(0.012, 0.55, 5, DMT, M=M @ frame((0, 0.0, 0.72), (0, 0, 1)), x0=0.0)


def stairs(mb, x0, x1, ya, yb, z0, z1, n=16):
    """stair from (ya, z0) to (yb, z1); ya->yb may run either direction."""
    run = (yb - ya) / n
    rise = (z1 - z0) / n
    for k in range(n):
        y = ya + run * (k + 0.5)
        mb.box(((x0 + x1) / 2, y, z0 + rise * (k + 0.5) - 0.02), (x1 - x0 - 0.1, abs(run) + 0.02, 0.05), WOD)
    for x in (x0 + 0.03, x1 - 0.03):
        a = Vector((x, ya, z0))
        b = Vector((x, yb, z1))
        beam(mb, a + Vector((0, 0, -0.1)), b + Vector((0, 0, -0.1)), 0.06, 0.22, DMT)
    for x in (x0 + 0.05, x1 - 0.05):
        a = Vector((x, ya, z0 + 0.95))
        b = Vector((x, yb, z1 + 0.95))
        beam(mb, a, b, 0.04, 0.04, BRS)
        for f in (0.0, 0.5, 1.0):
            p = a.lerp(b, f)
            beam(mb, p, p - Vector((0, 0, 0.95)), 0.035, 0.035, DMT)


def railing(mb, pts, z, h=1.0):
    for a, b in zip(pts, pts[1:]):
        A, B = Vector((a[0], a[1], z + h)), Vector((b[0], b[1], z + h))
        beam(mb, A, B, 0.05, 0.05, BRS)
        beam(mb, A - Vector((0, 0, h * 0.5)), B - Vector((0, 0, h * 0.5)), 0.035, 0.035, DMT)
    for p in pts:
        beam(mb, (p[0], p[1], z), (p[0], p[1], z + h), 0.045, 0.045, DMT)


def gauge(mb, c, n, r=0.06):
    mb.cyl(r, 0.04, 10, BRS, M=frame(c, n), x0=0.0)
    mb.cyl(r * 0.85, 0.045, 10, GLS, M=frame(c, n), x0=0.0)


def pipe(mb, a, b, r=0.05, mat=DMT, segs=8):
    a, b = Vector(a), Vector(b)
    mb.cyl(r, (b - a).length, segs, mat, M=frame(a, b - a), x0=0.0)


def fire_ext(mb, c):
    x, y, z = c
    mb.lathe([(0, 0), (0.08, 0), (0.08, 0.42), (0.05, 0.5), (0.02, 0.56), (0, 0.56)], 8, RED, M=frame(c, (0, 0, 1)))
    mb.box((x, y, z + 0.56), (0.03, 0.12, 0.03), DMT)


# ------------------------------------------------------------------------------ the ship
class Ship(Tank):
    def __init__(self, name):
        self.name, self.origin = name, Vector((0, 0, 0))
        self.coll = get_coll('Airship')
        self.mbs, self.objs, self.bones, self.wheel_drv = {}, [], [], []
        self.guns, self.flashes, self.tracks, self.meta, self.temp_meshes = [], [], {}, {}, []
        self.mat_list = build_materials()
        self.seats, self.lights, self.controls, self.turrets, self.props = [], [], {}, [], []
        self.doors = {}
        self.extra = []


def side_wall_openings(u_of_y, y_ranges_door, deck_windows):
    pass


def build_gondola(S):
    ext = S.mb('exterior', 'body', 'static')
    lo = S.mb('int_lower', 'body', 'static')
    up = S.mb('int_upper', 'body', 'static')
    zbreaks = (FL0, CL0, FL1, CL1)
    n = len(PLAN)
    win_c = [-22.8 + 2.4 * k for k in range(22) if -22.8 + 2.4 * k < 27.0]
    for i in range(n):
        A, B = Vector(PLAN[i]), Vector(PLAN[(i + 1) % n])
        L = (B - A).length
        d = (B - A) / L
        ops = []

        def y_to_u(y):
            return (y - A.y) / d.y
        if abs(d.x) < 1e-6 and L > 20:          # long straight side walls
            right = A.x < 0
            for c in win_c:
                u = y_to_u(c)
                lo_u = sorted((u - 0.4, u + 0.4))
                up_u = sorted((u - 0.65, u + 0.65))
                if abs(c + 6.0) > 1.6 and not (right and 20.5 < c < 26.0):
                    ops.append((lo_u[0], lo_u[1], 1.45, 2.15, 'win'))
                ops.append((up_u[0], up_u[1], 4.3, 5.5, 'win'))
            du = sorted((y_to_u(-7.1), y_to_u(-4.9)))
            ops.append((du[0], du[1], 0.0, 2.4, 'door'))
        elif abs(d.y) < 1e-6:                    # rear wall with the ramp
            ops.append((L / 2 - 2.0, L / 2 + 2.0, 0.0, 2.8, 'door'))
            for c in (L / 2 - 2.6, L / 2 + 2.6):
                ops.append((c - 0.55, c + 0.55, 4.3, 5.5, 'win'))
        else:                                    # nose / tail facets
            m = 0.22
            if A.y < 0 or B.y < 0:
                ops.append((m, L - m, 3.85, 6.05, 'win'))
                if L > 1.5:
                    ops.append((m + 0.2, L - m - 0.2, 1.3, 2.2, 'win'))
            else:
                ops.append((m, L - m, 4.3, 5.5, 'win'))
        wall(ext, A, B, -0.2, ROOF, WT, ops, zbreaks)
    # keel, roof, decks
    ext.loft([ring(PLAN, -0.2), ring(PLAN, -0.8, 0.9, 0.97), ring(PLAN, -1.25, 0.62, 0.9)], HUL)
    ins = offset_poly(PLAN, WT)
    ext.loft([ring(ins, CL1), ring(PLAN, ROOF), ring(PLAN, ROOF + 0.55, 0.86, 0.95)], HUL,
             ring_mats=[DMT, HUL], cap_mats=(WAL, HUL))
    deck(lo, -0.2, FL0, ())
    deck(up, CL0, FL1, [(3.4, 5.4, -25.4, -21.3), (-5.4, -3.4, 21.0, 25.4)])
    # exterior trim: belt rails, door frames + tracks, searchlights, nav lights, ladders, keel details
    for z in (-0.2, FL1 - 0.1, ROOF):
        for s in (1, -1):
            ext.box((s * 6.04, 1.4, z), (0.08, 53.6, 0.12), DMT)
    for s in (1, -1):
        ext.box((s * 6.06, -4.8, 2.58), (0.06, 4.8, 0.1), DMT)
        for yy in (-7.2, -4.8):
            ext.box((s * 6.04, yy, 1.2), (0.06, 0.1, 2.5), DMT)
        for k in range(10):
            ext.box((s * 6.1, 12.0, 0.4 + k * 0.7), (0.06, 0.5, 0.04), DMT)
        for yy in (11.76, 12.24):
            ext.box((s * 6.12, yy, 3.6), (0.05, 0.05, 6.6), DMT)
    for s in (1, -1):
        c = Vector((s * 2.2, -31.6, 6.7))
        ext.lathe([(0, -0.3), (0.32, -0.3), (0.36, 0.2), (0.3, 0.25), (0, 0.25)], 14, DMT,
                  M=frame(c, (0, -1, 0)))
        ext.cyl(0.29, 0.02, 14, LMP, M=frame(c + Vector((0, -0.25, 0)), (0, -1, 0)), x0=0.0)
        ext.box((s * 2.2, -31.2, 6.4), (0.15, 0.3, 0.4), DMT)
        ext.box((s * 6.06, -24.0, 6.6), (0.08, 0.2, 0.2), RED if s < 0 else LMP)
    ext.lathe([(0, 0), (0.5, 0), (0.6, 0.5), (0.3, 0.9), (0, 1.0)], 12, DMT, M=frame((0, -30.0, -0.9), (0, 0, -1)))
    for yy in range(-24, 28, 4):
        ext.box((0, yy, -1.27), (2.0, 0.3, 0.06), DMT)
    # pylons and fairing to the envelope
    for yy in (-24.0, -8.0, 8.0, 24.0):
        for s in (1, -1):
            zt = ZE - math.sqrt(max(env_r(yy) ** 2 - (s * 3.0) ** 2, 1.0))
            beam(ext, (s * 4.8, yy, ROOF + 0.1), (s * 3.0, yy, zt + 0.3), 0.25, 0.35, DMT)
    for yy in (-16.0, 0.0, 16.0):
        beam(ext, (0, yy, ROOF + 0.4), (0, yy, ZE - env_r(yy) + 0.3), 0.4, 0.6, HUL)
    # roof walkway + hatch + antenna
    ext.box((0, 2.0, ROOF + 0.6), (1.2, 50.0, 0.06), WOD)
    railing(ext, [(1.4, -22.0), (1.4, 26.0)], ROOF + 0.55, 0.9)
    railing(ext, [(-1.4, -22.0), (-1.4, 26.0)], ROOF + 0.55, 0.9)
    as_hatch(ext, (0, -8.0, ROOF + 0.63), 0.45)
    for s in (1, -1):
        as_antenna(ext, (s * 4.0, 29.0, ROOF + 0.3), 4.0)
    # hull stripes (squadron band) on the tail facets
    for s in (1, -1):
        ext.box((s * 6.05, 26.2, 2.85), (0.03, 2.0, 0.22), RED)
        ext.box((s * 6.05, 26.2, 3.6), (0.03, 2.0, 0.22), RED)


def build_lower(S):
    mb = S.mb('int_lower', 'body', 'static')
    bulkhead(mb, -21.0, FL0, CL0, (-0.6, 0.6, 2.1))
    bulkhead(mb, 13.0, FL0, CL0, (-1.6, 1.6, 2.6))
    # frames: wall ribs + ceiling beams
    for k in range(23):
        y = -24.0 + 2.4 * k
        if y > 28.0:
            break
        for s in (1, -1):
            mb.box((s * 5.68, y, CL0 / 2), (0.14, 0.12, CL0), DMT)
        mb.box((0, y, CL0 - 0.08), (11.4, 0.12, 0.16), DMT)
    pipe(mb, (0, -21.0, 2.75), (0, 13.0, 2.75), 0.18, DMT, 12)
    for s in (1, -1):
        pipe(mb, (s * 5.55, -31.0 + 3.0, 2.95), (s * 5.55, 31.0, 2.95), 0.04, BRS)
        pipe(mb, (s * 5.5, -21.0, 2.85), (s * 5.5, 31.0, 2.85), 0.03, DMT)
        pipe(mb, (s * 2.9, -20.8, 2.55), (s * 2.9, 12.8, 2.55), 0.025, DMT, 6)   # static-line cables
    # --- troop bay: 4 rows x 50 seats = 200
    seat_ys = [-20.4 + 0.6 * k for k in range(22)] + [-4.3 + 0.6 * k for k in range(28)]
    rows = [(5.3, -1), (-5.3, 1), (0.75, 1), (-0.75, -1)]     # x, facing direction (x sign)
    for xr, f in rows:
        wallrow = abs(xr) > 3
        bx = xr + (-f) * 0.05
        mb.box((bx, -14.0, 0.44), (0.5, 13.3, 0.05), DMT)
        mb.box((bx, 4.15, 0.44), (0.5, 17.3, 0.05), DMT)
        for yy in list(range(-20, -7, 2)) + list(range(-4, 13, 2)):
            mb.box((bx, yy + 0.1, 0.21), (0.06, 0.06, 0.42), DMT)
        for y in seat_ys:
            mb.box((xr, y, 0.49), (0.46, 0.52, 0.07), FAB, top=(0.95, 0.95))
            back_x = xr - f * 0.27
            mb.box((back_x, y, 0.85), (0.05 if wallrow else 0.04, 0.5, 0.62), FAB)
            if wallrow:
                mb.box((back_x - f * 0.05, y, 1.3), (0.06, 0.06, 0.18), DMT)
                mb.box((xr - f * 0.1, y + 0.2, 1.1), (0.03, 0.04, 0.55), FAB)
            S.seats.append(((xr, y, 0.53), (f, 0.0, 0.0)))
        if not wallrow:
            mb.box((xr - f * 0.3, -14.0, 0.85), (0.04, 13.3, 0.7), DMT)
            mb.box((xr - f * 0.3, 4.15, 0.85), (0.04, 17.3, 0.7), DMT)
    for y in range(-20, 13, 3):
        for x in (2.9, -2.9):
            mb.box((x, y, 2.25), (0.03, 0.06, 0.55), FAB)
            mb.box((x, y, 1.95), (0.08, 0.14, 0.03), FAB)
    for y in range(-19, 13, 4):
        for x in (2.9, -2.9):
            lamp(S, mb, (x, y, CL0 - 0.16), 0.05)
    for s in (1, -1):
        mb.box((s * 5.55, -6.0, 2.62), (0.12, 0.3, 0.18), DMT)
        mb.box((s * 5.48, -6.08, 2.62), (0.04, 0.1, 0.1), RED)
        mb.box((s * 5.48, -5.92, 2.62), (0.04, 0.1, 0.1), LMP)
        fire_ext(mb, (s * 5.5, -7.6, 0.0))
        fire_ext(mb, (s * 5.5, 12.4, 0.0))
    mb.box((5.4, -20.7, 1.4), (0.3, 0.3, 0.3), RED)
    # --- radio / navigation room (nose, lower deck)
    for s, yy in ((1, -27.5), (-1, -27.5)):
        table(mb, (s * 4.2, yy, 0), 1.1, 2.6)
        for k, dy in enumerate((-0.8, 0.4)):
            mb.box((s * 4.45, yy + dy, 1.05), (0.5, 0.9, 0.55), DMT, top=(0.95, 0.9))
            for gx in (-0.25, 0.0, 0.25):
                gauge(mb, (s * 4.18, yy + dy + gx, 1.15), (-s, 0, 0), 0.05)
            mb.box((s * 4.18, yy + dy, 0.92), (0.02, 0.6, 0.1), BRS)
        chair(mb, (s * 3.3, yy - 0.3, 0), math.pi / 2 * s)
    table(mb, (0, -24.0, 0), 1.6, 1.0, 0.9)
    mb.box((0, -24.0, 0.905), (1.4, 0.8, 0.01), FAB)
    for s in (1, -1):
        mb.box((s * 1.8, -22.0, 0.75), (0.7, 0.5, 1.5), DMT)
    stairs(mb, 3.4, 5.4, -21.3, -25.4, FL0, FL1)
    lamp(S, mb, (0, -24.0, CL0 - 0.1), 0.3)
    lamp(S, mb, (-3.2, -28.0, CL0 - 0.1), 0.2)
    # --- cargo bay: crates, barrels, rails, rear stair
    for x in (-1.9, 1.9):
        mb.box((x, 22.4, 0.02), (0.08, 18.6, 0.04), DMT)
    rng = np.random.default_rng(9)
    for s in (1, -1):
        for k, yy in enumerate((14.2, 15.6, 17.0, 18.4)):
            crate(mb, (s * 4.7, yy, 0), (1.2, 1.2, 1.0), rng.uniform(-0.05, 0.05))
            if k % 2 == 0:
                crate(mb, (s * 4.7, yy + 0.1, 1.0), (1.0, 1.0, 0.8), rng.uniform(-0.1, 0.1))
        for k in range(3):
            barrel(mb, (s * 3.35, 14.4 + k * 0.7, 0), 0.3, 0.9, RED if k == 1 else DMT)
    for yy in (27.0, 28.4, 29.8):
        crate(mb, (4.7, yy, 0), (1.2, 1.2, 1.0))
        crate(mb, (4.6, yy, 1.0), (0.9, 0.7, 0.4))
    for k in range(4):
        crate(mb, (-4.6, 27.0 + k * 1.0, 0), (1.0, 0.9, 0.5))
    stairs(mb, -5.4, -3.4, 21.0, 25.4, FL0, FL1)
    for yy in (16.0, 20.0, 24.0, 28.0):
        lamp(S, mb, (0, yy, CL0 - 0.1), 0.25)
    mb.box((-2.6, 31.4, 1.4), (0.3, 0.2, 0.5), DMT)
    mb.box((-2.6, 31.28, 1.5), (0.1, 0.04, 0.1), RED)


def build_upper(S):
    mb = S.mb('int_upper', 'body', 'static')
    z = FL1
    bulkhead(mb, -26.0, FL1, CL1, (-0.6, 0.6, 2.1))
    bulkhead(mb, -14.0, FL1, CL1, (-0.6, 0.6, 2.1))
    bulkhead(mb, 6.0, FL1, CL1, (-0.7, 0.7, 2.1))
    bulkhead(mb, 18.0, FL1, CL1, (-0.6, 0.6, 2.1))
    for k in range(23):
        y = -24.0 + 2.4 * k
        if y > 28.0:
            break
        for s in (1, -1):
            mb.box((s * 5.68, y, z + 1.5), (0.14, 0.12, 3.0), DMT)
        mb.box((0, y, CL1 - 0.08), (11.4, 0.12, 0.16), DMT)
    for s in (1, -1):
        pipe(mb, (s * 5.5, -28.0, CL1 - 0.15), (s * 5.5, 31.0, CL1 - 0.15), 0.035, BRS)
    pipe(mb, (1.5, -26.0, CL1 - 0.3), (1.5, 31.0, CL1 - 0.3), 0.12, DMT, 10)
    railing(mb, [(3.4, -21.3), (3.4, -25.4), (5.4, -25.4)], z)
    railing(mb, [(-3.4, 21.0), (-3.4, 25.4), (-5.4, 25.4)], z)
    # --- bridge
    console_pts = [(-5.2, -27.4), (-4.2, -29.2), (-2.6, -30.4), (-0.9, -31.0), (0.9, -31.0), (2.6, -30.4),
                   (4.2, -29.2), (5.2, -27.4)]
    for a, b in zip(console_pts, console_pts[1:]):
        A, B = Vector(a), Vector(b)
        mid = (A + B) / 2
        ang = math.atan2(B.y - A.y, B.x - A.x)
        L = (B - A).length
        mb.box((0, 0, 0), (L, 0.6, 0.95), DMT, M=Mt(mid.x, mid.y, z + 0.475) @ Mrz(ang), top=(1, 0.7),
               top_off=(0, -0.1))
        nrm = Vector((-(B.y - A.y), B.x - A.x)).normalized()
        for f in (0.3, 0.7):
            p = A.lerp(B, f) + nrm * 0.25
            gauge(mb, (p.x, p.y, z + 1.02), (nrm.x * 0.5, nrm.y * 0.5, 0.85), 0.07)
        p = A.lerp(B, 0.5) + nrm * 0.15
        mb.box((p.x, p.y, z + 0.96), (0.12, 0.12, 0.04), BRS)
    hc = Vector((0, -29.2, z))
    mb.lathe([(0, 0), (0.35, 0), (0.25, 0.1), (0.14, 0.2), (0.12, 1.0), (0.18, 1.05), (0, 1.1)], 12, DMT,
             M=frame(hc, (0, 0, 1)))
    wc = hc + Vector((0, 0.15, 1.25))
    mb.lathe([(0.55, -0.03), (0.6, 0.0), (0.55, 0.03), (0.5, 0.0), (0.55, -0.03)], 24, WOD, M=frame(wc, (0, 1, 0)))
    mb.cyl(0.08, 0.12, 10, BRS, M=frame(wc, (0, 1, 0)))
    for k in range(8):
        a = k * TAU / 8
        d = Vector((math.cos(a), 0, math.sin(a)))
        beam(mb, wc, wc + d * 0.55, 0.03, 0.03, WOD)
        mb.cyl(0.022, 0.16, 6, WOD, M=frame(wc + d * 0.6, d), x0=0.0)
    for s in (1, -1):
        tc = Vector((s * 1.3, -28.8, z))
        mb.lathe([(0, 0), (0.25, 0), (0.15, 0.1), (0.1, 0.95), (0.25, 1.0), (0.26, 1.15), (0.1, 1.25), (0, 1.25)],
                 14, BRS, M=frame(tc, (0, 0, 1)))
        mb.cyl(0.22, 0.03, 14, GLS, M=frame(tc + Vector((0, -0.27, 1.08)), (0, -1, 0.3)), x0=0.0)
        mb.box((tc.x, tc.y - 0.05, tc.z + 1.35), (0.04, 0.04, 0.3), DMT)
    mb.lathe([(0, 0), (0.22, 0), (0.15, 0.6), (0.2, 0.95), (0.18, 1.1), (0, 1.15)], 12, BRS,
             M=frame((0.0, -27.8, z), (0, 0, 1)))
    chair(mb, (2.6, -27.0, z + 0.25), math.pi)
    mb.box((2.6, -27.0, z + 0.12), (0.8, 0.8, 0.25), WOD)
    chair(mb, (-2.8, -28.0, z), math.pi * 0.8)
    for x in (-0.9, 0.0, 0.9):
        pipe(mb, (x, -29.6, CL1), (x, -29.6, z + 1.9), 0.035, BRS)
        mb.lathe([(0.035, 0), (0.08, 0.1), (0.08, 0.13), (0, 0.13)], 10, BRS, M=frame((x, -29.6, z + 1.9), (0, 0, -1)))
    lamp(S, mb, (0, -28.4, CL1 - 0.1), 0.25)
    lamp(S, mb, (-3.5, -27.4, CL1 - 0.1), 0.2)
    lamp(S, mb, (3.5, -27.4, CL1 - 0.1), 0.2)
    # --- chart room / officers
    table(mb, (0, -20.0, z), 2.6, 1.6, 0.92)
    mb.box((0, -20.0, z + 0.925), (2.3, 1.3, 0.01), FAB)
    for s in (1, -1):
        for dy in (-0.9, 0.9):
            chair(mb, (s * 1.65, -20.0 + dy, z), -s * math.pi / 2)
    for s, y0 in ((-1, -25.2), (-1, -18.6)):
        mb.box((s * 5.2, y0 + 1.0, z + 1.0), (0.9, 2.2, 2.0), WOD)
        for k in range(4):
            for b in range(12):
                hgt = 0.26 + 0.06 * ((b * 7) % 3)
                mb.box((s * 4.95, y0 + 0.1 + b * 0.17, z + 0.25 + k * 0.46 + hgt / 2), (0.25, 0.12, hgt),
                       (RED, FAB, BRS)[(b + k) % 3])
    table(mb, (-4.9, -15.4, z), 1.2, 0.8)
    chair(mb, (-4.1, -15.4, z), -math.pi / 2)
    for k in range(2):
        mb.box((4.8, -16.0 + 0.0 * k, z + 0.4 + k * 1.2), (1.0, 2.0, 0.12), DMT)
        mb.box((4.8, -16.0, z + 0.52 + k * 1.2), (0.9, 1.9, 0.14), FAB)
    lamp(S, mb, (0, -20.0, CL1 - 0.1), 0.35)
    lamp(S, mb, (-3.6, -16.0, CL1 - 0.1), 0.2)
    # --- crew quarters: 2 x 8 triple bunks + central lockers
    for s in (1, -1):
        for k in range(8):
            y = -12.8 + 2.4 * k
            x = s * 5.15
            for zz in (0.35, 1.15, 1.95):
                mb.box((x, y, z + zz), (0.9, 2.0, 0.08), DMT)
                mb.box((x, y, z + zz + 0.1), (0.82, 1.92, 0.12), FAB)
                mb.box((x, y + 0.75, z + zz + 0.21), (0.6, 0.3, 0.1), FAB)
            for dy in (-1.0, 1.0):
                for dx in (-0.43, 0.43):
                    mb.box((x + dx, y + dy, z + 1.3), (0.05, 0.05, 2.6), DMT)
            beam(mb, (x - s * 0.43, y - 1.0, z + 2.5), (x - s * 0.43, y + 1.0, z + 2.5), 0.03, 0.03, DMT)
    for k in range(6):
        y = -12.0 + 2.8 * k
        mb.box((0, y, z + 0.95), (0.9, 1.6, 1.9), DMT)
        for s in (1, -1):
            for dy in (-0.4, 0.4):
                mb.box((s * 0.455, y + dy, z + 1.0), (0.01, 0.7, 1.7), HUL)
                mb.box((s * 0.465, y + dy + 0.25, z + 1.1), (0.01, 0.04, 0.12), BRS)
    for y in (-11.0, -5.0, 1.0):
        for x in (2.6, -2.6):
            lamp(S, mb, (x, y, CL1 - 0.1), 0.2)
    # --- mess hall + galley
    for x in (2.2, -2.2):
        table(mb, (x, 10.6, z), 1.0, 7.0)
        for s in (1, -1):
            mb.box((x + s * 0.8, 10.6, z + 0.44), (0.35, 6.8, 0.06), WOD)
            for yy in (7.6, 10.6, 13.6):
                mb.box((x + s * 0.8, yy, z + 0.21), (0.3, 0.06, 0.42), DMT)
        for k in range(8):
            yy = 7.6 + k * 0.85
            mb.cyl(0.04, 0.1, 8, BRS, M=frame((x + 0.25, yy, z + 0.77), (0, 0, 1)), x0=0.0)
            mb.cyl(0.11, 0.015, 10, WAL, M=frame((x - 0.2, yy, z + 0.77), (0, 0, 1)), x0=0.0)
    mb.box((-5.25, 14.8, z + 0.45), (0.9, 5.6, 0.9), DMT)
    mb.box((-5.25, 14.8, z + 0.92), (0.95, 5.65, 0.05), BRS)
    mb.box((-5.2, 12.8, z + 0.6), (0.9, 1.2, 1.2), DMT)
    pipe(mb, (-5.3, 12.8, z + 1.2), (-5.3, 12.8, CL1), 0.1)
    for k in range(4):
        mb.cyl(0.14 - k * 0.02, 0.2, 10, BRS, M=frame((-5.2, 14.2 + k * 0.7, z + 0.95), (0, 0, 1)), x0=0.0)
    for zz in (1.6, 2.1):
        mb.box((-5.55, 15.2, z + zz), (0.35, 4.6, 0.04), WOD)
        for k in range(10):
            mb.cyl(0.07, 0.18, 8, (RED, WAL)[k % 2], M=frame((-5.55, 13.2 + k * 0.45, z + zz + 0.02), (0, 0, 1)), x0=0.0)
    for y in (8.0, 12.0, 16.0):
        for x in (2.2, -2.2):
            lamp(S, mb, (x, y, CL1 - 0.1), 0.3)
    # --- armory: rifle racks, ammunition, workbench
    for k in range(3):
        y0 = 19.0 + k * 3.6
        mb.box((5.3, y0 + 1.5, z + 0.1), (0.6, 3.2, 0.2), DMT)
        mb.box((5.5, y0 + 1.5, z + 1.25), (0.08, 3.2, 0.08), DMT)
        for r in range(12):
            rifle(mb, (5.25, y0 + 0.15 + r * 0.25, z + 0.18), math.pi / 2, 0.18)
    for k in range(5):
        crate(mb, (-1.2 + (k % 3) * 1.0, 28.6 + (k // 3) * 1.0, z), (0.8, 0.5, 0.35))
        crate(mb, (-1.2 + (k % 3) * 1.0, 28.6 + (k // 3) * 1.0, z + 0.35), (0.8, 0.5, 0.35))
    table(mb, (1.6, 23.0, z), 1.0, 2.4, 0.9, top=DMT)
    mb.box((1.6, 22.4, z + 1.0), (0.3, 0.4, 0.2), DMT)
    mb.box((1.6, 23.6, z + 0.98), (0.6, 0.15, 0.14), WOD)
    fire_ext(mb, (5.5, 18.4, z))
    fire_ext(mb, (-5.5, -13.6, z))
    for y in (21.0, 26.0, 30.0):
        lamp(S, mb, (1.6, y, CL1 - 0.1), 0.25)


def build_envelope(S):
    """gored envelope mesh with its own UVs (u per gore, v = 10 m between frames)."""
    ys = []
    y = ENV_KEYS[0][0]
    while y < ENV_KEYS[-1][0]:
        ys.append(y)
        step = 0.6 if (y < -66 or y > 70) else (1.5 if (y < -50 or y > 56) else 3.0)
        y += step
    ys.append(ENV_KEYS[-1][0])
    G = 24
    N = G * 2
    verts, faces, uvs = [], [], []
    s_acc, prev = [], None
    for y in ys:
        r = env_r(y)
        if prev is None:
            s_acc.append(0.0)
        else:
            s_acc.append(s_acc[-1] + math.hypot(y - prev[0], r - prev[1]))
        prev = (y, r)
        for k in range(N):
            a = TAU * k / N - math.pi / 2
            rr = r * (0.9935 if k % 2 else 1.0)
            verts.append((rr * math.cos(a), y, ZE + rr * math.sin(a)))
    for i in range(len(ys) - 1):
        for k in range(N):
            a0, a1 = i * N + k, i * N + (k + 1) % N
            b0, b1 = a0 + N, a1 + N
            faces.append((a0, a1, b1, b0))
            u0 = (k % 2) * 0.5
            v0, v1 = s_acc[i] / 10.0, s_acc[i + 1] / 10.0
            uvs += [(u0, v0), (u0 + 0.5, v0), (u0 + 0.5, v1), (u0, v1)]
    for cap, last in ((0, False), (len(ys) - 1, True)):
        idx = [cap * N + k for k in range(N)]
        faces.append(tuple(reversed(idx)) if not last else tuple(idx))
        uvs += [(0.5, 0.5)] * N
    me = bpy.data.meshes.new('Airship_Envelope')
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', [c for uv in uvs for c in uv])
    for m in S.mat_list:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', [ENV] * len(me.polygons))
    me.update()
    f0 = me.polygons[len(ys) * 2]
    if (f0.center - Vector((0, f0.center.y, ZE))).dot(f0.normal) < 0:
        me.flip_normals()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('Airship_Envelope', me)
    S.coll.objects.link(ob)
    S.extra.append(ob)
    # emblem decals (both sides) and nose/tail hardware on the exterior part list
    dverts, dfaces, duvs = [], [], []
    for side in (1, -1):
        yc, size, n = -46.0, 13.0, 12
        base = len(dverts)
        for i in range(n + 1):
            for j in range(n + 1):
                y = yc + (i / n - 0.5) * size
                r = env_r(y) + 0.08
                phi = (j / n - 0.5) * size / r
                ang = phi if side > 0 else math.pi - phi
                dverts.append((r * math.cos(ang), y, ZE + r * math.sin(ang)))
        for i in range(n):
            for j in range(n):
                a = base + i * (n + 1) + j
                f = (a, a + n + 1, a + n + 2, a + 1) if side > 0 else (a, a + 1, a + n + 2, a + n + 1)
                dfaces.append(f)
                for (ii, jj) in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)) if side > 0 else \
                        ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)):
                    u = ii / n if side > 0 else 1 - ii / n
                    duvs.append((u, jj / n))
    dm = bpy.data.meshes.new('Airship_Decals')
    dm.from_pydata(dverts, [], dfaces)
    ul = dm.uv_layers.new(name='UVMap')
    ul.data.foreach_set('uv', [c for uv in duvs for c in uv])
    dm.materials.append(S.mat_list[DEC])
    for p in dm.polygons:
        p.use_smooth = True
    dob = bpy.data.objects.new('Airship_Decals', dm)
    S.coll.objects.link(dob)
    S.extra.append(dob)
    ext = S.mb('exterior', 'body', 'static')
    ext.lathe([(2.35, 0.0), (1.8, 0.5), (0.9, 1.0), (0.25, 1.25), (0, 1.3)], 24, DMT,
              M=frame((0, ENV_KEYS[0][0] + 0.2, ZE), (0, -1, 0)))
    ext.lathe([(1.1, 0.0), (0.7, 0.8), (0, 1.4)], 16, DMT, M=frame((0, ENV_KEYS[-1][0] - 0.1, ZE), (0, 1, 0)))
    for k in range(6):
        a = k * TAU / 6
        p = Vector((0, ENV_KEYS[0][0] + 1.6, ZE)) + Vector((math.cos(a), 0, math.sin(a))) * 2.6
        ext.box(tuple(p), (0.3, 0.5, 0.3), BRS)
    for yb in (-64.0, -61.5):
        r = env_r(yb) + 0.03
        rings_ = [[((r + dr) * math.cos(TAU * k / 48), y, ZE + (r + dr) * math.sin(TAU * k / 48)) for k in range(48)]
                  for y, dr in ((yb - 0.5, 0.0), (yb - 0.45, 0.05), (yb + 0.45, 0.05), (yb + 0.5, 0.0))]
        ext.loft(rings_, RED, cap0=False, cap1=False)
    # dorsal catwalk + gas valve hoods
    for yy in np.arange(-60.0, 50.0, 2.0):
        if any(abs(yy + 1.0 - yt) < 2.6 for yt in (-46.0, 38.0)):
            continue
        z0 = ZE + env_r(yy) + 0.06
        z1 = ZE + env_r(yy + 2.0) + 0.06
        a = math.atan2(z1 - z0, 2.0)
        ext.box((0, 0, 0), (0.9, 2.02, 0.05), WOD, M=Mt(0, yy + 1.0, (z0 + z1) / 2) @ Mrx(a))
        for s in (1, -1):
            ext.box((s * 0.55, yy + 1.0, (z0 + z1) / 2 + 0.45), (0.04, 0.04, 0.9), DMT)
            ext.box((0, 0, 0), (0.04, 2.0, 0.04), BRS, M=Mt(s * 0.55, yy + 1.0, (z0 + z1) / 2 + 0.9) @ Mrx(a))
    for yy in range(-50, 50, 12):
        for s in (1, -1):
            r = env_r(yy)
            a = math.radians(70)
            c = Vector((s * r * math.cos(a), yy, ZE + r * math.sin(a)))
            ext.box((0, 0, 0), (1.2, 1.6, 0.5), HUL, M=Mt(*c) @ Matrix.Rotation(-s * math.radians(20), 4, 'Y'),
                    top=(0.7, 0.8))


def fin_surface(S, horizontal, side, key_main, ctrl_bone):
    """tail fins: Planform from ak_core; root inside the envelope; rear 28% is the control surface."""
    pf = Planform([(3.0, 50.0, 0.0, 28.0, 0.05, 0), (20.5, 61.0, 0.0, 15.0, 0.05, 0),
                   (22.0, 64.0, 0.0, 11.0, 0.04, 0)])
    ext = S.mb(key_main, 'body', 'static')
    cm = S.mb(ctrl_bone, ctrl_bone, 'move')
    hinge = 0.72
    if horizontal:
        M = Mt(0, 0, ZE)
        mir = side < 0
        vert = False
    else:
        vert = True
        mir = False
        M = Mt(0, 0, ZE) if side > 0 else Mt(0, 0, ZE) @ Matrix.Diagonal((1, 1, -1, 1))
    kw = dict(npts=9, vertical=vert, mirror=mir, M=M, mat=HUL)
    a, b = 8.0, 20.0
    surface(ext, pf.secs(pf.span0, a), cap0=True, cap1=True, **kw)
    surface(ext, pf.secs(a, b), s1=hinge, cap0=True, cap1=True, **kw)
    surface(ext, pf.secs(b, pf.span1), cap0=True, cap1=True, **kw)
    surface(cm, pf.secs(a + 0.05, b - 0.05), s0=hinge + 0.004, s1=1.0, cap0=True, cap1=True, **kw)

    def hp(sp):
        _, yle, h, c, t, tw = pf.at(sp)
        p = Vector((h, yle + hinge * c, sp)) if vert else Vector((-sp if mir else sp, yle + hinge * c, h))
        return M @ p
    pa, pb = hp(a + 0.05), hp(b - 0.05)
    if horizontal and (pb - pa).x < 0:
        pa, pb = pb, pa
    if not horizontal and (pb - pa).z < 0:
        pa, pb = pb, pa
    S.bone(ctrl_bone, pa, pb, parent='body', z=(0, -1, 0) if vert else (0, 0, 1), shape='box',
           sxyz=(0.1, (pb - pa).length / 2, 0.1), color='THEME03',
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    S.controls[ctrl_bone] = 'pitch' if horizontal else 'yaw'


def build_engines(S):
    ext = S.mb('exterior', 'body', 'static')
    k = 0
    for yy in (-30.0, 0.0, 30.0):
        for s in (1, -1):
            k += 1
            r = env_r(yy)
            c = Vector((s * (r * 0.8 + 4.5), yy, ZE - r * 0.55 - 1.0))
            M = frame(c + Vector((0, 4.6, 0)), (0, -1, 0))
            ext.lathe([(0, 0), (0.5, 0.4), (1.2, 1.6), (1.5, 3.4), (1.55, 6.0), (1.45, 8.0), (1.3, 8.6),
                       (1.25, 8.6), (1.25, 8.4), (0, 8.4)], 20, HUL, mats=[HUL] * 6 + [DMT, DMT, DMT], M=M)
            ext.box(tuple(c + Vector((0, -2.2, -1.45))), (1.4, 1.6, 0.5), DMT, top=(0.9, 0.8))
            for j in range(9):
                ext.box(tuple(c + Vector((-0.6 + j * 0.15, -2.2, -1.71))), (0.04, 1.5, 0.03), HUL)
            for j in range(4):
                for side2 in (1, -1):
                    p = c + Vector((side2 * 1.45, -1.2 + j * 0.55, -0.3))
                    ext.cyl(0.08, 0.35, 8, DMT, M=frame(p, (side2, 0.3, -0.2)), x0=0.0)
            for wy in (0.6, 1.6):
                ext.box(tuple(c + Vector((s * 1.48, wy, 0.35))), (0.06, 0.6, 0.35), GLS)
            topz = ZE - math.sqrt(max(r ** 2 - (c.x * 0.75) ** 2, 1.0)) + 0.5
            for dy, w in ((-2.0, 0.3), (2.0, 0.3)):
                beam(ext, c + Vector((0, dy, 1.3)), Vector((c.x * 0.72, yy + dy * 0.5, topz)), w, 0.5, DMT)
            beam(ext, c + Vector((-s * 1.2, 0, 0.6)), Vector((c.x * 0.55, yy, ZE - r * 0.76)), 0.22, 0.22, DMT)
            hub = c + Vector((0, -4.0, 0))
            pmb = S.mb(f'prop_{k}', f'prop_{k}', 'move')
            pmb.lathe([(0, -0.05), (0.42, -0.05), (0.42, 0.2), (0.32, 0.7), (0, 1.05)], 16, DMT,
                      M=frame(hub + Vector((0, 0.05, 0)), (0, -1, 0)))
            ea = Vector((0, -1, 0))
            for bl in range(4):
                ang = bl * TAU / 4 + math.pi / 4
                er = Vector((math.cos(ang), 0, math.sin(ang)))
                et = Vector((-math.sin(ang), 0, math.cos(ang))) * (1 if s > 0 else -1)
                rings_ = []
                for f in (0.12, 0.3, 0.55, 0.8, 1.0):
                    rr = f * 2.9
                    ch = 0.42 * (1.25 - 0.6 * f)
                    beta = math.atan2(3.2, TAU * max(rr, 0.2))
                    cd = et * math.cos(beta) + ea * math.sin(beta)
                    nd = ea * math.cos(beta) - et * math.sin(beta)
                    rings_.append([hub + er * rr + cd * ((sx - 0.3) * ch) + nd * (th * ch)
                                   for sx, th in airfoil_poly(0, 1, 0.1, 6, 0.02)])
                pmb.loft(rings_, WOD)
                tip = hub + er * 2.82
                pmb.box(tuple(tip), (0.08, 0.08, 0.08), BRS)
            S.bone(f'prop_{k}', hub, hub + Vector((0, -0.8, 0)), parent='body', shape='circle',
                   sxyz=(3.0, 3.0, 3.0), color='THEME02',
                   locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
            S.props.append(f'prop_{k}')


def turret(S, idx, base, dorsal, gmin, gmax):
    base = Vector(base)
    up = Vector((0, 0, 1 if dorsal else -1))
    ext = S.mb('exterior', 'body', 'static')
    ext.lathe([(0, -0.6), (1.35, -0.6), (1.45, 0.0), (1.2, 0.08), (0, 0.08)], 24, HUL, M=frame(base, up))
    tb, gb = f'turret_{idx}', f'gun_{idx}'
    t = S.mb(tb, tb, 'move')
    t.lathe([(0, 0.08), (1.15, 0.08), (1.18, 0.5), (1.0, 1.0), (0.55, 1.3), (0, 1.38)], 20, HUL, M=frame(base, up))
    fwd = Vector((0, -1, 0))
    slit = base + up * 0.85 + fwd * 1.05
    t.box(tuple(slit), (0.9, 0.12, 0.22), GLS)
    for s in (1, -1):
        t.box(tuple(base + up * 0.55 + Vector((s * 1.12, 0, 0))), (0.12, 0.5, 0.35), DMT)
    trunnion = base + up * 0.72 + fwd * 0.6
    g = S.mb(gb, gb, 'move')
    g.box(tuple(trunnion), (0.9, 0.7, 0.45), DMT, top=(0.9, 0.9))
    S.bone(tb, base, base + up * 0.8, parent='body', z=(0, -1, 0), shape='circle', sxyz=(1.6,) * 3,
           color='THEME01', locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    S.bone(gb, trunnion, trunnion + fwd * 1.0, parent=tb, z=tuple(up), shape='arrow', sxyz=(1.0, 3.2, 1.0),
           color='THEME03', locks=dict(loc=(True,) * 3, rot=(False, True, True), scale=(True,) * 3))
    flashes = []
    for s in (1, -1):
        bpos = trunnion + Vector((s * 0.28, 0, 0))
        g.lathe([(0, 0.2), (0.07, 0.2), (0.07, 0.7), (0.045, 0.75), (0.042, 2.6), (0.07, 2.65), (0.07, 2.95),
                 (0.03, 2.95), (0, 2.85)], 10, DMT, M=frame(bpos, fwd))
        mz = bpos + fwd * 2.95
        sfx = f'{idx}{"L" if s > 0 else "R"}'
        S.bone(f'muzzle_{sfx}', mz, mz + fwd * 0.3, parent=gb, deform=False, coll='Sockets', shape='diamond',
               sxyz=(0.15,) * 3, color='THEME06', locks=dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3))
        S.bone(f'flash_{sfx}', mz, mz + fwd * 0.4, parent=f'muzzle_{sfx}', coll='Sockets', shape='diamond',
               sxyz=(0.1,) * 3, color='THEME06', locks=dict(loc=(True,) * 3, rot=(True, False, True)))
        S.flashes.append((f'flash_{sfx}', tuple(mz), tuple(fwd), 1.4, 0.6))
        flashes.append(f'flash_{sfx}')
    S.turrets.append(dict(turret=tb, gun=gb, min=gmin, max=gmax, flashes=flashes,
                          muzzles=[f.replace('flash', 'muzzle') for f in flashes], dorsal=dorsal))


def build_moving(S):
    # rear ramp (hinge at the floor line, swings down/out)
    r = S.mb('ramp', 'ramp', 'move')
    r.box((0, 32.04, 1.4), (4.0, 0.14, 2.8), HUL)
    for k in range(9):
        r.box((0, 31.95, 0.25 + k * 0.3), (3.8, 0.05, 0.04), DMT)
    for s in (1, -1):
        r.box((s * 1.95, 31.98, 1.4), (0.1, 0.1, 2.8), DMT)
    S.bone('ramp', (0, 32.0, 0.0), (0, 31.5, 0.0), parent='body', shape='box', sxyz=(2.0, 0.3, 0.1),
           color='THEME05', locks=dict(loc=(True,) * 3, rot=(False, True, True), scale=(True,) * 3))
    S.doors['ramp'] = dict(axis='x', angle=105.0)
    for side, s in (('L', 1), ('R', -1)):
        bn = f'door_{side}'
        d = S.mb(bn, bn, 'move')
        d.box((s * 6.1, -6.0, 1.22), (0.08, 2.3, 2.44), HUL)
        d.box((s * 6.15, -5.3, 1.1), (0.04, 0.1, 0.3), BRS)
        d.box((s * 6.15, -6.0, 1.7), (0.03, 0.5, 0.4), GLS)
        S.bone(bn, (s * 6.1, -6.0, 2.5), (s * 6.1, -6.5, 2.5), parent='body', shape='box', sxyz=(0.1, 1.2, 1.2),
               color='THEME05', locks=dict(loc=(True, False, True), rot=(True,) * 3, scale=(True,) * 3))
        S.doors[bn] = dict(axis='slide', travel=2.35)
    turret(S, 1, (0, -20.0, -1.25), False, -5.0, 80.0)
    turret(S, 2, (0, 18.0, -1.25), False, -5.0, 80.0)
    turret(S, 3, (0, -46.0, ZE + env_r(-46.0) - 0.05), True, -5.0, 85.0)
    turret(S, 4, (0, 38.0, ZE + env_r(38.0) - 0.05), True, -5.0, 85.0)


def build_ship():
    S = Ship('Leviathan')
    build_gondola(S)
    build_lower(S)
    build_upper(S)
    build_envelope(S)
    fin_surface(S, True, 1, 'exterior', 'elevator_L')
    fin_surface(S, True, -1, 'exterior', 'elevator_R')
    fin_surface(S, False, 1, 'exterior', 'rudder_U')
    fin_surface(S, False, -1, 'exterior', 'rudder_D')
    build_engines(S)
    build_moving(S)
    S.bone('root', (0, 0, 0), (0, -2.0, 0), shape='square', sxyz=(8.0, 82.0, 1.0), color='THEME09')
    S.bone('body', (0, 0, ZE), (0, -2.0, ZE), parent='root', shape='box', sxyz=(16.0, 80.0, 16.0), color='THEME09')
    S.finish_parts()
    return S


# ------------------------------------------------------------------------------ UVs, assembly, clips
def box_uv(me, skip=(DEC,)):
    uvl = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    co = [v.co.copy() for v in me.vertices]
    data = uvl.data
    for p in me.polygons:
        mi = p.material_index
        if mi in skip:
            continue
        su, sv = TILE.get(mi, (1.0, 1.0))
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        zo = (FL1 if p.center.z > CL0 + 0.05 else 0.0) if mi == WAL else 0.0
        for li in p.loop_indices:
            c = co[me.loops[li].vertex_index]
            if ax == 2 and mi == WAL:
                data[li].uv = (c.x / su, 0.62 + c.y * 0.0005)
            elif ax == 2:
                data[li].uv = (c.x / su, c.y / sv)
            elif ax == 0:
                data[li].uv = (c.y / su, (c.z - zo) / sv)
            else:
                data[li].uv = (c.x / su, (c.z - zo) / sv)


def prune_materials(me):
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get('material_index', idx)
    used = sorted(set(idx))
    mats = [me.materials[i] for i in used]
    remap = {o: n for n, o in enumerate(used)}
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', [remap[i] for i in idx])


def tri_big_ngons(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ng, quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me)
    bm.free()


def assemble_ship(S):
    rig = S.rig
    vl = bpy.context.view_layer
    names = {'exterior': 'Airship_Exterior', 'int_lower': 'Airship_Interior_Lower',
             'int_upper': 'Airship_Interior_Upper'}
    moving = []
    for ob, bone, group in S.objs:
        box_uv(ob.data)
        key = ob.name.split('_', 1)[1]
        if group == 'static':
            ob.name = ob.data.name = names.get(key, f'Airship_{key}')
            ob.parent = rig
        else:
            ob.vertex_groups.clear()
            vg = ob.vertex_groups.new(name=bone)
            vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
            moving.append(ob)
    for o in vl.objects:
        o.select_set(False)
    for o in moving:
        o.select_set(True)
    vl.objects.active = moving[0]
    bpy.ops.object.join()
    mv = vl.objects.active
    mv.name = mv.data.name = 'Airship_Moving'
    mv.parent = rig
    mo = mv.modifiers.new('Armature', 'ARMATURE')
    mo.object = rig
    S.static = [o for o in S.coll.objects if o.type == 'MESH' and o.parent == rig and o is not mv]
    for ob in S.extra:
        ob.parent = rig
    S.build_flash(flash_material())
    fo = S.flash_obj
    fo.name = fo.data.name = 'Airship_MuzzleFlash'
    fo.parent = rig
    fo.modifiers.new('Armature', 'ARMATURE').object = rig
    for ob in [o for o in rig.children if o.type == 'MESH']:
        if ob.name not in ('Airship_Decals', 'Airship_MuzzleFlash'):
            prune_materials(ob.data)
            tri_big_ngons(ob.data)
    for i, (x, y, z) in enumerate(S.lights):
        e = bpy.data.objects.new(f'LightSocket_{i:02d}', None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = 0.15
        S.coll.objects.link(e)
        e.location = (x, y, z)
        e.parent = rig
    S.moving = mv


def ship_clip(S, name, f0, f1, fn, interp='LINEAR'):
    rig = S.rig
    ad = rig.animation_data_create()
    pbs = rig.pose.bones

    def reset():
        for pb in pbs:
            pb.location, pb.rotation_euler, pb.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    reset()
    act = bpy.data.actions.new(f'Leviathan_{name}')
    act.use_fake_user = True
    ad.action = act

    def key(bn, path, idx, f, v):
        pb = pbs[bn]
        if idx is None:
            setattr(pb, path, v)
            pb.keyframe_insert(path, frame=f)
        else:
            getattr(pb, path)[idx] = v
            pb.keyframe_insert(path, index=idx, frame=f)
    fn(key)
    for fc in action_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
    act.use_frame_range = True
    act.frame_start, act.frame_end = f0, f1
    slot = ad.action_slot
    ad.action = None
    tr = ad.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, f0, act)
    if slot is not None and getattr(st, 'action_slot', None) is None:
        st.action_slot = slot
    tr.mute = True
    reset()
    return name


def ship_clips(S):
    made = []
    made.append(ship_clip(S, 'Props_Spin', 1, 7, lambda key: [
        (key(p, 'rotation_euler', 1, 1, 0.0), key(p, 'rotation_euler', 1, 7, -TAU / 4)) for p in S.props]))

    def ctl(key):
        for bn, ax in S.controls.items():
            seq = (1, 13, 25) if ax == 'pitch' else (25, 37, 49)
            for f, v in ((1, 0), (seq[0], 0), (seq[1], 22), (seq[2], 0), (49, 0)):
                key(bn, 'rotation_euler', 1, f, math.radians(v))
    made.append(ship_clip(S, 'Controls_Demo', 1, 49, ctl, 'BEZIER'))
    made.append(ship_clip(S, 'Ramp_Open', 1, 73, lambda key: (key('ramp', 'rotation_euler', 0, 1, 0.0),
                                                              key('ramp', 'rotation_euler', 0, 73, math.radians(105))),
                          'BEZIER'))
    made.append(ship_clip(S, 'Doors_Open', 1, 37, lambda key: [
        (key(d, 'location', 1, 1, 0.0), key(d, 'location', 1, 37, -2.35)) for d in ('door_L', 'door_R')], 'BEZIER'))
    made.append(ship_clip(S, 'Turrets_Traverse', 1, 193, lambda key: [
        (key(t['turret'], 'rotation_euler', 1, 1, 0.0), key(t['turret'], 'rotation_euler', 1, 193, TAU))
        for t in S.turrets]))

    def fire(key):
        Sx = 1.0 / FLASH_REST
        for ti, t in enumerate(S.turrets):
            for fi, fb in enumerate(t['flashes']):
                key(fb, 'scale', None, 1, (1, 1, 1))
                for s in range(1 + fi * 2, 22, 4):
                    key(fb, 'scale', None, s, (Sx, Sx, Sx))
                    key(fb, 'scale', None, s + 1, (0.6 * Sx,) * 3)
                    key(fb, 'scale', None, s + 2, (1, 1, 1))
                key(fb, 'scale', None, 25, (1, 1, 1))
    made.append(ship_clip(S, 'Fire', 1, 25, fire))
    S.rig.animation_data.action = None
    return made


def as_hatch(mb, c, r):
    M = frame(c, (0, 0, 1))
    mb.lathe([(0, 0), (r, 0), (r, 0.04), (r * 0.9, 0.08), (0, 0.08)], 14, HUL, M=M)
    mb.lathe([(r, -0.05), (r + 0.06, -0.05), (r + 0.06, 0.03), (r, 0.03)], 14, DMT, M=M)
    mb.cyl(0.03, r * 1.2, 8, DMT, M=frame(Vector(c) + Vector((0, r * 0.95, 0.06)), (1, 0, 0)))
    mb.box((c[0], c[1] - r * 0.6, c[2] + 0.1), (0.2, 0.04, 0.04), BRS)


def as_antenna(mb, c, h):
    x, y, z = c
    mb.cyl(0.08, 0.2, 8, DMT, M=frame((x, y, z), (0, 0, 1)), x0=0.0)
    mb.cyl(0.03, h, 6, DMT, M=frame((x, y, z + 0.2), (0, 0, 1)), x0=0.0, r2=0.012)
    for k in range(3):
        mb.box((x, y, z + 1.2 + k * 0.9), (0.6 - k * 0.15, 0.03, 0.03), BRS)


def build_collision(S):
    """simplified walkable shell for Godot ('-colonly' suffix -> StaticBody3D + trimesh shape)."""
    mb = MB()
    n = len(PLAN)
    for i in range(n):
        A, B = Vector(PLAN[i]), Vector(PLAN[(i + 1) % n])
        L = (B - A).length
        d = (B - A) / L
        ops = []
        if abs(d.x) < 1e-6 and L > 20:
            du = sorted(((-7.1 - A.y) / d.y, (-4.9 - A.y) / d.y))
            ops.append((du[0], du[1], 0.0, 2.4, 'door'))
        elif abs(d.y) < 1e-6:
            ops.append((L / 2 - 2.0, L / 2 + 2.0, 0.0, 2.8, 'door'))
        wall(mb, A, B, -0.2, ROOF, WT, ops)
    deck(mb, -0.2, FL0, ())
    deck(mb, CL0, FL1, [(3.4, 5.4, -25.4, -21.3), (-5.4, -3.4, 21.0, 25.4)])
    ins = offset_poly(PLAN, WT)
    mb.loft([ring(ins, CL1), ring(PLAN, ROOF), ring(PLAN, ROOF + 0.55, 0.86, 0.95)], 0)
    for y, z0, z1, door in ((-21.0, FL0, CL0, (-0.6, 0.6, 2.1)), (13.0, FL0, CL0, (-1.6, 1.6, 2.6)),
                            (-26.0, FL1, CL1, (-0.6, 0.6, 2.1)), (-14.0, FL1, CL1, (-0.6, 0.6, 2.1)),
                            (6.0, FL1, CL1, (-0.7, 0.7, 2.1)), (18.0, FL1, CL1, (-0.6, 0.6, 2.1))):
        bulkhead(mb, y, z0, z1, door)
    for x0, x1, ya, yb in ((3.4, 5.4, -21.3, -25.4), (-5.4, -3.4, 21.0, 25.4)):
        a, b = Vector(((x0 + x1) / 2, ya, FL0)), Vector(((x0 + x1) / 2, yb, FL1))
        dv = b - a
        mb.box((0, 0, 0), (x1 - x0, dv.length, 0.1), 0,
               M=Mt(*((a + b) / 2)) @ Mrx(math.atan2(dv.z, dv.y)) if dv.y > 0 else
               Mt(*((a + b) / 2)) @ Mrz(math.pi) @ Mrx(math.atan2(dv.z, -dv.y)))
    ys = list(np.arange(ENV_KEYS[0][0], ENV_KEYS[-1][0], 4.0)) + [ENV_KEYS[-1][0]]
    mb.loft([[(env_r(y) * math.cos(TAU * k / 16), y, ZE + env_r(y) * math.sin(TAU * k / 16)) for k in range(16)]
             for y in ys], 0)
    me = mb.to_mesh('Airship_Collision', [], sharp=30)
    ob = bpy.data.objects.new('Airship_Collision-colonly', me)
    S.coll.objects.link(ob)
    ob.parent = S.rig
    ob.display_type = 'WIRE'
    ob.hide_render = True
    return ob


def reset_airship():
    for c in ('Airship',):
        col = bpy.data.collections.get(c)
        if col:
            for o in list(col.all_objects):
                bpy.data.objects.remove(o)
    for a in [a for a in bpy.data.actions if a.name.startswith('Leviathan_')]:
        bpy.data.actions.remove(a)
    bpy.data.orphans_purge(do_recursive=True)
