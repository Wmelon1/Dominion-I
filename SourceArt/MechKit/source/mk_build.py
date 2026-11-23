# Mech Kit - three 9 m line-holding mechs (Aegis, Halberd, Thunderhead) on one shared humanoid skeleton,
# each with a back banner in 3 faction variants. Exports FBX for Unity (URP-packed textures).
# Needs tk_core, tk_tank, ak_core, as_tex, as_build, sd_build exec'd first.
# Z up, front -Y (-> Unity +Z), metres, origin between the feet.

MK_DIR = globals().get('MK_DIR')
TEX_DIR = os.path.join(MK_DIR, 'textures')
FBX_DIR = os.path.join(MK_DIR, 'fbx')

MECH_P = dict(hips=4.55, spine=5.05, chest=5.70, upper=6.35, neck=7.05, head=7.35, top=8.3, clav=0.2, sh_x=1.5,
              sh_z=6.85, ua=1.3, fa=1.35, palm=0.5, leg_x=0.75, hip_z=4.35, knee=2.45, ankle=0.62, fing=5.0)
FACTIONS = ['SkyLegion', 'IronRepublic', 'StormCorsairs']
POLE = Vector((-0.95, 1.7, 6.9))
BANNER_TOP, BANNER_H, BANNER_W = 11.75, 3.4, 2.0


# ------------------------------------------------------------------------------ helpers
def cbox(mb, c, s, ch=0.08, mat=P, M=None, top=(1.0, 1.0), bot=(1.0, 1.0), top_off=(0.0, 0.0)):
    """chamfered box (8-sided rings) centred at c, optional taper / offset / transform."""
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    ch = max(0.004, min(ch, hx * 0.45, hy * 0.45, hz * 0.45))
    tx, ty = top
    bx, by = bot
    ox, oy = top_off
    cx, cy, cz = c

    def rr(w, d, z, chf, dx=0.0, dy=0.0):
        return [(x + cx + dx, y + cy + dy, z + cz) for x, y, _ in ring_rect(w, -d, d, 0.0, chf)]
    rings = [rr(hx * bx - ch, hy * by - ch, -hz, ch * 0.6), rr(hx * bx, hy * by, -hz + ch, ch),
             rr(hx * tx, hy * ty, hz - ch, ch, ox, oy), rr(hx * tx - ch, hy * ty - ch, hz, ch * 0.6, ox, oy)]
    return mb.loft(rings, mat, M=M)


def joint(mb, c, axis, r, w, mat=MT, segs=18):
    mb.lathe([(0, -w / 2), (r * 0.82, -w / 2), (r, -w / 2 + w * 0.12), (r, w / 2 - w * 0.12), (r * 0.82, w / 2), (0, w / 2)],
             segs, mat, M=frame(c, axis))
    mb.lathe([(0, w / 2), (r * 0.45, w / 2), (r * 0.4, w / 2 + 0.05), (0, w / 2 + 0.05)], 12, MT, M=frame(c, axis))
    mb.lathe([(0, -w / 2), (r * 0.45, -w / 2), (r * 0.4, -w / 2 - 0.05), (0, -w / 2 - 0.05)], 12, MT, M=frame(c, axis))


def ball(mb, c, r, mat=MT, segs=16):
    c = Vector(c)
    prof = [(0, -r)] + [(r * math.sin(math.pi * i / 8), -r * math.cos(math.pi * i / 8)) for i in range(1, 8)] + [(0, r)]
    mb.lathe(prof, segs, mat, M=frame(c, (0, 0, 1)))


def piston(mb, a, b, r=0.09, mat=MT):
    a, b = Vector(a), Vector(b)
    mid = a.lerp(b, 0.55)
    mb.cyl(r, (mid - a).length, 10, mat, M=frame(a, b - a), x0=0.0)
    mb.cyl(r * 0.6, (b - mid).length + 0.1, 8, MT, M=frame(mid - (b - a).normalized() * 0.1, b - a), x0=0.0)
    for p in (a, b):
        mb.cyl(r * 1.25, 0.1, 10, MT, M=frame(p, b - a))


def vents(mb, c, w, h, n, normal, mat=MT):
    """louvred vent panel on a surface with outward normal (axis aligned)."""
    c = Vector(c)
    nrm = Vector(normal)
    if abs(nrm.x) > 0.5:
        for i in range(n):
            mb.box((c.x + nrm.x * 0.02, c.y - w / 2 + (i + 0.5) * w / n, c.z), (0.05, w / n * 0.55, h), mat)
        mb.box((c.x, c.y, c.z), (0.03, w + 0.06, h + 0.06), MT)
    elif abs(nrm.y) > 0.5:
        for i in range(n):
            mb.box((c.x - w / 2 + (i + 0.5) * w / n, c.y + nrm.y * 0.02, c.z), (w / n * 0.55, 0.05, h), mat)
        mb.box((c.x, c.y, c.z), (w + 0.06, 0.03, h + 0.06), MT)
    else:
        for i in range(n):
            mb.box((c.x - w / 2 + (i + 0.5) * w / n, c.y, c.z + nrm.z * 0.02), (w / n * 0.55, h, 0.05), mat)
        mb.box((c.x, c.y, c.z), (w + 0.06, h + 0.06, 0.03), MT)


def lamp_light(mb, c, fwd, r=0.12):
    mb.lathe([(0, -0.1), (r, -0.1), (r, 0.04), (r * 0.85, 0.06), (0, 0.06)], 12, MT, mats=[MT, MT, MT, LT],
             M=frame(c, fwd))


def mk_antenna(mb, c, h):
    x, y, z = c
    mb.cyl(0.07, 0.16, 8, MT, M=frame((x, y, z), (0, 0, 1)), x0=0.0)
    mb.cyl(0.025, h, 6, MT, M=frame((x, y, z + 0.16), (0, 0, 1)), x0=0.0, r2=0.01)
    mb.lathe([(0, 0), (0.04, 0.0), (0.04, 0.05), (0, 0.06)], 8, LR, M=frame((x, y, z + 0.16 + h), (0, 0, 1)))


# ------------------------------------------------------------------------------ banners (9 textures)
FPAL = {'SkyLegion': dict(field=(0.09, 0.12, 0.26), acc=(0.83, 0.67, 0.3), alt=(0.9, 0.88, 0.82)),
        'IronRepublic': dict(field=(0.24, 0.31, 0.17), acc=(0.8, 0.63, 0.22), alt=(0.08, 0.08, 0.08)),
        'StormCorsairs': dict(field=(0.55, 0.06, 0.08), acc=(0.93, 0.92, 0.86), alt=(0.06, 0.05, 0.05))}


def poly_mask(u, v, pts):
    inside = np.zeros_like(u, bool)
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        inside ^= ((yi > v) != (yj > v)) & (u < (xj - xi) * (v - yi) / (yj - yi + 1e-9) + xi)
        j = i
    return inside


def banner_tex(faction, cls, w=512, h=1024):
    pal = FPAL[faction]
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    u /= w
    v /= h
    asp = h / w
    col = solid(h, w, pal['field'])
    alpha = np.ones((h, w), np.float32)
    border = (u < 0.045) | (u > 0.955) | (v > 0.975)
    col[border] = pal['acc'] if faction != 'StormCorsairs' else pal['alt']
    if faction != 'StormCorsairs':
        col[(v > 0.86) & (v < 0.875)] = pal['acc']
    # faction badge (top)
    cx, cy = 0.5, 0.79
    x, y = (u - cx), (v - cy) * asp
    r = np.sqrt(x * x + y * y)
    if faction == 'SkyLegion':
        ecol, ea = tex_emblem(512)
        sx = ((x / 0.2) * 256 + 256).astype(int)
        sy = ((y / 0.2) * 256 + 256).astype(int)
        ok = (sx >= 0) & (sx < 512) & (sy >= 0) & (sy < 512)
        sxc, syc = np.clip(sx, 0, 511), np.clip(sy, 0, 511)
        m = ok & (ea[syc, sxc] > 0.5)
        col[m] = ecol[syc, sxc][m]
    elif faction == 'IronRepublic':
        th = np.arctan2(y, x)
        col[r < 0.2] = (0.88, 0.86, 0.8)
        cog = (r < 0.13 + 0.03 * (np.cos(th * 10) > 0)) & (r > 0.05)
        col[cog] = (0.08, 0.08, 0.08)
    else:
        bolt = [(0.43, 0.935), (0.57, 0.935), (0.53, 0.865), (0.61, 0.865), (0.45, 0.765), (0.485, 0.835), (0.4, 0.835)]
        col[poly_mask(u, v, bolt)] = pal['acc']
    # class sigil (centre)
    acc = pal['acc']
    if cls == 'Aegis':
        sh = [(0.24, 0.62), (0.76, 0.62), (0.76, 0.46), (0.7, 0.36), (0.6, 0.28), (0.5, 0.23), (0.4, 0.28),
              (0.3, 0.36), (0.24, 0.46)]
        inner = [(0.5 + (px - 0.5) * 0.78, 0.43 + (py - 0.43) * 0.78) for px, py in sh]
        col[poly_mask(u, v, sh)] = acc
        col[poly_mask(u, v, inner)] = pal['field']
        col[poly_mask(u, v, [(0.47, 0.58), (0.53, 0.58), (0.53, 0.3), (0.47, 0.3)])] = acc
        col[poly_mask(u, v, [(0.33, 0.5), (0.67, 0.5), (0.67, 0.45), (0.33, 0.45)])] = acc
    elif cls == 'Halberd':
        col[poly_mask(u, v, [(0.485, 0.66), (0.515, 0.66), (0.515, 0.16), (0.485, 0.16)])] = acc
        col[poly_mask(u, v, [(0.5, 0.72), (0.54, 0.64), (0.46, 0.64)])] = acc
        axe = [(0.515, 0.62), (0.7, 0.66), (0.76, 0.56), (0.72, 0.47), (0.515, 0.52)]
        col[poly_mask(u, v, axe)] = acc
        col[poly_mask(u, v, [(0.485, 0.6), (0.4, 0.57), (0.485, 0.55)])] = acc
    else:
        for k in range(3):
            y0 = 0.24 + k * 0.13
            chev = [(0.24, y0), (0.5, y0 + 0.13), (0.76, y0), (0.76, y0 + 0.06), (0.5, y0 + 0.19), (0.24, y0 + 0.06)]
            col[poly_mask(u, v, chev)] = acc
    # bottom: swallowtail for the Corsairs, fringe for the others
    if faction == 'StormCorsairs':
        alpha[v < 0.12 * (1 - np.abs(u - 0.5) * 2)] = 0.0
    else:
        fringe = (v < 0.05)
        col[fringe] = acc
        alpha[(v < 0.035) & (np.sin(u * np.pi * 2 * 22) < -0.2)] = 0.0
    weave = 0.96 + 0.04 * np.sin(u * np.pi * 2 * 160) * np.sin(v * np.pi * 2 * 320)
    shade = 0.88 + 0.16 * fbm(w, h, 2, 4, 4, hash((faction, cls)) % 1000)
    col = col * (weave * shade)[..., None]
    return np.clip(col, 0, 1), alpha


def banner_material(name, rgb, alpha):
    img = img_from(f'T_{name}', rgb, alpha)
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


def glow_material():
    return flat_material('MAT_MechGlow', (0.25, 0.85, 1.0), 0.2, emit=12.0)


# ------------------------------------------------------------------------------ paint schemes
def hazard_fn(nt, Pv, cfg):
    s = nt.sep(Pv)
    t = nt.math('FRACT', nt.math('DIVIDE', nt.math('ADD', s['X'], s['Z']), 0.45))
    m = nt.math('GREATER_THAN', t, 0.5)
    return nt.mix(m, cfg['mark'], cfg.get('mark2', (0.025, 0.025, 0.025)))


def mech_cfg(base):
    cfg = dict(ao_local=True, ao_dist=1.0, bevel=0.035, height_fn=panel_height, panel=1.1, bump=0.35,
               dust=0.55, dust_h=2.6, wear=0.8, chips=0.35, rough=0.5)
    cfg.update(base)
    return cfg


VARIANTS = {
    'Aegis': mech_cfg(dict(pattern='blotch', scale=0.18, distort=0.5,
                           stops=[(0.0, srgb('#56603f')), (0.55, srgb('#4a5236')), (0.7, srgb('#3d4430'))],
                           mark=srgb('#d9a520'), mark_fn=hazard_fn, dust_col=srgb('#8a7a5c'))),
    'Halberd': mech_cfg(dict(pattern='splinter', scale=0.22,
                             stops=[(0.0, srgb('#4d5258')), (0.45, srgb('#3d4248')), (0.7, srgb('#5b6067')),
                                    (0.88, srgb('#2f3337'))], mark=srgb('#9e1f1a'), dust_col=srgb('#6f6a62'),
                             metallic=0.15, rough=0.42)),
    'Thunderhead': mech_cfg(dict(pattern='blotch', scale=0.16, distort=0.6,
                                 stops=[(0.0, srgb('#b49a6c')), (0.56, srgb('#8f7652')), (0.68, srgb('#6e5b40'))],
                                 mark=srgb('#c8641c'), mark_fn=hazard_fn, dust_col=srgb('#a08a66'))),
}
LINEUP = {'Aegis': -13.0, 'Halberd': 0.0, 'Thunderhead': 13.0}


class Mech(Tank):
    def __init__(self, name, origin, cfg):
        self.name, self.origin, self.cfg, self.P = name, Vector(origin), cfg, MECH_P
        self.coll = get_coll(f'Mech_{name}', get_coll('MechKit'))
        self.mbs, self.objs, self.bones, self.wheel_drv = {}, [], [], []
        self.guns, self.flashes, self.tracks, self.meta, self.temp_meshes = [], [], {}, {}, []
        self.mats = {k: master_material(f'MM_{name}_{k}', k, cfg) for k in SLOTS}
        self.mat_list = self.mats_list = [self.mats[k] for k in SLOTS]
        self.flames, self.extra_objs = [], []
        self.extra_bones = []

    def part(self, bone, glow=False):
        return self.mb(f'{bone}{"__glow" if glow else ""}', bone, 'glow' if glow else 'hull')


# ------------------------------------------------------------------------------ skeleton
def mech_bones(T):
    D = T.P
    B = T.bone
    rot_only = dict(loc=(True,) * 3, scale=(True,) * 3)
    B('Root', (0, 0, 0), (0, 0, 1.0), z=(0, -1, 0), shape='circle', sxyz=(2.2,) * 3, color='THEME09')
    B('Hips', (0, 0, D['hips']), (0, 0, D['spine']), parent='Root', z=(0, -1, 0), shape='circle', sxyz=(1.4,) * 3,
      color='THEME09', locks=dict(scale=(True,) * 3))
    for name, a, b, par in (('Spine', 'spine', 'chest', 'Hips'), ('Chest', 'chest', 'upper', 'Spine'),
                            ('UpperChest', 'upper', 'neck', 'Chest'), ('Neck', 'neck', 'head', 'UpperChest'),
                            ('Head', 'head', 'top', 'Neck')):
        B(name, (0, 0, D[a]), (0, 0, D[b]), parent=par, z=(0, -1, 0), shape='circle', sxyz=(1.0,) * 3,
          color='THEME03', locks=rot_only)
    ex, wx = D['sh_x'] + D['ua'], D['sh_x'] + D['ua'] + D['fa']
    for side, s in (('Left', 1), ('Right', -1)):
        col = 'THEME01' if s > 0 else 'THEME04'
        B(f'{side}Shoulder', (s * D['clav'], 0, D['sh_z'] + 0.1), (s * D['sh_x'], 0, D['sh_z']), parent='UpperChest',
          z=(0, -1, 0), shape='circle', sxyz=(0.5,) * 3, color=col, locks=rot_only)
        B(f'{side}UpperArm', (s * D['sh_x'], 0, D['sh_z']), (s * ex, 0, D['sh_z']), parent=f'{side}Shoulder',
          z=(0, -1, 0), shape='circle', sxyz=(0.6,) * 3, color=col, locks=rot_only)
        B(f'{side}LowerArm', (s * ex, 0, D['sh_z']), (s * wx, 0, D['sh_z']), parent=f'{side}UpperArm',
          z=(0, -1, 0), shape='circle', sxyz=(0.6,) * 3, color=col, locks=rot_only)
        B(f'{side}Hand', (s * wx, 0, D['sh_z']), (s * (wx + D['palm']), 0, D['sh_z']), parent=f'{side}LowerArm',
          z=(0, -1, 0), shape='circle', sxyz=(0.4,) * 3, color=col, locks=rot_only)
        for name, (h, t) in finger_chain(D, side).items():
            if name.endswith('Metacarpal') or (name.endswith('Proximal') and 'Thumb' not in name):
                par = f'{side}Hand'
            elif name.endswith('Intermediate'):
                par = name.replace('Intermediate', 'Proximal')
            elif 'Thumb' in name:
                par = name.replace('Distal', 'Proximal') if name.endswith('Distal') else name.replace('Proximal', 'Metacarpal')
            else:
                par = name.replace('Distal', 'Intermediate')
            B(name, h, t, parent=par, z=(0, 0, 1), coll='Fingers', shape='circle', sxyz=(0.07,) * 3, color=col,
              locks=rot_only)
        lx = s * D['leg_x']
        B(f'{side}UpperLeg', (lx, 0, D['hip_z']), (lx, 0, D['knee']), parent='Hips', z=(0, -1, 0), shape='circle',
          sxyz=(0.7,) * 3, color=col, locks=rot_only)
        B(f'{side}LowerLeg', (lx, 0, D['knee']), (lx, 0.05, D['ankle']), parent=f'{side}UpperLeg', z=(0, -1, 0),
          shape='circle', sxyz=(0.6,) * 3, color=col, locks=rot_only)
        B(f'{side}Foot', (lx, 0.05, D['ankle']), (lx, -0.85, 0.24), parent=f'{side}LowerLeg', z=(0, 0, 1),
          shape='circle', sxyz=(0.45,) * 3, color=col, locks=rot_only)
        B(f'{side}Toes', (lx, -0.85, 0.24), (lx, -1.4, 0.2), parent=f'{side}Foot', z=(0, 0, 1), shape='circle',
          sxyz=(0.4,) * 3, color=col, locks=rot_only)
        tag = side[0]
        B(f'IK_Foot_{tag}', (lx, 0.05, D['ankle']), (lx, -0.8, D['ankle']), parent='Root', deform=False, coll='IK',
          shape='box', sxyz=(0.5, 0.9, 0.2), color='THEME02')
        B(f'IK_Knee_{tag}', (lx, -3.0, D['knee']), (lx, -3.5, D['knee']), parent='Root', deform=False, coll='IK',
          shape='diamond', sxyz=(0.25,) * 3, color='THEME02')
        B(f'IK_Hand_{tag}', (s * wx, 0, D['sh_z']), (s * (wx + 0.6), 0, D['sh_z']), parent='Root', deform=False,
          coll='IK', shape='box', sxyz=(0.3, 0.4, 0.3), color='THEME02')
        B(f'IK_Elbow_{tag}', (s * ex, 2.5, D['sh_z']), (s * ex, 3.0, D['sh_z']), parent='Root', deform=False,
          coll='IK', shape='diamond', sxyz=(0.25,) * 3, color='THEME02')
    W = Vector((-(wx + D['palm'] * 0.5), 0.0, D['sh_z'] - 0.2))
    B('WeaponR', W, W + Vector((-0.8, 0, 0)), parent='RightHand', z=(0, 0, 1), coll='Sockets', shape='diamond',
      sxyz=(0.25,) * 3, color='THEME06', locks=dict(scale=(True,) * 3))
    T.W = W
    # banner chain hanging from the crossbar (child of UpperChest); sways about X, slight side sway about Z
    xc = POLE.x + 0.1 + BANNER_W / 2
    seg = BANNER_H / 4
    for k in range(4):
        h = Vector((xc, POLE.y, BANNER_TOP - k * seg))
        B(f'Flag_{k}', h, h - Vector((0, 0, seg)), parent='UpperChest' if k == 0 else f'Flag_{k - 1}',
          z=(0, -1, 0), coll='Flags', shape='box', sxyz=(BANNER_W / 2, seg / 2, 0.04), color='THEME05',
          locks=dict(loc=(True,) * 3, rot=(False, True, False), scale=(True,) * 3))


def add_muzzle(T, name, parent, pos, fwd, Lf=2.4, Wf=1.1, flash=True):
    p = Vector(pos)
    f = Vector(fwd).normalized()
    T.bone(name, p, p + f * 0.5, parent=parent, coll='Sockets', shape='diamond', sxyz=(0.15,) * 3, color='THEME06',
           z=(0, 0, 1) if abs(f.z) < 0.9 else (0, -1, 0),
           locks=dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3))
    if flash:
        fb = name.replace('Muzzle', 'Flash')
        T.bone(fb, p, p + f * 0.6, parent=name, coll='Sockets', shape='diamond', sxyz=(0.1,) * 3, color='THEME06',
               z=(0, 0, 1) if abs(f.z) < 0.9 else (0, -1, 0), locks=dict(loc=(True,) * 3, rot=(True, False, True)))
        T.flashes.append((fb, tuple(p), tuple(f), Lf, Wf))


WROT = Matrix.Rotation(-math.pi / 2, 3, 'Z')   # hand weapons are drafted pointing -Y, then turned to point down the arm


def turn_weapon(T):
    W = T.W
    for v in T.mbs['WeaponR'][0].bm.verts:
        v.co = W + WROT @ (v.co - W)


def wpt(T, p):
    return tuple(T.W + WROT @ (Vector(p) - T.W))


# ------------------------------------------------------------------------------ shared frame
def sloft(mb, spec, axis='z', base=(0, 0, 0), s=1, mat=P):
    """loft of chamfered rectangles. rows: (t, half_w, half_d, chamfer[, du, dv]).
    axis 'z': ring in XY at height t (w along X, d along Y). axis 'x': ring in YZ at x = s*t (w along Z, d along Y)."""
    bx, by, bz = base
    rings = []
    for row in spec:
        t, hw, hd, c = row[:4]
        du = row[4] if len(row) > 4 else 0.0
        dv = row[5] if len(row) > 5 else 0.0
        c = max(0.004, min(c, hw * 0.45, hd * 0.45))
        pts = ring_rect(hw, -hd, hd, 0.0, c)
        if axis == 'z':
            rings.append([(bx + x + du, by + y + dv, bz + t) for x, y, _ in pts])
        else:
            rings.append([(bx + s * t, by + y + dv, bz + x + du) for x, y, _ in pts])
    return mb.loft(rings, mat)


def build_frame(T, V):
    D = T.P
    b = V['bulk']
    hz, kn, an, sz = D['hip_z'], D['knee'], D['ankle'], D['sh_z']
    ex, wx = D['sh_x'] + D['ua'], D['sh_x'] + D['ua'] + D['fa']
    # ---- pelvis
    m = T.part('Hips')
    sloft(m, [(4.0, 0.5, 0.42, 0.14), (4.22, 0.72, 0.55, 0.18), (4.7, 0.78, 0.6, 0.2), (4.92, 0.66, 0.52, 0.16)],
          base=(0, 0.05, 0), mat=MT)
    sloft(m, [(3.82, 0.2, 0.1, 0.05, 0, -0.6), (4.2, 0.36, 0.15, 0.06, 0, -0.66), (4.66, 0.44, 0.14, 0.06, 0, -0.66)])
    cbox(m, (0, -0.79, 4.5), (0.5, 0.06, 0.16), 0.02, K)
    cbox(m, (0, 0.05, 4.84), (1.66, 1.3, 0.14), 0.06, MT)
    for s in (1, -1):
        joint(m, (s * 0.75, 0, hz), (1, 0, 0), 0.44, 0.5)
        cbox(m, (0, 0, 0), (0.14, 1.05 * b, 1.0), 0.05, P, top=(1.0, 0.9), M=Mt(s * 1.34, 0.0, 4.1) @ Mry(-s * 0.22))
        cbox(m, (0, 0, 0), (0.06, 0.7 * b, 0.3), 0.02, K, M=Mt(s * 1.43, 0.0, 4.32) @ Mry(-s * 0.22))
        cbox(m, (0, 0, 0), (0.46, 0.1, 0.72), 0.04, P, top=(1.0, 1.0), bot=(0.8, 1.0),
             M=Mt(s * 0.44, -0.74, 4.08) @ Mrx(0.25))
    cbox(m, (0, 0, 0), (1.15, 0.12, 0.85), 0.04, P, bot=(0.85, 1.0), M=Mt(0, 0.76, 4.12) @ Mrx(-0.2))
    # ---- waist
    m = T.part('Spine')
    m.cyl(0.5, 0.8, 20, MT, M=frame((0, 0.05, 5.15), (0, 0, 1)))
    for zz in (4.95, 5.15, 5.35):
        m.cyl(0.55, 0.07, 20, MT, M=frame((0, 0.05, zz), (0, 0, 1)))
    sloft(m, [(4.9, 0.4, 0.1, 0.04, 0, -0.5), (5.12, 0.46, 0.12, 0.04, 0, -0.54)])
    sloft(m, [(5.2, 0.48, 0.1, 0.04, 0, -0.55), (5.45, 0.55, 0.12, 0.04, 0, -0.6)])
    cbox(m, (0, 0.58, 5.2), (0.7, 0.3, 0.7), 0.06, MT)
    for s in (1, -1):
        piston(m, (s * 0.6, -0.12, 4.85), (s * 0.64, -0.12, 5.55), 0.08)
    # ---- chest (barrel torso with V breast plates)
    m = T.part('Chest')
    sloft(m, [(5.42, 0.8 * b, 0.7, 0.2, 0, 0.05), (5.75, 1.0 * b, 0.84, 0.24), (6.3, 1.12 * b, 0.92, 0.28, 0, 0.02),
              (6.62, 1.02 * b, 0.86, 0.24, 0, 0.06)])
    for s in (1, -1):
        cbox(m, (0, 0, 0), (0.95 * b, 0.16, 0.9), 0.05, P, top=(0.92, 1.0), bot=(0.8, 1.0),
             M=Mt(s * 0.47 * b, -0.9, 6.12) @ Mrz(s * 0.32) @ Mrx(-0.1))
        cbox(m, (0, 0, 0), (0.7 * b, 0.05, 0.08), 0.02, K, M=Mt(s * 0.47 * b, -0.99, 6.48) @ Mrz(s * 0.32) @ Mrx(-0.1))
        vents(m, (s * (1.12 * b + 0.01), 0.0, 6.0), 0.9, 0.5, 6, (s, 0, 0))
        lamp_light(m, (s * 0.62 * b, -0.8, 5.6), (0, -1, -0.25), 0.1)
        m.box((s * 0.9 * b, -0.5, 6.66), (0.14, 0.14, 0.1), MT)
    cbox(m, (0, -1.0, 6.05), (0.32, 0.26, 0.98), 0.06, K, top=(0.8, 1.0), bot=(0.7, 1.0))
    m.box((0, -1.13, 6.05), (0.12, 0.04, 0.7), MT)
    # ---- upper chest / yoke / back reactor / banner pole
    m = T.part('UpperChest')
    sloft(m, [(6.48, 1.05 * b, 0.86, 0.22, 0, 0.12), (6.8, 1.3 * b, 0.92, 0.26, 0, 0.12),
              (7.05, 1.18 * b, 0.82, 0.24, 0, 0.14), (7.2, 0.85 * b, 0.62, 0.18, 0, 0.18)])
    m.lathe([(0.42, 0.0), (0.58, 0.0), (0.62, 0.1), (0.48, 0.16), (0.42, 0.16)], 20, MT,
            M=frame((0, 0.05, 7.16), (0, 0, 1)))
    cbox(m, (0, 1.15, 6.45), (1.55, 0.72, 1.55), 0.12, P)
    cbox(m, (0, 1.52, 6.45), (1.2, 0.06, 1.2), 0.04, MT)
    for s in (1, -1):
        m.cyl(0.13, 0.55, 12, MT, M=frame((s * 0.45, 1.6, 6.9), (0, 0, 1)), x0=0.0)
        m.lathe([(0.13, 0), (0.18, 0.05), (0.18, 0.12), (0.1, 0.14)], 12, MT, M=frame((s * 0.45, 1.6, 7.45), (0, 0, 1)))
        joint(m, (s * 1.32, 0, sz), (1, 0, 0), 0.48, 0.35)
        cbox(m, (s * 0.95 * b, -0.72, 6.95), (0.4, 0.1, 0.22), 0.03, K)
    for k in range(6):
        m.box((-0.5 + k * 0.2, 1.56, 6.4), (0.05, 0.1, 1.0), MT)
    beam(m, (POLE.x, 1.45, 6.6), POLE, 0.22, 0.22, MT)
    m.cyl(0.08, BANNER_TOP + 0.4 - POLE.z, 10, MT, M=frame(POLE, (0, 0, 1)), x0=0.0)
    m.cyl(0.05, BANNER_W + 0.15, 8, MT, M=frame((POLE.x, POLE.y, BANNER_TOP + 0.05), (1, 0, 0)), x0=0.0)
    m.lathe([(0, 0), (0.12, 0.05), (0.15, 0.2), (0.06, 0.4), (0, 0.45)], 10, K,
            M=frame((POLE.x, POLE.y, BANNER_TOP + 0.4), (0, 0, 1)))
    m.lathe([(0, 0), (0.1, 0.0), (0.1, 0.12), (0, 0.15)], 10, K,
            M=frame((POLE.x + BANNER_W + 0.15, POLE.y, BANNER_TOP + 0.05), (1, 0, 0)))
    # ---- neck
    m = T.part('Neck')
    m.cyl(0.3, 0.5, 14, MT, M=frame((0, 0.05, 7.0), (0, 0, 1)), x0=0.0)
    for k in range(4):
        a = k * TAU / 4 + 0.4
        piston(m, (0.36 * math.cos(a), 0.05 + 0.36 * math.sin(a), 7.05),
               (0.3 * math.cos(a), 0.05 + 0.3 * math.sin(a), 7.42), 0.04)
    for side, s in (('Left', 1), ('Right', -1)):
        # ---- arms
        m = T.part(f'{side}UpperArm')
        ball(m, (s * D['sh_x'], 0, sz), 0.42)
        m.cyl(0.28, D['ua'], 16, MT, M=frame((s * D['sh_x'], 0, sz), (s, 0, 0)), x0=0.0)
        sloft(m, [(0.25, 0.34 * b, 0.34 * b, 0.1), (0.48, 0.41 * b, 0.4 * b, 0.12), (0.98, 0.39 * b, 0.38 * b, 0.12),
                  (1.1, 0.31 * b, 0.3 * b, 0.08)], axis='x', base=(s * D['sh_x'], 0, sz + 0.04), s=s)
        piston(m, (s * (D['sh_x'] + 0.25), 0.0, sz - 0.42), (s * (ex - 0.2), 0.0, sz - 0.36), 0.07)
        m = T.part(f'{side}LowerArm')
        joint(m, (s * ex, 0, sz), (0, 0, 1), 0.36, 0.62)
        sloft(m, [(0.12, 0.36 * b, 0.38 * b, 0.1), (0.35, 0.46 * b, 0.46 * b, 0.14), (0.95, 0.45 * b, 0.44 * b, 0.14),
                  (1.2, 0.36 * b, 0.36 * b, 0.1)], axis='x', base=(s * ex, 0, sz), s=s)
        cbox(m, (s * (ex + 0.66), 0, sz + 0.46 * b + 0.02), (0.75, 0.46, 0.06), 0.02, K)
        for dy in (-1, 1):
            cbox(m, (s * (ex + 0.66), dy * (0.45 * b + 0.01), sz - 0.05), (0.7, 0.05, 0.3), 0.02, MT)
        joint(m, (s * (wx - 0.05), 0, sz), (1, 0, 0), 0.26, 0.2)
        m = T.part(f'{side}Hand')
        cbox(m, (s * (wx + 0.26), 0, sz), (0.5, 0.58, 0.26), 0.06, MT)
        cbox(m, (s * (wx + 0.24), 0, sz + 0.17), (0.42, 0.5, 0.08), 0.03, P)
        for name, (a, bb) in finger_chain(D, side).items():
            fm = T.part(name)
            w = 0.13 if 'Thumb' in name else 0.11
            beam(fm, a, bb, w, w, MT)
            beam(fm, a.lerp(bb, 0.5) + Vector((0, 0, 0.05)), bb + Vector((0, 0, 0.05)) - (bb - a).normalized() * 0.02,
                 w * 0.8, 0.035, P)
        # ---- legs
        lx = s * D['leg_x']
        m = T.part(f'{side}UpperLeg')
        ball(m, (lx, 0, hz), 0.42)
        m.cyl(0.34, hz - kn, 16, MT, M=frame((lx, 0, kn), (0, 0, 1)), x0=0.0)
        sloft(m, [(kn + 0.42, 0.34 * b, 0.36, 0.1, 0, -0.06), (3.2, 0.47 * b, 0.48, 0.14, 0, -0.1),
                  (3.85, 0.5 * b, 0.5, 0.15, 0, -0.06), (4.12, 0.4 * b, 0.42, 0.12)], base=(lx, 0, 0))
        cbox(m, (lx + s * 0.5 * b, -0.04, 3.5), (0.1, 0.72, 1.1), 0.04, P, top=(1.0, 0.85))
        cbox(m, (lx + s * 0.55 * b, -0.04, 3.5), (0.04, 0.4, 0.5), 0.015, K)
        for dx in (-0.16, 0.16):
            piston(m, (lx + dx, 0.47, hz - 0.3), (lx + dx, 0.44, kn + 0.38), 0.075)
        m = T.part(f'{side}LowerLeg')
        joint(m, (lx, 0, kn), (1, 0, 0), 0.44, 0.72)
        m.cyl(0.3, kn - an, 14, MT, M=frame((lx, 0.03, an), (0, 0, 1)), x0=0.0)
        sloft(m, [(an + 0.3, 0.36 * b, 0.4, 0.1, 0, -0.02), (1.15, 0.45 * b, 0.5, 0.14, 0, -0.08),
                  (1.85, 0.5 * b, 0.56, 0.16, 0, -0.12), (2.18, 0.44 * b, 0.48, 0.13, 0, -0.1)], base=(lx, 0.03, 0))
        cbox(m, (0, 0, 0), (0.74 * b, 0.3, 0.64), 0.07, K, top=(0.85, 1.0), M=Mt(lx, -0.66, kn + 0.06) @ Mrx(-0.2))
        cbox(m, (lx, -0.62, 1.5), (0.5 * b, 0.06, 0.7), 0.02, MT)
        for dx in (-0.18, 0.18):
            piston(m, (lx + dx, 0.52, kn - 0.3), (lx + dx, 0.46, an + 0.32), 0.07)
        m = T.part(f'{side}Foot')
        joint(m, (lx, 0.05, an), (1, 0, 0), 0.32, 0.62)
        cbox(m, (lx, -0.22, 0.3), (1.0, 1.3, 0.52), 0.1, P, top=(0.88, 0.82))
        cbox(m, (0, 0, 0), (0.62, 0.55, 0.36), 0.06, MT, M=Mt(lx, 0.65, 0.22) @ Mrx(0.25))
        m.box((lx, -0.1, 0.04), (1.06, 1.55, 0.08), RB)
        for dx in (-0.52, 0.52):
            cbox(m, (lx + dx, -0.25, 0.35), (0.08, 0.9, 0.35), 0.03, MT)
        m = T.part(f'{side}Toes')
        cbox(m, (lx, -1.12, 0.18), (0.96, 0.58, 0.32), 0.07, P, top=(0.9, 0.7))
        m.box((lx, -1.1, 0.04), (0.98, 0.6, 0.08), RB)
        for dx in (-0.16, 0.16):
            m.box((lx + dx, -1.15, 0.2), (0.03, 0.62, 0.3), MT)


# ------------------------------------------------------------------------------ variant kits
def kit_aegis(T):
    D = T.P
    wx = D['sh_x'] + D['ua'] + D['fa']
    ex = D['sh_x'] + D['ua']
    # knight helm with T visor
    m = T.part('Head')
    cbox(m, (0, -0.05, 7.78), (0.85, 0.9, 0.8), 0.14, P, top=(0.82, 0.78))
    cbox(m, (0, -0.02, 8.24), (0.09, 0.72, 0.24), 0.03, K)
    for s in (1, -1):
        vents(m, (s * 0.43, 0.0, 7.75), 0.35, 0.28, 4, (s, 0, 0))
    mk_antenna(m, (-0.28, 0.25, 8.15), 0.9)
    g = T.part('Head', glow=True)
    g.box((0, -0.5, 7.84), (0.56, 0.04, 0.08), GL)
    g.box((0, -0.5, 7.66), (0.1, 0.04, 0.3), GL)
    # domed pauldrons
    for side, s in (('Left', 1), ('Right', -1)):
        m = T.part(f'{side}Shoulder')
        c = Vector((s * 1.7, 0.0, 7.2))
        m.lathe([(0, 0.55), (0.45, 0.5), (0.8, 0.32), (0.98, 0.0), (1.0, -0.25), (0.9, -0.3), (0, -0.3)], 22, P,
                M=frame(c, (s * 0.55, 0, 0.85)))
        m.lathe([(0.98, -0.02), (1.06, -0.04), (1.06, -0.2), (0.98, -0.24)], 22, K, M=frame(c, (s * 0.55, 0, 0.85)))
    # smoke launchers on the chest corners
    m = T.part('Chest')
    for s in (1, -1):
        for k in range(3):
            c = Vector((s * (0.95 + k * 0.0), -0.6 + k * 0.28, 6.72))
            m.cyl(0.11, 0.5, 10, MT, M=frame(c, (s * 0.5, -0.4, 0.75)), x0=-0.1)
    # tower shield on the left forearm
    m = T.part('LeftLowerArm')
    sz = D['sh_z'] + 0.62
    cx = ex + 0.75
    cbox(m, (cx, 0, sz), (3.5, 2.1, 0.22), 0.08, P, top=(0.96, 0.96))
    for dy in (-1.0, 1.0):
        cbox(m, (cx, dy, sz + 0.06), (3.5, 0.14, 0.2), 0.04, K)
    for dx in (-1.72, 1.72):
        cbox(m, (cx + dx, 0, sz + 0.06), (0.14, 2.1, 0.2), 0.04, K)
    m.lathe([(0, 0.0), (0.42, 0.0), (0.38, 0.12), (0.2, 0.22), (0, 0.25)], 18, MT, M=frame((cx, 0, sz + 0.1), (0, 0, 1)))
    m.box((cx + 1.2, 0, sz + 0.12), (0.4, 0.5, 0.04), GL)
    for dx in (-0.4, 0.4):
        cbox(m, (cx + dx, 0, sz - 0.25), (0.25, 0.3, 0.32), 0.04, MT)
    # heavy autocannon (right hand)
    W = T.W
    m = T.part('WeaponR')

    def at(x, y, z):
        return (W.x + x, W.y + y, W.z + z)
    cbox(m, at(0, -0.55, 0.45), (0.5, 1.9, 0.62), 0.08, MT)
    cbox(m, at(0, -1.6, 0.48), (0.55, 0.8, 0.5), 0.06, P)
    m.cyl(0.12, 2.6, 14, MT, M=frame(at(0, -1.95, 0.5), (0, -1, 0)), x0=0.0)
    m.lathe([(0.13, 0), (0.22, 0.02), (0.22, 0.35), (0.16, 0.38), (0.16, 0.42), (0.22, 0.45), (0.22, 0.6), (0.1, 0.6)],
            14, MT, M=frame(at(0, -4.4, 0.5), (0, -1, 0)))
    m.cyl(0.5, 0.45, 18, MT, M=frame(at(0.42, -0.4, 0.2), (1, 0, 0)))
    m.box(at(0, 0.1, -0.02), (0.18, 0.28, 0.45), MT)
    cbox(m, at(0, 0.75, 0.42), (0.35, 0.7, 0.4), 0.05, P)
    cbox(m, at(0, -0.6, 0.9), (0.22, 0.55, 0.25), 0.04, MT)
    m.box(at(0, -0.88, 0.9), (0.18, 0.02, 0.18), GL)
    turn_weapon(T)
    add_muzzle(T, 'Muzzle', 'WeaponR', wpt(T, at(0, -5.0, 0.5)), WROT @ Vector((0, -1, 0)))
    T.meta['weapons'] = dict(main='autocannon')


def kit_halberd(T):
    D = T.P
    ex = D['sh_x'] + D['ua']
    # sleek head with mono-eye
    m = T.part('Head')
    cbox(m, (0, -0.1, 7.72), (0.72, 1.05, 0.56), 0.12, P, top=(0.7, 0.62), top_off=(0, 0.08))
    m.box((0, -0.62, 7.72), (0.6, 0.06, 0.12), MT)
    for s in (1, -1):
        beam(m, (s * 0.15, -0.3, 7.95), (s * 0.45, 0.2, 8.45), 0.06, 0.12, K)
        vents(m, (s * 0.37, 0.05, 7.7), 0.4, 0.22, 4, (s, 0, 0))
    g = T.part('Head', glow=True)
    g.lathe([(0, 0), (0.1, 0), (0.08, 0.05), (0, 0.06)], 14, GL, M=frame((0.12, -0.64, 7.72), (0, -1, 0)))
    # angular pauldrons
    for side, s in (('Left', 1), ('Right', -1)):
        m = T.part(f'{side}Shoulder')
        sloft(m, [(0.0, 0.36, 0.6, 0.14, 0.12), (0.3, 0.52, 0.78, 0.22, 0.1), (0.85, 0.48, 0.74, 0.22, -0.02),
                  (1.08, 0.3, 0.56, 0.14, -0.12)], axis='x', base=(s * 1.25, 0.0, 7.05), s=s)
        cbox(m, (s * 1.8, 0.05, 7.62), (0.75, 0.1, 0.24), 0.03, K, top=(0.7, 1.0))
        cbox(m, (s * 1.85, -0.79, 7.0), (0.6, 0.05, 0.5), 0.02, K)
        for dz in (6.75, 7.3):
            m.box((s * 2.34, 0.0, dz), (0.05, 0.6, 0.06), MT)
    # jump jets on the back
    m = T.part('UpperChest')
    for s, tag in ((1, 'L'), (-1, 'R')):
        c = Vector((s * 0.62, 1.55, 6.15))
        cbox(m, (s * 0.62, 1.35, 6.55), (0.5, 0.45, 0.8), 0.06, P)
        m.lathe([(0.22, 0), (0.3, 0.15), (0.34, 0.5), (0.3, 0.55), (0.18, 0.3), (0, 0.3)], 16, MT,
                M=frame(c, (0, 0.3, -1)))
        p = c + Vector((0, 0.3, -1)).normalized() * 0.55
        T.bone(f'Jet_{tag}', p, p + Vector((0, 0.3, -1)).normalized() * 0.5, parent='UpperChest', coll='Sockets',
               shape='diamond', sxyz=(0.15,) * 3, color='THEME02', z=(0, -1, 0),
               locks=dict(loc=(True,) * 3, rot=(True, False, True)))
        T.flames.append((f'Jet_{tag}', tuple(p), tuple(Vector((0, 0.3, -1)).normalized()), 3.2, 1.2))
    # forearm blade (own bone so it can extend)
    lw = D['sh_x'] + D['ua'] + D['fa']
    m = T.part('LeftLowerArm')
    cbox(m, (ex + 0.8, 0, D['sh_z'] + 0.5), (1.1, 0.45, 0.22), 0.05, MT)
    bl = T.mb('BladeL', 'BladeL', 'hull')
    z = D['sh_z'] + 0.62
    rings = []
    for x, wdt, th in ((ex + 0.4, 0.34, 0.1), (lw + 0.4, 0.36, 0.09), (lw + 1.6, 0.3, 0.07), (lw + 2.3, 0.08, 0.03),
                       (lw + 2.45, 0.01, 0.01)):
        rings.append([(x, -wdt / 2 + 0.06, z), (x, wdt / 2, z), (x, wdt / 2 - 0.02, z + th / 2),
                      (x, -wdt / 2, z), (x, wdt / 2 - 0.02, z - th / 2)][0:0] or
                     [(x, -wdt / 2, z), (x, 0.0, z + th / 2), (x, wdt / 2, z + th * 0.1), (x, wdt / 2, z - th * 0.1),
                      (x, 0.0, z - th / 2)])
    bl.loft(rings, MT)
    T.bone('BladeL', (ex + 0.4, 0, z), (ex + 1.0, 0, z), parent='LeftLowerArm', coll='Sockets', shape='box',
           sxyz=(0.1, 0.3, 0.1), color='THEME01', z=(0, 0, 1),
           locks=dict(loc=(True, False, True), rot=(True,) * 3, scale=(True,) * 3))
    # long rail rifle
    W = T.W
    m = T.part('WeaponR')

    def at(x, y, zz):
        return (W.x + x, W.y + y, W.z + zz)
    cbox(m, at(0, -0.5, 0.42), (0.42, 1.7, 0.55), 0.08, MT)
    for dx in (-0.13, 0.13):
        cbox(m, at(dx, -2.6, 0.45), (0.1, 2.9, 0.3), 0.03, MT)
    m.cyl(0.07, 3.0, 10, MT, M=frame(at(0, -1.2, 0.45), (0, -1, 0)), x0=0.0)
    for k in range(6):
        m.lathe([(0.18, -0.05), (0.24, -0.03), (0.24, 0.03), (0.18, 0.05)], 14, LT,
                M=frame(at(0, -1.4 - k * 0.42, 0.45), (0, -1, 0)))
    cbox(m, at(0, 0.6, 0.4), (0.3, 0.9, 0.38), 0.05, P, top=(1.0, 0.8))
    m.box(at(0, 0.1, -0.02), (0.18, 0.28, 0.45), MT)
    m.cyl(0.13, 0.9, 12, MT, M=frame(at(0, -0.6, 0.88), (0, -1, 0)))
    m.cyl(0.12, 0.02, 12, GL, M=frame(at(0, -1.06, 0.88), (0, -1, 0)), x0=0.0)
    cbox(m, at(0, -1.3, 0.12), (0.2, 0.25, 0.4), 0.03, P)
    turn_weapon(T)
    add_muzzle(T, 'Muzzle', 'WeaponR', wpt(T, at(0, -4.1, 0.45)), WROT @ Vector((0, -1, 0)), 2.0, 0.9)
    T.meta['weapons'] = dict(main='railgun', blade='BladeL', jets=['Jet_L', 'Jet_R'])


def kit_thunderhead(T):
    D = T.P
    ex = D['sh_x'] + D['ua']
    wx = ex + D['fa']
    m = T.part('Head')
    cbox(m, (0, 0.0, 7.72), (0.95, 0.85, 0.62), 0.12, P, top=(0.9, 0.85))
    m.lathe([(0, 0), (0.22, 0), (0.2, 0.1), (0.12, 0.18), (0, 0.2)], 14, GL, M=frame((0.22, 0.1, 8.02), (0, 0, 1)))
    mk_antenna(m, (-0.3, 0.2, 8.02), 1.2)
    mk_antenna(m, (-0.12, 0.3, 8.02), 0.7)
    g = T.part('Head', glow=True)
    g.box((0, -0.43, 7.74), (0.62, 0.04, 0.1), GL)
    for x in (-0.22, 0.0, 0.22):
        g.cyl(0.05, 0.03, 10, GL, M=frame((x, -0.44, 7.56), (0, -1, 0)), x0=0.0)
    for side, s in (('Left', 1), ('Right', -1)):
        m = T.part(f'{side}Shoulder')
        cbox(m, (s * 1.72, 0.0, 7.3), (1.1, 1.2, 0.5), 0.12, P, top=(0.8, 0.85))
        cbox(m, (s * 1.72, -0.62, 7.25), (0.9, 0.08, 0.3), 0.03, K)
    # missile pods on the back (pitch bones)
    for s, tag in ((1, 'L'), (-1, 'R')):
        piv = Vector((s * 1.12, 0.95, 7.45))
        T.bone(f'Pod_{tag}', piv, piv + Vector((0, -0.6, 0)), parent='UpperChest', coll='Controls', shape='box',
               sxyz=(0.6, 0.5, 0.5), color='THEME01', z=(0, 0, 1),
               locks=dict(loc=(True,) * 3, rot=(False, True, True), scale=(True,) * 3))
        m = T.part('UpperChest')
        cbox(m, (s * 1.12, 1.0, 7.05), (0.4, 0.5, 0.5), 0.05, MT)
        pd = T.mb(f'Pod_{tag}', f'Pod_{tag}', 'hull')
        c = piv + Vector((0, -0.1, 0.42))
        cbox(pd, tuple(c), (1.05, 1.4, 0.95), 0.1, P)
        cbox(pd, tuple(c + Vector((0, -0.71, 0))), (1.0, 0.06, 0.9), 0.03, MT)
        for i in range(3):
            for j in range(3):
                tc = c + Vector((-0.3 + i * 0.3, -0.74, -0.28 + j * 0.28))
                pd.cyl(0.11, 0.08, 12, MT, M=frame(tc, (0, -1, 0)), x0=-0.06)
                pd.lathe([(0, 0.0), (0.08, 0.0), (0.06, 0.05), (0, 0.09)], 10, K, M=frame(tc + Vector((0, 0.02, 0)), (0, -1, 0)))
        for dx in (-0.53, 0.53):
            cbox(pd, tuple(c + Vector((dx, 0, 0))), (0.06, 1.3, 0.8), 0.02, K)
        add_muzzle(T, f'PodMuzzle_{tag}', f'Pod_{tag}', tuple(c + Vector((0, -0.8, 0))), (0, -1, 0), 2.2, 1.4)
    # ammo drum + feed
    m = T.part('UpperChest')
    m.cyl(0.55, 0.9, 18, MT, M=frame((-0.2, 1.65, 6.1), (1, 0, 0)))
    for k in range(7):
        m.box((-0.6 - k * 0.14, 1.4 - k * 0.05, 6.4 + k * 0.05), (0.12, 0.25, 0.08), MT)
    # gatling on the right forearm (spinning barrel bone)
    m = T.part('RightLowerArm')
    gz = D['sh_z'] + 0.68
    cbox(m, (-(ex + 0.75), 0, gz - 0.1), (1.2, 0.55, 0.45), 0.06, MT)
    m.cyl(0.35, 0.9, 16, P, M=frame((-(ex + 0.55), 0, gz), (-1, 0, 0)))
    gb = T.mb('Gatling', 'Gatling', 'hull')
    g0 = Vector((-(ex + 1.0), 0, gz))
    gb.cyl(0.18, 0.12, 14, MT, M=frame(g0, (-1, 0, 0)), x0=0.0)
    for k in range(6):
        a = k * TAU / 6
        off = Vector((0, math.cos(a) * 0.17, math.sin(a) * 0.17))
        gb.cyl(0.06, 2.3, 8, MT, M=frame(g0 + off, (-1, 0, 0)), x0=0.0)
    for xx in (0.9, 1.9):
        gb.cyl(0.27, 0.08, 14, MT, M=frame(g0 + Vector((-xx, 0, 0)), (-1, 0, 0)), x0=0.0)
    T.bone('Gatling', g0, g0 + Vector((-0.6, 0, 0)), parent='RightLowerArm', coll='Sockets', shape='circle',
           sxyz=(0.35,) * 3, color='THEME06', z=(0, 0, 1),
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    add_muzzle(T, 'Muzzle', 'Gatling', tuple(g0 + Vector((-2.35, 0, 0))), (-1, 0, 0), 2.0, 1.0)
    # targeting radar on the left forearm
    m = T.part('LeftLowerArm')
    cbox(m, (ex + 0.8, 0, D['sh_z'] + 0.6), (0.8, 0.6, 0.35), 0.05, P)
    m.lathe([(0, 0), (0.32, 0.02), (0.34, 0.08), (0, 0.1)], 16, MT, M=frame((ex + 0.9, 0, D['sh_z'] + 0.85), (0, -0.5, 1)))
    T.meta['weapons'] = dict(main='gatling', pods=['Pod_L', 'Pod_R'])


KITS = {'Aegis': (kit_aegis, dict(bulk=1.12)), 'Halberd': (kit_halberd, dict(bulk=0.92)),
        'Thunderhead': (kit_thunderhead, dict(bulk=1.02))}


def build_mech(name):
    fn, V = KITS[name]
    T = Mech(name, (LINEUP[name], 0, 0), VARIANTS[name])
    mech_bones(T)
    build_frame(T, V)
    fn(T)
    T.finish_parts()
    return T


# ------------------------------------------------------------------------------ assembly
def attach_to_rig(ob, rig):
    """parent a mesh built in mech-local coordinates to the rig (rig sits at the mech origin) and skin it."""
    ob.parent = rig
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = (0.0, 0.0, 0.0)
    ob.modifiers.new('Armature', 'ARMATURE').object = rig


def assemble_mech(T):
    rig = T.rig
    mat = final_material(f'MAT_Mech_{T.name}', T.imgs['COLOR'], T.imgs['ORM'], T.imgs['NORMAL'])
    glow = glow_material()
    vl = bpy.context.view_layer
    parts = []
    for ob, bone, group in T.objs:
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        me = ob.data
        me.materials.clear()
        me.materials.append(mat)
        me.materials.append(glow)
        me.polygons.foreach_set('material_index', [1 if group == 'glow' else 0] * len(me.polygons))
        ob.vertex_groups.clear()
        ob.vertex_groups.new(name=bone).add(list(range(len(me.vertices))), 1.0, 'REPLACE')
        parts.append(ob)
    for o in vl.objects:
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    vl.objects.active = parts[0]
    bpy.ops.object.join()
    body = vl.objects.active
    body.name = body.data.name = f'Mech_{T.name}_Body'
    mw = body.matrix_world.copy()
    body.parent = rig
    body.matrix_parent_inverse = Matrix.Identity(4)
    body.matrix_world = mw
    body.modifiers.new('Armature', 'ARMATURE').object = rig
    prune_materials(body.data)
    tri_big_ngons(body.data)
    T.body = body
    for m in T.mat_list:
        bpy.data.materials.remove(m)
    T.objs = []
    build_extras(T)
    return body


def build_extras(T):
    """muzzle-flash / jet-flame quads and the three banner meshes."""
    rig = T.rig
    T.extra_objs = []

    def quads(name, items, mat):
        verts, faces, uvs, groups = [], [], [], {}
        for (bn, pos, fwd, Lf, Wf) in items:
            v, f, u = flash_quads(pos, fwd, Lf, Wf)
            base = len(verts)
            verts += v
            faces += [tuple(i + base for i in ff) for ff in f]
            uvs += u
            groups.setdefault(bn, []).extend(range(base, base + len(v)))
        me = bpy.data.meshes.new(f'Mech_{T.name}_{name}')
        me.from_pydata(verts, [], faces)
        me.uv_layers.new(name='UVMap').data.foreach_set('uv', [c for fu in uvs for uv in fu for c in uv])
        me.materials.append(mat)
        ob = bpy.data.objects.new(f'Mech_{T.name}_{name}', me)
        T.coll.objects.link(ob)
        for bn, idx in groups.items():
            ob.vertex_groups.new(name=bn).add(idx, 1.0, 'REPLACE')
        attach_to_rig(ob, rig)
        T.extra_objs.append(ob)
    if T.flashes:
        quads('MuzzleFlash', T.flashes, flash_material())
    if T.flames:
        quads('JetFlame', T.flames, flame_material())
    # banners: 3 faction variants on the same bones
    nu, nv = 10, 12
    T.banners = []
    for fac in FACTIONS:
        rgb, alpha = banner_tex(fac, T.name)
        mat_b = banner_material(f'Banner_{T.name}_{fac}', rgb, alpha)
        verts, faces, uvs, groups = [], [], [], {}
        x0 = POLE.x + 0.1
        nside = (nu + 1) * (nv + 1)
        for side in (0, 1):                      # front and back sheets (separate verts so normals stay clean)
            for i in range(nu + 1):
                for j in range(nv + 1):
                    u, v = i / nu, j / nv
                    verts.append((x0 + u * BANNER_W, POLE.y + 0.06 * math.sin(u * math.pi * 2) * u,
                                  BANNER_TOP - v * BANNER_H))
                    f = v * 4 - 0.5              # blend between neighbouring bones around each joint
                    if f <= 0:
                        pairs = [(0, 1.0)]
                    elif f >= 3:
                        pairs = [(3, 1.0)]
                    else:
                        k = int(f)
                        pairs = [(k, 1 - (f - k)), (k + 1, f - k)]
                    for bk, ww in pairs:
                        if ww > 1e-4:
                            groups.setdefault(f'Flag_{bk}', []).append((side * nside + i * (nv + 1) + j, ww))
        for side in (0, 1):
            for i in range(nu):
                for j in range(nv):
                    a = side * nside + i * (nv + 1) + j
                    q = (a, a + 1, a + nv + 2, a + nv + 1)
                    quv = [(i / nu, 1 - j / nv), (i / nu, 1 - (j + 1) / nv), ((i + 1) / nu, 1 - (j + 1) / nv),
                           ((i + 1) / nu, 1 - j / nv)]
                    if side:
                        q, quv = tuple(reversed(q)), list(reversed(quv))
                    faces.append(q)
                    uvs += quv
        me = bpy.data.meshes.new(f'Mech_{T.name}_Banner_{fac}')
        me.from_pydata(verts, [], faces)
        me.uv_layers.new(name='UVMap').data.foreach_set('uv', [c for uv in uvs for c in uv])
        me.materials.append(mat_b)
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(me.name, me)
        T.coll.objects.link(ob)
        for bn, lst in groups.items():
            vg = ob.vertex_groups.new(name=bn)
            for vi, ww in lst:
                vg.add([vi], ww, 'ADD')
        attach_to_rig(ob, rig)
        T.banners.append(ob)


# ------------------------------------------------------------------------------ animation
def roll_bone_to(rig, name, local_axis, target_dir):
    """spin a posed bone about its own Y so that local_axis (bone space) points as close as possible to target_dir."""
    pb = rig.pose.bones[name]
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    yax = M.col[1].xyz.normalized()
    cur = (M.to_3x3() @ Vector(local_axis)).normalized()
    tgt = Vector(target_dir)
    cur_p = (cur - yax * cur.dot(yax)).normalized()
    tgt_p = (tgt - yax * tgt.dot(yax)).normalized()
    ang = math.atan2(yax.dot(cur_p.cross(tgt_p)), cur_p.dot(tgt_p))
    R = Matrix.Rotation(ang, 4, yax)
    pb.matrix = Matrix.Translation(M.translation) @ R @ M.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def mech_base(arms=66, elbow=15, curl=25):
    p = {'LeftUpperArm': [('y', arms)], 'RightUpperArm': [('y', -arms)],
         'LeftLowerArm': [('z', -elbow)], 'RightLowerArm': [('z', elbow)]}
    finger_curl(p, 'Left', curl, curl, curl * 0.7)
    finger_curl(p, 'Right', curl * 2.4, curl * 2.4, curl * 1.5)
    return p


def mech_idle(t):
    ph = TAU * t
    b = math.sin(ph)
    p = mech_base()
    p['Chest'] = [('x', -0.6 * b)]
    p['UpperChest'] = [('x', -0.8 * b)]
    p['Head'] = [('z', 6 * math.sin(ph * 0.5)), ('x', 1.0 * b)]
    p['LeftUpperArm'] = [('y', 66 + 1.0 * b)]
    p['RightUpperArm'] = [('y', -66 - 1.0 * b)]
    p['_hips'] = (0.03 * math.sin(ph * 0.5), 0, 0.03 * b)
    return p


def mech_loco(t, run=False):
    ph = TAU * t
    s, c = math.sin(ph), math.cos(ph)
    A = 30 if run else 18
    K = 58 if run else 30
    p = mech_base(62 if run else 66, 55 if run else 18)
    p['LeftUpperLeg'] = [('x', -A * s)]
    p['RightUpperLeg'] = [('x', A * s)]
    kl = 5 + K * max(0.0, math.sin(ph + 1.9)) ** 1.5
    kr = 5 + K * max(0.0, math.sin(ph + 1.9 + math.pi)) ** 1.5
    p['LeftLowerLeg'] = [('x', kl)]
    p['RightLowerLeg'] = [('x', kr)]
    p['LeftFoot'] = [('x', -7 * s - 0.25 * kl + 3)]
    p['RightFoot'] = [('x', 7 * s - 0.25 * kr + 3)]
    sw = 24 if run else 12
    p['LeftUpperArm'] = [('y', 62 if run else 66), ('x', sw * s)]
    p['RightUpperArm'] = [('y', -(62 if run else 66)), ('x', -sw * s)]
    lean = 9 if run else 2
    p['Spine'] = [('x', lean * 0.5), ('z', -(5 if run else 3) * s)]
    p['Chest'] = [('x', lean * 0.5), ('z', -(3 if run else 2) * s)]
    p['Hips'] = [('z', (6 if run else 4) * s), ('y', (3 if run else 2.5) * c)]
    p['Head'] = [('x', -lean * 0.6), ('z', (3 if run else 2) * s)]
    bob = 0.3 if run else 0.15
    p['_hips'] = (0.08 * c, 0, -bob * (0.5 - 0.5 * math.cos(2 * ph)))
    return p


def carry_matrix():
    d = Vector((0.0, -0.75, -0.66)).normalized()
    up = Vector((0, 0, 1))
    zax = (up - d * up.dot(d)).normalized()
    return Matrix((d.cross(zax), d, zax)).transposed().to_4x4()


def arm_to(rig, side, E, Wt):
    set_bone_dir(rig, f'{side}UpperArm', E)
    set_bone_dir(rig, f'{side}LowerArm', Wt)


def mech_aim(T, t):
    """combat stance: weapon arm forward (one-handed mech grip), off arm in a guard pose."""
    rig, D = T.rig, T.P
    ph = TAU * t
    br = math.sin(ph)
    reset_pose(rig)
    p = {'Hips': [('z', -6)], 'Spine': [('z', -2), ('x', 2)], 'Chest': [('z', -3)],
         'UpperChest': [('z', -3), ('x', 0.8 * br)], 'Head': [('z', 12), ('x', 3)],
         'LeftUpperLeg': [('x', -12), ('z', 3)], 'RightUpperLeg': [('x', 9), ('z', -3)],
         'LeftLowerLeg': [('x', 14)], 'RightLowerLeg': [('x', 9)], 'LeftFoot': [('x', -2)],
         'RightFoot': [('x', -10), ('z', 10)], '_hips': (0, 0.1, -0.15 + 0.02 * br)}
    finger_curl(p, 'Right', 70, 65, 40, 25)
    finger_curl(p, 'Left', 35, 35, 25, 10)
    if T.name == 'Thunderhead':
        p['Pod_L'] = [('x', -22)]
        p['Pod_R'] = [('x', -22)]
    apply_pose(rig, p)
    bpy.context.view_layer.update()
    ua, fa = D['ua'], D['fa']
    S = rig.pose.bones['RightUpperArm'].head.copy()
    if T.name == 'Thunderhead':
        E = S + Vector((0.1, -0.35, -1.0)).normalized() * ua
        arm_to(rig, 'Right', E, E + Vector((0.14, -1.0, 0.03 + 0.01 * br)).normalized() * fa)
        roll_bone_to(rig, 'RightLowerArm', (1, 0, 0), (0, 0, 1))
    else:
        tgt = Vector((-0.55, -1.75, D['sh_z'] - 0.15 + 0.02 * br))
        E, Wt = solve2(S, tgt, ua, fa, S + Vector((-0.8, 0.4, -2.0)))
        arm_to(rig, 'Right', E, Wt)
        Hr = rig.data.bones['RightHand'].matrix_local
        rig.pose.bones['RightHand'].matrix = Matrix.Translation(Wt) @ Matrix.Rotation(math.pi / 2, 4, 'Z') @             Hr.to_3x3().to_4x4()
        bpy.context.view_layer.update()
    S = rig.pose.bones['LeftUpperArm'].head.copy()
    if T.name == 'Aegis':           # shield angled across the left-front
        E = S + Vector((0.25, -0.45, -1.0)).normalized() * ua
        arm_to(rig, 'Left', E, E + Vector((-0.6, -0.8, 0.05)).normalized() * fa)
        roll_bone_to(rig, 'LeftLowerArm', (-1, 0, 0), (0.8, -0.6, 0.0))
    elif T.name == 'Halberd':       # blade arm raised in guard
        E = S + Vector((0.1, -0.3, -1.0)).normalized() * ua
        arm_to(rig, 'Left', E, E + Vector((-0.3, -1.0, 0.45)).normalized() * fa)
        roll_bone_to(rig, 'LeftLowerArm', (-1, 0, 0), (0.4, 0.0, 1.0))
    else:                           # radar arm forward
        E = S + Vector((0.25, -0.2, -1.0)).normalized() * ua
        arm_to(rig, 'Left', E, E + Vector((0.1, -1.0, 0.25)).normalized() * fa)
        roll_bone_to(rig, 'LeftLowerArm', (-1, 0, 0), (0, 0, 1))


def mech_clips(T):
    rig = T.rig
    ad = rig.animation_data_create()
    body_bones = [b.name for b in rig.data.bones if b.use_deform and not b.name.startswith(('Flag_', 'Flash', 'PodFlash'))
                  and b.name not in ('Root',) and 'Muzzle' not in b.name]
    flag_bones = [f'Flag_{k}' for k in range(4)]
    R = carry_matrix()
    holds = T.name != 'Thunderhead'
    made = []

    def keys(f, bones):
        for bn in bones:
            pb = rig.pose.bones[bn]
            pb.keyframe_insert('rotation_quaternion', frame=f)
            pb.keyframe_insert('location', frame=f)
            pb.keyframe_insert('scale', frame=f)

    def clip(name, n, fn, step=2, carry=True, bones=None):
        act = bpy.data.actions.new(f'{T.name}_{name}')
        act.use_fake_user = True
        ad.action = act
        for f in range(1, n + 2, step):
            reset_pose(rig)
            fn((f - 1) / n, f)
            if carry and holds:
                bpy.context.view_layer.update()
                wb = rig.pose.bones['WeaponR']
                wb.matrix = Matrix.Translation(wb.matrix.translation) @ R
                bpy.context.view_layer.update()
            keys(f, bones or body_bones)
        act.use_frame_range = True
        act.frame_start, act.frame_end = 1, n + 1
        slot = ad.action_slot
        ad.action = None
        tr = ad.nla_tracks.new()
        tr.name = name
        st = tr.strips.new(name, 1, act)
        st.name = name
        if slot is not None and getattr(st, 'action_slot', None) is None:
            st.action_slot = slot
        tr.mute = True
        made.append(name)

    S = 1.0 / FLASH_REST
    flash_bones = [f[0] for f in T.flashes]
    jet_bones = [f[0] for f in T.flames]

    def idle(t, f):
        apply_pose(rig, mech_idle(t))
    flash_bones = [f[0] for f in T.flashes]
    body_bones = body_bones + flash_bones
    clip('Idle', 60, idle, 4)
    clip('Walk', 48, lambda t, f: apply_pose(rig, mech_loco(t, False)), 2)
    clip('Run', 32, lambda t, f: apply_pose(rig, mech_loco(t, True)), 2)
    clip('Aim', 48, lambda t, f: mech_aim(T, t), 8, carry=False)

    def fire(t, f):
        mech_aim(T, 0.0)
        fr = f - 1
        if T.name == 'Thunderhead':
            rig.pose.bones['Gatling'].rotation_quaternion = Quaternion((0, 1, 0), TAU * fr / 4.0 * 0.5)
            on = fr % 3 == 0
            rig.pose.bones['Flash'].scale = (S,) * 3 if on else (1, 1, 1)
            for tag, start in (('L', 2), ('R', 12)):
                pf = rig.pose.bones[f'PodFlash_{tag}']
                pf.scale = (S,) * 3 if start <= fr <= start + 2 else (1, 1, 1)
        else:
            shots = (0, 8, 16) if T.name == 'Aegis' else (0,)
            k = min((fr - s0 for s0 in shots if fr >= s0), default=99)
            rig.pose.bones['Flash'].scale = (S,) * 3 if k <= 1 else (1, 1, 1)
            rec = {0: 0.0, 1: -0.35, 2: -0.3, 3: -0.18, 4: -0.08, 5: -0.02}.get(k, 0.0) * (1.6 if T.name == 'Halberd' else 1.0)
            rig.pose.bones['WeaponR'].location = (0, rec, 0)
    clip('Fire', 24, fire, 1, carry=False)

    def wave(t, f):
        p = {}
        for k in range(4):
            ph = TAU * t - k * 1.05
            p[f'Flag_{k}'] = [('x', (5.0 if k == 0 else 2.0) + (5, 8, 11, 13)[k] * math.sin(ph)),
                              ('z', 3.0 * math.sin(2 * TAU * t + k * 0.8))]
        apply_pose(rig, p)
    clip('Flag_Wave', 24, wave, 1, carry=False, bones=flag_bones)
    if jet_bones:
        def jets(t, f):
            apply_pose(rig, mech_idle(0.0))
            sc = S * (1.0 + 0.06 * math.sin(TAU * t * 3))
            for jb in jet_bones:
                rig.pose.bones[jb].scale = (sc, sc, sc)
        clip('Jets_On', 12, jets, 1, bones=body_bones + jet_bones)
    reset_pose(rig)
    ad.action = None
    return made


# ------------------------------------------------------------------------------ Unity textures + FBX export
def unity_textures(T):
    """repack the baked maps for Unity URP/Standard: MetallicSmoothness (R metal, A smooth), Occlusion, Normal."""
    out = {}
    orm = np.array(T.imgs['ORM'].pixels[:], np.float32).reshape(-1, 4)
    n = T.imgs['ORM'].size[0]
    ms = np.zeros_like(orm)
    ms[:, 0] = orm[:, 2]
    ms[:, 3] = 1.0 - orm[:, 1]
    occ = np.ones_like(orm)
    occ[:, 0] = occ[:, 1] = occ[:, 2] = orm[:, 0]
    for suffix, data in (('MetallicSmoothness', ms), ('Occlusion', occ)):
        name = f'T_Mech_{T.name}_{suffix}'
        img = bpy.data.images.get(name)
        if img:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, n, n, alpha=True)
        img.colorspace_settings.name = 'Non-Color'
        img.pixels.foreach_set(data.ravel())
        out[suffix] = save_image(img, f'{name}.png')
    return out


def export_mech_fbx(T, path):
    rig = T.rig
    old = rig.location.copy()
    rig.location = (0, 0, 0)
    reset_pose(rig)
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    rig.hide_set(False)
    rig.select_set(True)
    for c in rig.children:
        c.hide_set(False)
        c.select_set(True)
    vl.objects.active = rig
    ad = rig.animation_data
    for tr in ad.nla_tracks:
        tr.mute = False
    try:
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'}, apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=False,
            use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=False, use_armature_deform_only=True,
            add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='NULL',
            bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=True,
            bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0, path_mode='STRIP', embed_textures=False, use_custom_props=False)
    finally:
        for tr in ad.nla_tracks:
            tr.mute = True
        rig.location = old
        reset_pose(rig)
        vl.update()
