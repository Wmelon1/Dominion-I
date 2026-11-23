# Skyship Kit - "Sentinel" sky-ship: 88 m envelope above a wooden boat hull with an open top deck,
# 4 anti-glider deck turrets, 100-seat troop deck, hold with engine room, bridge deckhouse, 3 swappable flags.
# Needs tk_core, tk_tank, tk_tanks, ak_core, as_tex, as_build exec'd first (this file overrides some globals).
# Coordinates: X = left(+)/right(-), Y = back(+)/front(-), Z = up. Origin = keel line, hull centre.

SS_DIR = globals().get('SS_DIR')
TEX_DIR = os.path.join(SS_DIR, 'textures')
GLB_DIR = os.path.join(SS_DIR, 'glb')

FLA, FLB, FLC, PLT = 11, 12, 13, 14
TILE.update({HUL: (2.0, 2.0), PLT: (3.0, 2.0), FLA: (1, 1), FLB: (1, 1), FLC: (1, 1)})
LEV_KEYS = [(-75.6, 2.2), (-74.5, 5.0), (-72.0, 8.4), (-68.0, 11.2), (-62.0, 13.2), (-54.0, 14.5), (-44.0, 15.0),
            (-20.0, 15.0), (10.0, 14.8), (30.0, 14.0), (48.0, 12.0), (62.0, 9.2), (74.0, 5.6), (81.0, 2.6),
            (83.5, 1.0)]
ENV_KEYS = [(y * 0.55 - 2.0, r * 0.6) for y, r in LEV_KEYS]
ZE = 23.0
HALF = [(0.0, -24.0), (1.6, -23.0), (3.0, -21.2), (4.1, -19.0), (4.8, -16.8), (5.0, -15.0), (5.0, 15.0),
        (4.7, 18.0), (4.0, 20.0), (2.8, 21.2)]
PLAN = HALF + [(-x, y) for x, y in reversed(HALF[1:])]
HOLD, TROOP, DECK, BUL = 0.6, 3.2, 6.0, 7.0
LEVELS = (HOLD, TROOP, DECK)
SHIP = 'Sentinel'


# ------------------------------------------------------------------------------ textures
def tex_hullwood():
    col, orm, nrm = tex_planks(1024, 11)
    col = np.transpose(col, (1, 0, 2)) * np.array((0.55, 0.47, 0.4), np.float32)
    orm = np.transpose(orm, (1, 0, 2))
    nrm = np.transpose(nrm, (1, 0, 2))[..., [1, 0, 2]]
    n = col.shape[0]
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    tar = sstep(0.55, 0.8, fbm(n, n, 3, 6, 4, 201)) * 0.35
    col = lerp(col, (0.1, 0.08, 0.06), tar)
    nail = np.zeros_like(u)
    for cx in (40.0, 552.0):
        d = np.sqrt((u - cx) ** 2 + ((v % 93.1) - 46.5) ** 2)
        nail = np.maximum(nail, 1 - sstep(2.0, 4.0, d))
    col = lerp(col, (0.55, 0.36, 0.18), nail)
    orm[..., 2] = np.maximum(orm[..., 2], nail * 0.9)
    return np.clip(col, 0, 1), orm, nrm


def tex_envelope2():
    col, orm, nrm = tex_envelope()
    col = np.clip(col * np.array((1.38, 1.18, 0.92), np.float32), 0, 1)
    return col, orm, nrm


def _flag_base(w, h, seed):
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    u /= w; v /= h
    weave = 0.96 + 0.04 * np.sin(u * np.pi * 2 * 300) * np.sin(v * np.pi * 2 * 190)
    shade = 0.9 + 0.14 * fbm(w, h, 3, 2, 4, seed)
    return u, v, (weave * shade)[..., None]


def tex_flag_a(w=1024, h=640):
    """Sky Legion: navy field, twin gold pinstripes, winged-star badge in the centre."""
    u, v, mod = _flag_base(w, h, 211)
    col = solid(h, w, (0.09, 0.12, 0.26))
    for c in (0.16, 0.84):
        col[np.abs(v - c) < 0.025] = (0.82, 0.66, 0.3)
        col[np.abs(v - c) < 0.008] = (0.09, 0.12, 0.26)
    ecol, ea = tex_emblem(512)
    cx, cy, rr = 0.5 * w, 0.5 * h, 0.23 * h
    yy, xx = np.mgrid[0:h, 0:w]
    sx = ((xx - cx) / rr * 256 + 256).astype(int)
    sy = ((yy - cy) / rr * 256 + 256).astype(int)
    inside = (sx >= 0) & (sx < 512) & (sy >= 0) & (sy < 512)
    sxc, syc = np.clip(sx, 0, 511), np.clip(sy, 0, 511)
    m = inside & (ea[syc, sxc] > 0.5)
    col[m] = ecol[syc, sxc][m]
    col[u < 0.02] = (0.75, 0.6, 0.3)
    return np.clip(col * mod, 0, 1), np.ones((h, w), np.float32)


def tex_flag_b(w=1024, h=640):
    """Iron Republic: olive field, gold diagonal band, black cog on a white disc."""
    u, v, mod = _flag_base(w, h, 212)
    col = solid(h, w, (0.24, 0.31, 0.17))
    d = np.abs((v - 0.5) - (u - 0.5) * (h / w) * 1.2 * 0 - (u - 0.5) * 0.62)
    col[d < 0.09] = (0.8, 0.63, 0.22)
    x = (u - 0.5) * w / h
    y = v - 0.5
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    col[r < 0.26] = (0.88, 0.86, 0.8)
    teeth = 0.17 + 0.035 * (np.cos(th * 10) > 0)
    cog = (r < teeth) & (r > 0.07)
    col[cog] = (0.08, 0.08, 0.08)
    col[(r < 0.035)] = (0.08, 0.08, 0.08)
    return np.clip(col * mod, 0, 1), np.ones((h, w), np.float32)


def tex_flag_c(w=1024, h=640):
    """Storm Corsairs: crimson swallowtail, black border, white lightning bolt."""
    u, v, mod = _flag_base(w, h, 213)
    col = solid(h, w, (0.55, 0.06, 0.08))
    border = (u < 0.03) | (v < 0.06) | (v > 0.94)
    col[border] = (0.06, 0.05, 0.05)
    pts = [(0.30, 0.86), (0.52, 0.86), (0.44, 0.58), (0.62, 0.58), (0.36, 0.12), (0.42, 0.44), (0.26, 0.44)]
    poly = np.array(pts, np.float32)
    inside = np.zeros_like(u, bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        cond = ((yi > v) != (yj > v)) & (u < (xj - xi) * (v - yi) / (yj - yi + 1e-9) + xi)
        inside ^= cond
        j = i
    col[inside] = (0.93, 0.92, 0.86)
    alpha = np.ones_like(u)
    notch = u > 0.78 + 0.22 * np.abs(v - 0.5) * 2
    alpha[notch] = 0.0
    return np.clip(col * mod, 0, 1), alpha


def flag_material(name, gen):
    col, alpha = gen()
    img = img_from(f'T_{name}', col, alpha)
    mat = bpy.data.materials.get(f'MAT_{name}') or bpy.data.materials.new(f'MAT_{name}')
    nt = NT(mat)
    ti = nt.n('ShaderNodeTexImage', image=img)
    b = nt.n('ShaderNodeBsdfPrincipled')
    gt = nt.n('ShaderNodeMath', operation='GREATER_THAN')
    gt.inputs[1].default_value = 0.5
    out = nt.n('ShaderNodeOutputMaterial')
    nt.L.new(ti.outputs['Color'], b.inputs['Base Color'])
    nt.L.new(ti.outputs['Alpha'], gt.inputs[0])
    nt.L.new(gt.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.85
    nt.L.new(b.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    return mat


def build_materials2():
    M = [None] * 15
    M[ENV] = tex_material('SkyEnvelope', tex_envelope2)
    M[HUL] = tex_material('HullWood', tex_hullwood)
    M[WOD] = tex_material('DeckPlanks', tex_planks)
    M[WAL] = tex_material('InteriorWall', tex_wall)
    M[DMT] = tex_material('DarkMetal', tex_darkmetal)
    M[BRS] = tex_material('Brass', tex_brass)
    M[FAB] = tex_material('Canvas', tex_canvas)
    M[PLT] = tex_material('MetalPlating', tex_plating)
    M[GLS] = flat_material('MAT_Glass', (0.10, 0.13, 0.14), 0.04, alpha=0.22)
    M[LMP] = flat_material('MAT_Lamp', (1.0, 0.78, 0.5), 0.3, emit=5.0)
    M[RED] = flat_material('MAT_RedPaint', (0.5, 0.07, 0.05), 0.45)
    M[DEC] = M[RED]
    M[FLA] = flag_material('Flag_SkyLegion', tex_flag_a)
    M[FLB] = flag_material('Flag_IronRepublic', tex_flag_b)
    M[FLC] = flag_material('Flag_StormCorsairs', tex_flag_c)
    return M


class Sky(Tank):
    def __init__(self, name):
        self.name, self.origin = name, Vector((0, 0, 0))
        self.coll = get_coll('Skyship')
        self.mbs, self.objs, self.bones, self.wheel_drv = {}, [], [], []
        self.guns, self.flashes, self.tracks, self.meta, self.temp_meshes = [], [], {}, {}, []
        self.mat_list = build_materials2()
        self.seats, self.lights, self.controls, self.turrets, self.props = [], [], {}, [], []
        self.doors, self.extra, self.flagpos = {}, [], []


# ------------------------------------------------------------------------------ helpers
def bulkhead2(mb, y, z0, z1, door=None, half=5.0, t=0.12):
    xw = half - WT
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


def rope_coil(mb, c, r=0.45):
    for k in range(4):
        mb.lathe([(r - 0.05 - k * 0.07, 0.0), (r - k * 0.07, 0.04), (r - 0.05 - k * 0.07, 0.08),
                  (r - 0.1 - k * 0.07, 0.04), (r - 0.05 - k * 0.07, 0.0)], 14, FAB,
                 M=frame((c[0], c[1], c[2] + k * 0.07), (0, 0, 1)))


def ladder(mb, x, y, z0, z1, w=0.5, face=(1, 0, 0)):
    for s in (-1, 1):
        mb.box((x, y + s * w / 2, (z0 + z1) / 2), (0.05, 0.05, z1 - z0), DMT)
    zz = z0 + 0.25
    while zz < z1:
        mb.box((x, y, zz), (0.04, w, 0.035), DMT)
        zz += 0.3


# ------------------------------------------------------------------------------ hull & decks
def build_hull(S):
    ext = S.mb('exterior', 'body', 'static')
    hold = S.mb('int_hold', 'body', 'static')
    troop = S.mb('int_troop', 'body', 'static')
    zbreaks = (HOLD, TROOP - 0.2, TROOP, DECK - 0.2, DECK)
    win_c = [-13.8 + 2.4 * k for k in range(13) if -13.8 + 2.4 * k < 14.4]
    n = len(PLAN)
    for i in range(n):
        A, B = Vector(PLAN[i]), Vector(PLAN[(i + 1) % n])
        L = (B - A).length
        d = (B - A) / L
        ops = []
        if abs(d.x) < 1e-6 and L > 20:
            for c in win_c:
                u = (c - A.y) / d.y
                if not (9.3 < c < 12.9):
                    ops.append((u - 0.42, u + 0.42, 4.15, 5.0, 'win'))
                ops.append((u - 0.28, u + 0.28, 1.65, 2.15, 'win'))
            du = sorted(((10.0 - A.y) / d.y, (12.2 - A.y) / d.y))
            ops.append((du[0], du[1], TROOP, TROOP + 2.4, 'door'))
        elif abs(d.y) < 1e-6:
            for c in (L / 2 - 1.4, L / 2 + 1.4):
                ops.append((c - 0.45, c + 0.45, 4.15, 5.0, 'win'))
            ops.append((L / 2 - 0.3, L / 2 + 0.3, 1.65, 2.15, 'win'))
        elif L > 1.6:
            ops.append((0.35, L - 0.35, 4.2, 4.9, 'win'))
        wall(ext, A, B, 0.4, BUL, WT, ops, zbreaks, mo=HUL, mi=WAL)
    ext.loft([ring(PLAN, 0.4), ring(PLAN, -0.6, 0.78, 0.97), ring(PLAN, -1.5, 0.28, 0.9)], HUL)
    ext.box((0, -1.4, -1.55), (0.3, 43.0, 0.12), DMT)
    deck(hold, 0.4, HOLD, ())
    deck(troop, TROOP - 0.2, TROOP, [(3.0, 4.0, -14.5, -13.5)])
    deck(ext, DECK - 0.2, DECK, [(-0.8, 0.8, -14.4, -10.6), (-0.8, 0.8, 8.6, 12.4)])
    # rail cap, rub strakes, metal bands, bow & stern hardware
    for i in range(n):
        A, B = Vector(PLAN[i]), Vector(PLAN[(i + 1) % n])
        mid = (A + B) / 2 + Vector((-(B - A).y, (B - A).x)).normalized() * 0.1
        ang = math.atan2(B.y - A.y, B.x - A.x)
        L = (B - A).length
        ext.box((0, 0, 0), (L + 0.05, 0.42, 0.08), WOD, M=Mt(mid.x, mid.y, BUL + 0.04) @ Mrz(ang))
        out = (A + B) / 2 - Vector((-(B - A).y, (B - A).x)).normalized() * 0.04
        for zz in (DECK - 0.1, TROOP - 0.1, 0.5):
            ext.box((0, 0, 0), (L + 0.05, 0.1, 0.16), DMT if zz < 1 else PLT, M=Mt(out.x, out.y, zz) @ Mrz(ang))
    for s in (1, -1):
        ext.box((s * 5.06, 11.1, TROOP + 2.5), (0.06, 2.6, 0.1), DMT)
        for yy in (9.9, 12.3):
            ext.box((s * 5.04, yy, TROOP + 1.2), (0.06, 0.1, 2.5), DMT)
        ext.lathe([(0, 0), (0.18, 0), (0.2, 0.25), (0.12, 0.35), (0, 0.35)], 10, LMP,
                  M=frame((s * 4.9, 17.0, BUL + 0.1), (0, 0, 1)))
    ext.box((0, -24.6, 5.6), (0.3, 1.6, 0.3), WOD, top=(0.6, 1.0))
    ext.lathe([(0, 0), (0.14, 0), (0.12, 2.0), (0.05, 2.4), (0, 2.45)], 10, WOD,
              M=frame((0, -24.0, 5.8), (0, -0.9, 0.35)))
    # sponsons for the 4 deck turrets
    for s in (1, -1):
        for yy in (-8.0, 5.0):
            c = Vector((s * 5.9, yy, DECK))
            ext.lathe([(0, -0.25), (1.45, -0.25), (1.5, 0.0), (0, 0.0)], 20, WOD, M=frame(c, (0, 0, 1)))
            ext.lathe([(0, -0.25), (1.45, -0.25), (0.4, -1.4), (0, -1.4)], 20, HUL, M=frame(c, (0, 0, 1)))
            pts = [(c.x + s * 1.4 * math.cos(a), c.y + 1.4 * math.sin(a)) for a in np.linspace(-1.25, 1.25, 7)]
            pts = [(c.x + 1.4 * math.cos(a) * s, c.y + 1.4 * math.sin(a)) for a in np.linspace(-1.3, 1.3, 7)]
            railing(ext, pts, DECK, 0.9)


def build_deck(S):
    ext = S.mb('exterior', 'body', 'static')
    z = DECK
    # deckhouse / bridge
    dh = [(3.0, 13.2), (3.0, 19.6), (-3.0, 19.6), (-3.0, 13.2)]
    for i in range(4):
        A, B = Vector(dh[i]), Vector(dh[(i + 1) % 4])
        L = (B - A).length
        ops = []
        if i == 3:
            ops.append((L - 2.0, L - 1.0, z, z + 2.1, 'door'))
            ops += [(0.4, 1.9, z + 1.2, z + 2.4, 'win'), (2.3, 3.8, z + 1.2, z + 2.4, 'win')]
        else:
            k = int(L // 1.6)
            for j in range(k):
                c = (j + 0.5) * L / k
                ops.append((c - 0.55, c + 0.55, z + 1.2, z + 2.3, 'win'))
        wall(ext, A, B, z, z + 3.0, 0.18, ops, (), mo=HUL, mi=WAL)
    ext.box((0, 16.4, z + 3.08), (6.5, 6.9, 0.16), PLT)
    railing(ext, [(3.1, 13.1), (3.1, 19.7), (-3.1, 19.7), (-3.1, 13.1), (3.1, 13.1)], z + 3.16, 0.8)
    for s in (1, -1):
        c = Vector((s * 2.2, 13.6, z + 3.2))
        ext.box(tuple(c + Vector((0, 0, 0.25))), (0.25, 0.25, 0.5), DMT)
        ext.lathe([(0, -0.3), (0.3, -0.3), (0.34, 0.15), (0.28, 0.2), (0, 0.2)], 12, DMT,
                  M=frame(c + Vector((0, 0, 0.75)), (0, -1, 0)))
        ext.cyl(0.27, 0.02, 12, LMP, M=frame(c + Vector((0, -0.2, 0.75)), (0, -1, 0)), x0=0.0)
    as_antenna(ext, (0, 19.2, z + 3.16), 4.0)
    # deckhouse interior (bridge)
    hc = Vector((0, 14.3, z))
    ext.lathe([(0, 0), (0.3, 0), (0.2, 0.1), (0.12, 0.2), (0.1, 0.95), (0.16, 1.0), (0, 1.05)], 12, DMT,
              M=frame(hc, (0, 0, 1)))
    wc = hc + Vector((0, -0.12, 1.2))
    ext.lathe([(0.45, -0.03), (0.5, 0.0), (0.45, 0.03), (0.4, 0.0), (0.45, -0.03)], 20, WOD, M=frame(wc, (0, 1, 0)))
    for k in range(8):
        a = k * TAU / 8
        dd = Vector((math.cos(a), 0, math.sin(a)))
        beam(ext, wc, wc + dd * 0.45, 0.025, 0.025, WOD)
        ext.cyl(0.02, 0.14, 6, WOD, M=frame(wc + dd * 0.5, dd), x0=0.0)
    for s in (1, -1):
        tc = Vector((s * 1.3, 14.0, z))
        ext.lathe([(0, 0), (0.22, 0), (0.13, 0.1), (0.09, 0.9), (0.22, 0.95), (0.23, 1.1), (0.09, 1.2), (0, 1.2)],
                  12, BRS, M=frame(tc, (0, 0, 1)))
        ext.box((s * 2.5, 13.8, z + 0.45), (0.8, 0.5, 0.9), DMT, top=(1, 0.7))
        for gx in (-0.2, 0.2):
            gauge(ext, (s * 2.5 + gx, 13.56, z + 0.85), (0, -0.6, 0.8), 0.06)
    ext.lathe([(0, 0), (0.2, 0), (0.13, 0.55), (0.18, 0.9), (0.16, 1.05), (0, 1.1)], 12, BRS,
              M=frame((0, 15.6, z), (0, 0, 1)))
    table(ext, (0, 18.2, z), 1.8, 1.0, 0.92)
    ext.box((0, 18.2, z + 0.925), (1.6, 0.85, 0.01), FAB)
    chair(ext, (-1.8, 17.0, z), -math.pi / 2)
    for x in (-0.6, 0.6):
        pipe(ext, (x, 14.4, z + 3.0), (x, 14.4, z + 1.9), 0.03, BRS)
    lamp(S, ext, (0, 15.2, z + 2.9), 0.2)
    lamp(S, ext, (0, 18.2, z + 2.9), 0.2)
    # openings: coamings + railings
    for (x0, x1, y0, y1, entry) in ((-0.8, 0.8, -14.4, -10.6, 'f'), (-0.8, 0.8, 8.6, 12.4, 'f')):
        for xx in (x0, x1):
            ext.box((xx, (y0 + y1) / 2, z + 0.08), (0.1, y1 - y0, 0.16), WOD)
        ext.box(((x0 + x1) / 2, y1, z + 0.08), (x1 - x0, 0.1, 0.16), WOD)
        railing(ext, [(x0, y0 + 0.4), (x0, y1), (x1, y1), (x1, y0 + 0.4)], z, 1.0)
    # bow fittings
    ext.lathe([(0, 0), (0.5, 0), (0.42, 0.15), (0.35, 0.2), (0.35, 0.8), (0.45, 0.9), (0.45, 1.0), (0, 1.0)],
              16, DMT, M=frame((0, -19.0, z), (0, 0, 1)))
    for k in range(6):
        a = k * TAU / 6
        p0 = Vector((0, -19.0, z + 0.85))
        beam(ext, p0, p0 + Vector((math.cos(a), math.sin(a), 0)) * 0.9, 0.05, 0.05, WOD)
    ext.box((0, -21.3, z + 0.3), (1.4, 1.4, 0.6), WOD)
    c = Vector((0, -21.3, z + 0.6))
    ext.lathe([(0, 0), (0.08, 0), (0.08, 0.6), (0, 0.6)], 8, DMT, M=frame(c, (0, 0, 1)))
    ext.lathe([(0, -0.35), (0.38, -0.35), (0.42, 0.2), (0.35, 0.25), (0, 0.25)], 14, DMT,
              M=frame(c + Vector((0, 0, 0.95)), (0, -1, 0)))
    ext.cyl(0.35, 0.02, 14, LMP, M=frame(c + Vector((0, -0.25, 0.95)), (0, -1, 0)), x0=0.0)
    for s in (1, -1):
        rope_coil(ext, (s * 2.2, -17.6, z))
        for yy in (-12.6, 0.8):
            pipe(ext, (s * 3.2, yy, z), (s * 3.2, yy, z + 1.4), 0.18, DMT, 10)
            ext.lathe([(0.18, 0), (0.3, 0.1), (0.34, 0.45), (0.0, 0.5)], 10, RED,
                      M=frame((s * 3.2, yy, z + 1.4), (0, -0.4, 0.9)))
        for yy in (-3.0, 1.8):
            ext.box((s * 4.45, yy, z + 0.3), (0.55, 1.6, 0.6), WOD)
            for dy in (-0.5, 0.5):
                ext.box((s * 4.16, yy + dy, z + 0.45), (0.03, 0.12, 0.08), BRS)
        for k in range(4):
            ext.lathe([(0, 0), (0.12, 0), (0.15, 0.3), (0, 0.3)], 8, RED, M=frame((s * 2.6, 10.6 + k * 0.4, z + 0.85), (0, 0, 1)))
        ext.box((s * 2.6, 11.2, z + 0.82), (0.25, 1.7, 0.04), DMT)
        for yy in (11.2,):
            ext.box((s * 2.6, yy, z + 0.41), (0.05, 0.05, 0.82), DMT)
        crate(ext, (s * 3.6, -5.6, z), (1.0, 0.8, 0.6), 0.05)
        crate(ext, (s * 3.6, -5.6, z + 0.6), (0.8, 0.7, 0.45), -0.08)
        fire_ext(ext, (s * 4.6, 12.0, z))
    # rigging: suspension cables, girder struts, keel catwalk, ladder
    for yy in range(-18, 19, 4):
        zt = ZE - env_r(yy) + 0.3
        for s in (1, -1):
            xt = math.sqrt(max(env_r(yy) ** 2 - (ZE - zt) ** 2, 0.5))
            pipe(ext, (s * 4.95, yy, BUL + 0.05), (s * xt * 0.95, yy, zt + 0.15), 0.025, DMT, 5)
            ext.box((s * 4.95, yy, BUL + 0.12), (0.12, 0.12, 0.14), BRS)
    for yy in (-6.0, 2.0):
        beam(ext, (0, yy, z), (0, yy, ZE - env_r(yy) + 0.3), 0.3, 0.3, DMT)
        for s in (1, -1):
            beam(ext, (s * 1.4, yy - 1.2, z), (0, yy, z + 3.0), 0.12, 0.12, DMT)
    beam(ext, (0, 16.4, z + 3.16), (0, 16.4, ZE - env_r(16.4) + 0.3), 0.3, 0.3, DMT)
    ladder(ext, 0.2, -4.2, z, ZE - env_r(-4.2) + 0.3)
    for yy in np.arange(-30.0, 30.0, 2.0):
        z0 = ZE - env_r(yy) - 0.1
        z1 = ZE - env_r(yy + 2.0) - 0.1
        a = math.atan2(z1 - z0, 2.0)
        M = Mt(0, yy + 1.0, (z0 + z1) / 2) @ Mrx(a)
        ext.box((0, 0, 0), (0.9, 2.02, 0.06), WOD, M=M)
        for s in (1, -1):
            ext.box((s * 0.55, 0, 0.4), (0.05, 2.0, 0.05), DMT, M=M)
            ext.box((s * 0.55, 0, 0.2), (0.04, 0.04, 0.4), DMT, M=M)


def build_interior(S):
    hold = S.mb('int_hold', 'body', 'static')
    tr = S.mb('int_troop', 'body', 'static')
    # ---------------- hold: cargo + engine room
    bulkhead2(hold, 3.0, HOLD, TROOP - 0.2, (-0.6, 0.6, 2.0))
    for k in range(14):
        y = -14.4 + 2.4 * k
        if y > 15.0:
            break
        for s in (1, -1):
            hold.box((s * 4.68, y, (HOLD + TROOP) / 2 - 0.1), (0.14, 0.12, TROOP - HOLD - 0.2), DMT)
            tr.box((s * 4.68, y, (TROOP + DECK) / 2 - 0.1), (0.14, 0.12, DECK - TROOP - 0.2), DMT)
        hold.box((0, y, TROOP - 0.28), (9.4, 0.12, 0.16), DMT)
        tr.box((0, y, DECK - 0.28), (9.4, 0.12, 0.16), DMT)
    for s in (1, -1):
        for k, yy in enumerate((-12.0, -10.6, -9.2, -7.8, -4.0, -2.6)):
            crate(hold, (s * 3.8, yy, HOLD), (1.1, 1.1, 0.9), 0.04 * k)
            if k % 2 == 0:
                crate(hold, (s * 3.8, yy, HOLD + 0.9), (0.9, 0.9, 0.6), -0.05)
        for k in range(3):
            barrel(hold, (s * 2.6, -0.8 + k * 0.7, HOLD), 0.28, 0.85, RED if k == 1 else DMT)
    for zz in (HOLD + 0.4, HOLD + 1.1, HOLD + 1.8):
        hold.box((0, -6.0, zz), (0.8, 5.0, 0.05), WOD)
        for k in range(10):
            hold.cyl(0.08, 0.6, 8, BRS, M=frame((0.0, -8.2 + k * 0.48, zz + 0.1), (1, 0, 0)))
    for x in (-0.4, 0.4):
        for yy in (-8.5, -3.5):
            hold.box((x, yy, (HOLD + TROOP) / 2), (0.05, 0.05, TROOP - HOLD - 0.2), DMT)
    ladder(hold, 3.5, -14.0, HOLD, TROOP + 1.0)
    for s in (1, -1):
        e = Vector((s * 2.2, 9.0, HOLD))
        hold.box(tuple(e + Vector((0, 0, 0.55))), (1.3, 4.2, 1.1), DMT, top=(0.9, 0.97))
        for k in range(6):
            p = e + Vector((s * 0.0, -1.6 + k * 0.64, 1.1))
            hold.lathe([(0, 0), (0.22, 0), (0.22, 0.05)] +
                       [q for j in range(3) for q in ((0.3, 0.1 + j * 0.12), (0.3, 0.15 + j * 0.12), (0.22, 0.17 + j * 0.12))] +
                       [(0.2, 0.55), (0.12, 0.62), (0, 0.62)], 10, DMT,
                       M=frame(p, (s * 0.5, 0, 0.87)))
        hold.lathe([(0, -0.08), (0.65, -0.08), (0.65, 0.08), (0, 0.08)], 18, PLT,
                   M=frame(e + Vector((0, -2.4, 0.75)), (0, -1, 0)))
        pipe(hold, e + Vector((0, 0, 0.6)), Vector((s * 4.7, 9.0, HOLD + 0.6)), 0.09, BRS, 8)
        hold.box((s * 4.4, 9.0, HOLD + 0.6), (0.5, 0.7, 0.7), PLT)
        pipe(hold, e + Vector((s * 0.5, -1.8, 1.4)), e + Vector((s * 0.5, 1.8, 1.4)), 0.1, DMT, 8)
        pipe(hold, e + Vector((s * 0.5, 1.8, 1.4)), Vector((s * 4.5, 12.5, TROOP - 0.4)), 0.1, DMT, 8)
        hold.cyl(0.55, 3.0, 14, PLT, M=frame((s * 2.8, 17.0, HOLD + 0.75), (0, 1, 0)))
        for dy in (-1.0, 1.0):
            hold.box((s * 2.8, 17.0 + dy, HOLD + 0.2), (0.9, 0.12, 0.4), DMT)
    hold.box((0, 14.0, HOLD + 0.9), (1.6, 0.4, 1.8), DMT)
    for gx in (-0.5, 0.0, 0.5):
        for gz in (1.2, 1.6):
            gauge(hold, (gx, 13.78, HOLD + gz), (0, -1, 0), 0.07)
    table(hold, (-3.4, 14.5, HOLD), 0.8, 2.0, 0.85, top=DMT)
    for y in (-12.0, -7.0, -2.0, 6.0, 10.0, 16.5):
        lamp(S, hold, (0.0 if y > 3 else 1.6, y, TROOP - 0.4), 0.12)
    # ---------------- troop deck
    bulkhead2(tr, -15.0, TROOP, DECK - 0.2, (-0.6, 0.6, 2.1))
    bulkhead2(tr, 8.0, TROOP, DECK - 0.2, (-0.7, 0.7, 2.1))
    bulkhead2(tr, 14.0, TROOP, DECK - 0.2, (-0.6, 0.6, 2.1))
    stairs(tr, -0.8, 0.8, -10.6, -14.4, TROOP, DECK)
    stairs(tr, -0.8, 0.8, 12.4, 8.6, TROOP, DECK)
    railing(tr, [(3.0, -13.5), (4.0, -13.5)], TROOP, 0.9)
    railing(tr, [(3.0, -14.5), (3.0, -13.5)], TROOP, 0.9)
    seat_ys = [-9.7 + 0.6 * k for k in range(25)]
    for xr, f in ((4.3, -1), (-4.3, 1), (0.75, 1), (-0.75, -1)):
        wallrow = abs(xr) > 3
        bx = xr + (-f) * 0.05
        tr.box((bx, -2.5, TROOP + 0.44), (0.5, 15.2, 0.05), DMT)
        for yy in range(-9, 6, 2):
            tr.box((bx, yy + 0.1, TROOP + 0.21), (0.06, 0.06, 0.42), DMT)
        for y in seat_ys:
            tr.box((xr, y, TROOP + 0.49), (0.46, 0.52, 0.07), FAB, top=(0.95, 0.95))
            bxk = xr - f * 0.27
            tr.box((bxk, y, TROOP + 0.85), (0.05, 0.5, 0.62), FAB)
            if wallrow:
                tr.box((bxk - f * 0.04, y, TROOP + 1.3), (0.06, 0.06, 0.18), DMT)
                tr.box((xr - f * 0.1, y + 0.2, TROOP + 1.1), (0.03, 0.04, 0.55), FAB)
            S.seats.append(((xr, y, TROOP + 0.53), (f, 0.0, 0.0)))
        if not wallrow:
            tr.box((xr - f * 0.3, -2.5, TROOP + 0.85), (0.04, 15.2, 0.7), DMT)
    for y in range(-9, 6, 3):
        for x in (2.5, -2.5):
            tr.box((x, y, DECK - 0.75), (0.03, 0.06, 0.55), FAB)
            tr.box((x, y, DECK - 1.05), (0.08, 0.14, 0.03), FAB)
    pipe(tr, (0, -9.8, DECK - 0.45), (0, 7.8, DECK - 0.45), 0.16, DMT, 12)
    for s in (1, -1):
        pipe(tr, (s * 4.55, -14.0, DECK - 0.35), (s * 4.55, 19.0, DECK - 0.35), 0.035, BRS)
        pipe(tr, (s * 2.5, -9.8, DECK - 0.6), (s * 2.5, 7.8, DECK - 0.6), 0.025, DMT, 6)
        fire_ext(tr, (s * 4.5, -10.4, TROOP))
    for y in (-8.0, -4.0, 0.0, 4.0):
        for x in (2.5, -2.5):
            lamp(S, tr, (x, y, DECK - 0.3), 0.05)
    lamp(S, tr, (2.0, -12.4, DECK - 0.3), 0.1)
    # armory in the bow
    for s in (1, -1):
        tr.box((s * 3.3, -18.0, TROOP + 0.1), (0.5, 3.0, 0.2), DMT)
        tr.box((s * 3.5, -18.0, TROOP + 1.25), (0.06, 3.0, 0.08), DMT)
        for r in range(11):
            rifle(tr, (s * 3.25, -19.3 + r * 0.25, TROOP + 0.18), math.pi / 2 * s, 0.18)
    for k in range(4):
        crate(tr, (-0.9 + (k % 2) * 1.8, -21.0 + (k // 2) * 1.0, TROOP), (0.8, 0.5, 0.4))
    lamp(S, tr, (0, -18.5, DECK - 0.3), 0.15)
    # mess + galley
    for x in (2.6, -2.6):
        table(tr, (x, 10.0, TROOP), 0.9, 3.2)
        for s in (1, -1):
            tr.box((x + s * 0.72, 10.0, TROOP + 0.44), (0.32, 3.0, 0.06), WOD)
            for yy in (8.8, 11.2):
                tr.box((x + s * 0.72, yy, TROOP + 0.21), (0.28, 0.06, 0.42), DMT)
        for k in range(4):
            yy = 8.8 + k * 0.8
            tr.cyl(0.04, 0.1, 8, BRS, M=frame((x + 0.22, yy, TROOP + 0.77), (0, 0, 1)), x0=0.0)
            tr.cyl(0.11, 0.015, 10, WAL, M=frame((x - 0.18, yy, TROOP + 0.77), (0, 0, 1)), x0=0.0)
    tr.box((-3.6, 13.3, TROOP + 0.45), (2.0, 0.9, 0.9), DMT)
    tr.box((-3.6, 13.3, TROOP + 0.92), (2.05, 0.95, 0.05), BRS)
    for k in range(3):
        tr.cyl(0.13, 0.2, 10, BRS, M=frame((-4.2 + k * 0.6, 13.3, TROOP + 0.95), (0, 0, 1)), x0=0.0)
    pipe(tr, (-4.3, 13.5, TROOP + 1.0), (-4.3, 13.5, DECK - 0.2), 0.08)
    tr.box((3.8, 13.4, TROOP + 1.5), (1.6, 0.4, 0.05), WOD)
    for k in range(6):
        tr.cyl(0.07, 0.18, 8, (RED, WAL)[k % 2], M=frame((3.2 + k * 0.25, 13.4, TROOP + 1.52), (0, 0, 1)), x0=0.0)
    lamp(S, tr, (2.6, 10.0, DECK - 0.3), 0.15)
    lamp(S, tr, (-2.6, 10.0, DECK - 0.3), 0.15)
    # crew quarters at the stern
    for s in (1, -1):
        for yy in (15.4, 17.6):
            x = s * 3.7
            for zz in (0.35, 1.2):
                tr.box((x, yy, TROOP + zz), (0.9, 2.0, 0.08), DMT)
                tr.box((x, yy, TROOP + zz + 0.1), (0.82, 1.92, 0.12), FAB)
                tr.box((x, yy + 0.75, TROOP + zz + 0.21), (0.6, 0.3, 0.1), FAB)
            for dy in (-1.0, 1.0):
                for dx in (-0.43, 0.43):
                    tr.box((x + dx, yy + dy, TROOP + 0.95), (0.05, 0.05, 1.9), DMT)
    table(tr, (0, 19.4, TROOP), 1.4, 0.8)
    chair(tr, (0, 18.6, TROOP), 0.0)
    tr.box((0.0, 15.3, TROOP + 0.9), (1.0, 0.5, 1.8), HUL)
    lamp(S, tr, (0, 16.5, DECK - 0.3), 0.15)
    lamp(S, tr, (0, 19.0, DECK - 0.3), 0.15)


# ------------------------------------------------------------------------------ envelope, fins, engines, turrets
def build_envelope2(S):
    ys = []
    y = ENV_KEYS[0][0]
    while y < ENV_KEYS[-1][0]:
        ys.append(y)
        y += 0.4 if (y < -36 or y > 38) else (1.0 if (y < -28 or y > 28) else 2.0)
    ys.append(ENV_KEYS[-1][0])
    N = 48
    verts, faces, uvs = [], [], []
    s_acc, prev = [], None
    for y in ys:
        r = env_r(y)
        s_acc.append(0.0 if prev is None else s_acc[-1] + math.hypot(y - prev[0], r - prev[1]))
        prev = (y, r)
        for k in range(N):
            a = TAU * k / N - math.pi / 2
            rr = r * (0.9935 if k % 2 else 1.0)
            verts.append((rr * math.cos(a), y, ZE + rr * math.sin(a)))
    for i in range(len(ys) - 1):
        for k in range(N):
            a0, a1 = i * N + k, i * N + (k + 1) % N
            faces.append((a0, a1, a1 + N, a0 + N))
            u0 = (k % 2) * 0.5
            uvs += [(u0, s_acc[i] / 6.0), (u0 + 0.5, s_acc[i] / 6.0), (u0 + 0.5, s_acc[i + 1] / 6.0),
                    (u0, s_acc[i + 1] / 6.0)]
    for cap in (0, len(ys) - 1):
        idx = [cap * N + k for k in range(N)]
        faces.append(tuple(reversed(idx)) if cap == 0 else tuple(idx))
        uvs += [(0.5, 0.5)] * N
    me = bpy.data.meshes.new('Skyship_Envelope')
    me.from_pydata(verts, [], faces)
    me.uv_layers.new(name='UVMap').data.foreach_set('uv', [c for uv in uvs for c in uv])
    for m in S.mat_list:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', [ENV] * len(me.polygons))
    me.update()
    f0 = me.polygons[len(ys) * 2]
    if (f0.center - Vector((0, f0.center.y, ZE))).dot(f0.normal) < 0:
        me.flip_normals()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('Skyship_Envelope', me)
    S.coll.objects.link(ob)
    S.extra.append(ob)
    ext = S.mb('exterior', 'body', 'static')
    ext.lathe([(1.45, 0.0), (1.1, 0.35), (0.55, 0.65), (0, 0.8)], 20, DMT, M=frame((0, ENV_KEYS[0][0] + 0.15, ZE), (0, -1, 0)))
    ext.lathe([(0.7, 0.0), (0.4, 0.5), (0, 0.9)], 14, DMT, M=frame((0, ENV_KEYS[-1][0] - 0.1, ZE), (0, 1, 0)))
    for yb in (-36.0, -34.6):
        r = env_r(yb) + 0.03
        ext.loft([[((r + dr) * math.cos(TAU * k / 48), y, ZE + (r + dr) * math.sin(TAU * k / 48)) for k in range(48)]
                  for y, dr in ((yb - 0.35, 0.0), (yb - 0.3, 0.04), (yb + 0.3, 0.04), (yb + 0.35, 0.0))], RED,
                 cap0=False, cap1=False)
    for yy in range(-26, 26, 9):
        r = env_r(yy)
        c = Vector((0, yy, ZE + r))
        ext.box(tuple(c), (1.0, 1.4, 0.35), PLT, top=(0.7, 0.8))


def fin2(S, horizontal, side, ctrl_bone):
    pf = Planform([(1.8, 25.5, 0.0, 15.4, 0.05, 0), (12.3, 31.55, 0.0, 8.25, 0.05, 0), (13.2, 33.2, 0.0, 6.05, 0.04, 0)])
    ext = S.mb('exterior', 'body', 'static')
    cm = S.mb(ctrl_bone, ctrl_bone, 'move')
    hinge = 0.72
    vert = not horizontal
    mir = horizontal and side < 0
    M = Mt(0, 0, ZE) if (horizontal or side > 0) else Mt(0, 0, ZE) @ Matrix.Diagonal((1, 1, -1, 1))
    kw = dict(npts=9, vertical=vert, mirror=mir, M=M, mat=PLT)
    a, b = 4.8, 12.0
    surface(ext, pf.secs(pf.span0, a), cap0=True, cap1=True, **kw)
    surface(ext, pf.secs(a, b), s1=hinge, cap0=True, cap1=True, **kw)
    surface(ext, pf.secs(b, pf.span1), cap0=True, cap1=True, **kw)
    surface(cm, pf.secs(a + 0.04, b - 0.04), s0=hinge + 0.004, s1=1.0, cap0=True, cap1=True, **kw)

    def hp(sp):
        _, yle, h, c, t, tw = pf.at(sp)
        p = Vector((h, yle + hinge * c, sp)) if vert else Vector((-sp if mir else sp, yle + hinge * c, h))
        return M @ p
    pa, pb = hp(a + 0.04), hp(b - 0.04)
    if horizontal and (pb - pa).x < 0:
        pa, pb = pb, pa
    if vert and (pb - pa).z < 0:
        pa, pb = pb, pa
    S.bone(ctrl_bone, pa, pb, parent='body', z=(0, -1, 0) if vert else (0, 0, 1), shape='box',
           sxyz=(0.08, (pb - pa).length / 2, 0.08), color='THEME03',
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    S.controls[ctrl_bone] = 'pitch' if horizontal else 'yaw'


def build_engines2(S):
    ext = S.mb('exterior', 'body', 'static')
    k = 0
    for yy in (-3.0, 11.0):
        for s in (1, -1):
            k += 1
            c = Vector((s * 8.8, yy, 4.4))
            ext.lathe([(0, 0), (0.4, 0.3), (0.9, 1.1), (1.05, 2.6), (1.0, 4.4), (0.75, 5.6), (0.45, 6.0), (0, 6.0)],
                      18, PLT, mats=[DMT, PLT, PLT, PLT, PLT, PLT, DMT], M=frame(c + Vector((0, -3.0, 0)), (0, 1, 0)))
            ext.box(tuple(c + Vector((0, -1.6, -0.95))), (0.9, 1.4, 0.4), DMT, top=(0.9, 0.8))
            for j in range(7):
                ext.box(tuple(c + Vector((-0.39 + j * 0.13, -1.6, -1.16))), (0.03, 1.3, 0.03), PLT)
            for j in range(3):
                for side2 in (1, -1):
                    p = c + Vector((side2 * 1.0, -0.8 + j * 0.6, 0.25))
                    ext.cyl(0.06, 0.3, 8, DMT, M=frame(p, (side2, 0.3, 0.2)), x0=0.0)
            for dy in (-1.3, 1.3):
                beam(ext, Vector((s * 4.98, yy + dy, 4.1)), c + Vector((-s * 0.8, dy * 0.6, 0.1)), 0.2, 0.3, DMT)
            beam(ext, Vector((s * 4.98, yy, 1.6)), c + Vector((-s * 0.7, 0, -0.6)), 0.16, 0.16, DMT)
            beam(ext, Vector((s * 4.98, yy + 1.3, BUL)), c + Vector((-s * 0.6, 0.8, 0.8)), 0.06, 0.06, DMT)
            hub = c + Vector((0, 3.2, 0))
            pmb = S.mb(f'prop_{k}', f'prop_{k}', 'move')
            pmb.lathe([(0, -0.05), (0.3, -0.05), (0.3, 0.15), (0.22, 0.5), (0, 0.75)], 14, DMT,
                      M=frame(hub + Vector((0, -0.05, 0)), (0, 1, 0)))
            ea = Vector((0, 1, 0))
            for bl in range(3):
                ang = bl * TAU / 3 + math.pi / 2
                er = Vector((math.cos(ang), 0, math.sin(ang)))
                et = Vector((-math.sin(ang), 0, math.cos(ang))) * s
                rings_ = []
                for f in (0.14, 0.35, 0.6, 0.85, 1.0):
                    rr = f * 2.0
                    ch = 0.34 * (1.25 - 0.6 * f)
                    beta = math.atan2(2.4, TAU * max(rr, 0.15))
                    cd = et * math.cos(beta) + ea * math.sin(beta)
                    nd = ea * math.cos(beta) - et * math.sin(beta)
                    rings_.append([hub + er * rr + cd * ((sx - 0.3) * ch) + nd * (th * ch)
                                   for sx, th in airfoil_poly(0, 1, 0.1, 6, 0.02)])
                pmb.loft(rings_, WOD)
                pmb.box(tuple(hub + er * 1.94), (0.07, 0.07, 0.07), BRS)
            S.bone(f'prop_{k}', hub, hub + Vector((0, -0.6, 0)), parent='body', shape='circle', sxyz=(2.1,) * 3,
                   color='THEME02', locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
            S.props.append(f'prop_{k}')


def deck_turret(S, idx, c, s):
    """twin anti-air autocannon on a sponson; rests facing outboard."""
    c = Vector(c)
    fwd = Vector((s, 0, 0))
    up = Vector((0, 0, 1))
    side = up.cross(fwd)
    tb, gb = f'turret_{idx}', f'gun_{idx}'
    ext = S.mb('exterior', 'body', 'static')
    ext.lathe([(0, 0), (0.75, 0), (0.7, 0.18), (0.42, 0.25), (0, 0.25)], 18, DMT, M=frame(c, up))
    t = S.mb(tb, tb, 'move')
    t.lathe([(0, 0.25), (0.6, 0.25), (0.6, 0.35), (0.25, 0.4), (0.22, 1.05), (0, 1.05)], 16, DMT, M=frame(c, up))
    sh = c + fwd * 0.75 + up * 1.25
    t.box((0, 0, 0), (1.5, 0.06, 1.0), PLT, M=Mt(*sh) @ Mrz(math.atan2(fwd.y, fwd.x) - math.pi / 2), top=(0.9, 1.0))
    for sgn in (1, -1):
        p = c + fwd * 0.45 + side * (sgn * 0.78) + up * 1.2
        t.box((0, 0, 0), (0.75, 0.05, 0.85), PLT, M=Mt(*p) @ Mrz(math.atan2(fwd.y, fwd.x) + sgn * 0.5))
    t.box(tuple(c - fwd * 0.35 + up * 0.7), (0.45, 0.45, 0.08), FAB)
    t.box(tuple(c - fwd * 0.6 + up * 0.95), (0.06, 0.4, 0.45), FAB)
    trunnion = c + up * 1.25 + fwd * 0.1
    g = S.mb(gb, gb, 'move')
    g.box(tuple(trunnion), (0.7, 0.55, 0.35), DMT)
    for sgn in (1, -1):
        bpos = trunnion + side * (sgn * 0.2)
        g.lathe([(0, -0.3), (0.06, -0.3), (0.06, 0.4), (0.04, 0.45), (0.035, 2.1), (0.055, 2.15), (0.055, 2.45),
                 (0.025, 2.45), (0, 2.35)], 10, DMT, M=frame(bpos, fwd))
        g.cyl(0.2, 0.18, 12, BRS, M=frame(bpos + up * 0.28 - fwd * 0.05, side), x0=-0.09)
        g.box(tuple(bpos + fwd * 0.9 + up * 0.09), (0.03, 0.03, 0.12), DMT)
    S.bone(tb, c, c + up * 0.8, parent='body', z=tuple(fwd), shape='circle', sxyz=(1.1,) * 3, color='THEME01',
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    S.bone(gb, trunnion, trunnion + fwd * 0.8, parent=tb, z=(0, 0, 1), shape='arrow', sxyz=(0.8, 2.5, 0.8),
           color='THEME03', locks=dict(loc=(True,) * 3, rot=(False, True, True), scale=(True,) * 3))
    flashes = []
    for sgn, tag in ((1, 'L'), (-1, 'R')):
        mz = trunnion + side * (sgn * 0.2) + fwd * 2.45
        sfx = f'{idx}{tag}'
        S.bone(f'muzzle_{sfx}', mz, mz + fwd * 0.3, parent=gb, deform=False, coll='Sockets', shape='diamond',
               sxyz=(0.1,) * 3, color='THEME06', locks=dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3))
        S.bone(f'flash_{sfx}', mz, mz + fwd * 0.4, parent=f'muzzle_{sfx}', coll='Sockets', shape='diamond',
               sxyz=(0.08,) * 3, color='THEME06', locks=dict(loc=(True,) * 3, rot=(True, False, True)))
        S.flashes.append((f'flash_{sfx}', tuple(mz), tuple(fwd), 1.0, 0.45))
        flashes.append(f'flash_{sfx}')
    S.turrets.append(dict(turret=tb, gun=gb, min=-10.0, max=85.0, flashes=flashes,
                          muzzles=[f.replace('flash', 'muzzle') for f in flashes]))


def build_moving2(S):
    for side, s in (('L', 1), ('R', -1)):
        bn = f'door_{side}'
        d = S.mb(bn, bn, 'move')
        d.box((s * 5.1, 11.1, TROOP + 1.22), (0.08, 2.3, 2.44), HUL)
        d.box((s * 5.15, 11.8, TROOP + 1.1), (0.04, 0.1, 0.3), BRS)
        d.box((s * 5.15, 11.1, TROOP + 1.7), (0.03, 0.5, 0.4), GLS)
        S.bone(bn, (s * 5.1, 11.1, TROOP + 2.5), (s * 5.1, 10.6, TROOP + 2.5), parent='body', shape='box',
               sxyz=(0.1, 1.2, 1.2), color='THEME05', locks=dict(loc=(True, False, True), rot=(True,) * 3, scale=(True,) * 3))
        S.doors[bn] = dict(axis='slide', travel=2.35)
    idx = 0
    for yy in (-8.0, 5.0):
        for s in (1, -1):
            idx += 1
            deck_turret(S, idx, (s * 5.9, yy, DECK), s)


def build_flagpoles(S):
    """3 flag positions (stern ensign + two bow side flags). Flag meshes are made after the rig."""
    ext = S.mb('exterior', 'body', 'static')
    specs = []
    base = Vector((0, 14.0, ZE + env_r(14.0) - 0.25))
    tip = base + Vector((0, 2.2, 6.2))
    specs.append(('stern', base, tip + Vector((0, 0, 1.2)), 9.0, 5.4))
    for s in (1, -1):
        yy = -22.0
        r = env_r(yy)
        b = Vector((s * (r - 0.25) * math.cos(0.3), yy, ZE + (r - 0.25) * math.sin(0.3)))
        t = b + Vector((s * 3.0, 0.6, 2.6))
        specs.append(('bow_' + ('L' if s > 0 else 'R'), b, t + Vector((0, 0, 0.8)), 6.0, 3.6))
    for name, b, t, L, H in specs:
        pipe(ext, b, t + Vector((0, 0, 0.15)), 0.09, DMT, 10)
        ext.lathe([(0.22, 0), (0.3, 0.05), (0.3, 0.2), (0, 0.25)], 10, PLT, M=frame(b, (t - b)))
        ext.lathe([(0, 0), (0.12, 0.05), (0.14, 0.15), (0.08, 0.25), (0, 0.3)], 10, BRS,
                  M=frame(t + Vector((0, 0, 0.15)), (0, 0, 1)))
        S.flagpos.append(dict(name=name, top=t, L=L, H=H))
        for k in range(4):
            bn = f'flag_{name}_{k}'
            hh = t + Vector((0, k * L / 4, -H / 2))
            S.bone(bn, hh, hh + Vector((0, L / 4, 0)), parent='body' if k == 0 else f'flag_{name}_{k - 1}',
                   z=(0, 0, 1), coll='Flags', shape='box', sxyz=(0.05, L / 8, H / 2), color='THEME04',
                   locks=dict(loc=(True,) * 3, rot=(True, True, False), scale=(True,) * 3))


def build_flag_meshes(S):
    rig = S.rig
    variants = [('Flag_SkyLegion', FLA), ('Flag_IronRepublic', FLB), ('Flag_StormCorsairs', FLC)]
    nu, nv = 12, 6
    objs = []
    for vi, (vname, mi) in enumerate(variants):
        verts, faces, uvs, groups = [], [], [], {}
        for fp in S.flagpos:
            t, L, H = fp['top'], fp['L'], fp['H']
            base = len(verts)
            for i in range(nu + 1):
                for j in range(nv + 1):
                    u, v = i / nu, j / nv
                    x = 0.12 * math.sin(u * math.pi * 2.0) * u
                    verts.append((t.x + x, t.y + u * L, t.z - v * H))
                    f = u * 4
                    k = min(int(f), 3)
                    w = f - k
                    for bk, ww in ((k, 1 - w), (k + 1, w)):
                        if bk <= 3 and ww > 1e-4:
                            groups.setdefault(f"flag_{fp['name']}_{bk}", []).append((base + i * (nv + 1) + j, ww))
            for i in range(nu):
                for j in range(nv):
                    a = base + i * (nv + 1) + j
                    faces.append((a, a + 1, a + nv + 2, a + nv + 1))
                    uvs += [(i / nu, 1 - j / nv), (i / nu, 1 - (j + 1) / nv), ((i + 1) / nu, 1 - (j + 1) / nv),
                            ((i + 1) / nu, 1 - j / nv)]
        me = bpy.data.meshes.new(f'Skyship_{vname}')
        me.from_pydata(verts, [], faces)
        me.uv_layers.new(name='UVMap').data.foreach_set('uv', [c for uv in uvs for c in uv])
        me.materials.append(S.mat_list[mi])
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(f'Skyship_{vname}', me)
        S.coll.objects.link(ob)
        for bn, lst in groups.items():
            vg = ob.vertex_groups.new(name=bn)
            for vi2, ww in lst:
                vg.add([vi2], ww, 'ADD')
        ob.parent = rig
        ob.modifiers.new('Armature', 'ARMATURE').object = rig
        objs.append(ob)
    S.flag_objs = objs
    return objs


def build_sky():
    S = Sky(SHIP)
    build_hull(S)
    build_deck(S)
    build_interior(S)
    build_envelope2(S)
    fin2(S, True, 1, 'elevator_L')
    fin2(S, True, -1, 'elevator_R')
    fin2(S, False, 1, 'rudder_U')
    fin2(S, False, -1, 'rudder_D')
    build_engines2(S)
    build_moving2(S)
    build_flagpoles(S)
    S.bone('root', (0, 0, 0), (0, -2.0, 0), shape='square', sxyz=(6.0, 45.0, 1.0), color='THEME09')
    S.bone('body', (0, 0, 10.0), (0, -2.0, 10.0), parent='root', shape='box', sxyz=(9.0, 44.0, 9.0), color='THEME09')
    S.finish_parts()
    return S


# ------------------------------------------------------------------------------ assembly / clips / collision
def box_uv2(me):
    uvl = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    co = [v.co.copy() for v in me.vertices]
    data = uvl.data
    for p in me.polygons:
        mi = p.material_index
        if mi in (DEC, FLA, FLB, FLC):
            continue
        if mi == WAL and p.center.z > DECK + 0.05 and abs(p.normal.z) < 0.5 and \
                not (abs(p.center.x) < 3.3 and 13.0 < p.center.y < 19.8):
            p.material_index = mi = HUL
        su, sv = TILE.get(mi, (1.0, 1.0))
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        zo = 0.0
        if mi == WAL:
            zo = max([lv for lv in LEVELS if lv <= p.center.z + 0.05] or [0.0])
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


def assemble_sky(S):
    rig = S.rig
    vl = bpy.context.view_layer
    names = {'exterior': 'Skyship_Exterior', 'int_hold': 'Skyship_Interior_Hold',
             'int_troop': 'Skyship_Interior_TroopDeck'}
    moving = []
    for ob, bone, group in S.objs:
        box_uv2(ob.data)
        key = ob.name.split('_', 1)[1]
        if group == 'static':
            ob.name = ob.data.name = names.get(key, f'Skyship_{key}')
            ob.parent = rig
        else:
            ob.vertex_groups.clear()
            ob.vertex_groups.new(name=bone).add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
            moving.append(ob)
    for o in vl.objects:
        o.select_set(False)
    for o in moving:
        o.select_set(True)
    vl.objects.active = moving[0]
    bpy.ops.object.join()
    mv = vl.objects.active
    mv.name = mv.data.name = 'Skyship_Moving'
    mv.parent = rig
    mv.modifiers.new('Armature', 'ARMATURE').object = rig
    for ob in S.extra:
        ob.parent = rig
    S.build_flash(flash_material())
    fo = S.flash_obj
    fo.name = fo.data.name = 'Skyship_MuzzleFlash'
    fo.parent = rig
    fo.modifiers.new('Armature', 'ARMATURE').object = rig
    for ob in [o for o in rig.children if o.type == 'MESH']:
        if ob.name not in ('Skyship_MuzzleFlash',):
            prune_materials(ob.data)
            tri_big_ngons(ob.data)
    build_flag_meshes(S)
    for i, (x, y, z) in enumerate(S.lights):
        e = bpy.data.objects.new(f'LightSocket_{i:02d}', None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = 0.15
        S.coll.objects.link(e)
        e.location = (x, y, z)
        e.parent = rig
    S.moving = mv


def sky_clip(S, name, f0, f1, fn, interp='LINEAR'):
    rig = S.rig
    ad = rig.animation_data_create()
    pbs = rig.pose.bones

    def reset():
        for pb in pbs:
            pb.location, pb.rotation_euler, pb.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    reset()
    act = bpy.data.actions.new(f'{SHIP}_{name}')
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


def sky_clips(S):
    made = []
    made.append(sky_clip(S, 'Props_Spin', 1, 5, lambda key: [
        (key(p, 'rotation_euler', 1, 1, 0.0), key(p, 'rotation_euler', 1, 5, TAU / 3)) for p in S.props]))

    def ctl(key):
        for bn, ax in S.controls.items():
            seq = (1, 13, 25) if ax == 'pitch' else (25, 37, 49)
            for f, v in ((1, 0), (seq[0], 0), (seq[1], 22), (seq[2], 0), (49, 0)):
                key(bn, 'rotation_euler', 1, f, math.radians(v))
    made.append(sky_clip(S, 'Controls_Demo', 1, 49, ctl, 'BEZIER'))
    made.append(sky_clip(S, 'Doors_Open', 1, 37, lambda key: [
        (key(d, 'location', 1, 1, 0.0), key(d, 'location', 1, 37, -2.35)) for d in ('door_L', 'door_R')], 'BEZIER'))

    def trav(key):
        for t in S.turrets:
            for f, v in ((1, 0), (25, 60), (73, -60), (97, 0)):
                key(t['turret'], 'rotation_euler', 1, f, math.radians(v))
            for f, v in ((1, 0), (25, 45), (49, 80), (73, 20), (97, 0)):
                key(t['gun'], 'rotation_euler', 0, f, math.radians(v))
    made.append(sky_clip(S, 'Turrets_Sweep', 1, 97, trav, 'BEZIER'))

    def fire(key):
        Sx = 1.0 / FLASH_REST
        for t in S.turrets:
            for fi, fb in enumerate(t['flashes']):
                key(fb, 'scale', None, 1, (1, 1, 1))
                for s in range(1 + fi * 2, 22, 4):
                    key(fb, 'scale', None, s, (Sx, Sx, Sx))
                    key(fb, 'scale', None, s + 1, (0.6 * Sx,) * 3)
                    key(fb, 'scale', None, s + 2, (1, 1, 1))
                key(fb, 'scale', None, 25, (1, 1, 1))
    made.append(sky_clip(S, 'Fire', 1, 25, fire))

    def wave(key):
        amps = (0.16, 0.26, 0.34, 0.42)
        for pi, fp in enumerate(S.flagpos):
            for k in range(4):
                bn = f"flag_{fp['name']}_{k}"
                for f in range(1, 26, 2):
                    ph = TAU * (f - 1) / 24.0 - k * 1.15 - pi * 0.8
                    key(bn, 'rotation_euler', 2, f, amps[k] * math.sin(ph))
    made.append(sky_clip(S, 'Flags_Wave', 1, 25, wave))
    S.rig.animation_data.action = None
    return made


def build_collision2(S):
    mb = MB()
    n = len(PLAN)
    for i in range(n):
        A, B = Vector(PLAN[i]), Vector(PLAN[(i + 1) % n])
        L = (B - A).length
        d = (B - A) / L
        ops = []
        if abs(d.x) < 1e-6 and L > 20:
            du = sorted(((10.0 - A.y) / d.y, (12.2 - A.y) / d.y))
            ops.append((du[0], du[1], TROOP, TROOP + 2.4, 'door'))
        wall(mb, A, B, 0.4, BUL, WT, ops)
    deck(mb, 0.4, HOLD, ())
    deck(mb, TROOP - 0.2, TROOP, [(3.0, 4.0, -14.5, -13.5)])
    deck(mb, DECK - 0.2, DECK, [(-0.8, 0.8, -14.4, -10.6), (-0.8, 0.8, 8.6, 12.4)])
    mb.loft([ring(PLAN, 0.4), ring(PLAN, -0.6, 0.78, 0.97), ring(PLAN, -1.5, 0.28, 0.9)], 0)
    for y, z0, z1, door in ((3.0, HOLD, TROOP - 0.2, (-0.6, 0.6, 2.0)), (-15.0, TROOP, DECK - 0.2, (-0.6, 0.6, 2.1)),
                            (8.0, TROOP, DECK - 0.2, (-0.7, 0.7, 2.1)), (14.0, TROOP, DECK - 0.2, (-0.6, 0.6, 2.1))):
        bulkhead2(mb, y, z0, z1, door)
    dh = [(3.0, 13.2), (3.0, 19.6), (-3.0, 19.6), (-3.0, 13.2)]
    for i in range(4):
        A, B = Vector(dh[i]), Vector(dh[(i + 1) % 4])
        ops = [((B - A).length - 2.0, (B - A).length - 1.0, DECK, DECK + 2.1, 'door')] if i == 3 else []
        wall(mb, A, B, DECK, DECK + 3.0, 0.18, ops)
    mb.box((0, 16.4, DECK + 3.08), (6.5, 6.9, 0.16), 0)
    for ya, yb in ((-10.6, -14.4), (12.4, 8.6)):
        a, b = Vector((0, ya, TROOP)), Vector((0, yb, DECK))
        dv = b - a
        M = (Mt(*((a + b) / 2)) @ Mrx(math.atan2(dv.z, dv.y))) if dv.y > 0 else \
            (Mt(*((a + b) / 2)) @ Mrz(math.pi) @ Mrx(math.atan2(dv.z, -dv.y)))
        mb.box((0, 0, 0), (1.6, dv.length, 0.1), 0, M=M)
    for s in (1, -1):
        for yy in (-8.0, 5.0):
            mb.lathe([(0, -0.25), (1.45, -0.25), (1.5, 0.0), (0, 0.0)], 12, 0, M=frame((s * 5.9, yy, DECK), (0, 0, 1)))
    ys = list(np.arange(ENV_KEYS[0][0], ENV_KEYS[-1][0], 3.0)) + [ENV_KEYS[-1][0]]
    mb.loft([[(env_r(y) * math.cos(TAU * k / 16), y, ZE + env_r(y) * math.sin(TAU * k / 16)) for k in range(16)]
             for y in ys], 0)
    me = mb.to_mesh('Skyship_Collision', [], sharp=30)
    ob = bpy.data.objects.new('Skyship_Collision-colonly', me)
    S.coll.objects.link(ob)
    ob.parent = S.rig
    ob.display_type = 'WIRE'
    ob.hide_render = True
    return ob


def reset_sky():
    col = bpy.data.collections.get('Skyship')
    if col:
        for o in list(col.all_objects):
            bpy.data.objects.remove(o)
    for a in [a for a in bpy.data.actions if a.name.startswith(SHIP + '_')]:
        bpy.data.actions.remove(a)
    bpy.data.orphans_purge(do_recursive=True)
