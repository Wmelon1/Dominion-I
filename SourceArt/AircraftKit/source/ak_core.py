# Aircraft Kit builder - aircraft geometry, paint schemes, rig, clips and extras.
# Requires TankKit/source/tk_core.py + tk_tank.py to be exec'd first (shared mesh/material/bake code).
# Coordinates: X = left(+)/right(-), Y = back(+)/front(-), Z = up. Origin = aircraft reference point (CG).

AIR_DIR = globals().get('AIR_DIR')
TEX_DIR = os.path.join(AIR_DIR, 'textures')
GLB_DIR = os.path.join(AIR_DIR, 'glb')


# ------------------------------------------------------------------------------ fuselage
def _cr(a, b, c, d, t):
    return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3)


def smooth_stations(st, sub=3):
    out, m = [], len(st)
    for i in range(m - 1):
        p0, p1, p2, p3 = st[max(i - 1, 0)], st[i], st[i + 1], st[min(i + 2, m - 1)]
        for k in range(sub):
            t = k / sub
            v = [_cr(p0[j], p1[j], p2[j], p3[j], t) for j in range(6)]
            v[2:5] = [max(x, 0.004) for x in v[2:5]]
            v[5] = max(v[5], 1.6)
            out.append(tuple(v))
    out.append(tuple(st[-1]))
    return out


def fuse_ring(y, zc, hw, ht, hb, n, N=24, xc=0.0, top_only=False, a0=0.0, a1=math.pi):
    pts = []
    e = 2.0 / n
    cnt = N + 1 if top_only else N
    for i in range(cnt):
        a = (a0 + (a1 - a0) * i / N) if top_only else TAU * i / N
        c, s = math.cos(a), math.sin(a)
        x = hw * math.copysign(abs(c) ** e, c)
        z = (ht if s >= 0 else hb) * math.copysign(abs(s) ** e, s)
        pts.append((xc + x, y, zc + z))
    return pts


def fuselage(mb, stations, mat=P, N=24, sub=3, xc=0.0, cap0=True, cap1=True):
    st = smooth_stations(stations, sub)
    mb.loft([fuse_ring(*s[:6], N=N, xc=xc) for s in st], mat, cap0=cap0, cap1=cap1)
    return st


def fuse_at(st, y):
    """interpolated (zc, hw, ht, hb, n) of a smoothed station list at y."""
    if y <= st[0][0]:
        return st[0][1:]
    for a, b in zip(st, st[1:]):
        if y <= b[0]:
            f = (y - a[0]) / max(b[0] - a[0], 1e-9)
            return tuple(a[i] + (b[i] - a[i]) * f for i in range(1, 6))
    return st[-1][1:]


# ------------------------------------------------------------------------------ lifting surfaces
def naca_t(s, t):
    s = min(max(s, 0.0), 1.0)
    return 5 * t * (0.2969 * math.sqrt(s) - 0.1260 * s - 0.3516 * s * s + 0.2843 * s ** 3 - 0.1015 * s ** 4) + 0.0012


def airfoil_poly(s0, s1, t, npts=9, camber=0.0):
    ss = [s0 + (s1 - s0) * (1 - math.cos(math.pi * i / (npts - 1))) / 2 for i in range(npts)]

    def yc(s):
        return camber * (1 - (2 * s - 1) ** 2)
    top = [(s, yc(s) + naca_t(s, t)) for s in ss]
    bot = [(s, yc(s) - naca_t(s, t)) for s in reversed(ss)]
    if s0 <= 1e-6:
        top[0] = (0.0, yc(0.0))
        bot = bot[:-1]
    return top + bot


def _sec_point(sp, y, h, vertical, mirror, M):
    p = Vector((h, y, sp)) if vertical else Vector((-sp if mirror else sp, y, h))
    return (M @ p) if M is not None else p


def surface(mb, secs, s0=0.0, s1=1.0, npts=9, vertical=False, mat=P, cap0=True, cap1=True, camber=0.0,
            mirror=False, M=None):
    rings = []
    for (sp, yle, h, c, t, tw) in secs:
        ca, sa = math.cos(math.radians(tw)), math.sin(math.radians(tw))
        ring = []
        for s, th in airfoil_poly(s0, s1, t, npts, camber):
            dy, dh = (s - 0.25) * c, th * c
            dy2 = dy * ca + dh * sa
            dh2 = -dy * sa + dh * ca
            ring.append(_sec_point(sp, yle + 0.25 * c + dy2, h + dh2, vertical, mirror, M))
        rings.append(ring)
    mb.loft(rings, mat, cap0=cap0, cap1=cap1)


class Planform:
    def __init__(self, keys):
        self.k = sorted(keys, key=lambda k: k[0])
        self.span0, self.span1 = self.k[0][0], self.k[-1][0]

    def at(self, s):
        k = self.k
        if s <= k[0][0]:
            return (s,) + tuple(k[0][1:])
        for a, b in zip(k, k[1:]):
            if s <= b[0]:
                f = (s - a[0]) / max(b[0] - a[0], 1e-9)
                return (s,) + tuple(a[i] + (b[i] - a[i]) * f for i in range(1, 6))
        return (s,) + tuple(k[-1][1:])

    def secs(self, a, b):
        pts = [a] + [kk[0] for kk in self.k if a + 1e-4 < kk[0] < b - 1e-4] + [b]
        return [self.at(s) for s in pts]


def lifting(T, pf, key, bone='body', sides=('L', 'R'), ctrl=None, hinge=0.72, vertical=False, cap_root=True,
            npts=9, camber=0.0, mat=P, M=None, ctrl_dir='out', ctrl_max=20.0, axis='roll', pivot=0.4,
            group='hull'):
    """wing / tail with an optional control surface. ctrl=(span_a, span_b, bone_basename).
    hinge=0 makes the whole span section move (stabilator) around `pivot` chord."""
    s0, s1 = pf.span0, pf.span1
    for side in sides:
        mir = side == 'R'
        mb = T.mb(key, bone, group)
        kw = dict(npts=npts, vertical=vertical, mat=mat, camber=camber, mirror=mir, M=M)
        if ctrl is None:
            surface(mb, pf.secs(s0, s1), cap0=cap_root, cap1=True, **kw)
            continue
        a, b, cname = ctrl
        g = 0.012
        if a > s0 + 1e-3:
            surface(mb, pf.secs(s0, a), cap0=cap_root, cap1=True, **kw)
        if hinge > 0:
            surface(mb, pf.secs(a, b), s1=hinge, cap0=True, cap1=True, **kw)
        if b < s1 - 1e-3:
            surface(mb, pf.secs(b, s1), cap0=True, cap1=True, **kw)
        bn = f'{cname}_{side}' if side else cname
        cm = T.mb(bn, bn, group)
        surface(cm, pf.secs(a + g, b - g), s0=(hinge + 0.006) if hinge > 0 else 0.0, s1=1.0,
                cap0=True, cap1=True, **kw)
        frac = hinge if hinge > 0 else pivot

        def hp(sp):
            _, yle, h, c, t, tw = pf.at(sp)
            return _sec_point(sp, yle + frac * c, h, vertical, mir, M)
        pa, pb = hp(a + g), hp(b - g)
        if ctrl_dir == '+x' and (pb - pa).x < 0:
            pa, pb = pb, pa
        z = (0, -1, 0) if vertical else (0, 0, 1)
        T.bone(bn, pa, pb, parent='body', z=z, shape='box', sxyz=(0.04, (pb - pa).length / 2, 0.04),
               color='THEME03' if axis == 'pitch' else ('THEME04' if axis == 'yaw' else 'THEME01'),
               locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
        T.controls[bn] = dict(axis=axis, max=ctrl_max)


# ------------------------------------------------------------------------------ parts
def propeller(T, hub, R, nb, chord, pitch, spinner=(0.12, 0.35), blade_mat=MT, spin_mat=P, key='prop'):
    mb = T.mb(key, 'prop', 'hull')
    hub = Vector(hub)
    ea = Vector((0, -1, 0))
    for k in range(nb):
        ang = k * TAU / nb + math.pi / 2
        er = Vector((math.cos(ang), 0, math.sin(ang)))
        et = Vector((-math.sin(ang), 0, math.cos(ang)))
        rings = []
        rs = [0.1, 0.22, 0.4, 0.6, 0.78, 0.92, 1.0]
        for f in rs:
            r = f * R
            c = chord * (0.55 + 0.9 * math.sin(math.pi * min(f, 0.97) ** 0.8) * (1.15 - f)) if f < 1.0 else chord * 0.35
            beta = math.atan2(pitch, TAU * max(r, 0.05))
            cd = et * math.cos(beta) + ea * math.sin(beta)
            nd = ea * math.cos(beta) - et * math.sin(beta)
            t = 0.12 if f > 0.2 else 0.3
            ring = [hub + er * r + cd * ((s - 0.3) * c) + nd * (th * c) for s, th in airfoil_poly(0, 1, t, 7, 0.02)]
            rings.append(ring)
        mb.loft(rings, blade_mat)
    sr, sl = spinner
    mb.lathe([(0, -0.02), (sr, -0.02), (sr, 0.08 * sl), (sr * 0.92, 0.4 * sl), (sr * 0.6, 0.8 * sl), (0, sl)], 16,
             spin_mat, M=frame(hub + Vector((0, 0.06, 0)), (0, -1, 0)))
    T.prop = dict(hub=tuple(hub), R=R, blades=nb)


def radial_engine(mb, c, n, r_out, cyl_r=0.055, mat=MT, depth=0.0):
    c = Vector(c)
    mb.lathe([(0, -0.08), (r_out * 0.32, -0.08), (r_out * 0.34, 0.06), (r_out * 0.22, 0.12), (0, 0.13)], 16, mat,
             M=frame(c, (0, -1, 0)))
    for k in range(n):
        a = k * TAU / n + math.pi / 2
        d = Vector((math.cos(a), 0, math.sin(a)))
        o = c + d * (r_out * 0.3)
        mb.lathe([(0, 0), (cyl_r, 0), (cyl_r, 0.02)] +
                 [p for i in range(4) for p in ((cyl_r * 1.35, 0.03 + i * 0.045), (cyl_r * 1.35, 0.05 + i * 0.045),
                                                (cyl_r, 0.055 + i * 0.045))] +
                 [(cyl_r * 1.1, r_out * 0.68), (cyl_r * 0.9, r_out * 0.72), (0, r_out * 0.72)], 8, mat, M=frame(o, d))
        mb.cyl(0.012, r_out * 0.6, 5, MT, M=frame(o + Vector((0, 0.05, 0)), d), x0=0.0)


def wheel(T, key, bone, center, r, w, parent, spat=False, hub_mat=WP):
    me_mb = MB()
    a = w / 2
    me_mb.lathe([(0, a + 0.02), (0.3 * r, a + 0.02), (0.38 * r, a - 0.01), (0.62 * r, a - 0.03), (0.7 * r, a),
                 (0.92 * r, a), (r, a * 0.4), (r, -a * 0.4), (0.92 * r, -a), (0.7 * r, -a), (0.3 * r, -a + 0.01),
                 (0, -a)], 16, mats=[WM, WM, hub_mat, hub_mat, RB, RB, RB, RB, RB, hub_mat, hub_mat])
    me = me_mb.to_mesh(f'{T.name}_{key}', T.mat_list, sharp=40)
    T.temp_meshes.append(me)
    T.instance(me, key, bone, center, 0.0, 'turret' if parent.startswith('gear') else 'hull')
    c = Vector(center)
    T.bone(bone, c, c + Vector((0.2, 0, 0)), parent=parent, coll='Gear', shape='circle', sxyz=(r * 1.1,) * 3,
           color='THEME07', locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    T.wheels[bone] = r


def strut(mb, a, b, w=0.05, d=0.11, mat=P):
    beam(mb, a, b, w, d, mat)


def wire(mb, a, b):
    beam(mb, a, b, 0.012, 0.012, MT)


def pilot(mb, c, helmet_mat=RB):
    c = Vector(c)
    mb.lathe([(0, -0.11), (0.08, -0.1), (0.11, 0.0), (0.1, 0.08), (0.06, 0.13), (0, 0.14)], 12, RB,
             M=frame(c + Vector((0, 0, 0.0)), (0, 0, 1)))
    mb.lathe([(0, 0.0), (0.125, 0.0), (0.125, 0.06), (0.1, 0.13), (0.05, 0.16), (0, 0.165)], 12, helmet_mat,
             M=frame(c + Vector((0, 0, -0.01)), (0, 0, 1)))
    for s in (1, -1):
        g = mb.box((s * 0.045, c.y - 0.1, c.z + 0.04), (0.07, 0.04, 0.05), MT)
        g[0].material_index = GL
    mb.box((c.x, c.y + 0.03, c.z - 0.28), (0.42, 0.26, 0.3), RB, top=(0.75, 0.9))
    mb.box((c.x, c.y + 0.2, c.z - 0.2), (0.4, 0.06, 0.55), MT)


def gun_barrel(mb, base, L, r=0.02, jacket=True):
    base = Vector(base)
    if jacket:
        mb.cyl(r * 1.9, L * 0.7, 10, MT, M=frame(base, (0, -1, 0)), x0=0.0)
    mb.cyl(r, L, 6, MT, M=frame(base, (0, -1, 0)), x0=0.0)
    mb.box((base.x, base.y + 0.15, base.z), (r * 4, 0.3, r * 4), MT)


def missile(mb, nose, L=2.9, r=0.085):
    nose = Vector(nose)
    M = frame(nose + Vector((0, L, 0)), (0, -1, 0))
    mb.lathe([(0, 0), (r, 0), (r, L * 0.82), (r * 0.7, L * 0.92), (0, L)], 10, P, mats=[MT, P, K, GL], M=M)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        d = Vector((math.cos(a), 0, math.sin(a)))
        for yy, sz in ((L - 0.15, 0.17), (0.55, 0.12)):
            c = nose + Vector((0, yy, 0)) + d * (r + sz / 2)
            mb.box((0, 0, 0), (sz, 0.28 if yy > 1 else 0.18, 0.012), P,
                   M=Mt(*c) @ Matrix.Rotation(-a, 4, 'Y'))


# ------------------------------------------------------------------------------ paint scheme nodes
def _mask_box(nt, Ps, Ns, bx, origin):
    x0, x1, y0, y1, z0, z1, nz = bx
    ox, oy, oz = origin
    e = 0.004
    m = nt.math('MULTIPLY', nt.mr(Ps['X'], x0 + ox - e, x0 + ox), nt.mr(Ps['X'], x1 + ox, x1 + ox + e, 1, 0))
    m = nt.math('MULTIPLY', m, nt.math('MULTIPLY', nt.mr(Ps['Y'], y0 + oy - e, y0 + oy),
                                       nt.mr(Ps['Y'], y1 + oy, y1 + oy + e, 1, 0)))
    m = nt.math('MULTIPLY', m, nt.math('MULTIPLY', nt.mr(Ps['Z'], z0 + oz - e, z0 + oz),
                                       nt.mr(Ps['Z'], z1 + oz, z1 + oz + e, 1, 0)))
    if nz is not None:
        m = nt.math('MULTIPLY', m, nt.mr(Ns['Z'], nz - 0.05, nz))
    return m


def air_base(nt, Pv, Nrm, Ns, cfg):
    o = cfg['origin']
    Ps = nt.sep(Pv)
    if cfg.get('pattern'):
        top = camo_pattern(nt, Pv, cfg)
    else:
        top = nt.mix(nt.math('MULTIPLY', nt.mr(nt.noise(Pv, 0.8, 3.0, 0.5), 0.3, 0.7), 0.25), cfg['top'],
                     cfg.get('top2', cfg['top']))
    split = nt.mr(Ns['Z'], cfg.get('split', -0.3) - 0.06, cfg.get('split', -0.3))
    col = nt.mix(split, cfg['under'], top)
    for bx, c in cfg.get('boxes', []):
        col = nt.mix(_mask_box(nt, Ps, Ns, bx, o), col, c)
    for (cx, cy, cz, ax, r, depth, rings) in cfg.get('insignia', []):
        C = (cx + o[0], cy + o[1], cz + o[2])
        d = nt.vmath('SUBTRACT', Pv, C)
        along = nt.vmath('DOT_PRODUCT', d, ax)
        perp = nt.vmath('LENGTH', nt.vmath('SUBTRACT', d, nt.vmath('SCALE', ax, scale=along)))
        rr = nt.math('DIVIDE', perp, r)
        inside = nt.math('MULTIPLY', nt.mr(rr, 1.0, 0.985), nt.mr(nt.math('ABSOLUTE', along), depth, depth * 0.9))
        col = nt.mix(inside, col, nt.ramp(rr, rings))
    return col


def _line(nt, v, spacing, width=0.012):
    f = nt.math('FRACT', nt.math('DIVIDE', v, spacing))
    return nt.mr(nt.math('ABSOLUTE', nt.math('SUBTRACT', f, 0.5)), 0.5 - width, 0.5)


def panel_height(nt, Pv, cfg):
    Ps = nt.sep(Pv)
    sp = cfg.get('panel', 0.9)
    g = nt.math('MAXIMUM', _line(nt, Ps['Y'], sp * 1.3, 0.008), _line(nt, Ps['X'], sp, 0.008))
    g = nt.math('MAXIMUM', g, _line(nt, Ps['Z'], sp * 0.7, 0.01))
    rivet = nt.mr(nt.noise(Pv, 160.0, 0.0, 0.5), 0.72, 0.78)
    return nt.math('SUBTRACT', 0.0, nt.math('ADD', nt.math('MULTIPLY', g, 1.0), nt.math('MULTIPLY', rivet, 0.15)))


def rib_height(nt, Pv, cfg):
    Ps = nt.sep(Pv)
    ribs = _line(nt, Ps['X'], cfg.get('rib', 0.3), 0.03)
    str_ = _line(nt, Ps['Y'], cfg.get('rib', 0.3) * 1.6, 0.02)
    return nt.math('ADD', nt.math('MULTIPLY', ribs, 0.8), nt.math('MULTIPLY', str_, 0.25))


# ------------------------------------------------------------------------------ extra images / materials
def blur_material():
    mat = bpy.data.materials.get('MAT_PropBlur')
    if mat:
        return mat
    w = h = 256
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = (xx - 127.5) / 127.5, (yy - 127.5) / 127.5
    r = np.sqrt(x * x + y * y)
    a = np.clip((1 - r) * 40, 0, 1) * (0.18 + 0.25 * np.exp(-((r - 0.93) / 0.04) ** 2) + 0.05 * np.cos(r * 60) ** 2)
    a *= np.clip((r - 0.12) * 20, 0, 1)
    px = np.zeros((h, w, 4), np.float32)
    px[..., 0], px[..., 1], px[..., 2] = 0.08, 0.07, 0.06
    tip = np.exp(-((r - 0.95) / 0.03) ** 2)
    px[..., 0] += tip * 0.8
    px[..., 1] += tip * 0.7
    px[..., 3] = np.clip(a, 0, 1)
    img = bpy.data.images.new('T_PropBlur', w, h, alpha=True)
    img.pixels.foreach_set(px.ravel())
    save_image(img, 'T_PropBlur.png')
    mat = bpy.data.materials.new('MAT_PropBlur')
    nt = NT(mat)
    ti = nt.n('ShaderNodeTexImage', image=img)
    b = nt.n('ShaderNodeBsdfPrincipled')
    out = nt.n('ShaderNodeOutputMaterial')
    nt.L.new(ti.outputs['Color'], b.inputs['Base Color'])
    nt.L.new(ti.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.7
    nt.L.new(b.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    return mat


def flame_material():
    mat = bpy.data.materials.get('MAT_Afterburner')
    if mat:
        return mat
    w, h = 512, 256
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    px = np.zeros((h, w, 4), np.float32)
    u = xx[:, :256] / 255.0
    v = (yy[:, :256] / 255.0) * 2 - 1
    width = 0.55 * (1 - u) ** 0.6 + 0.05
    core = np.exp(-((v / width) ** 2) * 2.5) * (1 - u) ** 1.1
    diamonds = 0.55 + 0.45 * np.cos(u * 34) ** 6 * (1 - u)
    I1 = core * diamonds
    sx, sy = (xx[:, 256:] - 384) / 128.0, (yy[:, 256:] - 128) / 128.0
    r = np.sqrt(sx ** 2 + sy ** 2)
    I2 = np.exp(-(r / 0.6) ** 2) * 0.9
    I = np.clip(np.concatenate([I1, I2], axis=1), 0, 1)
    t = I[..., None]
    hot = np.array([0.85, 0.9, 1.0])
    mid = np.array([1.0, 0.62, 0.25])
    edge = np.array([0.9, 0.25, 0.05])
    px[..., :3] = np.where(t > 0.55, mid + (hot - mid) * ((t - 0.55) / 0.45), edge + (mid - edge) * (t / 0.55))
    px[..., 3] = np.clip(I * 1.2, 0, 1)
    img = bpy.data.images.new('T_Afterburner', w, h, alpha=True)
    img.pixels.foreach_set(px.ravel())
    save_image(img, 'T_Afterburner.png')
    mat = bpy.data.materials.new('MAT_Afterburner')
    nt = NT(mat)
    ti = nt.n('ShaderNodeTexImage', image=img)
    b = nt.n('ShaderNodeBsdfPrincipled')
    out = nt.n('ShaderNodeOutputMaterial')
    nt.L.new(ti.outputs['Color'], b.inputs['Base Color'])
    nt.L.new(ti.outputs['Alpha'], b.inputs['Alpha'])
    nt.L.new(ti.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 8.0
    nt.L.new(b.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    return mat


def glass_material():
    mat = bpy.data.materials.get('MAT_CanopyGlass')
    if mat:
        return mat
    mat = bpy.data.materials.new('MAT_CanopyGlass')
    nt = NT(mat)
    b = nt.n('ShaderNodeBsdfPrincipled')
    out = nt.n('ShaderNodeOutputMaterial')
    b.inputs['Base Color'].default_value = (0.03, 0.05, 0.06, 1)
    b.inputs['Roughness'].default_value = 0.03
    b.inputs['Alpha'].default_value = 0.28
    nt.L.new(b.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    return mat


# ------------------------------------------------------------------------------ Aircraft
class Aircraft(Tank):
    def __init__(self, name, origin, cfg):
        self.name, self.origin = name, Vector(origin)
        cfg = dict(cfg)
        cfg['origin'] = tuple(self.origin)
        cfg['base_fn'] = air_base
        self.cfg = cfg
        self.coll = get_coll(f'Aircraft_{name}', get_coll('AircraftKit'))
        self.mbs, self.objs, self.bones, self.wheel_drv = {}, [], [], []
        self.guns, self.flashes, self.tracks, self.meta, self.temp_meshes = [], [], {}, {}, []
        self.controls, self.wheels, self.gears, self.flames, self.stores = {}, {}, {}, [], []
        self.glass, self.prop, self.canopy = MB(), None, None
        self.glass_bones = []
        self.mats = {k: master_material(f'MM_{name}_{k}', k, cfg) for k in SLOTS}
        self.mat_list = [self.mats[k] for k in SLOTS]
        self.extra_objs = []

    def glass_part(self, bone, fn):
        """fn(mb) adds glass geometry; all of it is weighted to `bone`."""
        before = len(self.glass.bm.verts)
        fn(self.glass)
        self.glass_bones.append((bone, before, len(self.glass.bm.verts)))

    def gear_bone(self, name, pivot, kind, angle):
        p = Vector(pivot)
        self.bone(name, p, p + Vector((0, -0.4, 0)), parent='body', coll='Gear', shape='diamond', sxyz=(0.12,) * 3,
                  color='THEME06', locks=dict(loc=(True,) * 3, scale=(True,) * 3))
        self.gears[name] = dict(axis=kind, angle=angle)

    def muzzle(self, i, pos, Lf=0.6, Wf=0.28):
        p = Vector(pos)
        mz, fb = f'muzzle_{i}', f'flash_{i}'
        self.bone(mz, p, p + Vector((0, -0.25, 0)), parent='body', deform=False, coll='Sockets', shape='diamond',
                  sxyz=(0.08,) * 3, color='THEME06', locks=dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3))
        self.bone(fb, p, p + Vector((0, -0.3, 0)), parent=mz, coll='Sockets', shape='diamond', sxyz=(0.05,) * 3,
                  color='THEME06', locks=dict(loc=(True,) * 3, rot=(True, False, True)))
        self.flashes.append((fb, tuple(p), (0, -1, 0), Lf, Wf))

    def afterburner(self, name, pos, Lf, Wf):
        p = Vector(pos)
        self.bone(name, p, p + Vector((0, 0.5, 0)), parent='body', coll='Sockets', shape='diamond', sxyz=(0.1,) * 3,
                  color='THEME02', locks=dict(loc=(True,) * 3, rot=(True, False, True)))
        self.flames.append((name, tuple(p), (0, 1, 0), Lf, Wf))

    def std_bones(self, length):
        self.bone('root', (0, 0, 0), (0, -1.0, 0), shape='square', sxyz=(1.5, length / 2 + 0.5, 1), color='THEME09')
        self.bone('body', (0, 0, 0), (0, -0.8, 0), parent='root', shape='box', sxyz=(0.4, length / 2, 0.4),
                  color='THEME09')
        if self.prop:
            h = Vector(self.prop['hub'])
            self.bone('prop', h, h + Vector((0, -0.4, 0)), parent='body', shape='circle',
                      sxyz=(self.prop['R'] * 1.05,) * 3, color='THEME02',
                      locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
            self.bone('prop_blur', h + Vector((0, -0.02, 0)), h + Vector((0, -0.3, 0)), parent='body',
                      coll='Sockets', shape='diamond', sxyz=(0.08,) * 3, color='THEME02')

    # ---------------------------------------------------------------- extras (after bake)
    def _extra_object(self, name, me, groups):
        ob = bpy.data.objects.new(f'{self.name}_{name}', me)
        self.coll.objects.link(ob)
        ob.location = self.origin
        for bn, idx in groups.items():
            vg = ob.vertex_groups.new(name=bn)
            vg.add(idx, 1.0, 'REPLACE')
        ob.parent = self.rig
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = (0, 0, 0)
        mo = ob.modifiers.new('Armature', 'ARMATURE')
        mo.object = self.rig
        self.extra_objs.append(ob)
        return ob

    def _quads_object(self, name, items, mat, scale_rest=FLASH_REST):
        verts, faces, uvs, groups = [], [], [], {}
        for (bn, pos, fwd, Lf, Wf) in items:
            v, f, u = flash_quads(pos, fwd, Lf, Wf)
            base = len(verts)
            verts += v
            faces += [tuple(i + base for i in ff) for ff in f]
            uvs += u
            groups.setdefault(bn, []).extend(range(base, base + len(v)))
        me = bpy.data.meshes.new(f'{self.name}_{name}')
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', [c for fu in uvs for uv in fu for c in uv])
        me.materials.append(mat)
        return self._extra_object(name, me, groups)

    def build_extras(self):
        if self.flashes:
            self.flash_obj = self._quads_object('MuzzleFlash', self.flashes, flash_material())
        if self.flames:
            self._quads_object('Afterburner', self.flames, flame_material())
        if self.prop:
            h, R = Vector(self.prop['hub']) + Vector((0, -0.02, 0)), self.prop['R'] * 1.02
            n = 24
            verts = [tuple(h)] + [tuple(h + Vector((math.cos(TAU * i / n), 0, math.sin(TAU * i / n))) * R * FLASH_REST)
                                  for i in range(n)]
            verts[0] = tuple(h)
            verts = [tuple(h + (Vector(v) - h)) for v in verts]
            faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
            me = bpy.data.meshes.new(f'{self.name}_PropBlur')
            me.from_pydata(verts, [], faces)
            uvl = me.uv_layers.new(name='UVMap')
            uv = []
            for f in faces:
                for vi in f:
                    if vi == 0:
                        uv += [0.5, 0.5]
                    else:
                        a = TAU * (vi - 1) / n
                        uv += [0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)]
            uvl.data.foreach_set('uv', uv)
            me.materials.append(blur_material())
            self._extra_object('PropBlur', me, {'prop_blur': list(range(n + 1))})
        if len(self.glass.bm.verts):
            bm = self.glass.bm
            me = bpy.data.meshes.new(f'{self.name}_Canopy')
            bm.to_mesh(me)
            bm.free()
            me.materials.append(glass_material())
            for p in me.polygons:
                p.use_smooth = True
            groups = {}
            for bn, a, b in self.glass_bones:
                groups.setdefault(bn, []).extend(range(a, b))
            self._extra_object('Canopy', me, groups)

    def assemble(self):
        rig = self.rig
        mat = final_material(f'MAT_{self.name}', self.imgs['COLOR'], self.imgs['ORM'], self.imgs['NORMAL'])
        vl = bpy.context.view_layer
        parts = []
        for ob, bone, group in self.objs:
            if ob.data.users > 1:
                ob.data = ob.data.copy()
            me = ob.data
            me.materials.clear()
            me.materials.append(mat)
            me.polygons.foreach_set('material_index', [0] * len(me.polygons))
            ob.vertex_groups.clear()
            vg = ob.vertex_groups.new(name=bone)
            vg.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
            parts.append(ob)
        for o in vl.objects:
            o.select_set(False)
        for o in parts:
            o.select_set(True)
        vl.objects.active = next(o for o in parts if o.name.endswith('_hull'))
        bpy.ops.object.join()
        body = vl.objects.active
        body.name = body.data.name = f'{self.name}_Body'
        mw = body.matrix_world.copy()
        body.parent = rig
        body.matrix_parent_inverse = Matrix.Identity(4)
        body.matrix_world = mw
        mo = body.modifiers.new('Armature', 'ARMATURE')
        mo.object = rig
        self.body = body
        for m in self.mat_list:
            bpy.data.materials.remove(m)
        for me in self.temp_meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        self.objs = []
        self.build_extras()
        return body

    def stats(self):
        out = {}
        for ob in [self.body] + self.extra_objs:
            ob.data.calc_loop_triangles()
            out[ob.name] = len(ob.data.loop_triangles)
        out['bones'] = len(self.rig.data.bones)
        return out

    # ---------------------------------------------------------------- clips
    def build_clips(self):
        rig = self.rig
        ad = rig.animation_data_create()
        pbs = rig.pose.bones
        made = []

        def reset():
            for pb in pbs:
                pb.location = (0, 0, 0)
                pb.rotation_euler = (0, 0, 0)
                pb.scale = (1, 1, 1)

        def key(bn, path, idx, f, v):
            pb = pbs[bn]
            if idx is None:
                setattr(pb, path, v)
                pb.keyframe_insert(path, frame=f)
            else:
                getattr(pb, path)[idx] = v
                pb.keyframe_insert(path, index=idx, frame=f)

        def clip(name, f0, f1, fn, interp='LINEAR'):
            reset()
            act = bpy.data.actions.new(f'{self.name}_{name}')
            act.use_fake_user = True
            ad.action = act
            fn()
            if interp:
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
            made.append(name)

        S = 1.0 / FLASH_REST
        if self.prop:
            nb = self.prop['blades']
            clip('Prop_Spin', 1, 5, lambda: (key('prop', 'rotation_euler', 1, 1, 0.0),
                                             key('prop', 'rotation_euler', 1, 5, -TAU / nb)))

            def blur():
                key('prop_blur', 'scale', None, 1, (S, S, S))
                key('prop_blur', 'scale', None, 2, (S, S, S))
            clip('Prop_Blur_On', 1, 2, blur)

        def controls():
            for bn, c in self.controls.items():
                m = math.radians(c['max'])
                seq = {'roll': (1, 13, 25), 'pitch': (25, 37, 49), 'yaw': (49, 61, 73)}[c['axis']]
                key(bn, 'rotation_euler', 1, 1, 0.0)
                key(bn, 'rotation_euler', 1, seq[0], 0.0)
                key(bn, 'rotation_euler', 1, seq[1], m)
                key(bn, 'rotation_euler', 1, seq[2], 0.0)
                key(bn, 'rotation_euler', 1, 73, 0.0)
        clip('Controls_Demo', 1, 73, controls, interp='BEZIER')

        if self.gears:
            def retract():
                for bn, g in self.gears.items():
                    idx = 0 if g['axis'] == 'x' else 1
                    key(bn, 'rotation_euler', idx, 1, 0.0)
                    key(bn, 'rotation_euler', idx, 49, math.radians(g['angle']))
            clip('Gear_Retract', 1, 49, retract, interp='BEZIER')
        if self.canopy:
            c = self.canopy

            def can():
                if c['mode'] == 'slide':
                    key('canopy', 'location', 1, 1, 0.0)
                    key('canopy', 'location', 1, 37, -c['travel'])
                else:
                    key('canopy', 'rotation_euler', 0, 1, 0.0)
                    key('canopy', 'rotation_euler', 0, 37, math.radians(c['travel']))
            clip('Canopy_Open', 1, 37, can, interp='BEZIER')
        if self.flashes:
            def fire():
                import random
                rnd = random.Random(3)
                n = len(self.flashes)
                for i, (fb, pos, fwd, Lf, Wf) in enumerate(self.flashes):
                    key(fb, 'scale', None, 1, (1, 1, 1))
                    for s in range(1 + (i % 2) * 2, 22, 4):
                        key(fb, 'scale', None, s, (S, S, S))
                        key(fb, 'rotation_euler', 1, s, rnd.uniform(0, TAU))
                        key(fb, 'scale', None, s + 1, (0.6 * S,) * 3)
                        key(fb, 'scale', None, s + 2, (1, 1, 1))
                    key(fb, 'scale', None, 25, (1, 1, 1))
            clip('Fire', 1, 25, fire)
        if self.flames:
            def ab():
                for (bn, pos, fwd, Lf, Wf) in self.flames:
                    for f, s in ((1, 1.0), (4, 0.93), (7, 1.04), (10, 0.96), (13, 1.0)):
                        key(bn, 'scale', None, f, (S * s, S * s, S * s * (2 - s)))
            clip('Afterburner', 1, 13, ab)
        ad.action = None
        return made


def finish_air_meta(T, kind):
    T.meta.update(dict(aircraft=T.name, kind=kind, controls=T.controls, gears=T.gears,
                       wheels={k: round(v, 4) for k, v in T.wheels.items()},
                       canopy=T.canopy or {}, prop=T.prop or {}, stores=T.stores,
                       muzzles=[f[0].replace('flash', 'muzzle') for f in T.flashes],
                       afterburners=[f[0] for f in T.flames]))


def air_export(T):
    T.rig.hide_set(False)
    for pb in T.rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    path = os.path.join(GLB_DIR, f'Aircraft_{T.name}.glb')
    export_tank(T, path)
    for pb in T.rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    s = glb_summary(path)
    return dict(kb=s['size_kb'], joints=s['skins'], materials=s['materials'],
                anims={k: sum(v.values()) for k, v in s['anims'].items()})
