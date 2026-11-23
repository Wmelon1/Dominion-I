# Tank Kit builder - detail helpers and the five tank designs.
# Coordinates are tank-local metres: X = left (+) / right (-), Y = back (+) / front (-), Z = up. Ground at Z=0.


# ---------------------------------------------------------------------------------------- details
def hatch(mb, c, r, n=(0, 0, 1), h=0.045, segs=12, mat=P):
    M = frame(c, n)
    mb.lathe([(0, 0), (r, 0), (r, h * 0.7), (r * 0.9, h), (0, h)], segs, mat, M=M)
    nn = Vector(n).normalized()
    rear = Vector((0, 1, 0)) - nn * nn.y
    rear.normalize()
    hc = Vector(c) + rear * (r * 0.92) + nn * (h * 0.6)
    mb.cyl(0.028, r * 0.7, 8, MT, M=frame(hc, (1, 0, 0)))
    hd = Vector(c) - rear * (r * 0.55) + nn * (h + 0.015)
    mb.box((0, 0, 0), (0.12, 0.03, 0.03), MT, M=Mt(*hd))


def periscope(mb, c, yaw=0.0, w=0.12, d=0.07, h=0.07, tilt=0.0, mat=P):
    fs = mb.box((0, 0, h / 2), (w, d, h), mat, M=Mt(*c) @ Mrz(yaw) @ Mrx(tilt), top=(0.92, 0.7))
    fs[0].material_index = GL


def cupola(mb, c, r, h, n=6, mat=P):
    x, y, z = c
    mb.lathe([(0, 0), (r, 0), (r, h * 0.7), (r * 0.9, h), (0, h)], 16, mat, M=frame((x, y, z), (0, 0, 1)))
    hatch(mb, (x, y, z + h), r * 0.78, h=0.05)
    for i in range(n):
        a = TAU * i / n - math.pi / 2
        o = (x + (r - 0.025) * math.cos(a), y + (r - 0.025) * math.sin(a), z + h * 0.28)
        periscope(mb, o, a + math.pi / 2, 0.11, 0.07, h * 0.45)


def smoke_launchers(mb, base, out_dir, n=4, spacing=0.11):
    d = Vector((out_dir[0], out_dir[1], 0)).normalized()
    up = Vector((0, 0, 1))
    side = up.cross(d)
    b = Vector(base)
    beam(mb, b - side * (spacing * n / 2), b + side * (spacing * n / 2), 0.13, 0.08, P)
    td = (d * 0.8 + up * 0.6).normalized()
    for i in range(n):
        o = b + side * ((i - (n - 1) / 2) * spacing) + up * 0.05
        mb.cyl(0.042, 0.24, 8, P, M=frame(o, td), x0=-0.04, cap_mat=MT)


def antenna(mb, c, h):
    x, y, z = c
    mb.cyl(0.045, 0.1, 8, MT, M=frame((x, y, z), (0, 0, 1)), x0=0.0)
    mb.cyl(0.012, h, 5, MT, M=frame((x, y, z + 0.1), (0, 0, 1)), x0=0.0, r2=0.006)


def headlight(mb, c, fwd=(0, -1, 0), r=0.07):
    M = frame(c, fwd)
    mb.lathe([(0, -0.07), (r, -0.07), (r, 0.03), (r * 0.88, 0.045), (0, 0.045)], 10, P, mats=[P, P, P, LT], M=M)
    c = Vector(c)
    mb.box((c.x, c.y + 0.07, c.z - r - 0.02), (0.06, 0.1, 0.06), P)
    beam(mb, c + Vector((-r - 0.03, -0.03, -r)), c + Vector((-r - 0.03, -0.03, r + 0.04)), 0.025, 0.025, MT)
    beam(mb, c + Vector((r + 0.03, -0.03, -r)), c + Vector((r + 0.03, -0.03, r + 0.04)), 0.025, 0.025, MT)
    beam(mb, c + Vector((-r - 0.03, -0.03, r + 0.04)), c + Vector((r + 0.03, -0.03, r + 0.04)), 0.025, 0.025, MT)


def taillight(mb, c):
    fs = mb.box(c, (0.14, 0.05, 0.08), P)
    fs[2].material_index = LR


def grille(mb, c, sx, sy, n=6):
    x, y, z = c
    mb.box((x, y, z + 0.005), (sx, sy, 0.03), MT)
    for dy in (-sy / 2, sy / 2):
        mb.box((x, y + dy, z + 0.018), (sx + 0.05, 0.05, 0.036), P)
    for dx in (-sx / 2, sx / 2):
        mb.box((x + dx, y, z + 0.018), (0.05, sy, 0.036), P)
    for i in range(n):
        xx = x - sx / 2 + (i + 0.5) * sx / n
        mb.box((xx, y, z + 0.016), (0.025, sy - 0.02, 0.03), P)


def storage_box(mb, c, s, mat=P, latch_dir=-1):
    x, y, z = c
    mb.box((x, y, z + s[2] * 0.42), (s[0], s[1], s[2] * 0.84), mat)
    mb.box((x, y, z + s[2] * 0.92), (s[0] + 0.025, s[1] + 0.025, s[2] * 0.16), mat)
    if latch_dir == -1:
        for dx in (-s[0] * 0.3, s[0] * 0.3):
            mb.box((x + dx, y - s[1] / 2 - 0.012, z + s[2] * 0.76), (0.05, 0.025, 0.07), MT)
    else:
        for dy in (-s[1] * 0.3, s[1] * 0.3):
            mb.box((x + latch_dir * (s[0] / 2 + 0.012), y + dy, z + s[2] * 0.76), (0.025, 0.05, 0.07), MT)


def jerrycan(mb, c, yaw=0.0):
    M = Mt(*c) @ Mrz(yaw)
    mb.box((0, 0, 0.24), (0.17, 0.36, 0.48), P, M=M, top=(0.95, 0.97))
    mb.box((0, 0.05, 0.5), (0.04, 0.16, 0.04), P, M=M)
    mb.cyl(0.025, 0.05, 6, MT, M=M @ frame((0, -0.12, 0.49), (0, 0, 1)), x0=0.0)


def towhook(mb, c):
    mb.box(c, (0.09, 0.14, 0.11), MT)
    mb.cyl(0.03, 0.14, 8, MT, M=frame(Vector(c) + Vector((0, -0.07, -0.02)), (1, 0, 0)))


def machine_gun(mb, base, yaw=0.0, L=1.1):
    M = Mt(*base) @ Mrz(yaw)
    mb.cyl(0.03, 0.26, 6, MT, M=M @ frame((0, 0, 0), (0, 0, 1)), x0=0.0)
    mb.box((0, 0, 0.31), (0.1, 0.36, 0.12), MT, M=M)
    mb.cyl(0.02, L, 6, MT, M=M @ frame((0, -0.17, 0.32), (0, -1, 0)), x0=0.0)
    mb.cyl(0.032, 0.12, 6, MT, M=M @ frame((0, -0.17 - L, 0.32), (0, -1, 0)), x0=-0.06)
    mb.box((0.11, 0.0, 0.3), (0.12, 0.18, 0.15), P, M=M)
    mb.box((0, 0.17, 0.34), (0.06, 0.12, 0.06), MT, M=M)


def bustle_rack(mb, x, y0, y1, z0, h, posts=4):
    for s in (1, -1):
        beam(mb, (s * x, y0, z0 + h), (s * x, y1, z0 + h), 0.035, 0.035, MT)
        beam(mb, (s * x, y0, z0 + h * 0.45), (s * x, y1, z0 + h * 0.45), 0.03, 0.03, MT)
    beam(mb, (-x, y1, z0 + h), (x, y1, z0 + h), 0.035, 0.035, MT)
    beam(mb, (-x, y1, z0 + h * 0.45), (x, y1, z0 + h * 0.45), 0.03, 0.03, MT)
    for i in range(posts):
        xx = -x + 2 * x * i / (posts - 1)
        beam(mb, (xx, y1, z0), (xx, y1, z0 + h), 0.035, 0.035, MT)
    for s in (1, -1):
        beam(mb, (s * x, (y0 + y1) / 2, z0), (s * x, (y0 + y1) / 2, z0 + h), 0.035, 0.035, MT)
    mb.box((0, (y0 + y1) / 2, z0 + 0.01), (2 * x, y1 - y0, 0.02), MT)


def tarp_roll(mb, c, L, r=0.13):
    mb.cyl(r, L, 10, P, M=frame(c, (1, 0, 0)))
    for dx in (-L * 0.3, L * 0.3):
        mb.cyl(r + 0.008, 0.04, 10, MT, M=frame(Vector(c) + Vector((dx, 0, 0)), (1, 0, 0)))


def skirts(mb, x, z0, z1, y0, y1, n, t=0.04, gap=0.025, rubber=True):
    L = y1 - y0
    pw = (L - gap * (n - 1)) / n
    for s in (1, -1):
        for i in range(n):
            yc = y0 + pw / 2 + i * (pw + gap)
            mb.box((s * x, yc, (z0 + z1) / 2 + 0.035), (t, pw, (z1 - z0) - 0.07), P)
            if rubber:
                mb.box((s * x, yc, z0 + 0.035), (t * 0.75, pw, 0.07), RB)
            for dy in (-pw * 0.35, pw * 0.35):
                mb.box((s * (x + t / 2), yc + dy, z1 - 0.06), (0.02, 0.05, 0.05), MT)


def era_skirts(mb, x, z0, z1, y0, y1, cols, rows=2, t=0.12, gap=0.03):
    bw = (y1 - y0 - gap * (cols - 1)) / cols
    bh = (z1 - z0 - gap * (rows - 1)) / rows
    for s in (1, -1):
        for i in range(cols):
            for j in range(rows):
                yc = y0 + bw / 2 + i * (bw + gap)
                zc = z0 + bh / 2 + j * (bh + gap)
                mb.box((s * x, yc, zc), (t, bw, bh), P, top=(1.0, 0.94))
                mb.box((s * (x + t / 2 + 0.008), yc, zc), (0.016, bw * 0.3, 0.04), MT)


def turret_ring(mb, ty, zd, r):
    mb.lathe([(0, zd - 0.01), (r + 0.1, zd - 0.01), (r + 0.1, zd + 0.03), (r + 0.06, zd + 0.05), (0, zd + 0.05)],
             24, P, M=Mt(0, ty, 0) @ frame((0, 0, 0), (0, 0, 1)))


# ---------------------------------------------------------------------------------------- shells
def hull_shell(T, H):
    mb = T.mb('hull', 'hull', 'hull')
    wi = H['wi']
    prof = H['lower']
    mb.loft([[(-wi, y, z) for y, z in prof], [(wi, y, z) for y, z in prof]], P)
    mb.loft([ring_rect(*lv) for lv in H['upper']], P)
    return mb


def glacis(H, x, t, off=0.0):
    L1, L2 = H['upper'][1], H['upper'][2]
    y = L1[1] + (L2[1] - L1[1]) * t
    z = L1[3] + (L2[3] - L1[3]) * t
    n = Vector((0, -(L2[3] - L1[3]), (L2[1] - L1[1]))).normalized()
    return Vector((x, y, z)) + n * off, n, math.atan2(L2[3] - L1[3], L2[1] - L1[1])


def rear_plate(H, x, t, off=0.0):
    L1, L2 = H['upper'][1], H['upper'][2]
    y = L1[2] + (L2[2] - L1[2]) * t
    z = L1[3] + (L2[3] - L1[3]) * t
    n = Vector((0, (L2[3] - L1[3]), -(L2[2] - L1[2]))).normalized()
    return Vector((x, y, z)) + n * off, n


def hull_details(T, H, rg, o):
    mb = T.mb('hull', 'hull', 'hull')
    wu, wi = H['wu'], H['wi']
    L0, L1, L2 = H['upper']
    zd = L2[3]
    for s in (1, -1):
        p, n, ga = glacis(H, s * (wu - o.get('light_in', 0.25)), 0.14, 0.1)
        headlight(mb, p, (0, -1, 0), o.get('light_r', 0.07))
    dx = o.get('driver_x', 0.0)
    p, n, ga = glacis(H, dx, o.get('hatch_t', 0.55))
    hatch(mb, p, o.get('hatch_r', 0.27), n)
    pt = o.get('peri_t', 0.86)
    for k in (-1, 0, 1):
        pp, nn, ga = glacis(H, dx + k * 0.2, pt)
        periscope(mb, pp, 0.0, 0.13, 0.08, 0.07, tilt=ga * 0.5)
    # front mudguards
    for s in (1, -1):
        a = 0.32
        c = Vector((s * rg['tx'], L0[1] - 0.14 * math.cos(a), L0[3] - 0.14 * math.sin(a)))
        mb.box((0, 0, 0), (rg['tw'] + 0.08, 0.3, 0.025), P, M=Mt(*c) @ Mrx(a))
    # tow hooks front / rear on the lower hull plates
    lw = H['lower']
    fz = (lw[0][1] + lw[3][1]) / 2
    fy = (lw[0][0] + lw[3][0]) / 2
    rz = (lw[1][1] + lw[2][1]) / 2
    ry = (lw[1][0] + lw[2][0]) / 2
    for s in (1, -1):
        towhook(mb, (s * wi * 0.55, fy - 0.05, fz))
        towhook(mb, (s * wi * 0.55, ry + 0.05, rz))
    for i in range(o.get('spare_links', 0)):
        n = o['spare_links']
        x = (i - (n - 1) / 2) * (rg['tw'] * 0.9)
        c = Vector((x, fy - 0.04, fz + 0.12))
        a = math.atan2(lw[3][1] - lw[0][1], lw[3][0] - lw[0][0])
        mb.box((0, 0, 0), (rg['tw'] * 0.8, 0.2, 0.05), MT, M=Mt(*c) @ Mrx(math.pi / 2 - a))
    # rear plate items
    for s in (1, -1):
        p, n = rear_plate(H, s * (wu - 0.16), 0.55, 0.02)
        taillight(mb, p)
    if o.get('exhaust', True):
        p, n = rear_plate(H, 0.0, 0.45, 0.05)
        mb.box(p, (o.get('exhaust_w', 1.2), 0.1, 0.22), MT)
        for i in range(7):
            xx = p.x - o.get('exhaust_w', 1.2) / 2 + (i + 0.5) * o.get('exhaust_w', 1.2) / 7
            mb.box((xx, p.y + 0.055, p.z), (0.03, 0.03, 0.22), P)
    for (x, y, sx, sy) in o.get('grilles', []):
        grille(mb, (x, y, zd), sx, sy, max(3, int(sx / 0.11)))
    for (x, y, s, ld) in o.get('boxes', []):
        storage_box(mb, (x, y, zd), s, latch_dir=ld)
    for (x, y, z, yaw) in o.get('cans', []):
        jerrycan(mb, (x, y, z), yaw)
    for (x, y, h) in o.get('antennas', []):
        antenna(mb, (x, y, zd), h)


def turret_shell(T, TU, zd, ring_r):
    mb = T.mb('turret', 'turret', 'turret')
    half = TU['half']
    ext = max(math.hypot(x, y) for x, y in half)
    s0 = (ring_r * 1.05) / ext
    rings = [ring_half(half, zd - 0.03, s0 * 1.15, s0, 0.0, TU['ty'])]
    mats = [P]
    for (z, sx, sy, dy, m) in TU['levels']:
        rings.append(ring_half(half, z, sx, sy, 0.0, TU['ty'] + dy))
        mats.append(m)
    mb.loft(rings, P, ring_mats=mats[:-1] if len(mats) > 1 else None)
    return mb


def barrel_lathe(mb, origin, prof, segs=14, fwd=(0, -1, 0), metal_tail=2):
    n = len(prof) - 1
    mats = [P] * (n - metal_tail) + [MT] * metal_tail
    mb.lathe(prof, segs, mats=mats, M=frame(origin, fwd))


def std_bones(T, H, TU, zd, ring_r, trunnion, gun_len, barrels):
    wu = H['wu']
    L0 = H['upper'][0]
    yf, yr, zf = L0[1], L0[2], L0[3]
    halfL = (yr - yf) / 2
    T.bone('root', (0, 0, 0), (0, -1.0, 0), shape='square', sxyz=(wu + 0.35, halfL + 0.35, 1), color='THEME09')
    zh = (zf + zd) / 2
    T.bone('hull', (0, (yf + yr) / 2, zh), (0, (yf + yr) / 2 - 0.8, zh), parent='root', shape='box',
           sxyz=(wu * 0.97, halfL * 0.97, (zd - zf) / 2 + 0.08), color='THEME09')
    ty = TU['ty']
    lock_all = dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3)
    T.bone('turret', (0, ty, zd), (0, ty, zd + 0.8), parent='hull', z=(0, -1, 0), shape='circle',
           sxyz=(ring_r * 1.4,) * 3, color='THEME01',
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    tr = Vector(trunnion)
    T.bone('gun', tr, tr + Vector((0, -1.2, 0)), parent='turret', shape='arrow', sxyz=(2.0, gun_len, 2.0),
           color='THEME03', locks=dict(loc=(True,) * 3, rot=(False, True, True), scale=(True,) * 3))
    for (sfx, base, muzzle, rec, Lf, Wf, shots) in barrels:
        bb, mz, fb = 'barrel' + sfx, 'muzzle' + sfx, 'flash' + sfx
        base, muzzle = Vector(base), Vector(muzzle)
        T.bone(bb, base, base + Vector((0, -0.8, 0)), parent='gun', shape='box', sxyz=(0.16, 0.4, 0.16),
               color='THEME04', locks=dict(loc=(True, False, True), rot=(True,) * 3, scale=(True,) * 3))
        T.bone(mz, muzzle, muzzle + Vector((0, -0.3, 0)), parent=bb, deform=False, coll='Sockets',
               shape='diamond', sxyz=(0.12,) * 3, color='THEME06', locks=lock_all)
        T.bone(fb, muzzle, muzzle + Vector((0, -0.4, 0)), parent=mz, coll='Sockets', shape='diamond',
               sxyz=(0.06,) * 3, color='THEME06',
               locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(False,) * 3))
        T.flashes.append((fb, tuple(muzzle), (0, -1, 0), Lf, Wf))
        T.guns.append((bb, fb, rec, shots))
    for side, s in (('L', 1), ('R', -1)):
        x = s * (wu + 0.6)
        T.bone(f'track_{side}', (x, 0, 0.12), (x, -1.0, 0.12), parent='root', deform=False, shape='arrow',
               sxyz=(1.3, 1.3, 1.3), color='THEME02',
               locks=dict(loc=(True, False, True), rot=(True,) * 3, scale=(True,) * 3))


def finish_meta(T, kind, gmin, gmax, extra=None):
    m = T.meta
    m.update(dict(tank=T.name, kind=kind, turret_bone='turret', gun_bone='gun', gun_min=gmin, gun_max=gmax,
                  track_pitch=round(T.sol['p'], 6), links_per_side=T.sol['N'],
                  drive_clip_speed=round(T.sol['p'] / (LINK_FRAMES / 24.0), 4)))
    m['barrels'] = [dict(bone=g[0], flash=g[1], recoil=g[2]) for g in T.guns]
    m['wheels'] = {bn: round(r, 5) for (bn, side, r) in T.wheel_drv}
    if extra:
        m.update(extra)


# ---------------------------------------------------------------------------------------- tanks
def build_scout(T):
    H = dict(wi=0.85, wu=1.32,
             lower=[(-1.95, 0.36), (2.0, 0.36), (2.42, 0.87), (-2.42, 0.87)],
             upper=[(1.32, -2.42, 2.42, 0.87, 0.05), (1.32, -2.38, 2.40, 0.93, 0.05),
                    (1.22, -1.30, 2.30, 1.20, 0.08)])
    T.H = H
    rg = dict(p=0.16, tp=0.045, g=0.03, tw=0.38, tx=1.10, horn_w=0.05, horn_h=0.05,
              road=dict(r=0.34, ys=[-1.48, -0.50, 0.48, 1.46]),
              front=dict(kind='idler', y=-2.13, z=0.46, r=0.22),
              rear=dict(kind='sprocket', y=2.20, z=0.48, Z=11), top='wheels')
    T.running_gear(rg)
    zd = 1.20
    hull = hull_shell(T, H)
    hull_details(T, H, rg, dict(light_in=0.22, light_r=0.06, driver_x=0.45, hatch_t=0.45, hatch_r=0.24,
                                peri_t=0.78, exhaust_w=0.8,
                                grilles=[(0.42, 1.55, 0.62, 1.0), (-0.42, 1.55, 0.62, 1.0)],
                                boxes=[(1.02, 1.85, (0.34, 0.75, 0.26), 1), (-1.02, 1.85, (0.34, 0.75, 0.26), -1)],
                                cans=[(0.32, 2.52, 0.78, 0.0), (-0.32, 2.52, 0.78, 0.0)],
                                antennas=[(-0.95, 0.9, 1.7)]))
    TU = dict(ty=-0.12, half=[(0, -1.0), (0.42, -0.92), (0.80, -0.40), (0.84, 0.40), (0.70, 0.82), (0, 0.86)],
              levels=[(1.30, 1.0, 1.0, 0.0, P), (1.40, 0.98, 0.98, 0.02, K), (1.47, 0.96, 0.965, 0.03, P),
                      (1.64, 0.84, 0.86, 0.07, P)])
    ring_r = 0.62
    turret_ring(hull, TU['ty'], zd, ring_r)
    tur = turret_shell(T, TU, zd, ring_r)
    ty = TU['ty']
    tz = 1.64
    hatch(tur, (-0.33, ty + 0.25, tz), 0.25)
    tur.box((0.33, ty + 0.18, tz + 0.09), (0.2, 0.22, 0.18), P)
    pf = tur.box((0.33, ty + 0.12, tz + 0.26), (0.26, 0.2, 0.16), P, top=(0.9, 0.8))
    pf[0].material_index = GL
    for x in (0.12, -0.12):
        periscope(tur, (x, ty - 0.62, tz - 0.02), 0.0, 0.12, 0.07, 0.07)
    for s in (1, -1):
        smoke_launchers(tur, (s * 0.66, ty - 0.66, 1.52), (s * 0.55, -0.83), n=3)
    antenna(tur, (-0.45, ty + 0.62, tz), 1.5)
    # twin ATGM launcher on the left side
    tur.box((0.93, ty + 0.05, 1.44), (0.12, 0.3, 0.12), P)
    tur.box((1.02, ty - 0.1, 1.5), (0.22, 0.95, 0.3), P, top=(1.0, 0.98))
    for z in (1.43, 1.57):
        tur.cyl(0.07, 0.04, 10, MT, M=frame((1.02, ty - 0.6, z), (0, -1, 0)), x0=-0.02)
    # gun: 30 mm autocannon
    trunnion = (0.0, ty - 0.80, 1.43)
    gun = T.mb('gun', 'gun', 'turret')
    gun.box((0, ty - 1.0, 1.43), (0.36, 0.32, 0.30), P, top=(0.92, 0.85))
    gun.cyl(0.02, 0.2, 6, MT, M=frame((-0.13, ty - 1.18, 1.40), (0, -1, 0)), x0=0.0)
    gun.box((0.22, ty - 1.02, 1.5), (0.1, 0.22, 0.12), P)
    brl = T.mb('barrel', 'barrel', 'turret')
    prof = [(0, 0.12), (0.07, 0.12), (0.07, 0.45), (0.045, 0.5), (0.04, 1.95), (0.058, 1.97), (0.058, 2.17),
            (0.03, 2.17), (0.03, 2.07), (0, 2.07)]
    barrel_lathe(brl, trunnion, prof, 12)
    muzzle = (0.0, trunnion[1] - 2.17, trunnion[2])
    std_bones(T, H, TU, zd, ring_r, trunnion, 2.2,
              [('', (0, trunnion[1] - 0.2, trunnion[2]), muzzle, 0.12, 0.9, 0.42, [1, 7, 13])])
    finish_meta(T, 'light_scout', -10.0, 35.0)


def build_medium(T):
    H = dict(wi=1.115, wu=1.755,
             lower=[(-2.50, 0.45), (2.62, 0.45), (3.12, 1.07), (-3.22, 1.07)],
             upper=[(1.755, -3.22, 3.12, 1.07, 0.05), (1.755, -3.18, 3.10, 1.13, 0.05),
                    (1.64, -2.05, 3.0, 1.50, 0.10)])
    T.H = H
    rg = dict(p=0.18, tp=0.05, g=0.03, tw=0.55, tx=1.45, horn_w=0.06, horn_h=0.065,
              road=dict(r=0.33, ys=[-2.22, -1.36, -0.50, 0.36, 1.22, 2.08]),
              front=dict(kind='idler', y=-2.92, z=0.58, r=0.27),
              rear=dict(kind='sprocket', y=2.98, z=0.64, Z=12),
              rollers=dict(r=0.11, ys=[-1.79, -0.07, 1.65]))
    T.running_gear(rg)
    zd = 1.50
    hull = hull_shell(T, H)
    skirts(hull, 1.755 + 0.025, 0.66, 1.07, -2.95, 2.75, 5)
    hull_details(T, H, rg, dict(light_in=0.25, driver_x=0.0, hatch_t=0.42, hatch_r=0.26, peri_t=0.78,
                                spare_links=3, exhaust_w=1.5,
                                grilles=[(0.0, 2.15, 1.2, 0.85), (1.05, 1.95, 0.42, 1.2), (-1.05, 1.95, 0.42, 1.2)],
                                boxes=[(1.42, 2.62, (0.42, 0.62, 0.3), 1), (-1.42, 2.62, (0.42, 0.62, 0.3), -1)],
                                cans=[]))
    TU = dict(ty=-0.30, half=[(0, -1.92), (0.60, -1.84), (1.18, -1.10), (1.30, -0.20), (1.27, 0.85),
                              (1.08, 1.45), (0, 1.55)],
              levels=[(1.62, 1.0, 1.0, 0.0, P), (1.76, 0.99, 0.99, 0.02, K), (1.84, 0.98, 0.985, 0.03, P),
                      (2.14, 0.88, 0.90, 0.10, P)])
    ring_r = 0.95
    turret_ring(hull, TU['ty'], zd, ring_r)
    tur = turret_shell(T, TU, zd, ring_r)
    ty, tz = TU['ty'], 2.14
    cupola(tur, (-0.55, ty + 0.15, tz - 0.01), 0.32, 0.2, 6)
    machine_gun(tur, (-0.55, ty - 0.12, tz + 0.2), 0.0, 1.0)
    hatch(tur, (0.55, ty + 0.25, tz), 0.3)
    gs = tur.box((-0.78, ty - 1.12, tz + 0.15), (0.32, 0.42, 0.3), P, top=(0.92, 0.8))
    gs[0].material_index = GL
    tur.cyl(0.14, 0.3, 12, P, M=frame((0.62, ty - 0.62, tz), (0, 0, 1)), x0=0.0)
    cs = tur.box((0.62, ty - 0.62, tz + 0.4), (0.24, 0.22, 0.2), P, top=(0.95, 0.85))
    cs[0].material_index = GL
    for s in (1, -1):
        smoke_launchers(tur, (s * 1.22, ty - 1.0, 1.96), (s * 0.7, -0.7), n=4)
        storage_box(tur, (s * 1.33, ty + 0.45, 1.68), (0.18, 1.0, 0.36), latch_dir=s)
    antenna(tur, (0.85, ty + 1.12, tz), 2.0)
    antenna(tur, (-0.85, ty + 1.12, tz), 2.0)
    tur.cyl(0.02, 0.45, 6, MT, M=frame((0.0, ty + 0.95, tz), (0, 0, 1)), x0=0.0)
    tur.box((0, ty + 0.95, tz + 0.47), (0.08, 0.08, 0.06), MT)
    bustle_rack(tur, 1.0, ty + 1.42, ty + 1.95, 1.86, 0.32)
    storage_box(tur, (0.45, ty + 1.68, 1.88), (0.6, 0.42, 0.28))
    storage_box(tur, (-0.35, ty + 1.68, 1.88), (0.7, 0.42, 0.24))
    tarp_roll(tur, (0.0, ty + 1.72, 2.25), 1.5)
    # gun: 120 mm
    trunnion = (0.0, ty - 1.55, 1.84)
    gun = T.mb('gun', 'gun', 'turret')
    gun.box((0, ty - 1.98, 1.84), (0.78, 0.5, 0.52), P, top=(0.9, 0.85))
    gun.cyl(0.025, 0.25, 6, MT, M=frame((0.25, ty - 2.2, 1.78), (0, -1, 0)), x0=0.0)
    brl = T.mb('barrel', 'barrel', 'turret')
    prof = [(0, 0.2), (0.135, 0.2), (0.135, 0.62), (0.105, 0.68), (0.105, 1.68), (0.14, 1.80), (0.14, 2.12),
            (0.1, 2.24), (0.098, 3.6), (0.108, 3.62), (0.108, 3.68), (0.09, 3.70), (0.09, 5.0), (0.097, 5.02),
            (0.097, 5.12), (0.06, 5.12), (0.06, 4.98), (0, 4.98)]
    barrel_lathe(brl, trunnion, prof, 14)
    muzzle = (0.0, trunnion[1] - 5.12, trunnion[2])
    std_bones(T, H, TU, zd, ring_r, trunnion, 5.2,
              [('', (0, trunnion[1] - 0.3, trunnion[2]), muzzle, 0.35, 2.0, 1.0, [1])])
    finish_meta(T, 'main_battle_tank', -8.0, 20.0)


def build_heavy(T):
    H = dict(wi=1.22, wu=1.98,
             lower=[(-3.0, 0.5), (3.15, 0.5), (3.85, 1.22), (-3.92, 1.22)],
             upper=[(1.98, -3.92, 3.85, 1.22, 0.06), (1.98, -3.88, 3.83, 1.30, 0.06),
                    (1.86, -2.62, 3.72, 1.70, 0.12)])
    T.H = H
    rg = dict(p=0.2, tp=0.06, g=0.035, tw=0.66, tx=1.62, horn_w=0.07, horn_h=0.075,
              road=dict(r=0.36, ys=[-2.82, -1.90, -0.98, -0.06, 0.86, 1.78, 2.70]),
              front=dict(kind='idler', y=-3.62, z=0.66, r=0.31),
              rear=dict(kind='sprocket', y=3.66, z=0.74, Z=12),
              rollers=dict(r=0.12, ys=[-2.36, -0.52, 1.32]))
    T.running_gear(rg)
    zd = 1.70
    hull = hull_shell(T, H)
    era_skirts(hull, 1.98 + 0.07, 0.72, 1.22, -3.55, 3.2, 7)
    # glacis ERA
    for x in (-1.45, -0.87, -0.29, 0.29, 0.87, 1.45):
        if abs(x) < 0.4:
            continue
        p, n, ga = glacis(H, x, 0.42, 0.05)
        hull.box((0, 0, 0), (0.54, 0.62, 0.1), P, M=Mt(*p) @ Mrx(ga), top=(0.94, 0.94))
    hull_details(T, H, rg, dict(light_in=0.2, light_r=0.08, driver_x=0.0, hatch_t=0.55, hatch_r=0.28,
                                peri_t=0.86, spare_links=4, exhaust_w=1.8,
                                grilles=[(0.0, 2.45, 1.5, 1.0), (1.15, 2.3, 0.5, 1.4), (-1.15, 2.3, 0.5, 1.4)],
                                boxes=[(1.62, 3.15, (0.5, 0.7, 0.34), 1), (-1.62, 3.15, (0.5, 0.7, 0.34), -1)],
                                cans=[(0.45, 3.93, 1.0, 0.0), (-0.45, 3.93, 1.0, 0.0)]))
    TU = dict(ty=0.10, half=[(0, -2.25), (0.92, -2.25), (1.45, -1.62), (1.62, -0.45), (1.62, 1.0), (1.42, 1.72),
                             (0, 1.80)],
              levels=[(1.84, 1.0, 1.0, 0.0, P), (2.02, 1.0, 1.0, 0.0, K), (2.12, 0.995, 0.995, 0.0, P),
                      (2.55, 0.93, 0.95, 0.06, P)])
    ring_r = 1.12
    turret_ring(hull, TU['ty'], zd, ring_r)
    tur = turret_shell(T, TU, zd, ring_r)
    ty, tz = TU['ty'], 2.55
    # remote weapon station
    tur.cyl(0.25, 0.1, 14, P, M=frame((-0.6, ty + 0.55, tz), (0, 0, 1)), x0=0.0)
    tur.box((-0.6, ty + 0.55, tz + 0.28), (0.36, 0.46, 0.34), P, top=(0.95, 0.9))
    rs = tur.box((-0.38, ty + 0.4, tz + 0.36), (0.12, 0.18, 0.14), P)
    rs[0].material_index = GL
    tur.cyl(0.024, 1.2, 6, MT, M=frame((-0.62, ty + 0.3, tz + 0.3), (0, -1, 0)), x0=0.0)
    tur.box((-0.86, ty + 0.55, tz + 0.24), (0.14, 0.3, 0.2), P)
    cupola(tur, (0.65, ty + 0.5, tz - 0.01), 0.34, 0.2, 6)
    gs = tur.box((-0.95, ty - 1.45, tz + 0.18), (0.42, 0.5, 0.36), P, top=(0.92, 0.8))
    gs[0].material_index = GL
    tur.cyl(0.15, 0.4, 12, P, M=frame((0.95, ty - 0.8, tz), (0, 0, 1)), x0=0.0)
    ps = tur.box((0.95, ty - 0.8, tz + 0.5), (0.26, 0.26, 0.22), P, top=(0.95, 0.85))
    ps[0].material_index = GL
    for s in (1, -1):
        smoke_launchers(tur, (s * 1.56, ty - 1.25, 2.32), (s * 0.75, -0.66), n=5)
        storage_box(tur, (s * 1.69, ty + 0.25, 1.95), (0.15, 1.4, 0.42), latch_dir=s)
    storage_box(tur, (0, ty + 1.95, 1.95), (2.4, 0.32, 0.46))
    antenna(tur, (1.2, ty + 1.45, tz), 2.2)
    antenna(tur, (-1.2, ty + 1.45, tz), 2.2)
    # gun: 140 mm
    trunnion = (0.0, ty - 1.85, 2.14)
    gun = T.mb('gun', 'gun', 'turret')
    gun.box((0, ty - 2.3, 2.14), (1.0, 0.62, 0.62), P, top=(0.9, 0.85))
    gun.cyl(0.028, 0.25, 6, MT, M=frame((0.33, ty - 2.6, 2.05), (0, -1, 0)), x0=0.0)
    brl = T.mb('barrel', 'barrel', 'turret')
    prof = [(0, 0.3), (0.16, 0.3), (0.16, 0.72), (0.13, 0.78), (0.13, 2.2), (0.17, 2.32), (0.17, 2.75),
            (0.125, 2.86), (0.118, 4.4), (0.13, 4.42), (0.13, 4.5), (0.112, 4.52), (0.11, 5.55), (0.17, 5.58),
            (0.17, 5.78), (0.15, 5.80), (0.15, 5.86), (0.175, 5.88), (0.175, 6.10), (0.08, 6.10), (0.08, 5.95),
            (0, 5.95)]
    barrel_lathe(brl, trunnion, prof, 16)
    for x in (0.18, -0.18):
        brl.box((x, trunnion[1] - 5.69, trunnion[2]), (0.06, 0.12, 0.16), MT)
    muzzle = (0.0, trunnion[1] - 6.10, trunnion[2])
    std_bones(T, H, TU, zd, ring_r, trunnion, 6.2,
              [('', (0, trunnion[1] - 0.4, trunnion[2]), muzzle, 0.45, 2.6, 1.4, [1])])
    finish_meta(T, 'heavy_tank', -6.0, 15.0)


def build_artillery(T):
    H = dict(wi=1.09, wu=1.68,
             lower=[(-2.85, 0.42), (2.80, 0.42), (3.40, 1.03), (-3.62, 1.03)],
             upper=[(1.68, -3.62, 3.40, 1.03, 0.05), (1.68, -3.56, 3.38, 1.09, 0.05),
                    (1.58, -2.55, 3.32, 1.48, 0.08)])
    T.H = H
    rg = dict(p=0.17, tp=0.05, g=0.03, tw=0.50, tx=1.40, horn_w=0.06, horn_h=0.06,
              road=dict(r=0.30, ys=[-2.58, -1.74, -0.90, -0.06, 0.78, 1.62, 2.46]),
              front=dict(kind='sprocket', y=-3.34, z=0.62, Z=12),
              rear=dict(kind='idler', y=3.16, z=0.55, r=0.26),
              rollers=dict(r=0.10, ys=[-2.16, -0.48, 1.20]))
    T.running_gear(rg)
    zd = 1.48
    hull = hull_shell(T, H)
    hull_details(T, H, rg, dict(light_in=0.22, driver_x=0.75, hatch_t=0.6, hatch_r=0.26, peri_t=0.9,
                                exhaust=False, spare_links=0,
                                grilles=[(-0.55, -1.75, 0.9, 1.2), (0.55, -1.1, 0.6, 0.5)],
                                boxes=[(1.3, -1.9, (0.4, 0.8, 0.28), 1)],
                                cans=[(0.45, 3.48, 0.95, 0.0), (-0.45, 3.48, 0.95, 0.0)]))
    hull.box((-1.74, -1.55, 1.27), (0.12, 0.6, 0.22), MT)
    for i in range(5):
        hull.box((-1.81, -1.79 + i * 0.12, 1.27), (0.03, 0.03, 0.22), P)
    TU = dict(ty=1.05, half=[(0, -1.72), (1.25, -1.72), (1.50, -1.38), (1.55, 1.55), (1.42, 2.15), (0, 2.2)],
              levels=[(1.60, 1.0, 1.0, 0.0, P), (2.42, 1.0, 1.0, 0.0, K), (2.52, 1.0, 1.0, 0.0, P),
                      (2.80, 0.95, 0.96, 0.04, P)])
    ring_r = 1.05
    turret_ring(hull, TU['ty'], zd, ring_r)
    tur = turret_shell(T, TU, zd, ring_r)
    ty, tz = TU['ty'], 2.80
    cupola(tur, (-0.8, ty + 0.55, tz - 0.01), 0.32, 0.2, 6)
    machine_gun(tur, (-0.8, ty + 0.28, tz + 0.2), 0.0, 1.0)
    hatch(tur, (0.8, ty + 0.75, tz), 0.32)
    for x in (-0.2, 0.25):
        tur.box((x, ty + 1.45, tz + 0.06), (0.3, 0.3, 0.12), P)
    door = tur.box((0, ty + 2.22, 2.05), (1.0, 0.05, 1.05), P)
    tur.box((0.38, ty + 2.26, 2.05), (0.04, 0.04, 0.2), MT)
    for s in (1, -1):
        tur.box((s * 1.6, ty + 0.5, 2.0), (0.12, 1.8, 0.55), P)
        for k in range(4):
            tur.box((s * 1.67, ty - 0.2 + k * 0.46, 2.0), (0.03, 0.04, 0.5), MT)
        smoke_launchers(tur, (s * 1.42, ty - 1.62, 2.55), (s * 0.6, -0.8), n=4)
    antenna(tur, (1.2, ty + 1.95, tz), 2.2)
    periscope(tur, (0.75, ty - 1.4, tz - 0.01), 0.0, 0.2, 0.12, 0.12)
    # gun: 155 mm howitzer
    trunnion = (0.0, ty - 1.45, 2.22)
    gun = T.mb('gun', 'gun', 'turret')
    gun.box((0, ty - 1.73, 2.22), (0.95, 0.5, 0.75), P, top=(0.92, 0.9))
    for x in (0.2, -0.2):
        gun.cyl(0.065, 0.95, 10, P, M=frame((x, trunnion[1] - 0.3, 2.43), (0, -1, 0)), x0=0.0)
    brl = T.mb('barrel', 'barrel', 'turret')
    prof = [(0, 0.4), (0.15, 0.4), (0.15, 0.95), (0.12, 1.0), (0.115, 3.0), (0.145, 3.1), (0.145, 3.65),
            (0.11, 3.75), (0.1, 6.7), (0.19, 6.72), (0.19, 6.98), (0.13, 7.0), (0.13, 7.06), (0.19, 7.08),
            (0.19, 7.36), (0.09, 7.36), (0.09, 7.2), (0, 7.2)]
    barrel_lathe(brl, trunnion, prof, 16)
    for x in (0.2, -0.2):
        brl.box((x, trunnion[1] - 6.85, trunnion[2]), (0.05, 0.2, 0.2), MT)
        brl.box((x, trunnion[1] - 7.22, trunnion[2]), (0.05, 0.2, 0.2), MT)
    muzzle = (0.0, trunnion[1] - 7.36, trunnion[2])
    std_bones(T, H, TU, zd, ring_r, trunnion, 7.4,
              [('', (0, trunnion[1] - 0.5, trunnion[2]), muzzle, 0.75, 3.0, 1.7, [1])])
    finish_meta(T, 'self_propelled_artillery', -3.0, 70.0)


def build_antiair(T):
    H = dict(wi=1.08, wu=1.65,
             lower=[(-2.48, 0.44), (2.55, 0.44), (3.12, 1.03), (-3.18, 1.03)],
             upper=[(1.65, -3.18, 3.12, 1.03, 0.05), (1.65, -3.14, 3.10, 1.09, 0.05),
                    (1.55, -2.10, 2.98, 1.42, 0.08)])
    T.H = H
    rg = dict(p=0.17, tp=0.05, g=0.03, tw=0.48, tx=1.38, horn_w=0.055, horn_h=0.06,
              road=dict(r=0.32, ys=[-2.20, -1.32, -0.44, 0.44, 1.32, 2.20]),
              front=dict(kind='idler', y=-2.90, z=0.56, r=0.27),
              rear=dict(kind='sprocket', y=2.98, z=0.62, Z=12),
              rollers=dict(r=0.10, ys=[-1.76, 0.0, 1.76]))
    T.running_gear(rg)
    zd = 1.42
    hull = hull_shell(T, H)
    skirts(hull, 1.65 + 0.025, 0.70, 1.03, -2.9, 2.6, 4)
    hull_details(T, H, rg, dict(light_in=0.24, driver_x=0.55, hatch_t=0.5, hatch_r=0.25, peri_t=0.82,
                                spare_links=0, exhaust_w=1.3,
                                grilles=[(0.0, 2.2, 1.1, 0.8), (0.95, 2.05, 0.4, 1.05), (-0.95, 2.05, 0.4, 1.05)],
                                boxes=[(-0.85, -1.75, (0.5, 0.55, 0.26), -1)],
                                cans=[(0.4, 3.23, 0.86, 0.0), (-0.4, 3.23, 0.86, 0.0)]))
    TU = dict(ty=0.35, half=[(0, -1.30), (0.80, -1.30), (1.12, -0.92), (1.18, 0.90), (1.0, 1.36), (0, 1.42)],
              levels=[(1.52, 1.0, 1.0, 0.0, P), (1.80, 0.99, 0.99, 0.01, K), (1.88, 0.985, 0.985, 0.015, P),
                      (2.25, 0.9, 0.92, 0.06, P)])
    ring_r = 0.95
    turret_ring(hull, TU['ty'], zd, ring_r)
    tur = turret_shell(T, TU, zd, ring_r)
    ty, tz = TU['ty'], 2.25
    hatch(tur, (0.45, ty + 0.35, tz), 0.26)
    hatch(tur, (-0.45, ty + 0.35, tz), 0.26)
    for x in (-0.25, 0.25):
        periscope(tur, (x, ty - 0.82, tz - 0.01), 0.0, 0.14, 0.08, 0.08)
    for s in (1, -1):
        smoke_launchers(tur, (s * 0.88, ty - 1.08, 2.02), (s * 0.55, -0.83), n=3)
    antenna(tur, (0.75, ty + 1.08, tz), 1.8)
    antenna(tur, (-0.75, ty + 1.08, tz), 1.8)
    # tracking radar (fixed to the turret front)
    tur.box((0, ty - 1.36, 1.95), (0.3, 0.16, 0.3), P)
    tur.lathe([(0, 0.0), (0.3, 0.0), (0.33, 0.07), (0.27, 0.13), (0, 0.15)], 16, P, mats=[P, P, P, MT],
              M=frame((0, ty - 1.44, 1.95), (0, -1, 0)))
    # search radar mast + rotating antenna (radar bone)
    mast_y = ty + 1.0
    tur.cyl(0.08, 0.35, 10, P, M=frame((0, mast_y, tz), (0, 0, 1)), x0=0.0)
    rad = T.mb('radar', 'radar', 'turret')
    rad.cyl(0.11, 0.08, 10, MT, M=frame((0, mast_y, tz + 0.35), (0, 0, 1)), x0=0.0)
    rad.box((0, mast_y, tz + 0.5), (0.12, 0.12, 0.25), P)
    rad.box((0, mast_y + 0.02, tz + 0.82), (1.55, 0.12, 0.5), P, M=None, top=(0.82, 0.8))
    rad.box((0, mast_y - 0.32, tz + 0.72), (0.08, 0.08, 0.08), MT)
    beam(rad, (0, mast_y - 0.05, tz + 0.58), (0, mast_y - 0.32, tz + 0.72), 0.03, 0.03, MT)
    # twin 35 mm guns on external cradles
    trunnion = (0.0, ty - 0.25, 2.0)
    gun = T.mb('gun', 'gun', 'turret')
    gun.cyl(0.11, 2.6, 12, MT, M=frame(trunnion, (1, 0, 0)))
    barrels = []
    for sfx, s in (('_L', 1), ('_R', -1)):
        x = s * 1.45
        gun.box((x, trunnion[1] - 0.42, 2.0), (0.32, 1.36, 0.44), P, top=(0.92, 0.97))
        gun.box((x + s * 0.2, trunnion[1] - 0.3, 2.05), (0.08, 0.6, 0.22), P)
        gun.cyl(0.075, 0.25, 10, P, M=frame((x, trunnion[1] - 1.1, 2.0), (0, -1, 0)), x0=0.0)
        b = T.mb('barrel' + sfx, 'barrel' + sfx, 'turret')
        prof = [(0, 1.0), (0.062, 1.0), (0.062, 1.3), (0.048, 1.34), (0.046, 3.5), (0.072, 3.52), (0.072, 3.86),
                (0.035, 3.86), (0.035, 3.7), (0, 3.7)]
        barrel_lathe(b, (x, trunnion[1], 2.0), prof, 10)
        muzzle = (x, trunnion[1] - 3.86, 2.0)
        barrels.append((sfx, (x, trunnion[1] - 1.1, 2.0), muzzle, 0.15, 1.0, 0.5,
                        [1, 5, 9, 13] if s == 1 else [3, 7, 11, 15]))
    std_bones(T, H, TU, zd, ring_r, trunnion, 3.9, barrels)
    T.bone('radar', (0, mast_y, tz + 0.35), (0, mast_y, tz + 0.85), parent='turret', z=(0, -1, 0),
           shape='circle', sxyz=(0.9, 0.9, 0.9), color='THEME05',
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    finish_meta(T, 'anti_air', -5.0, 85.0, dict(radar_bone='radar'))


DESIGNS = {
    'Scout': (build_scout, dict(pattern='blotch', scale=0.42, distort=0.6, dust=0.8,
                                stops=[(0.0, srgb('#b49b70')), (0.53, srgb('#8a6844')), (0.64, srgb('#6b6948'))],
                                mark=srgb('#202020'), dust_col=srgb('#a08a66'))),
    'Medium': (build_medium, dict(pattern='blotch', scale=0.5, distort=0.55, dust=0.7,
                                  stops=[(0.0, srgb('#4d5a34')), (0.46, srgb('#2e3a22')), (0.56, srgb('#5a4831')),
                                         (0.66, srgb('#1d1d18'))], mark=srgb('#d6d6cc'))),
    'Heavy': (build_heavy, dict(pattern='splinter', scale=0.55, dust=0.6,
                                stops=[(0.0, srgb('#737980')), (0.40, srgb('#4b5057')), (0.65, srgb('#2c3034')),
                                       (0.85, srgb('#8f9399'))], mark=srgb('#c9a227'), dust_col=srgb('#7d7468'))),
    'Artillery': (build_artillery, dict(pattern='blotch', scale=0.38, distort=0.4, dust=0.85,
                                        stops=[(0.0, srgb('#d3d5cf')), (0.62, srgb('#9aa09c')), (0.72, srgb('#5d6360'))],
                                        mark=srgb('#8a2a1e'), dust_col=srgb('#867461'))),
    'AntiAir': (build_antiair, dict(pattern='stripe', scale=0.55, dust=0.75,
                                    stops=[(0.0, srgb('#6e6a43')), (0.55, srgb('#a8925e')), (0.68, srgb('#3a3524'))],
                                    mark=srgb('#d8d8d0'))),
}
LINEUP = {'Scout': -16.0, 'Medium': -8.0, 'Heavy': 0.0, 'Artillery': 8.5, 'AntiAir': 17.0}


def build_geometry(name):
    fn, cfg = DESIGNS[name]
    T = Tank(name, (LINEUP[name], 0.0, 0.0), cfg)
    fn(T)
    T.finish_parts()
    return T


def make_track_material(size=512):
    mat = bpy.data.materials.get('MAT_Track')
    if mat:
        return mat
    setup_cycles_gpu()
    sc = bpy.context.scene
    sc.cycles.samples = 48
    mm = master_material('MM_Track', 'track', dict(bevel=0.008, ao_dist=0.12, dust=0.8, chips=0.3))
    tpl = link_template(0.18, 0.05, 0.03, 0.55, 0.06, 0.065)
    me = mesh_from_template('TK_LinkBake', tpl, [mm], lambda i: [tuple(v) for v in tpl['verts']], 1)
    ob = bpy.data.objects.new('TK_LinkBake', me)
    sc.collection.objects.link(ob)
    ob.location = (0, -60, 0)
    imgs = {'COLOR': new_image('T_Track_BaseColor', size, (0.1, 0.1, 0.1), False),
            'ORM': new_image('T_Track_ORM', size, (1.0, 0.6, 0.6), True),
            'NORMAL': new_image('T_Track_Normal', size, (0.5, 0.5, 1.0), True)}
    vl = bpy.context.view_layer
    hidden = [o for o in sc.objects if o.type == 'MESH' and o is not ob and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    try:
        for o in vl.objects:
            o.select_set(False)
        ob.select_set(True)
        vl.objects.active = ob
        for mode, img in imgs.items():
            set_bake_mode(mm, mode, img)
            if mode == 'NORMAL':
                bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8, margin_type='EXTEND',
                                    use_clear=False, target='IMAGE_TEXTURES')
            else:
                bpy.ops.object.bake(type='EMIT', margin=8, margin_type='EXTEND', use_clear=False,
                                    target='IMAGE_TEXTURES')
    finally:
        for o in hidden:
            o.hide_render = False
    for img in imgs.values():
        save_image(img, f'{img.name}.png')
    mat = final_material('MAT_Track', imgs['COLOR'], imgs['ORM'], imgs['NORMAL'])
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bpy.data.materials.remove(mm)
    return mat


def tri_ngons(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ng, quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me)
    bm.free()


def reset_pose(T):
    for pb in T.rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def export_and_check(T):
    T.rig.hide_set(False)
    reset_pose(T)
    path = os.path.join(GLB_DIR, f'Tank_{T.name}.glb')
    export_tank(T, path)
    w = glb_postprocess(path)
    s = glb_summary(path)
    return dict(kb=s['size_kb'], joints=s['skins'], anims={k: v for k, v in s['anims'].items()},
                morph_ok=bool(w) and abs(w[0] - EPS) < 1e-3 and abs(w[-1] - (1 - EPS)) < 1e-3)


def full_build(name):
    t0 = time.time()
    T = build_geometry(name)
    T.build_tracks(make_track_material())
    T.build_flash(flash_material())
    T.build_rig()
    bad = T.build_drivers()
    clips = T.build_clips()
    T.unwrap()
    T.bake(2048, 16)
    T.assemble()
    tri_ngons(T.body.data)
    res = export_and_check(T)
    res.update(stats=T.stats(), bad_drivers=bad, secs=round(time.time() - t0, 1))
    return T, res
