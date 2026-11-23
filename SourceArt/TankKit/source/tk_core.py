# Tank Kit builder - core library (Blender 5.x)
# Geometry helpers, procedural "master" materials for baking, track/running-gear solver,
# rig + drivers, animation clips, texture baking and glTF export.
# Executed with exec() from a driver that defines KIT_DIR.
import bpy, bmesh, math, os, time, json
from mathutils import Vector, Matrix
import numpy as np

TAU = math.tau
KIT_DIR = globals().get('KIT_DIR')
TEX_DIR = os.path.join(KIT_DIR, 'textures')
GLB_DIR = os.path.join(KIT_DIR, 'glb')

# material slot indices used while modelling (all baked into one material per tank)
P, K, MT, RB, WP, GL, LT, LR, WM = range(9)
SLOTS = ['paint', 'mark', 'metal', 'rubber', 'wheelpaint', 'glass', 'light', 'lightred', 'wheelmetal']
FLASH_REST = 0.001      # muzzle flash geometry is stored at 1/1000 size; the flash bone scales it up
LINK_FRAMES = 12        # frames per track-link cycle in the Drive clips (24 fps)
EPS = 0.001             # keeps loop clips strictly inside one link so they wrap seamlessly


def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent if parent else bpy.context.scene.collection).children.link(c)
    return c


def frame(o, xdir, up=(0, 0, 1)):
    """4x4 matrix whose local X points along xdir, positioned at o."""
    x = Vector(xdir).normalized()
    u = Vector(up).normalized()
    if abs(x.dot(u)) > 0.999:
        u = Vector((0, 1, 0)) if abs(x.y) < 0.9 else Vector((1, 0, 0))
    y = u.cross(x).normalized()
    z = x.cross(y)
    return Matrix(((x.x, y.x, z.x, o[0]), (x.y, y.y, z.y, o[1]), (x.z, y.z, z.z, o[2]), (0, 0, 0, 1)))


def Mt(x=0.0, y=0.0, z=0.0):
    return Matrix.Translation((x, y, z))


def Mrz(a):
    return Matrix.Rotation(a, 4, 'Z')


def Mrx(a):
    return Matrix.Rotation(a, 4, 'X')


def Mry(a):
    return Matrix.Rotation(a, 4, 'Y')


# ----------------------------------------------------------------------------------------------
# Mesh builder
# ----------------------------------------------------------------------------------------------
class MB:
    def __init__(self):
        self.bm = bmesh.new()

    def _pts(self, pts, M):
        return [(M @ Vector(p)) if M is not None else Vector(p) for p in pts]

    def face(self, vs, mat=0):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = mat
        return f

    def loft(self, rings, mat=0, cap0=True, cap1=True, ring_mats=None, closed=True, M=None, cap_mats=None):
        vr = [[self.bm.verts.new(p) for p in self._pts(r, M)] for r in rings]
        n = len(vr[0])
        faces = []
        for i in range(len(vr) - 1):
            m = ring_mats[i] if ring_mats is not None else mat
            a, b = vr[i], vr[i + 1]
            for j in range(n if closed else n - 1):
                k = (j + 1) % n
                faces.append(self.face((a[j], a[k], b[k], b[j]), m))
        c0, c1 = cap_mats if cap_mats else (mat, mat)
        if cap0:
            faces.append(self.face(list(reversed(vr[0])), c0))
        if cap1:
            faces.append(self.face(vr[-1], c1))
        return faces

    def box(self, c, s, mat=0, M=None, top=(1.0, 1.0), top_off=(0.0, 0.0), bot=(1.0, 1.0),
            cap0=True, cap1=True):
        """faces: 0 front(-y) 1 right(+x) 2 back(+y) 3 left(-x) [4 bottom] [5 top]"""
        cx, cy, cz = c
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        tx, ty = top
        bx, by = bot
        ox, oy = top_off
        r0 = [(cx - hx * bx, cy - hy * by, cz - hz), (cx + hx * bx, cy - hy * by, cz - hz),
              (cx + hx * bx, cy + hy * by, cz - hz), (cx - hx * bx, cy + hy * by, cz - hz)]
        r1 = [(cx - hx * tx + ox, cy - hy * ty + oy, cz + hz), (cx + hx * tx + ox, cy - hy * ty + oy, cz + hz),
              (cx + hx * tx + ox, cy + hy * ty + oy, cz + hz), (cx - hx * tx + ox, cy + hy * ty + oy, cz + hz)]
        return self.loft([r0, r1], mat, M=M, cap0=cap0, cap1=cap1)

    def lathe(self, prof, segs, mat=0, mats=None, M=None, phase=0.0):
        """revolve (radius, x) profile around local X."""
        rings = []
        for r, x in prof:
            if r <= 1e-7:
                rings.append([(x, 0.0, 0.0)])
            else:
                rings.append([(x, r * math.cos(phase + TAU * i / segs), r * math.sin(phase + TAU * i / segs))
                              for i in range(segs)])
        vr = [[self.bm.verts.new(p) for p in self._pts(r, M)] for r in rings]
        for i in range(len(vr) - 1):
            m = mats[i] if mats else mat
            a, b = vr[i], vr[i + 1]
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                for j in range(segs):
                    self.face((a[0], b[j], b[(j + 1) % segs]), m)
            elif len(b) == 1:
                for j in range(segs):
                    self.face((a[(j + 1) % segs], a[j], b[0]), m)
            else:
                for j in range(segs):
                    k = (j + 1) % segs
                    self.face((a[j], a[k], b[k], b[j]), m)
        return vr

    def cyl(self, r, length, segs, mat=0, M=None, r2=None, cap_mat=None, phase=0.0, x0=None):
        """cylinder along local X, centred (or starting at x0)."""
        r2 = r if r2 is None else r2
        if x0 is None:
            a, b = -length / 2, length / 2
        else:
            a, b = x0, x0 + length
        vr = self.lathe([(r, a), (r2, b)], segs, mat, M=M, phase=phase)
        cm = mat if cap_mat is None else cap_mat
        self.face(list(reversed(vr[0])), cm)
        self.face(vr[1], cm)
        return vr

    def to_mesh(self, name, mats, sharp=35.0, recalc=True):
        bm = self.bm
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        me.set_sharp_from_angle(angle=math.radians(sharp))
        return me

    def finish(self, name, mats, coll, sharp=35.0, recalc=True):
        me = self.to_mesh(name, mats, sharp, recalc)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def ring_half(half, z, sx=1.0, sy=1.0, dx=0.0, dy=0.0):
    """half outline from front centre (x=0) along +x side to rear centre (x=0) -> full CCW ring."""
    pts = [(x * sx, y * sy) for x, y in half]
    full = pts + [(-x, y) for x, y in reversed(pts[1:-1])]
    return [(x + dx, y + dy, z) for x, y in full]


def ring_rect(w, yf, yr, z, c=0.0):
    if c <= 0:
        return [(-w, yf, z), (w, yf, z), (w, yr, z), (-w, yr, z)]
    return [(-w + c, yf, z), (w - c, yf, z), (w, yf + c, z), (w, yr - c, z), (w - c, yr, z),
            (-w + c, yr, z), (-w, yr - c, z), (-w, yf + c, z)]


# ----------------------------------------------------------------------------------------------
# Shader node helpers
# ----------------------------------------------------------------------------------------------
def sk(socks, ident):
    for s in socks:
        if s.identifier == ident:
            return s
    raise KeyError(ident)


class NT:
    def __init__(self, mat):
        self.t = mat.node_tree
        self.t.nodes.clear()
        self.L = self.t.links
        self._x = -3000

    def n(self, idn, **kw):
        nd = self.t.nodes.new(idn)
        nd.location = (self._x, (len(self.t.nodes) % 8) * -180)
        self._x += 70
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def put(self, s, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, s)
        else:
            if s.type == 'RGBA' and hasattr(v, '__len__') and len(v) == 3:
                v = (v[0], v[1], v[2], 1.0)
            s.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        nd = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.put(nd.inputs[0], a)
        if b is not None:
            self.put(nd.inputs[1], b)
        if c is not None:
            self.put(nd.inputs[2], c)
        return nd.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        nd = self.n('ShaderNodeVectorMath', operation=op)
        self.put(nd.inputs[0], a)
        if b is not None:
            self.put(nd.inputs[1], b)
        if scale is not None:
            self.put(sk(nd.inputs, 'Scale'), scale)
        if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE'):
            return sk(nd.outputs, 'Value')
        return sk(nd.outputs, 'Vector')

    def mr(self, v, a, b, c=0.0, d=1.0, clamp=True):
        nd = self.n('ShaderNodeMapRange', clamp=clamp)
        self.put(nd.inputs[0], v)
        nd.inputs[1].default_value = a
        nd.inputs[2].default_value = b
        nd.inputs[3].default_value = c
        nd.inputs[4].default_value = d
        return nd.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        nd = self.n('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_factor=True)
        self.put(sk(nd.inputs, 'Factor_Float'), fac)
        self.put(sk(nd.inputs, 'A_Color'), a)
        self.put(sk(nd.inputs, 'B_Color'), b)
        return sk(nd.outputs, 'Result_Color')

    def mixf(self, fac, a, b):
        nd = self.n('ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
        self.put(sk(nd.inputs, 'Factor_Float'), fac)
        self.put(sk(nd.inputs, 'A_Float'), a)
        self.put(sk(nd.inputs, 'B_Float'), b)
        return sk(nd.outputs, 'Result_Float')

    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0, out='Fac'):
        nd = self.n('ShaderNodeTexNoise')
        self.put(nd.inputs['Vector'], vec)
        nd.inputs['Scale'].default_value = scale
        nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough
        nd.inputs['Distortion'].default_value = distortion
        return nd.outputs[out]

    def ramp(self, fac, stops, interp='CONSTANT'):
        nd = self.n('ShaderNodeValToRGB')
        cr = nd.color_ramp
        cr.interpolation = interp
        els = cr.elements
        els[0].position = stops[0][0]
        els[0].color = (*stops[0][1], 1.0)
        els[1].position = stops[1][0]
        els[1].color = (*stops[1][1], 1.0)
        for p, c in stops[2:]:
            e = els.new(p)
            e.color = (*c, 1.0)
        self.put(nd.inputs['Fac'], fac)
        return nd.outputs['Color']

    def sep(self, v):
        nd = self.n('ShaderNodeSeparateXYZ')
        self.put(nd.inputs[0], v)
        return nd.outputs

    def comb(self, x=0.0, y=0.0, z=0.0):
        nd = self.n('ShaderNodeCombineXYZ')
        self.put(nd.inputs['X'], x)
        self.put(nd.inputs['Y'], y)
        self.put(nd.inputs['Z'], z)
        return nd.outputs[0]


def camo_pattern(nt, Pv, cfg):
    s = cfg['scale']
    pat = cfg['pattern']
    if pat == 'splinter':
        warp = nt.noise(Pv, s * 1.7, 2.0, 0.5, out='Color')
        Pw = nt.vmath('ADD', Pv, nt.vmath('SCALE', nt.vmath('SUBTRACT', warp, (0.5, 0.5, 0.5)), scale=0.5 / s))
        vor = nt.n('ShaderNodeTexVoronoi', feature='F1', distance='CHEBYCHEV')
        nt.put(vor.inputs['Vector'], Pw)
        vor.inputs['Scale'].default_value = s
        sc = nt.n('ShaderNodeSeparateColor')
        nt.put(sc.inputs[0], vor.outputs['Color'])
        fac = sc.outputs[0]
    elif pat == 'stripe':
        mp = nt.n('ShaderNodeMapping')
        nt.put(mp.inputs['Vector'], Pv)
        mp.inputs['Scale'].default_value = (0.7, 2.6, 0.45)
        fac = nt.noise(mp.outputs[0], s, 3.0, 0.5, distortion=0.8)
    else:
        fac = nt.noise(Pv, s, 3.0, 0.55, distortion=cfg.get('distort', 0.5))
    return nt.ramp(fac, cfg['stops'])


def master_material(name, kind, cfg):
    """Procedural shader used only for baking. Exposes OUT_COLOR / OUT_ORM / BSDF / BAKE_* nodes."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = NT(mat)
    wheel = kind in ('wheelpaint', 'rubber', 'wheelmetal')
    track = kind == 'track'

    # ---- coordinates (wheels use a rotation-symmetric space so the loop clips never pop)
    if wheel:
        tc = nt.n('ShaderNodeTexCoord')
        o = nt.sep(tc.outputs['Object'])
        rad = nt.vmath('LENGTH', nt.comb(0.0, o['Y'], o['Z']))
        Pv = nt.comb(rad, o['X'], cfg.get('seed', 0.0))
    elif track:
        tc = nt.n('ShaderNodeTexCoord')
        Pv = tc.outputs['Object']
    else:
        g0 = nt.n('ShaderNodeNewGeometry')
        Pv = g0.outputs['Position']
    geo = nt.n('ShaderNodeNewGeometry')
    Nrm = geo.outputs['Normal']
    Ps = nt.sep(Pv)
    Ns = nt.sep(Nrm)

    # ---- edge / cavity masks
    bev = nt.n('ShaderNodeBevel', samples=8)
    bev.inputs['Radius'].default_value = cfg.get('bevel', 0.02)
    dot = nt.vmath('DOT_PRODUCT', bev.outputs['Normal'], Nrm)
    edge = nt.mr(dot, 0.995, 0.90)
    aon = nt.n('ShaderNodeAmbientOcclusion', samples=16, only_local=(wheel or track or cfg.get('ao_local', False)))
    aon.inputs['Distance'].default_value = cfg.get('ao_dist', 0.45)
    AO = aon.outputs['AO']
    grime = nt.mr(AO, 0.3, 0.97, 1.0, 0.0)

    nb = nt.mr(nt.noise(Pv, 7.0, 6.0, 0.62), 0.40, 0.62)
    wear = nt.mr(nt.math('MULTIPLY', edge, nb), 0.18, 0.45)
    chips = nt.math('MULTIPLY', nt.mr(nt.noise(Pv, 24.0, 3.0, 0.6), 0.705, 0.735), cfg.get('chips', 0.55))
    wear = nt.math('MULTIPLY', nt.math('MAXIMUM', wear, chips), cfg.get('wear', 1.0))

    # ---- dust
    if wheel:
        dust = nt.math('MULTIPLY_ADD', nt.mr(nt.noise(Pv, 5.0, 4.0, 0.6), 0.3, 0.75), 0.45, 0.30)
        streak = 0.0
    elif track:
        inner = nt.mr(Ps['Z'], 0.0, -0.05)
        dust = nt.math('MAXIMUM', nt.math('MULTIPLY', inner, 0.7),
                       nt.math('MULTIPLY', nt.mr(nt.noise(Pv, 9.0, 4.0, 0.6), 0.45, 0.7), 0.6))
        streak = 0.0
    else:
        dmask = nt.mr(Ps['Z'], 0.15, cfg.get('dust_h', 1.35), 1.0, 0.0)
        dn = nt.mr(nt.noise(Pv, 1.6, 3.0, 0.55), 0.3, 0.72)
        dust = nt.math('MULTIPLY', dmask, dn)
        top = nt.mr(Ns['Z'], 0.55, 0.95)
        dtop = nt.math('MULTIPLY', top, nt.mr(nt.noise(Pv, 2.6, 4.0, 0.6), 0.45, 0.8))
        dust = nt.math('MAXIMUM', dust, nt.math('MULTIPLY', dtop, 0.42))
        vf = nt.mr(nt.math('ABSOLUTE', Ns['Z']), 0.2, 0.5, 1.0, 0.0)
        mp = nt.n('ShaderNodeMapping')
        nt.put(mp.inputs['Vector'], Pv)
        mp.inputs['Scale'].default_value = (13.0, 13.0, 0.7)
        streak = nt.math('MULTIPLY', nt.mr(nt.noise(mp.outputs[0], 1.0, 2.0, 0.5), 0.5, 0.74), vf)
        streak = nt.math('MULTIPLY', streak, 0.5)
    dust = nt.math('MULTIPLY', nt.math('ADD', dust, nt.math('MULTIPLY', grime, 0.3), clamp=True),
                   cfg.get('dust', 0.75), clamp=True)

    dust_col = cfg.get('dust_col', srgb('#8f7b5e'))
    grime_col = (0.035, 0.03, 0.022)
    var = nt.mr(nt.noise(Pv, 3.0, 3.0, 0.5), 0.3, 0.7, -1.0, 1.0)

    # ---- base colour per kind
    if kind == 'paint':
        base = cfg['base_fn'](nt, Pv, Nrm, Ns, cfg) if 'base_fn' in cfg else camo_pattern(nt, Pv, cfg)
    elif kind == 'mark':
        base = cfg['mark_fn'](nt, Pv, cfg) if 'mark_fn' in cfg else cfg['mark']
    elif kind == 'wheelpaint':
        base = cfg['stops'][0][1]
    elif kind in ('metal', 'wheelmetal'):
        base = (0.045, 0.045, 0.05)
    elif kind == 'rubber':
        base = (0.022, 0.022, 0.024)
    elif kind == 'glass':
        base = (0.008, 0.02, 0.026)
    elif kind == 'light':
        base = (0.92, 0.86, 0.62)
    elif kind == 'lightred':
        base = (0.55, 0.025, 0.015)
    else:  # track
        base = (0.06, 0.056, 0.052)

    col = nt.mix(nt.math('MULTIPLY', var, 0.06), base, (1.0, 1.0, 1.0), blend='OVERLAY') \
        if kind in ('paint', 'wheelpaint', 'mark') else nt.mix(0.0, base, base)

    if kind in ('paint', 'mark', 'wheelpaint'):
        if not isinstance(streak, float):
            col = nt.mix(streak, col, (0.55, 0.53, 0.5), blend='MULTIPLY')
        col = nt.mix(nt.math('MULTIPLY', grime, 0.75), col, grime_col)
        col = nt.mix(dust, col, dust_col)
        col = nt.mix(wear, col, (0.30, 0.29, 0.28))
        rough = nt.math('ADD', cfg.get('rough', 0.56), nt.math('MULTIPLY', var, 0.06))
        rough = nt.mixf(dust, rough, 0.92)
        rough = nt.mixf(nt.math('MULTIPLY', grime, 0.5), rough, 0.82)
        rough = nt.mixf(wear, rough, 0.3)
        metal = nt.math('MAXIMUM', nt.math('MULTIPLY', wear, 0.9),
                        nt.math('MULTIPLY', nt.math('SUBTRACT', 1.0, dust), cfg.get('metallic', 0.0)))
        bump_s, bump_scale = cfg.get('bump', 0.12), 45.0
    elif kind in ('metal', 'wheelmetal', 'track'):
        rust_c = (0.13, 0.055, 0.022)
        rust = nt.math('MULTIPLY', grime, nt.mr(nt.noise(Pv, 5.0, 5.0, 0.6), 0.35, 0.65))
        col = nt.mix(nt.math('MULTIPLY', rust, 0.9), col, rust_c)
        col = nt.mix(nt.math('MULTIPLY', dust, 0.8), col, dust_col if kind != 'track' else srgb('#5b4a38'))
        bright = wear
        if track:
            bright = nt.math('MAXIMUM', wear, nt.math('MULTIPLY', nt.mr(Ps['Z'], 0.02, 0.06),
                                                      nt.mr(nt.noise(Pv, 30.0, 2.0, 0.5), 0.3, 0.6)))
        col = nt.mix(bright, col, (0.42, 0.42, 0.43))
        metal = nt.mixf(rust, 0.82, 0.25)
        metal = nt.mixf(dust, metal, 0.05)
        metal = nt.mixf(bright, metal, 1.0)
        rough = nt.mixf(rust, 0.42, 0.85)
        rough = nt.mixf(dust, rough, 0.9)
        rough = nt.mixf(bright, rough, 0.25)
        bump_s, bump_scale = 0.18, 60.0
    elif kind == 'rubber':
        col = nt.mix(dust, col, dust_col)
        col = nt.mix(nt.math('MULTIPLY', grime, 0.6), col, grime_col)
        rough = nt.mixf(dust, 0.82, 0.95)
        metal = 0.0
        bump_s, bump_scale = 0.3, 70.0
    else:  # glass / lights
        col = nt.mix(nt.math('MULTIPLY', dust, 0.5), col, dust_col)
        col = nt.mix(nt.math('MULTIPLY', grime, 0.5), col, grime_col)
        rough = nt.mixf(dust, 0.06 if kind == 'glass' else 0.2, 0.7)
        metal = 0.0
        bump_s, bump_scale = 0.0, 10.0

    bump = nt.n('ShaderNodeBump')
    bump.inputs['Strength'].default_value = bump_s
    bump.inputs['Distance'].default_value = 0.002
    hgt = nt.noise(Pv, bump_scale, 4.0, 0.55)
    if kind in ('paint', 'mark') and 'height_fn' in cfg:
        hgt = nt.math('ADD', nt.math('MULTIPLY', hgt, 0.3), cfg['height_fn'](nt, Pv, cfg))
    nt.put(bump.inputs['Height'], hgt)
    nt.put(bump.inputs['Normal'], bev.outputs['Normal'])

    out_col = nt.n('NodeReroute', name='OUT_COLOR')
    nt.put(out_col.inputs[0], col)
    orm = nt.n('ShaderNodeCombineColor', name='OUT_ORM')
    nt.put(orm.inputs['Red'], AO)
    nt.put(orm.inputs['Green'], rough)
    nt.put(orm.inputs['Blue'], metal)
    bsdf = nt.n('ShaderNodeBsdfPrincipled', name='BSDF')
    nt.put(bsdf.inputs['Base Color'], col)
    nt.put(bsdf.inputs['Roughness'], rough)
    nt.put(bsdf.inputs['Metallic'], metal)
    nt.put(bsdf.inputs['Normal'], bump.outputs['Normal'])
    emit = nt.n('ShaderNodeEmission', name='BAKE_EMIT')
    out = nt.n('ShaderNodeOutputMaterial', name='MAT_OUT')
    out.target = 'ALL'
    nt.n('ShaderNodeTexImage', name='BAKE_TARGET')
    nt.L.new(bsdf.outputs[0], out.inputs['Surface'])
    mat['tk_master'] = kind
    return mat


def set_bake_mode(mat, mode, img):
    nt = mat.node_tree
    N = nt.nodes
    emit, out, bsdf, tgt = N['BAKE_EMIT'], N['MAT_OUT'], N['BSDF'], N['BAKE_TARGET']
    tgt.image = img
    for nd in N:
        nd.select = False
    tgt.select = True
    N.active = tgt
    for l in list(out.inputs['Surface'].links):
        nt.links.remove(l)
    for l in list(emit.inputs['Color'].links):
        nt.links.remove(l)
    if mode == 'COLOR':
        nt.links.new(N['OUT_COLOR'].outputs[0], emit.inputs['Color'])
        nt.links.new(emit.outputs[0], out.inputs['Surface'])
    elif mode == 'ORM':
        nt.links.new(N['OUT_ORM'].outputs[0], emit.inputs['Color'])
        nt.links.new(emit.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(bsdf.outputs[0], out.inputs['Surface'])


def gltf_output_group():
    ng = bpy.data.node_groups.get('glTF Material Output')
    if ng is None:
        ng = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        ng.interface.new_socket(name='Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
        ng.nodes.new('NodeGroupInput')
    return ng


def final_material(name, col_img, orm_img, nrm_img):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = NT(mat)
    tc = nt.n('ShaderNodeTexImage', image=col_img)
    to = nt.n('ShaderNodeTexImage', image=orm_img)
    tn = nt.n('ShaderNodeTexImage', image=nrm_img)
    sc = nt.n('ShaderNodeSeparateColor')
    nm = nt.n('ShaderNodeNormalMap')
    bsdf = nt.n('ShaderNodeBsdfPrincipled')
    out = nt.n('ShaderNodeOutputMaterial')
    g = nt.n('ShaderNodeGroup')
    g.node_tree = gltf_output_group()
    nt.L.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
    nt.L.new(to.outputs['Color'], sc.inputs[0])
    nt.L.new(sc.outputs[1], bsdf.inputs['Roughness'])
    nt.L.new(sc.outputs[2], bsdf.inputs['Metallic'])
    nt.L.new(sc.outputs[0], g.inputs['Occlusion'])
    nt.L.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.L.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    nt.L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def new_image(name, size, color, noncolor):
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    w, h = (size, size) if isinstance(size, int) else size
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    px = np.empty((h, w, 4), dtype=np.float32)
    px[:] = (*color, 1.0)
    img.pixels.foreach_set(px.ravel())
    return img


def save_image(img, fname):
    path = os.path.join(TEX_DIR, fname)
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    img.filepath = '//textures/' + fname
    return path


# ----------------------------------------------------------------------------------------------
# Running gear / track solver
# ----------------------------------------------------------------------------------------------
def wheel_quant(r, p, lo, hi):
    """pick segment count `segs` and m so that one link of travel rotates the wheel by exactly
    m segments (seamless loop clips); returns (segs, m, exact radius)."""
    best = None
    for m in range(1, 8):
        exact = TAU * r * m / p
        segs = int(round(exact))
        if lo <= segs <= hi:
            r2 = p * segs / (TAU * m)
            score = abs(r2 - r) / r
            if best is None or score < best[0]:
                best = (score, segs, m, r2)
    if best is None:
        raise ValueError(f"no wheel quantisation for r={r} p={p}")
    return best[1], best[2], best[3]


def belt(circles):
    n = len(circles)
    betas = []
    for i in range(n):
        y1, z1, r1 = circles[i]
        y2, z2, r2 = circles[(i + 1) % n]
        dy, dz = y2 - y1, z2 - z1
        L = math.hypot(dy, dz)
        a = math.atan2(dz, dy)
        betas.append(a - math.acos(max(-1.0, min(1.0, (r1 - r2) / L))))
    segs, total = [], 0.0
    for i in range(n):
        y, z, r = circles[i]
        b_in, b_out = betas[i - 1], betas[i]
        sweep = (b_out - b_in) % TAU
        if sweep > TAU - 1e-7:
            sweep = 0.0
        if sweep > 1e-9:
            segs.append(('arc', (y, z), r, b_in, sweep))
            total += r * sweep
        y2, z2, r2 = circles[(i + 1) % n]
        p1 = (y + r * math.cos(b_out), z + r * math.sin(b_out))
        p2 = (y2 + r2 * math.cos(b_out), z2 + r2 * math.sin(b_out))
        Ls = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if Ls > 1e-9:
            segs.append(('line', p1, p2, b_out, Ls))
            total += Ls
    return segs, total


def belt_sample(segs, s):
    for sg in segs:
        if sg[0] == 'arc':
            _, c, r, a0, sw = sg
            Ls = r * sw
            if s <= Ls + 1e-12:
                a = a0 + s / r
                n = (math.cos(a), math.sin(a))
                return (c[0] + r * n[0], c[1] + r * n[1]), (-n[1], n[0]), n
            s -= Ls
        else:
            _, p1, p2, b, Ls = sg
            if s <= Ls + 1e-12:
                d = ((p2[0] - p1[0]) / Ls, (p2[1] - p1[1]) / Ls)
                return (p1[0] + d[0] * s, p1[1] + d[1] * s), d, (math.cos(b), math.sin(b))
            s -= Ls
    return belt_sample(segs, 0.0)


def solve_running_gear(rg):
    p, tp, g = rg['p'], rg['tp'], rg['g']
    segs_r, m_r, R = wheel_quant(rg['road']['r'], p, 11, 24)
    zc = g + tp + R
    road = [dict(kind='road', y=y, z=zc, r=R, rp=R + tp / 2, reff=R, segs=segs_r) for y in rg['road']['ys']]

    def end(e):
        if e['kind'] == 'sprocket':
            rp = e['Z'] * p / TAU
            return dict(kind='sprocket', y=e['y'], z=e['z'], r=rp, rp=rp, reff=rp, segs=e['Z'], Z=e['Z'])
        sg, m, r = wheel_quant(e['r'], p, 11, 24)
        return dict(kind='idler', y=e['y'], z=e['z'], r=r, rp=r + tp / 2, reff=r, segs=sg)

    front, rear = end(rg['front']), end(rg['rear'])
    idler = front if front['kind'] == 'idler' else rear
    christie = rg.get('top') == 'wheels'

    def circles():
        c = [(rear['y'], rear['z'], rear['rp'])]
        if christie:
            c += [(w['y'], w['z'], w['rp']) for w in reversed(road)]
        c += [(front['y'], front['z'], front['rp'])]
        c += [(w['y'], w['z'], w['rp']) for w in road]
        return c

    L0 = belt(circles())[1]
    N = int(round(L0 / p))
    target = N * p

    def f(y):
        idler['y'] = y
        return belt(circles())[1] - target

    sgn = -1.0 if idler is front else 1.0
    a, b = idler['y'], idler['y'] + 0.02 * sgn
    fa, fb = f(a), f(b)
    for _ in range(40):
        if abs(fb) < 1e-10 or fb == fa:
            break
        c = b - fb * (b - a) / (fb - fa)
        a, fa, b = b, fb, c
        fb = f(b)
    idler['y'] = b
    segs, L = belt(circles())

    rollers = []
    if rg.get('rollers'):
        sgr, mr, rr = wheel_quant(rg['rollers']['r'], p, 8, 14)
        top = max((sg for sg in segs if sg[0] == 'line'), key=lambda sg: math.sin(sg[3]))
        _, p1, p2, bb, Ls = top
        nrm = (math.cos(bb), math.sin(bb))
        for y in rg['rollers']['ys']:
            t = (y - p1[0]) / (p2[0] - p1[0])
            z = p1[1] + t * (p2[1] - p1[1])
            rollers.append(dict(kind='roller', y=y, z=z - nrm[1] * (tp / 2 + rr), r=rr, reff=rr, segs=sgr))
    links = [belt_sample(segs, i * p) for i in range(N)]
    return dict(p=p, N=N, L=L, road=road, front=front, rear=rear, rollers=rollers, links=links, segs=segs)


# ----------------------------------------------------------------------------------------------
# Wheel / sprocket / link templates (local axis X = axle, +X = outer face)
# ----------------------------------------------------------------------------------------------
def road_wheel_mesh(name, R, ww, gap, segs, mats, steel=False):
    a, g2 = ww / 2, gap / 2
    tire = WM if steel else RB
    prof = [(0, a + 0.045), (0.2 * R, a + 0.045), (0.3 * R, a + 0.004), (0.78 * R, a - 0.014),
            (0.85 * R, a), (R, a - 0.03), (R, g2), (0.55 * R, g2), (0.55 * R, -g2), (R, -g2),
            (R, -a + 0.025), (0.86 * R, -a), (0, -a)]
    mm = [WM, WM, WP, WP, tire, tire, WP, WP, WP, tire, tire, WP]
    mb = MB()
    mb.lathe(prof, segs, mats=mm)
    # hub bolts are omitted on purpose: wheel geometry must stay `segs`-fold symmetric
    return mb.to_mesh(name, mats, sharp=40.0)


def roller_mesh(name, R, ww, gap, segs, mats):
    a, g2 = ww / 2, gap / 2
    prof = [(0, a + 0.03), (0.35 * R, a + 0.03), (0.8 * R, a), (R, a - 0.015), (R, g2), (0.62 * R, g2),
            (0.62 * R, -g2), (R, -g2), (R, -a), (0, -a)]
    mm = [WM, WM, WP, RB, WP, WP, WP, RB, WP]
    mb = MB()
    mb.lathe(prof, segs, mats=mm)
    return mb.to_mesh(name, mats, sharp=40.0)


def sprocket_mesh(name, rp, tw, Z, mats):
    mb = MB()
    a = tw / 2
    hub_segs = Z * (2 if Z < 10 else 1)
    prof = [(0, a + 0.06), (0.22 * rp, a + 0.06), (0.3 * rp, a + 0.02), (0.5 * rp, a - 0.005),
            (0.66 * rp, a - 0.03), (0.66 * rp, -a + 0.04), (0, -a + 0.04)]
    mb.lathe(prof, hub_segs, mats=[WM, WM, WP, WP, WP, WP], phase=math.pi / Z)
    r_tip, r_root, r_in = rp + 0.075, rp - 0.04, 0.6 * rp
    step = TAU / Z
    for xc in (a * 0.55, -a * 0.55):
        x0, x1 = xc - 0.024, xc + 0.024
        outer, inner = [], []
        for k in range(Z):
            th = k * step
            for ang, r in ((th - 0.17 * step, r_tip), (th + 0.17 * step, r_tip), (th + 0.5 * step, r_root)):
                outer.append((r * math.cos(ang), r * math.sin(ang)))
                inner.append((r_in * math.cos(ang), r_in * math.sin(ang)))
        o0 = [mb.bm.verts.new((x0, y, z)) for y, z in outer]
        o1 = [mb.bm.verts.new((x1, y, z)) for y, z in outer]
        i0 = [mb.bm.verts.new((x0, y, z)) for y, z in inner]
        i1 = [mb.bm.verts.new((x1, y, z)) for y, z in inner]
        n = len(outer)
        for j in range(n):
            k = (j + 1) % n
            mb.face((o0[j], o0[k], o1[k], o1[j]), WM)
            mb.face((o1[j], o1[k], i1[k], i1[j]), WM)
            mb.face((i0[j], i0[k], o0[k], o0[j]), WM)
            mb.face((i1[j], i1[k], i0[k], i0[j]), WM)
    return mb.to_mesh(name, mats, sharp=40.0)


LINK_REGIONS = {  # face index -> uv rect (u0, v0, u1, v1) ; shared layout for every tank
    0: (0.00, 0.76, 0.50, 0.82), 1: (0.50, 0.50, 0.60, 0.70), 2: (0.00, 0.82, 0.50, 0.88),
    3: (0.60, 0.50, 0.70, 0.70), 4: (0.50, 0.00, 1.00, 0.50), 5: (0.00, 0.00, 0.50, 0.50),
    6: (0.00, 0.60, 0.50, 0.68), 7: (0.70, 0.50, 0.75, 0.60), 8: (0.00, 0.68, 0.50, 0.76),
    9: (0.75, 0.50, 0.80, 0.60), 10: (0.00, 0.50, 0.50, 0.60),
    11: (0.62, 0.72, 0.74, 0.86), 12: (0.86, 0.72, 0.93, 0.86), 13: (0.74, 0.72, 0.86, 0.86),
    14: (0.93, 0.72, 1.00, 0.86), 15: (0.50, 0.72, 0.62, 0.80),
}


def link_template(p, tp, g, tw, hw=0.06, hh=0.065):
    """one track link in local (x across, y along pitch, z outward). Returns verts, faces, uvs."""
    mb = MB()
    gap = 0.014
    mb.box((0, 0, 0), (tw, p - gap, tp), 0)
    mb.box((0, 0, tp / 2 + g / 2), (tw - 0.02, 0.36 * p, g), 0, top=(0.97, 0.55), cap0=False)
    mb.box((0, 0, -tp / 2 - hh / 2), (hw, 0.56 * p, hh), 0, bot=(0.6, 0.45), cap1=False)
    bm = mb.bm
    bm.verts.index_update()
    verts = [tuple(v.co) for v in bm.verts]
    faces, uvs = [], []
    for fi, f in enumerate(bm.faces):
        idx = [v.index for v in f.verts]
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a1, a2 = [i for i in range(3) if i != ax]
        cs = [v.co for v in f.verts]
        lo1, hi1 = min(c[a1] for c in cs), max(c[a1] for c in cs)
        lo2, hi2 = min(c[a2] for c in cs), max(c[a2] for c in cs)
        u0, v0, u1, v1 = LINK_REGIONS[fi]
        pad = 0.004
        fu = []
        for c in cs:
            s = (c[a1] - lo1) / max(hi1 - lo1, 1e-9)
            t = (c[a2] - lo2) / max(hi2 - lo2, 1e-9)
            fu.append((u0 + pad + s * (u1 - u0 - 2 * pad), v0 + pad + t * (v1 - v0 - 2 * pad)))
        faces.append(idx)
        uvs.append(fu)
    bm.free()
    return dict(verts=verts, faces=faces, uvs=uvs)


def mesh_from_template(name, tpl, mats, place_fn, count):
    """build a mesh by instancing a template `count` times; place_fn(i) -> list of world verts."""
    nv = len(tpl['verts'])
    verts, faces = [], []
    for i in range(count):
        verts += place_fn(i)
        faces += [tuple(v + i * nv for v in f) for f in tpl['faces']]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    flat = [c for i in range(count) for fu in tpl['uvs'] for uv in fu for c in uv]
    uvl.data.foreach_set('uv', flat)
    for m in mats:
        me.materials.append(m)
    me.set_sharp_from_angle(angle=math.radians(35))
    me.update()
    return me


# ----------------------------------------------------------------------------------------------
# Muzzle flash texture + geometry
# ----------------------------------------------------------------------------------------------
def flash_image():
    name = 'T_MuzzleFlash'
    w, h = 512, 256
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = 'sRGB'
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    px = np.zeros((h, w, 4), np.float32)
    # left half: side flame (u along flame, v across)
    u = xx[:, :256] / 255.0
    v = (yy[:, :256] / 255.0) * 2 - 1
    width = 0.12 + 0.75 * u * (1 - u) * 1.6 + 0.05
    I1 = np.exp(-((v / width) ** 2) * 2.2) * (1 - u) ** 1.4 * np.clip(u / 0.05 + 0.25, 0, 1)
    I1 *= 0.8 + 0.2 * np.cos(u * 34.0) ** 2
    # right half: star burst seen from the front
    sx = (xx[:, 256:] - 384) / 128.0
    sy = (yy[:, 256:] - 128) / 128.0
    r = np.sqrt(sx ** 2 + sy ** 2)
    th = np.arctan2(sy, sx)
    spikes = ((0.5 + 0.5 * np.cos(5 * th)) ** 8) * np.clip(1 - r, 0, 1) ** 1.2
    spikes2 = ((0.5 + 0.5 * np.cos(5 * th + 0.63)) ** 14) * np.clip(1 - r * 1.4, 0, 1)
    I2 = np.exp(-(r / 0.22) ** 2) + 0.9 * spikes + 0.5 * spikes2
    I = np.concatenate([I1, I2], axis=1)
    I = np.clip(I, 0, 1)
    hot = np.array([1.0, 0.93, 0.7])
    mid = np.array([1.0, 0.55, 0.12])
    edge = np.array([0.85, 0.22, 0.03])
    t = I[..., None]
    col = np.where(t > 0.5, mid + (hot - mid) * ((t - 0.5) * 2), edge + (mid - edge) * (t * 2))
    px[..., :3] = col
    px[..., 3] = np.clip(I * 1.35, 0, 1)
    img.pixels.foreach_set(px.ravel())
    save_image(img, 'T_MuzzleFlash.png')
    return img


def flash_material():
    mat = bpy.data.materials.get('MAT_MuzzleFlash')
    if mat:
        return mat
    img = flash_image()
    mat = bpy.data.materials.new('MAT_MuzzleFlash')
    mat.use_nodes = True
    nt = NT(mat)
    ti = nt.n('ShaderNodeTexImage', image=img)
    bsdf = nt.n('ShaderNodeBsdfPrincipled')
    out = nt.n('ShaderNodeOutputMaterial')
    nt.L.new(ti.outputs['Color'], bsdf.inputs['Base Color'])
    nt.L.new(ti.outputs['Alpha'], bsdf.inputs['Alpha'])
    nt.L.new(ti.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 6.0
    bsdf.inputs['Roughness'].default_value = 1.0
    nt.L.new(bsdf.outputs[0], out.inputs['Surface'])
    try:
        mat.surface_render_method = 'BLENDED'
    except Exception:
        pass
    mat.use_backface_culling = False
    return mat


def flash_quads(muzzle, fwd, Lf, Wf):
    """returns verts (rest size = FLASH_REST), faces, per-face uvs"""
    F = frame(muzzle, fwd)
    R3 = F.to_3x3()
    o = Vector(muzzle)
    verts, faces, uvs = [], [], []

    def add(local_pts, uv):
        base = len(verts)
        for lp in local_pts:
            verts.append(tuple(o + (R3 @ Vector(lp)) * FLASH_REST))
        faces.append(tuple(range(base, base + len(local_pts))))
        uvs.append(uv)

    for k in range(3):
        ang = k * math.pi / 3
        py, pz = math.cos(ang) * Wf / 2, math.sin(ang) * Wf / 2
        add([(-0.04 * Lf, -py, -pz), (Lf, -py, -pz), (Lf, py, pz), (-0.04 * Lf, py, pz)],
            [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)])
    s = Wf * 0.8
    add([(0.12 * Lf, -s, -s), (0.12 * Lf, s, -s), (0.12 * Lf, s, s), (0.12 * Lf, -s, s)],
        [(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)])
    return verts, faces, uvs


# ----------------------------------------------------------------------------------------------
# Widgets for bone custom shapes
# ----------------------------------------------------------------------------------------------
def widget(name):
    full = 'WGT_' + name
    ob = bpy.data.objects.get(full)
    if ob:
        return ob
    wc = get_coll('TK_Widgets')
    verts, edges = [], []
    if name == 'circle':
        n = 32
        verts = [(math.cos(TAU * i / n), 0.0, math.sin(TAU * i / n)) for i in range(n)]
        edges = [(i, (i + 1) % n) for i in range(n)]
    elif name == 'square':
        verts = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    elif name == 'arrow':
        verts = [(0, 0, 0), (0, 1, 0), (0.12, 0.85, 0), (-0.12, 0.85, 0), (0, 0.85, 0.12), (0, 0.85, -0.12)]
        edges = [(0, 1), (1, 2), (1, 3), (1, 4), (1, 5)]
    elif name == 'box':
        verts = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    elif name == 'diamond':
        verts = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        edges = [(0, 2), (2, 1), (1, 3), (3, 0), (0, 4), (4, 1), (1, 5), (5, 0), (2, 4), (4, 3), (3, 5), (5, 2)]
    me = bpy.data.meshes.new(full)
    me.from_pydata(verts, edges, [])
    ob = bpy.data.objects.new(full, me)
    wc.objects.link(ob)
    return ob


def action_fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def set_engine(name):
    sc = bpy.context.scene
    try:
        sc.render.engine = name
    except TypeError as e:
        print('engine error', e)


def setup_cycles_gpu():
    cp = bpy.context.preferences.addons['cycles'].preferences
    for t in ('OPTIX', 'CUDA'):
        try:
            cp.compute_device_type = t
            cp.get_devices()
            ok = False
            for d in cp.devices:
                d.use = (d.type == t)
                ok = ok or d.use
            if ok:
                break
        except TypeError:
            continue
    set_engine('CYCLES')
    sc = bpy.context.scene
    sc.cycles.device = 'GPU'
    sc.cycles.samples = 16
    sc.render.bake.margin = 6
