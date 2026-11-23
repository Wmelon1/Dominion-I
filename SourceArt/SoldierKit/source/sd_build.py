# Soldier Kit - male / female mannequin soldiers with full kit and a Godot-humanoid skeleton.
# Needs tk_core, tk_tank, as_tex, as_build exec'd first. Z up, front = -Y (Godot +Z), metres, origin between the feet.
from mathutils import Quaternion

SD_DIR = globals().get('SD_DIR')
TEX_DIR = os.path.join(SD_DIR, 'textures')
GLB_DIR = os.path.join(SD_DIR, 'glb')

MAN, JNT, CAM, WEB, LEA, PLY, MET, LNS, DEC, RED = range(10)
CTILE = {MAN: (0.5, 0.5), JNT: (0.5, 0.5), CAM: (0.7, 0.7), WEB: (0.12, 0.12), LEA: (0.25, 0.25),
         PLY: (0.3, 0.3), MET: (0.4, 0.4), LNS: (1, 1), RED: (0.5, 0.5)}

MALE = dict(name='Male', hips=0.98, spine=1.08, chest=1.22, upper=1.35, neck=1.52, head=1.62, top=1.80,
            clav=0.025, sh_x=0.19, sh_z=1.455, ua=0.29, fa=0.26, palm=0.09, leg_x=0.095, hip_z=0.93, knee=0.50,
            ankle=0.085, pel=(0.165, 0.105), waist=(0.13, 0.095), ribs=(0.165, 0.11), chestr=(0.185, 0.12),
            arm_r=0.052, fore_r=0.045, thigh_r=0.085, calf_r=0.056, neck_r=0.052, headr=(0.082, 0.097, 0.113),
            bust=False, bun=False, fing=1.0)
FEMALE = dict(name='Female', hips=0.925, spine=1.02, chest=1.155, upper=1.275, neck=1.435, head=1.53, top=1.70,
              clav=0.022, sh_x=0.172, sh_z=1.375, ua=0.27, fa=0.24, palm=0.082, leg_x=0.10, hip_z=0.88, knee=0.475,
              ankle=0.085, pel=(0.172, 0.11), waist=(0.115, 0.085), ribs=(0.145, 0.10), chestr=(0.158, 0.103),
              arm_r=0.045, fore_r=0.039, thigh_r=0.086, calf_r=0.052, neck_r=0.045, headr=(0.077, 0.092, 0.107),
              bust=True, bun=True, fing=0.92)
FINGERS = [('Index', -0.028, (0.042, 0.026, 0.02), 0.0095), ('Middle', -0.009, (0.046, 0.029, 0.021), 0.0098),
           ('Ring', 0.01, (0.043, 0.027, 0.02), 0.0092), ('Little', 0.028, (0.034, 0.021, 0.018), 0.0082)]


# ------------------------------------------------------------------------------ textures / materials
def tex_camo(n=1024):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    col = solid(n, n, (0.45, 0.43, 0.31))
    for seed, cell, thr, c in ((301, 3, 0.52, (0.24, 0.31, 0.17)), (302, 4, 0.58, (0.37, 0.26, 0.15)),
                               (303, 6, 0.66, (0.08, 0.08, 0.06))):
        m = sstep(thr - 0.01, thr + 0.01, fbm(n, n, cell, cell, 5, seed, 0.55))
        col = lerp(col, c, m)
    weave = 0.5 + 0.25 * np.sin(u * np.pi * 2 * 420) + 0.25 * np.sin(v * np.pi * 2 * 420)
    col *= (0.9 + 0.12 * fbm(n, n, 16, 16, 3, 304) + 0.04 * weave)[..., None]
    H = weave * 0.3 + fbm(n, n, 24, 24, 3, 305) * 0.3
    return pack(col, ao_from_height(H, 2, 2.0), 0.82 + 0.0 * H, np.zeros_like(H), H, 3.0)


def tex_webbing(n=512):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    rib = 0.5 + 0.5 * np.sin(v * np.pi * 2 * 64)
    col = solid(n, n, (0.31, 0.32, 0.22)) * (0.86 + 0.14 * rib + 0.08 * fbm(n, n, 8, 8, 3, 311))[..., None]
    H = rib * 0.6 + fbm(n, n, 32, 32, 2, 312) * 0.2
    return pack(col, ao_from_height(H, 2, 2.0), 0.85 + 0.0 * H, np.zeros_like(H), H, 4.0)


def tex_leather(n=512):
    grain = fbm(n, n, 48, 48, 3, 321)
    crease = sstep(0.62, 0.7, fbm(n, n, 6, 12, 4, 322))
    col = solid(n, n, (0.12, 0.093, 0.07)) * (0.85 + 0.3 * grain)[..., None]
    col = lerp(col, (0.2, 0.17, 0.13), crease * 0.4)
    H = grain * 0.5 - crease * 0.4
    return pack(col, ao_from_height(H, 2, 2.0), 0.5 + 0.15 * grain + crease * 0.1, np.zeros_like(H), H, 3.0)


def tex_mannequin(n=512):
    f = fbm(n, n, 4, 4, 5, 331)
    col = solid(n, n, (0.74, 0.72, 0.68)) * (0.96 + 0.06 * f)[..., None]
    H = fbm(n, n, 64, 64, 2, 332) * 0.15
    return pack(col, np.ones_like(f) * 0.97, 0.42 + 0.06 * f, np.zeros_like(f), H, 1.5)


def tex_polymer(n=512):
    st = fbm(n, n, 96, 96, 2, 341)
    col = solid(n, n, (0.065, 0.066, 0.07)) * (0.85 + 0.3 * st)[..., None]
    wear = sstep(0.7, 0.8, fbm(n, n, 6, 6, 4, 342))
    col = lerp(col, (0.16, 0.16, 0.16), wear * 0.5)
    return pack(col, np.ones_like(st) * 0.96, 0.58 + 0.1 * st - wear * 0.1, np.zeros_like(st), st * 0.6, 2.5)


def build_char_materials():
    M = [None] * 10
    M[MAN] = tex_material('Mannequin', tex_mannequin)
    M[JNT] = flat_material('MAT_MannequinJoint', (0.40, 0.41, 0.44), 0.35, metal=0.35)
    M[CAM] = tex_material('CamoFabric', tex_camo)
    M[WEB] = tex_material('Webbing', tex_webbing)
    M[LEA] = tex_material('Leather', tex_leather)
    M[PLY] = tex_material('Polymer', tex_polymer)
    M[MET] = tex_material('DarkMetal', tex_darkmetal)
    M[LNS] = flat_material('MAT_Lens', (0.03, 0.06, 0.05), 0.05, metal=0.2)
    M[DEC] = decal_material()
    M[RED] = flat_material('MAT_RedPaint', (0.5, 0.07, 0.05), 0.45)
    return M


# ------------------------------------------------------------------------------ shape helpers
def ring_pts(c, ax_a, ax_b, ra, rb, segs, n=2.0):
    e = 2.0 / n
    out = []
    for k in range(segs):
        p = TAU * k / segs
        ca, sa = math.cos(p), math.sin(p)
        out.append(c + ax_a * (ra * math.copysign(abs(ca) ** e, ca)) + ax_b * (rb * math.copysign(abs(sa) ** e, sa)))
    return out


def rloft(mb, rings, mat):
    vr = [[mb.bm.verts.new(p) for p in r] for r in rings]
    for i in range(len(vr) - 1):
        m = mat[i] if isinstance(mat, (list, tuple)) else mat
        a, b = vr[i], vr[i + 1]
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for j in range(len(b)):
                mb.face((a[0], b[j], b[(j + 1) % len(b)]), m)
        elif len(b) == 1:
            for j in range(len(a)):
                mb.face((a[(j + 1) % len(a)], a[j], b[0]), m)
        else:
            for j in range(len(a)):
                k = (j + 1) % len(a)
                mb.face((a[j], a[k], b[k], b[j]), m)


def vloft(mb, cx, cy, prof, segs=18, mat=MAN, n=2.0):
    """vertical loft: prof = [(z, rx, ry, dy?)]; r = 0 -> pole."""
    X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
    rings = []
    for p in prof:
        z, rx, ry = p[0], p[1], p[2]
        dy = p[3] if len(p) > 3 else 0.0
        c = Vector((cx, cy + dy, z))
        rings.append([c] if rx <= 1e-6 else ring_pts(c, X, Y, rx, ry, segs, n))
    rloft(mb, rings, mat)


def aloft(mb, A, d, prof, ax_a, ax_b, segs=16, mat=MAN, n=2.0):
    """loft along direction d from A: prof = [(s, ra, rb, offset?)]."""
    A, d = Vector(A), Vector(d).normalized()
    ax_a, ax_b = Vector(ax_a).normalized(), Vector(ax_b).normalized()
    rings = []
    for p in prof:
        c = A + d * p[0] + (Vector(p[3]) if len(p) > 3 else Vector())
        rings.append([c] if p[1] <= 1e-6 else ring_pts(c, ax_a, ax_b, p[1], p[2], segs, n))
    rloft(mb, rings, mat)


def ploft(mb, prof, ax_a, ax_b, segs=16, mat=LEA, n=2.6):
    """path loft: prof = [(center Vector, ra, rb)]."""
    rings = [[Vector(c)] if ra <= 1e-6 else ring_pts(Vector(c), Vector(ax_a), Vector(ax_b), ra, rb, segs, n)
             for c, ra, rb in prof]
    rloft(mb, rings, mat)


def ellipsoid(mb, c, r, segs=16, nr=8, mat=MAN):
    c = Vector(c)
    prof = []
    for i in range(nr + 1):
        th = -math.pi / 2 + math.pi * i / nr
        k = math.cos(th)
        prof.append((c.z + r[2] * math.sin(th), r[0] * k if 0 < i < nr else 0.0, r[1] * k, 0.0))
    vloft(mb, c.x, c.y, prof, segs, mat)


def capsule(mb, A, B, r, segs=6, mat=LEA):
    A, B = Vector(A), Vector(B)
    d = B - A
    L = d.length
    d.normalize()
    hint = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    a = d.cross(hint).normalized()
    b = d.cross(a)
    aloft(mb, A, d, [(-r * 0.7, 0, 0), (-r * 0.4, r * 0.8, r * 0.8), (0, r, r), (L, r * 0.93, r * 0.93),
                     (L + r * 0.4, r * 0.75, r * 0.75), (L + r * 0.7, 0, 0)], a, b, segs, mat)


# ------------------------------------------------------------------------------ skeleton layout
def finger_chain(P, side):
    """returns {bone: (head, tail)} for one hand."""
    s = 1 if side == 'Left' else -1
    wx = P['sh_x'] + P['ua'] + P['fa']
    kx = wx + P['palm']
    z = P['sh_z']
    f = P['fing']
    out = {}
    for name, y, lens, r in FINGERS:
        p = Vector((s * kx, y * f, z - 0.004))
        for seg, L in zip(('Proximal', 'Intermediate', 'Distal'), lens):
            q = p + Vector((s * L * f, 0, 0))
            out[f'{side}{name}{seg}'] = (p, q)
            p = q
    p = Vector((s * (wx + 0.012), -0.022 * f, z - 0.008))
    for seg, L, dv in (('Metacarpal', 0.04, (0.55, -0.75, -0.25)), ('Proximal', 0.033, (0.45, -0.85, -0.2)),
                       ('Distal', 0.027, (0.4, -0.9, -0.15))):
        dvec = Vector((s * dv[0], dv[1], dv[2])).normalized()
        q = p + dvec * L * f
        out[f'{side}Thumb{seg}'] = (p, q)
        p = q
    return out


def soldier_bones(T, P):
    B = T.bone
    rot_only = dict(loc=(True,) * 3, scale=(True,) * 3)
    B('Root', (0, 0, 0), (0, 0, 0.2), z=(0, -1, 0), shape='circle', sxyz=(0.45,) * 3, color='THEME09')
    B('Hips', (0, 0, P['hips']), (0, 0, P['spine']), parent='Root', z=(0, -1, 0), shape='circle', sxyz=(0.26,) * 3,
      color='THEME09', locks=dict(scale=(True,) * 3))
    chain = [('Spine', 'spine', 'chest', 'Hips'), ('Chest', 'chest', 'upper', 'Spine'),
             ('UpperChest', 'upper', 'neck', 'Chest'), ('Neck', 'neck', 'head', 'UpperChest'),
             ('Head', 'head', 'top', 'Neck')]
    for name, a, b, par in chain:
        B(name, (0, 0, P[a]), (0, 0, P[b]), parent=par, z=(0, -1, 0), shape='circle', sxyz=(0.2,) * 3,
          color='THEME03', locks=rot_only)
    ex, wx = P['sh_x'] + P['ua'], P['sh_x'] + P['ua'] + P['fa']
    for side, s in (('Left', 1), ('Right', -1)):
        col = 'THEME01' if s > 0 else 'THEME04'
        B(f'{side}Shoulder', (s * P['clav'], 0, P['sh_z'] + 0.02), (s * P['sh_x'], 0, P['sh_z']), parent='UpperChest',
          z=(0, -1, 0), shape='circle', sxyz=(0.06,) * 3, color=col, locks=rot_only)
        B(f'{side}UpperArm', (s * P['sh_x'], 0, P['sh_z']), (s * ex, 0, P['sh_z']), parent=f'{side}Shoulder',
          z=(0, -1, 0), shape='circle', sxyz=(0.08,) * 3, color=col, locks=rot_only)
        B(f'{side}LowerArm', (s * ex, 0, P['sh_z']), (s * wx, 0, P['sh_z']), parent=f'{side}UpperArm',
          z=(0, -1, 0), shape='circle', sxyz=(0.07,) * 3, color=col, locks=rot_only)
        B(f'{side}Hand', (s * wx, 0, P['sh_z']), (s * (wx + P['palm']), 0, P['sh_z']), parent=f'{side}LowerArm',
          z=(0, -1, 0), shape='circle', sxyz=(0.06,) * 3, color=col, locks=rot_only)
        fc = finger_chain(P, side)
        for name in fc:
            h, t = fc[name]
            if name.endswith('Proximal') and 'Thumb' not in name or name.endswith('Metacarpal'):
                par = f'{side}Hand'
            else:
                base = name.replace('Distal', 'Intermediate') if 'Thumb' not in name else \
                    name.replace('Distal', 'Proximal')
                if name.endswith('Intermediate'):
                    base = name.replace('Intermediate', 'Proximal')
                if 'Thumb' in name and name.endswith('Proximal'):
                    base = name.replace('Proximal', 'Metacarpal')
                par = base
            B(name, h, t, parent=par, z=(0, 0, 1), coll='Fingers', shape='circle', sxyz=(0.012,) * 3, color=col,
              locks=rot_only)
        lx = s * P['leg_x']
        B(f'{side}UpperLeg', (lx, 0, P['hip_z']), (lx, 0, P['knee']), parent='Hips', z=(0, -1, 0), shape='circle',
          sxyz=(0.1,) * 3, color=col, locks=rot_only)
        B(f'{side}LowerLeg', (lx, 0, P['knee']), (lx, 0.012, P['ankle']), parent=f'{side}UpperLeg', z=(0, -1, 0),
          shape='circle', sxyz=(0.08,) * 3, color=col, locks=rot_only)
        B(f'{side}Foot', (lx, 0.012, P['ankle']), (lx, -0.11, 0.03), parent=f'{side}LowerLeg', z=(0, 0, 1),
          shape='circle', sxyz=(0.06,) * 3, color=col, locks=rot_only)
        B(f'{side}Toes', (lx, -0.11, 0.03), (lx, -0.185, 0.03), parent=f'{side}Foot', z=(0, 0, 1), shape='circle',
          sxyz=(0.05,) * 3, color=col, locks=rot_only)
        tag = side[0]
        B(f'IK_Foot_{tag}', (lx, 0.012, P['ankle']), (lx, -0.15, P['ankle']), parent='Root', deform=False, coll='IK',
          shape='box', sxyz=(0.06, 0.12, 0.03), color='THEME02')
        B(f'IK_Knee_{tag}', (lx, -0.5, P['knee']), (lx, -0.6, P['knee']), parent='Root', deform=False, coll='IK',
          shape='diamond', sxyz=(0.04,) * 3, color='THEME02')
        B(f'IK_Hand_{tag}', (s * wx, 0, P['sh_z']), (s * (wx + 0.12), 0, P['sh_z']), parent='Root', deform=False,
          coll='IK', shape='box', sxyz=(0.04, 0.06, 0.04), color='THEME02')
        B(f'IK_Elbow_{tag}', (s * ex, 0.45, P['sh_z']), (s * ex, 0.55, P['sh_z']), parent='Root', deform=False,
          coll='IK', shape='diamond', sxyz=(0.04,) * 3, color='THEME02')
    W = Vector((-(wx + P['palm'] * 0.5), 0.0, P['sh_z'] - 0.045))
    B('WeaponR', W, W + Vector((0, -0.15, 0)), parent='RightHand', z=(0, 0, 1), coll='Sockets', shape='diamond',
      sxyz=(0.04,) * 3, color='THEME06', locks=dict(scale=(True,) * 3))
    mz = W + Vector((0, -0.76, 0.07))
    B('Muzzle', mz, mz + Vector((0, -0.1, 0)), parent='WeaponR', coll='Sockets', shape='diamond', sxyz=(0.02,) * 3,
      color='THEME06', locks=dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3))
    T.weapon_rest = W


# ------------------------------------------------------------------------------ body
def build_body(T, P):
    def mb(bone):
        return T.mb(f'BODY__{bone}', bone, 'Body')
    hz, sp, ch, up, nk, hd = P['hip_z'], P['spine'], P['chest'], P['upper'], P['neck'], P['head']
    prx, pry = P['pel']
    wrx, wry = P['waist']
    rrx, rry = P['ribs']
    crx, cry = P['chestr']
    nr = P['neck_r']
    vloft(mb('Hips'), 0, 0, [(hz - 0.10, 0, 0), (hz - 0.09, 0.07, 0.055), (hz - 0.05, prx * 0.82, pry * 0.88, 0.004),
                             (hz + 0.01, prx, pry, 0.008), (sp - 0.03, prx * 0.92, pry * 0.95),
                             (sp + 0.02, wrx * 1.02, wry), (sp + 0.03, 0, 0)])
    vloft(mb('Spine'), 0, 0, [(sp - 0.03, 0, 0), (sp - 0.02, wrx, wry), (sp + 0.06, wrx * 1.03, wry * 1.03),
                              (ch - 0.01, rrx * 0.93, rry * 0.95), (ch + 0.02, rrx * 0.88, rry * 0.9), (ch + 0.03, 0, 0)])
    vloft(mb('Chest'), 0, 0, [(ch - 0.02, 0, 0), (ch - 0.01, rrx * 0.95, rry * 0.96), (ch + 0.06, rrx, rry),
                              (up, crx * 0.97, cry), (up + 0.02, 0, 0)])
    vloft(mb('UpperChest'), 0, 0, [(up - 0.02, 0, 0), (up - 0.01, crx * 0.98, cry), (up + 0.06, crx * 1.02, cry * 1.02),
                                   (P['sh_z'] + 0.01, crx * 0.96, cry * 0.85), (nk - 0.01, nr * 2.4, nr * 1.7),
                                   (nk + 0.005, 0, 0)])
    if P['bust']:
        for s in (1, -1):
            ellipsoid(mb('UpperChest'), (s * 0.068, -cry * 0.72, up + 0.03), (0.06, 0.052, 0.056), 14, 7)
    vloft(mb('Neck'), 0, 0, [(nk - 0.02, 0, 0), (nk - 0.015, nr, nr * 0.95), (hd + 0.02, nr * 0.95, nr * 0.9),
                             (hd + 0.03, 0, 0)], 14)
    hx, hy, hzr = P['headr']
    h = mb('Head')
    ellipsoid(h, (0, -0.005, hd + 0.09), (hx, hy, hzr), 20, 12)
    ellipsoid(h, (0, -0.028, hd + 0.035), (hx * 0.74, hy * 0.72, 0.055), 16, 8)
    h.box((0, -(hy + 0.0), hd + 0.075), (0.022, 0.03, 0.045), MAN, top=(0.45, 0.5))
    ellipsoid(h, (0, -hy * 0.82, hd + 0.118), (hx * 0.82, 0.02, 0.016), 14, 6)
    for s in (1, -1):
        ellipsoid(h, (s * (hx + 0.002), 0.004, hd + 0.08), (0.012, 0.022, 0.03), 10, 6)
    if P['bun']:
        ellipsoid(h, (0, hy + 0.018, hd + 0.05), (0.042, 0.04, 0.045), 14, 8)
        vloft(h, 0, hy - 0.005, [(hd + 0.03, 0, 0), (hd + 0.03, 0.03, 0.02), (hd + 0.07, 0.03, 0.02), (hd + 0.07, 0, 0)],
              12, WEB)
    ex, wx = P['sh_x'] + P['ua'], P['sh_x'] + P['ua'] + P['fa']
    ar, fr = P['arm_r'], P['fore_r']
    Zv, Yv = (0, 0, 1), (0, 1, 0)
    for side, s in (('Left', 1), ('Right', -1)):
        ellipsoid(mb(f'{side}UpperArm'), (s * P['sh_x'], 0, P['sh_z']), (ar * 1.12,) * 3, 14, 8, JNT)
        aloft(mb(f'{side}UpperArm'), (s * P['sh_x'], 0, P['sh_z']), (s, 0, 0),
              [(-0.01, 0, 0), (0.0, ar * 0.95, ar), (0.06, ar * 1.05, ar * 1.07), (P['ua'] - 0.08, ar * 0.88, ar * 0.9),
               (P['ua'] - 0.015, ar * 0.78, ar * 0.78), (P['ua'] - 0.005, 0, 0)], Zv, Yv)
        ellipsoid(mb(f'{side}LowerArm'), (s * ex, 0, P['sh_z']), (ar * 0.8,) * 3, 12, 6, JNT)
        aloft(mb(f'{side}LowerArm'), (s * ex, 0, P['sh_z']), (s, 0, 0),
              [(0.005, 0, 0), (0.015, fr * 0.85, fr * 0.85), (0.07, fr, fr * 1.06), (P['fa'] - 0.035, fr * 0.72, fr * 0.78),
               (P['fa'] - 0.005, 0, 0)], Zv, Yv)
        aloft(mb(f'{side}LowerArm'), (s * ex, 0, P['sh_z']), (s, 0, 0),
              [(P['fa'] - 0.07, 0, 0), (P['fa'] - 0.07, fr * 0.84, fr * 0.9), (P['fa'] - 0.005, fr * 0.8, fr * 0.86),
               (P['fa'] - 0.005, 0, 0)], Zv, Yv, 14, LEA)
        hb = mb(f'{side}Hand')
        aloft(hb, (s * wx, 0, P['sh_z']), (s, 0, 0),
              [(-0.012, 0, 0), (0.0, 0.02, 0.03), (0.03, 0.024, 0.042), (P['palm'] - 0.01, 0.021, 0.044),
               (P['palm'] + 0.004, 0, 0)], Zv, Yv, 14, LEA)
        hb.box((s * (wx + P['palm'] * 0.72), 0, P['sh_z'] + 0.021), (0.03, 0.075, 0.012), PLY)
        for name, (a, b) in finger_chain(P, side).items():
            rr = next((f[3] for f in FINGERS if f[0] in name), 0.0105) * P['fing']
            capsule(mb(name), a, b, rr * (0.92 if 'Distal' in name else 1.0), 7, LEA)
        lx = s * P['leg_x']
        tr, cr, kn, an = P['thigh_r'], P['calf_r'], P['knee'], P['ankle']
        vloft(mb(f'{side}UpperLeg'), lx, 0, [(hz + 0.03, 0, 0), (hz + 0.02, tr * 0.95, tr * 0.95), (hz - 0.06, tr, tr * 1.02),
                                             (kn + 0.12, tr * 0.72, tr * 0.76), (kn + 0.03, tr * 0.6, tr * 0.62),
                                             (kn + 0.015, 0, 0)])
        ellipsoid(mb(f'{side}LowerLeg'), (lx, 0, kn), (tr * 0.58,) * 3, 14, 8, JNT)
        vloft(mb(f'{side}LowerLeg'), lx, 0, [(kn - 0.015, 0, 0), (kn - 0.03, cr * 0.9, cr * 0.9),
                                             (kn - 0.12, cr, cr * 1.05, 0.008), (an + 0.12, cr * 0.68, cr * 0.7),
                                             (an + 0.05, 0, 0)])
        # boots
        vloft(mb(f'{side}LowerLeg'), lx, 0.008, [(an + 0.02, 0, 0), (an + 0.02, 0.048, 0.054), (an + 0.18, 0.05, 0.056),
                                                 (an + 0.215, 0.054, 0.058), (an + 0.22, 0, 0)], 16, LEA, 2.4)
        vloft(mb(f'{side}LowerLeg'), lx, 0.008, [(an + 0.185, 0, 0), (an + 0.185, 0.057, 0.061), (an + 0.213, 0.057, 0.061),
                                                 (an + 0.213, 0, 0)], 16, WEB, 2.4)
        for k in range(3):
            mb(f'{side}LowerLeg').box((lx, -0.05, an + 0.07 + k * 0.045), (0.045, 0.01, 0.008), WEB)
        ft = mb(f'{side}Foot')
        X, Zz = (1, 0, 0), (0, 0, 1)
        ploft(ft, [((lx, 0.075, 0.05), 0, 0), ((lx, 0.07, 0.05), 0.042, 0.045), ((lx, 0.03, 0.06), 0.047, 0.058),
                   ((lx, -0.03, 0.055), 0.05, 0.05), ((lx, -0.09, 0.04), 0.052, 0.038), ((lx, -0.095, 0.04), 0, 0)],
              X, Zz, 16, LEA)
        ft.box((lx, -0.01, 0.012), (0.105, 0.17, 0.024), PLY)
        for k in range(4):
            ft.box((lx, 0.0 - k * 0.022, 0.104 - k * 0.006), (0.06, 0.012, 0.008), WEB)
        tt = mb(f'{side}Toes')
        ploft(tt, [((lx, -0.085, 0.038), 0, 0), ((lx, -0.09, 0.038), 0.052, 0.038), ((lx, -0.15, 0.033), 0.048, 0.031),
                   ((lx, -0.185, 0.03), 0.035, 0.024), ((lx, -0.195, 0.03), 0, 0)], X, Zz, 16, LEA)
        tt.box((lx, -0.142, 0.01), (0.1, 0.1, 0.02), PLY)
    # shoulder patch (left arm) with its own UVs
    c = Vector((P['sh_x'] + 0.1, 0.0, P['sh_z'] + ar * 1.02 + 0.003))
    sz = 0.035
    T.extra_parts.append(quad_part(T, 'Patch', [c + Vector((-sz, -sz, 0)), c + Vector((sz, -sz, 0)),
                                                c + Vector((sz, sz, 0)), c + Vector((-sz, sz, 0))],
                                   'LeftUpperArm', 'Body'))


def quad_part(T, key, pts, bone, group, mat=DEC):
    me = bpy.data.meshes.new(f'{T.name}_{key}')
    me.from_pydata([tuple(p) for p in pts], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name='UVMap').data.foreach_set('uv', [0, 0, 1, 0, 1, 1, 0, 1])
    for m in T.mat_list:
        me.materials.append(m)
    me.polygons[0].material_index = mat
    ob = bpy.data.objects.new(f'{T.name}_{key}', me)
    T.coll.objects.link(ob)
    ob.location = T.origin
    return (ob, bone, group)


# ------------------------------------------------------------------------------ gear
def build_gear(T, P):
    hz, sp, ch, up, nk, hd = P['hip_z'], P['spine'], P['chest'], P['upper'], P['neck'], P['head']
    prx, pry = P['pel']
    rrx, rry = P['ribs']
    crx, cry = P['chestr']
    bust = 0.06 if P['bust'] else 0.0
    # --- plate carrier (spine-weighted)
    v = T.mb('VEST__SPINE', 'SPINE', 'Vest')
    z0, z1 = ch - 0.10, up + 0.075
    vloft(v, 0, 0, [(z0, 0, 0), (z0, rrx * 0.93 + 0.02, rry * 0.95 + 0.032), (z0 + 0.015, rrx * 0.93 + 0.024, rry * 0.95 + 0.036),
                    (ch + 0.05, rrx + 0.024, rry + 0.038), (up, crx * 0.97 + 0.024, cry + 0.04 + bust / 2, -bust / 2),
                    (up + 0.035, crx * 0.95 + 0.024, cry + 0.04 + bust / 2, -bust / 2),
                    (z1 - 0.015, crx * 0.9 + 0.022, cry + 0.036), (z1, crx * 0.9 + 0.018, cry + 0.032), (z1, 0, 0)],
          24, CAM, 3.2)
    vf = -(rry + 0.038)
    for k in range(4):
        v.box((0, rry + 0.04, z0 + 0.05 + k * 0.04), (0.26, 0.008, 0.018), WEB)
    us = T.mb('VEST__UpperChest', 'UpperChest', 'Vest')
    for s in (1, -1):
        beam(us, (s * 0.105, -(cry + 0.035 + bust * 0.3), z1 - 0.01), (s * 0.115, 0.0, P['sh_z'] + 0.065), 0.055, 0.012, WEB)
        beam(us, (s * 0.115, 0.0, P['sh_z'] + 0.065), (s * 0.105, cry + 0.035, z1 - 0.01), 0.055, 0.012, WEB)
    cv = T.mb('VEST__Chest', 'Chest', 'Vest')
    sc = crx / 0.185
    for x in (-0.08, 0.0, 0.08):
        x *= sc
        cv.box((x, vf - 0.022, ch), (0.072, 0.044, 0.125), CAM)
        cv.box((x, vf - 0.024, ch + 0.06), (0.076, 0.05, 0.03), CAM)
        cv.box((x, vf - 0.047, ch + 0.015), (0.05, 0.006, 0.012), WEB)
        cv.box((x, vf - 0.03, ch + 0.088), (0.06, 0.02, 0.02), PLY)
    ay = -(cry + 0.04 + bust + 0.015)
    us.box((0, ay, up + 0.02), (0.16, 0.03, 0.07), CAM)
    us.box((0, ay - 0.002, up + 0.075), (0.12, 0.03, 0.025), WEB)
    T.extra_parts.append(quad_part(T, 'IFFPatch', [Vector((-0.025, ay - 0.0165, up - 0.005)), Vector((0.025, ay - 0.0165, up - 0.005)),
                                                   Vector((0.025, ay - 0.0165, up + 0.045)), Vector((-0.025, ay - 0.0165, up + 0.045))],
                                   'UpperChest', 'Vest'))
    rx_ = crx + 0.045
    cv.box((rx_, 0.01, ch + 0.04), (0.045, 0.075, 0.14), CAM)
    cv.box((rx_, 0.01, ch + 0.13), (0.04, 0.06, 0.04), PLY)
    cv.cyl(0.006, 0.26, 5, MET, M=frame((rx_ + 0.005, 0.025, ch + 0.15), (0.05, 0.25, 1.0)), x0=0.0)
    beam(cv, (rx_ - 0.02, -0.02, ch + 0.12), (0.06, vf - 0.03, up + 0.02), 0.008, 0.008, PLY)
    cv.box((0.065, vf - 0.035, up + 0.03), (0.03, 0.02, 0.05), PLY)
    for dy in (-0.04, 0.035):
        vloft(cv, -rx_, dy, [(ch - 0.02, 0, 0), (ch - 0.02, 0.032, 0.032), (ch + 0.065, 0.032, 0.032), (ch + 0.065, 0, 0)], 12, CAM)
        vloft(cv, -rx_, dy, [(ch + 0.065, 0, 0), (ch + 0.065, 0.034, 0.034), (ch + 0.08, 0.03, 0.03), (ch + 0.08, 0, 0)], 12, CAM)
    cv.box((0, rry + 0.04 + 0.024, ch + 0.06), (0.22, 0.045, 0.30), CAM)
    us.box((0, cry + 0.04 + 0.012, z1 - 0.03), (0.08, 0.02, 0.03), WEB)
    # --- battle belt (+ holster on the right thigh)
    b = T.mb('BELT__Hips', 'Hips', 'Belt')
    b0 = P['hips'] - 0.01
    bx, by = prx * 0.97 + 0.014, pry * 0.97 + 0.016
    vloft(b, 0, 0, [(b0, 0, 0), (b0, bx, by), (b0 + 0.05, bx, by), (b0 + 0.05, 0, 0)], 24, WEB, 2.4)
    b.box((0, -(by + 0.006), b0 + 0.025), (0.055, 0.014, 0.042), MET)
    vloft(b, bx * 0.78, by * 0.6 + 0.04, [(b0 - 0.11, 0, 0), (b0 - 0.11, 0.05, 0.045), (b0 + 0.04, 0.05, 0.045),
                                         (b0 + 0.04, 0, 0)], 14, CAM)
    b.cyl(0.02, 0.02, 10, PLY, M=frame((bx * 0.78, by * 0.6 + 0.04, b0 + 0.04), (0, 0, 1)), x0=0.0)
    b.box((-bx * 0.62, by + 0.025, b0 - 0.03), (0.12, 0.05, 0.14), CAM)
    b.box((0, by + 0.028, b0 + 0.005), (0.13, 0.05, 0.09), CAM)
    b.box((0, by + 0.054, b0 + 0.005), (0.05, 0.004, 0.014), RED)
    b.box((0, by + 0.054, b0 + 0.005), (0.014, 0.004, 0.05), RED)
    b.box((bx * 0.86, -by * 0.55, b0 - 0.08), (0.03, 0.022, 0.16), PLY)
    b.box((bx * 0.86, -by * 0.55, b0 + 0.02), (0.022, 0.02, 0.06), MET)
    b.box((bx * 0.45, -(by + 0.022), b0 - 0.01), (0.07, 0.04, 0.09), CAM)
    hl = T.mb('BELT__RightUpperLeg', 'RightUpperLeg', 'Belt')
    lx, tr = P['leg_x'], P['thigh_r']
    hxp = -(lx + tr + 0.02)
    hl.box((hxp, 0.0, hz - 0.13), (0.045, 0.10, 0.20), PLY, top=(1, 0.8))
    hl.box((hxp, -0.022, hz - 0.01), (0.032, 0.045, 0.08), PLY, top=(1, 0.8))
    hl.box((hxp, 0.012, hz - 0.0), (0.028, 0.07, 0.03), MET)
    for zz, rr in ((hz - 0.08, tr * 0.98), (hz - 0.22, tr * 0.86)):
        vloft(hl, -lx, 0.0, [(zz, 0, 0), (zz, rr + 0.006, rr * 1.02 + 0.006), (zz + 0.025, rr + 0.006, rr * 1.02 + 0.006),
                             (zz + 0.025, 0, 0)], 16, WEB)
    beam(b, (-bx * 0.92, 0.0, b0), (hxp, 0.0, hz - 0.03), 0.035, 0.008, WEB)
    # --- knee / elbow pads
    ex = P['sh_x'] + P['ua']
    for side, s in (('Left', 1), ('Right', -1)):
        kp = T.mb(f'PADS__{side}LowerLeg', f'{side}LowerLeg', 'Pads')
        ellipsoid(kp, (s * lx, -0.045, P['knee'] - 0.01), (0.058, 0.03, 0.075), 14, 8, PLY)
        vloft(kp, s * lx, 0, [(P['knee'] - 0.095, 0, 0), (P['knee'] - 0.095, P['calf_r'] * 0.98, P['calf_r'] * 1.02),
                              (P['knee'] - 0.07, P['calf_r'] * 0.98, P['calf_r'] * 1.02), (P['knee'] - 0.07, 0, 0)], 16, WEB)
        ep = T.mb(f'PADS__{side}LowerArm', f'{side}LowerArm', 'Pads')
        ellipsoid(ep, (s * (ex + 0.015), 0.038, P['sh_z']), (0.052, 0.022, 0.044), 12, 6, PLY)
        aloft(ep, (s * ex, 0, P['sh_z']), (s, 0, 0), [(0.06, 0, 0), (0.06, P['fore_r'] * 1.02, P['fore_r'] * 1.08),
                                                     (0.08, P['fore_r'] * 1.02, P['fore_r'] * 1.08), (0.08, 0, 0)],
              (0, 0, 1), (0, 1, 0), 14, WEB)
    # --- helmet
    h = T.mb('HELMET__Head', 'Head', 'Helmet')
    hx, hy, hzr = P['headr']
    hb = hd + 0.055
    vloft(h, 0, 0.006, [(hb, 0, 0), (hb, hx + 0.034, hy + 0.04), (hb + 0.012, hx + 0.04, hy + 0.046),
                        (hb + 0.06, hx + 0.041, hy + 0.046), (hb + 0.12, hx + 0.026, hy + 0.031),
                        (hb + 0.158, hx * 0.56, hy * 0.6), (hb + 0.174, 0, 0)], 22, CAM)
    vloft(h, 0, 0.006, [(hb - 0.004, 0, 0), (hb - 0.004, hx + 0.037, hy + 0.043), (hb + 0.014, hx + 0.042, hy + 0.048),
                        (hb + 0.014, 0, 0)], 22, WEB)
    vloft(h, 0, 0.006, [(hb + 0.058, 0, 0), (hb + 0.058, hx + 0.045, hy + 0.05), (hb + 0.084, hx + 0.044, hy + 0.049),
                        (hb + 0.084, 0, 0)], 22, WEB)
    for s in (1, -1):
        c = Vector((s * 0.036, -(hy + 0.05), hb + 0.072))
        h.cyl(0.031, 0.018, 14, PLY, M=frame(c, (0, -1, 0.15)), x0=0.0)
        h.cyl(0.026, 0.02, 14, LNS, M=frame(c, (0, -1, 0.15)), x0=0.001)
        h.box((s * (hx + 0.043), 0.0, hb + 0.045), (0.01, 0.12, 0.018), MET)
        beam(h, (s * (hx + 0.03), 0.01, hb + 0.005), (s * 0.03, -(hy * 0.55), hd - 0.005), 0.012, 0.004, WEB)
    beam(h, (0.03, -(hy * 0.55), hd - 0.005), (-0.03, -(hy * 0.55), hd - 0.005), 0.012, 0.004, WEB)
    h.box((0, -(hy + 0.045), hb + 0.03), (0.05, 0.025, 0.05), PLY)
    h.box((0, -(hy + 0.06), hb + 0.0), (0.03, 0.03, 0.03), MET)
    h.box((0, hy + 0.035, hb + 0.08), (0.06, 0.02, 0.04), WEB)
    h.box((0, hy * 0.4 + 0.02, hb + 0.165), (0.03, 0.04, 0.02), PLY)
    # --- assault pack (spine-weighted)
    k = T.mb('PACK__SPINE', 'SPINE', 'Backpack')
    py = rry + 0.04 + 0.05 + 0.075
    zb, zt = ch - 0.12, up + 0.14
    vloft(k, 0, py, [(zb, 0, 0), (zb, 0.15, 0.075), (zb + 0.02, 0.155, 0.08), (zt - 0.05, 0.15, 0.08),
                     (zt - 0.01, 0.135, 0.07), (zt, 0, 0)], 20, CAM, 4.0)
    k.box((0, py + 0.01, zt - 0.02), (0.31, 0.15, 0.05), CAM, top=(0.95, 0.9))
    for s in (1, -1):
        k.box((s * 0.17, py, ch), (0.05, 0.11, 0.16), CAM)
        k.box((s * 0.07, py + 0.082, (zb + zt) / 2), (0.026, 0.008, 0.28), WEB)
        beam(k, (s * 0.1, py - 0.08, zt - 0.03), (s * 0.12, 0.0, P['sh_z'] + 0.085), 0.05, 0.012, WEB)
        beam(k, (s * 0.12, 0.0, P['sh_z'] + 0.085), (s * 0.12, -(cry + 0.065 + bust), up - 0.04), 0.05, 0.012, WEB)
        beam(k, (s * 0.15, py - 0.08, zb + 0.03), (s * (rrx + 0.04), 0.0, ch - 0.06), 0.03, 0.01, WEB)
    k.box((0, py + 0.083, ch + 0.08), (0.18, 0.01, 0.12), CAM)
    k.cyl(0.055, 0.36, 14, WEB, M=frame((0, py, zt + 0.055), (1, 0, 0)))
    for s in (1, -1):
        k.cyl(0.058, 0.025, 14, PLY, M=frame((s * 0.11, py, zt + 0.055), (1, 0, 0)))
    # --- rifle (on the WeaponR socket bone), modelled pointing -Y with the grip at the bone origin
    W = T.weapon_rest
    r = T.mb('RIFLE__WeaponR', 'WeaponR', 'Rifle')

    def at(x, y, z):
        return (W.x + x, W.y + y, W.z + z)
    r.box(at(0, -0.06, 0.06), (0.046, 0.30, 0.07), MET)
    r.box(at(0, -0.33, 0.066), (0.052, 0.24, 0.056), PLY)
    r.box(at(0, -0.33, 0.1), (0.022, 0.26, 0.012), MET)
    r.cyl(0.011, 0.30, 8, MET, M=frame(at(0, -0.45, 0.07), (0, -1, 0)), x0=0.0)
    r.cyl(0.017, 0.055, 10, MET, M=frame(at(0, -0.705, 0.07), (0, -1, 0)), x0=0.0)
    r.cyl(0.021, 0.16, 12, MET, M=frame(at(0, -0.02, 0.132), (0, -1, 0)))
    for yy in (-0.06, 0.02):
        r.box(at(0, yy, 0.108), (0.016, 0.018, 0.03), MET)
    for yy, d in ((-0.1, -1), (0.06, 1)):
        r.cyl(0.018, 0.004, 12, LNS, M=frame(at(0, yy + d * 0.0, 0.132), (0, d, 0)), x0=0.0)
    r.box((0, 0, 0), (0.03, 0.04, 0.10), PLY, M=Mt(*at(0, 0.02, -0.03)) @ Mrx(-0.25))
    r.box(at(0, -0.03, -0.0), (0.012, 0.06, 0.006), MET)
    r.box((0, 0, 0), (0.025, 0.07, 0.15), PLY, M=Mt(*at(0, -0.11, -0.03)) @ Mrx(0.22))
    r.box(at(0, 0.23, 0.05), (0.04, 0.22, 0.065), PLY, top=(1.0, 1.0), bot=(1.0, 1.0))
    r.box(at(0, 0.345, 0.04), (0.042, 0.02, 0.09), PLY)
    r.box(at(0, -0.3, 0.03), (0.02, 0.06, 0.03), PLY)
    r.box(at(0, 0.18, 0.02), (0.01, 0.02, 0.02), MET)


# ------------------------------------------------------------------------------ character object
class Soldier(Tank):
    def __init__(self, P, origin, mats):
        self.name, self.origin, self.P = P['name'], Vector(origin), P
        self.coll = get_coll(f'Soldier_{P["name"]}', get_coll('SoldierKit'))
        self.mbs, self.objs, self.bones, self.wheel_drv = {}, [], [], []
        self.guns, self.flashes, self.tracks, self.meta, self.temp_meshes = [], [], {}, {}, []
        self.mat_list = mats
        self.extra_parts = []


def spine_weights(P, z):
    knots = [('Hips', P['hips']), ('Spine', P['spine']), ('Chest', P['chest']), ('UpperChest', P['upper']),
             ('Neck', P['neck'])]
    if z <= knots[0][1]:
        return [('Hips', 1.0)]
    for (b0, z0), (b1, z1) in zip(knots, knots[1:]):
        if z <= z1:
            t = (z - z0) / (z1 - z0)
            return [(b0, 1 - t), (b1, t)]
    return [('UpperChest', 0.3), ('Neck', 0.7)] if z < P['head'] else [('Neck', 1.0)]


def char_uv(me):
    uvl = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    co = [v.co.copy() for v in me.vertices]
    for p in me.polygons:
        mi = p.material_index
        if mi == DEC:
            continue
        su, sv = CTILE.get(mi, (0.5, 0.5))
        ax = max(range(3), key=lambda i: abs(p.normal[i]))
        for li in p.loop_indices:
            c = co[me.loops[li].vertex_index]
            uvl.data[li].uv = ((c.x, c.y) if ax == 2 else (c.y, c.z) if ax == 0 else (c.x, c.z))
            uvl.data[li].uv = (uvl.data[li].uv[0] / su, uvl.data[li].uv[1] / sv)


def build_soldier(P, origin, mats):
    T = Soldier(P, origin, mats)
    soldier_bones(T, P)
    build_body(T, P)
    build_gear(T, P)
    T.finish_parts()
    return T


def assemble_soldier(T):
    rig = T.rig
    P = T.P
    vl = bpy.context.view_layer
    groups = {}
    for ob, bone, group in T.objs + T.extra_parts:
        me = ob.data
        if not any(p.material_index == DEC for p in me.polygons):
            char_uv(me)
        ob.vertex_groups.clear()
        if bone == 'SPINE':
            vgs = {}
            for v in me.vertices:
                for bn, w in spine_weights(P, v.co.z):
                    if bn not in vgs:
                        vgs[bn] = ob.vertex_groups.new(name=bn)
                    vgs[bn].add([v.index], w, 'REPLACE')
        else:
            ob.vertex_groups.new(name=bone).add(list(range(len(me.vertices))), 1.0, 'REPLACE')
        groups.setdefault(group, []).append(ob)
    out = {}
    for group, obs in groups.items():
        for o in vl.objects:
            o.select_set(False)
        for o in obs:
            o.select_set(True)
        vl.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        ob = vl.objects.active
        ob.name = ob.data.name = f'Soldier{T.name}_{group}'
        mw = ob.matrix_world.copy()
        ob.parent = rig
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_world = mw
        ob.modifiers.new('Armature', 'ARMATURE').object = rig
        prune_materials(ob.data)
        out[group] = ob
    T.parts = out
    return out


def add_ik(T):
    """IK constraints for animators in Blender (influence 0 = FK by default; exported clips are FK)."""
    rig = T.rig
    res = {}
    for side, tag in (('Left', 'L'), ('Right', 'R')):
        for bone, tgt, pole in ((f'{side}LowerLeg', f'IK_Foot_{tag}', f'IK_Knee_{tag}'),
                                (f'{side}LowerArm', f'IK_Hand_{tag}', f'IK_Elbow_{tag}')):
            pb = rig.pose.bones[bone]
            c = pb.constraints.new('IK')
            c.target, c.subtarget = rig, tgt
            c.pole_target, c.pole_subtarget = rig, pole
            c.chain_count = 2
            best = None
            for ang in (0.0, 90.0, -90.0, 180.0):
                c.pole_angle = math.radians(ang)
                c.influence = 1.0
                bpy.context.view_layer.update()
                dev = (pb.matrix.to_3x3() - pb.bone.matrix_local.to_3x3())
                err = sum(abs(dev[i][j]) for i in range(3) for j in range(3))
                if best is None or err < best[0]:
                    best = (err, ang)
            c.pole_angle = math.radians(best[1])
            c.influence = 0.0
            res[bone] = best[1]
    bpy.context.view_layer.update()
    return res


# ------------------------------------------------------------------------------ posing / clips
AXV = {'x': Vector((1, 0, 0)), 'y': Vector((0, 1, 0)), 'z': Vector((0, 0, 1))}


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def apply_pose(rig, pose):
    for bn, rots in pose.items():
        if bn.startswith('_'):
            continue
        pb = rig.pose.bones[bn]
        Q = Quaternion()
        for ax, deg in rots:
            Q = Quaternion(AXV[ax], math.radians(deg)) @ Q
        R = pb.bone.matrix_local.to_quaternion()
        pb.rotation_quaternion = R.inverted() @ Q @ R
    if '_hips' in pose:
        pb = rig.pose.bones['Hips']
        pb.location = pb.bone.matrix_local.to_quaternion().inverted() @ Vector(pose['_hips'])


def finger_curl(pose, side, prox, mid, dist, thumb=10):
    sgn = 1 if side == 'Left' else -1
    for name, *_ in FINGERS:
        pose[f'{side}{name}Proximal'] = [('y', sgn * prox)]
        pose[f'{side}{name}Intermediate'] = [('y', sgn * mid)]
        pose[f'{side}{name}Distal'] = [('y', sgn * dist)]
    pose[f'{side}ThumbProximal'] = [('z', -sgn * thumb)]
    pose[f'{side}ThumbDistal'] = [('z', -sgn * thumb)]


def base_pose(arms_down=76, elbow=12, curl=18):
    p = {'LeftUpperArm': [('y', arms_down)], 'RightUpperArm': [('y', -arms_down)],
         'LeftLowerArm': [('z', -elbow)], 'RightLowerArm': [('z', elbow)]}
    finger_curl(p, 'Left', curl, curl, curl * 0.7)
    finger_curl(p, 'Right', curl * 2.5, curl * 2.5, curl * 1.6)
    return p


def pose_idle(t):
    ph = TAU * t
    p = base_pose()
    b = math.sin(ph)
    p['Chest'] = [('x', -0.8 * b)]
    p['UpperChest'] = [('x', -1.2 * b)]
    p['Head'] = [('x', 0.6 * b), ('z', 1.5 * math.sin(ph * 0.5 + 0.4))]
    p['LeftUpperArm'] = [('y', 76 + 1.2 * b)]
    p['RightUpperArm'] = [('y', -76 - 1.2 * b)]
    p['_hips'] = (0.006 * math.sin(ph * 0.5), 0, 0.003 * b)
    return p


def pose_locomotion(t, run=False):
    ph = TAU * t
    s = math.sin(ph)
    c = math.cos(ph)
    A = 42 if run else 24
    K = 75 if run else 38
    p = base_pose(70 if run else 76, 85 if run else 15)
    p['LeftUpperLeg'] = [('x', -A * s)]
    p['RightUpperLeg'] = [('x', A * s)]
    kl = 6 + K * max(0.0, math.sin(ph + 1.9)) ** 1.5
    kr = 6 + K * max(0.0, math.sin(ph + 1.9 + math.pi)) ** 1.5
    p['LeftLowerLeg'] = [('x', kl)]
    p['RightLowerLeg'] = [('x', kr)]
    p['LeftFoot'] = [('x', -8 * s - 0.25 * kl + (10 if run else 4))]
    p['RightFoot'] = [('x', 8 * s - 0.25 * kr + (10 if run else 4))]
    sw = (38 if run else 18)
    p['LeftUpperArm'] = [('y', 70 if run else 76), ('x', sw * s)]
    p['RightUpperArm'] = [('y', -(70 if run else 76)), ('x', -sw * s)]
    lean = 12 if run else 3
    p['Spine'] = [('x', lean * 0.5), ('z', -(6 if run else 4) * s)]
    p['Chest'] = [('x', lean * 0.5), ('z', -(4 if run else 2) * s)]
    p['Hips'] = [('z', (7 if run else 5) * s), ('y', (3 if run else 2) * c)]
    p['Head'] = [('x', -lean * 0.6), ('z', (4 if run else 2) * s)]
    bob = (0.05 if run else 0.025)
    p['_hips'] = (0.012 * c, 0, -bob * (0.5 - 0.5 * math.cos(2 * ph)))
    return p


def pose_crouch(t):
    ph = TAU * t
    a, b = 75, 115
    p = base_pose(64, 35, 22)
    p['LeftUpperArm'] = [('y', 64), ('x', -20)]
    p['RightUpperArm'] = [('y', -64), ('x', -20)]
    for side in ('Left', 'Right'):
        p[f'{side}UpperLeg'] = [('x', -a)]
        p[f'{side}LowerLeg'] = [('x', b)]
        p[f'{side}Foot'] = [('x', a - b)]
    p['Spine'] = [('x', 14 + 0.6 * math.sin(ph))]
    p['Chest'] = [('x', 10)]
    p['Head'] = [('x', -18)]
    p['_hips'] = (0, 0.15, -0.40)
    return p


def set_bone_dir(rig, name, target):
    pb = rig.pose.bones[name]
    pb.rotation_quaternion = (1, 0, 0, 0)
    bpy.context.view_layer.update()
    M0 = pb.matrix.copy()
    head = M0.translation.copy()
    d0 = M0.col[1].xyz.normalized()
    d1 = (Vector(target) - head).normalized()
    Rd = d0.rotation_difference(d1).to_matrix().to_4x4()
    pb.matrix = Matrix.Translation(head) @ Rd @ M0.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def solve2(S, Tg, a, b, P):
    S, Tg, P = Vector(S), Vector(Tg), Vector(P)
    d = min((Tg - S).length, a + b - 1e-4)
    u = (Tg - S).normalized()
    along = (a * a - b * b + d * d) / (2 * d)
    h = math.sqrt(max(a * a - along * along, 0.0))
    pv = (P - S) - u * (P - S).dot(u)
    pv.normalize()
    return S + u * along + pv * h, S + u * d


def pose_aim(T, t):
    """two-hand rifle aim solved with analytic two-bone IK; returns nothing (sets the rig)."""
    rig, P = T.rig, T.P
    ph = TAU * t
    reset_pose(rig)
    p = {'Hips': [('z', -12)], 'Spine': [('z', 4), ('x', 3)], 'Chest': [('z', 4)], 'UpperChest': [('z', 4), ('x', 1.0 * math.sin(ph))],
         'Neck': [('x', 4)], 'Head': [('x', 8), ('z', 4)],
         'LeftUpperLeg': [('x', -14), ('z', 4)], 'RightUpperLeg': [('x', 10), ('z', -4)],
         'LeftLowerLeg': [('x', 16)], 'RightLowerLeg': [('x', 10)], 'LeftFoot': [('x', -2)], 'RightFoot': [('x', -12), ('z', 20)],
         '_hips': (0, 0.02, -0.03)}
    finger_curl(p, 'Right', 70, 65, 40, 25)
    finger_curl(p, 'Left', 55, 45, 30, 20)
    apply_pose(rig, p)
    bpy.context.view_layer.update()
    crx, cry = P['chestr']
    W_des = Vector((-0.11, -(cry + 0.03) - 0.34, P['sh_z'] + 0.02 + 0.004 * math.sin(ph)))
    Wr = rig.data.bones['WeaponR'].matrix_local
    Hr = rig.data.bones['RightHand'].matrix_local
    Wrel = Hr.inverted() @ Wr
    Wm = Matrix.Translation(W_des) @ Wr.to_3x3().to_4x4()
    Hd = Wm @ Wrel.inverted()
    for side, s, wrist, pole_off, hand_m in (
            ('Right', -1, Hd.translation, Vector((-0.35, 0.2, -0.45)), Hd), ('Left', 1, None, Vector((0.35, -0.05, -0.5)), None)):
        S = rig.pose.bones[f'{side}UpperArm'].head.copy()
        if side == 'Left':
            G = W_des + Vector((0.0, -0.30, 0.035))
            Yh = Vector((-0.9, -0.42, 0.1)).normalized()
            Xh = Vector((0, 0, 1))
            Xh = (Xh - Yh * Xh.dot(Yh)).normalized()
            Zh = Xh.cross(Yh)
            R3 = Matrix((Xh, Yh, Zh)).transposed()
            wrist = G - Yh * (P['palm'] * 0.55) - Xh * 0.03
            hand_m = Matrix.Translation(wrist) @ R3.to_4x4()
        E, Tw = solve2(S, wrist, P['ua'], P['fa'], S + pole_off)
        set_bone_dir(rig, f'{side}UpperArm', E)
        set_bone_dir(rig, f'{side}LowerArm', Tw)
        pb = rig.pose.bones[f'{side}Hand']
        pb.matrix = hand_m
        bpy.context.view_layer.update()


def key_all(rig, frame, bones):
    for bn in bones:
        pb = rig.pose.bones[bn]
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        if bn in ('Hips', 'WeaponR'):
            pb.keyframe_insert('location', frame=frame)


def soldier_clips(T):
    rig = T.rig
    ad = rig.animation_data_create()
    deform = [b.name for b in rig.data.bones if b.use_deform and b.name not in ('Root', 'Muzzle')]
    made = []
    reset_pose(rig)
    apply_pose(rig, pose_idle(0.0))
    bpy.context.view_layer.update()
    hand = rig.pose.bones['RightHand'].matrix
    wb = rig.pose.bones['WeaponR']
    d = Vector((0.0, -0.55, -0.83)).normalized()
    up = Vector((0, 0, 1))
    zax = (up - d * up.dot(d)).normalized()
    xax = d.cross(zax)
    R = Matrix((xax, d, zax)).transposed().to_4x4()
    wb.matrix = Matrix.Translation(wb.matrix.translation) @ R
    bpy.context.view_layer.update()
    carry_q = wb.rotation_quaternion.copy()
    carry_l = wb.location.copy()

    def clip(name, n, fn, step=2, carry=True):
        act = bpy.data.actions.new(f'{T.name}_{name}')
        act.use_fake_user = True
        ad.action = act
        for f in range(1, n + 2, step):
            reset_pose(rig)
            fn((f - 1) / n)
            if carry:
                bpy.context.view_layer.update()
                wbp = rig.pose.bones['WeaponR']
                wbp.matrix = Matrix.Translation(wbp.matrix.translation) @ R
                bpy.context.view_layer.update()
            key_all(rig, f, deform)
        act.use_frame_range = True
        act.frame_start, act.frame_end = 1, n + 1
        slot = ad.action_slot
        ad.action = None
        tr = ad.nla_tracks.new()
        tr.name = name
        st = tr.strips.new(name, 1, act)
        if slot is not None and getattr(st, 'action_slot', None) is None:
            st.action_slot = slot
        tr.mute = True
        made.append(name)

    clip('Idle', 48, lambda t: apply_pose(rig, pose_idle(t)), 4)
    clip('Walk', 32, lambda t: apply_pose(rig, pose_locomotion(t, False)), 2)
    clip('Run', 20, lambda t: apply_pose(rig, pose_locomotion(t, True)), 2)
    clip('Crouch', 48, lambda t: apply_pose(rig, pose_crouch(t)), 8)
    clip('Rifle_Aim', 48, lambda t: pose_aim(T, t), 8, carry=False)
    reset_pose(rig)
    ad.action = None
    return made


def export_soldier(T, path):
    rig = T.rig
    old = rig.location.copy()
    rig.location = (0, 0, 0)
    reset_pose(rig)
    bpy.context.view_layer.update()
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    rig.hide_set(False)
    rig.select_set(True)
    for c in rig.children:
        c.hide_set(False)
        c.select_set(True)
    vl.objects.active = rig
    try:
        bpy.ops.export_scene.gltf(
            filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
            export_animations=True, export_animation_mode='NLA_TRACKS', export_force_sampling=True,
            export_frame_step=1, export_optimize_animation_size=True,
            export_optimize_animation_keep_anim_armature=True, export_def_bones=True, export_skins=True,
            export_extras=False, export_tangents=True, export_image_format='AUTO', export_materials='EXPORT',
            export_rest_position_armature=True, export_anim_slide_to_zero=True, export_reset_pose_bones=True,
            export_cameras=False, export_lights=False)
    finally:
        rig.location = old
        reset_pose(rig)
        bpy.context.view_layer.update()


def clear_clips(T):
    ad = T.rig.animation_data
    if ad:
        for tr in list(ad.nla_tracks):
            ad.nla_tracks.remove(tr)
        ad.action = None
    for a in [a for a in bpy.data.actions if a.name.startswith(T.name + '_')]:
        bpy.data.actions.remove(a)
