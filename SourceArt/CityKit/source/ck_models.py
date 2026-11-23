# Dominion I - CityKit models (Blender 5.x): trees, civilian cars (+ burnt wrecks), street furniture and cover pieces.
# Executed with exec() from a driver that defines KIT_DIR. Everything: metres, Z up, front = -Y (Unity +Z), origin on
# the ground. Each model is an empty root <Name> with <Name>_LOD0 / <Name>_LOD1 children (Unity builds the LODGroup).
import bpy, bmesh, math, os, random, json
from mathutils import Vector, Matrix

KIT_DIR = globals().get('KIT_DIR')
TEX = os.path.join(KIT_DIR, 'textures')
BTEX = os.path.join(os.path.dirname(KIT_DIR), 'BuildingKit', 'textures')
Z = Vector((0, 0, 1))
TAU = math.tau

# material name -> (texture stem, folder, tint hex, alpha clip)
MATS = {
    'CK_Bark': ('Bark', TEX, 'ffffff', False),
    'CK_LeavesBroad': ('LeavesBroad', TEX, 'ffffff', True),
    'CK_LeavesConifer': ('LeavesConifer', TEX, 'ffffff', True),
    'CK_LeavesAutumn': ('LeavesAutumn', TEX, 'ffffff', True),
    'CK_CarPaint': ('CarPaint', TEX, 'b8bcc2', False),
    'CK_Burnt': ('Burnt', TEX, 'ffffff', False),
    'CK_CarGlass': (None, None, '1c2228', False),
    'CK_Rubber': (None, None, '1a1a1a', False),
    'CK_Chrome': (None, None, 'b4b8bc', False),
    'CK_Lights': (None, None, 'f2ead8', False),
    'CK_TailLights': (None, None, '8a1410', False),
    'CK_CarInterior': (None, None, '2a2826', False),
    'BLD_MetalDark': ('MetalDark', BTEX, 'ffffff', False),
    'BLD_Galvanized': ('Galvanized', BTEX, 'ffffff', False),
    'BLD_Concrete': ('Concrete', BTEX, 'ffffff', False),
    'BLD_Wood': ('Wood', BTEX, 'ffffff', False),
    'BLD_TrimGreen': ('Trim', BTEX, '4f6a58', False),
}
FLAT = {'CK_CarGlass': (0.08, 0.0), 'CK_Rubber': (0.85, 0.0), 'CK_Chrome': (0.2, 1.0), 'CK_Lights': (0.1, 0.0),
        'CK_TailLights': (0.2, 0.0), 'CK_CarInterior': (0.8, 0.0)}


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m and m.get('ck') == 2:
        return m
    m = m or bpy.data.materials.new(name)
    m['ck'] = 2
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs[0])
    stem, folder, tint, clip = MATS[name]
    if stem is None:
        bs.inputs['Base Color'].default_value = lin(tint)
        r, mt = FLAT[name]
        bs.inputs['Roughness'].default_value = r
        bs.inputs['Metallic'].default_value = mt
        m.diffuse_color = lin(tint)
        return m

    def img(kind, non):
        p = os.path.join(folder, f'T_{stem}_{kind}.png')
        im = bpy.data.images.load(p, check_existing=True)
        im.colorspace_settings.name = 'Non-Color' if non else 'sRGB'
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = im
        return n
    bc, orm, nm = img('BaseColor', False), img('ORM', True), img('Normal', True)
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(bc.outputs['Color'], mix.inputs[6])
    mix.inputs[7].default_value = lin(tint)
    nt.links.new(mix.outputs[2], bs.inputs['Base Color'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(orm.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[1], bs.inputs['Roughness'])
    nt.links.new(sep.outputs[2], bs.inputs['Metallic'])
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(nm.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bs.inputs['Normal'])
    if clip:
        nt.links.new(bc.outputs['Alpha'], bs.inputs['Alpha'])
        m.surface_render_method = 'DITHERED'
        m.use_backface_culling = False
    m.diffuse_color = lin(tint)
    return m


class Mesh:
    def __init__(self):
        self.V, self.F = [], []          # F: (idx, mat, uv, smooth, normals or None)

    def poly(self, pts, mat, uv=None, smooth=False, normals=None, normal=None):
        pts = [Vector(p) for p in pts]
        if normal is not None:
            nn = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if nn.dot(Vector(normal)) < 0:
                pts.reverse()
                uv = list(reversed(uv)) if uv else None
                normals = list(reversed(normals)) if normals else None
        b = len(self.V)
        self.V += pts
        if uv is None:
            uv = auto_uv(pts)
        self.F.append((list(range(b, b + len(pts))), mat, uv, smooth, normals))

    def tube(self, path, radii, segs, mat, cap=True, v_scale=1.0, u_tiles=1.0):
        """Generalised cylinder along a polyline (parallel-transport frames)."""
        path = [Vector(p) for p in path]
        rings = []
        t = (path[1] - path[0]).normalized()
        ref = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
        nrm = t.cross(ref).normalized()
        for i, p in enumerate(path):
            if i > 0:
                t2 = (path[min(i + 1, len(path) - 1)] - path[i - 1]).normalized()
                ax = t.cross(t2)
                if ax.length > 1e-6:
                    ang = t.angle(t2)
                    nrm = Matrix.Rotation(ang, 3, ax.normalized()) @ nrm
                t = t2
            b = t.cross(nrm).normalized()
            n2 = b.cross(t).normalized()
            rings.append([p + (n2 * math.cos(a) + b * math.sin(a)) * radii[i] for a in (k / segs * TAU for k in range(segs + 1))])
        L = 0.0
        vs = [0.0]
        for i in range(1, len(path)):
            L += (path[i] - path[i - 1]).length
            vs.append(L)
        for i in range(len(path) - 1):
            for k in range(segs):
                a, b2 = rings[i][k], rings[i][k + 1]
                c, d = rings[i + 1][k + 1], rings[i + 1][k]
                u0, u1 = k / segs * u_tiles, (k + 1) / segs * u_tiles
                uv = [(u0, vs[i] * v_scale), (u1, vs[i] * v_scale), (u1, vs[i + 1] * v_scale), (u0, vs[i + 1] * v_scale)]
                ns = [(rings[i][k] - path[i]).normalized(), (rings[i][k + 1] - path[i]).normalized(),
                      (rings[i + 1][k + 1] - path[i + 1]).normalized(), (rings[i + 1][k] - path[i + 1]).normalized()]
                self.poly([a, b2, c, d], mat, uv, True, ns)
        if cap and radii[-1] > 0.01:
            self.poly(rings[-1][:segs][::-1], mat)

    def box(self, c, s, mat, rot=None, skip=()):
        cx, cy, cz = c
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        R = rot or Matrix.Identity(3)
        P = lambda x, y, z: Vector((cx, cy, cz)) + R @ Vector((x, y, z))
        faces = {'-x': [(-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)], '+x': [(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)],
                 '-y': [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)], '+y': [(-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)],
                 '-z': [(-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1)], '+z': [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]}
        for k, f in faces.items():
            if k in skip:
                continue
            self.poly([P(x * hx, y * hy, z * hz) for x, y, z in f], mat)

    def prism(self, prof, x0, x1, mat, caps=True):
        """Extrude a closed (y, z) profile (counter-clockwise seen from +x) from x0 to x1."""
        n = len(prof)
        per = 0.0
        acc = [0.0]
        for i in range(n):
            a, b = prof[i], prof[(i + 1) % n]
            per += math.hypot(b[0] - a[0], b[1] - a[1])
            acc.append(per)
        for i in range(n):
            a, b = prof[i], prof[(i + 1) % n]
            pts = [(x0, a[0], a[1]), (x1, a[0], a[1]), (x1, b[0], b[1]), (x0, b[0], b[1])]
            self.poly(pts, mat, [(x0 / 2, acc[i] / 2), (x1 / 2, acc[i] / 2), (x1 / 2, acc[i + 1] / 2), (x0 / 2, acc[i + 1] / 2)],
                      normal=Vector((0, b[1] - a[1], -(b[0] - a[0]))))
        if caps:
            self.poly([(x0, y, z) for y, z in prof], mat, normal=(-1, 0, 0))
            self.poly([(x1, y, z) for y, z in prof], mat, normal=(1, 0, 0))

    def tris(self):
        return sum(len(f[0]) - 2 for f in self.F)


def auto_uv(pts):
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.length < 1e-9:
        return [(0, 0)] * len(pts)
    n.normalize()
    if abs(n.z) > 0.9:
        return [(p.x / 2, p.y / 2) for p in pts]
    if abs(n.x) > abs(n.y):
        return [(p.y / 2, p.z / 2) for p in pts]
    return [(p.x / 2, p.z / 2) for p in pts]


def build(m, name, coll):
    me = bpy.data.meshes.get(name)
    if me:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    used = []
    for f in m.F:
        if f[1] not in used:
            used.append(f[1])
    me.from_pydata([tuple(v) for v in m.V], [], [f[0] for f in m.F])
    for u in used:
        me.materials.append(get_mat(u))
    me.polygons.foreach_set('material_index', [used.index(f[1]) for f in m.F])
    me.polygons.foreach_set('use_smooth', [bool(f[3]) for f in m.F])
    uvl = me.uv_layers.new(name='UVMap')
    flat = []
    for f in m.F:
        for p in f[2]:
            flat += [p[0], p[1]]
    uvl.data.foreach_set('uv', flat)
    me.validate()
    if any(f[4] for f in m.F):
        ns = []
        for f in m.F:
            if f[4]:
                ns += [tuple(v) for v in f[4]]
            else:
                pts = [m.V[i] for i in f[0]]
                fn = (pts[1] - pts[0]).cross(pts[2] - pts[0]).normalized()
                ns += [tuple(fn)] * len(f[0])
        me.normals_split_custom_set(ns)
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


def finish(name, lods, coll, info=None):
    sub = get_coll(name, coll)
    for o in list(sub.objects):
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new(name, None)
    sub.objects.link(root)
    stats = []
    for i, m in enumerate(lods):
        o = build(m, f'{name}_LOD{i}', sub)
        o.parent = root
        if i > 0:
            o.hide_render = True
            o.hide_set(True)
        stats.append(m.tris())
    root['ck_info'] = json.dumps(dict(info or {}, tris=stats))
    return root, stats


# ============================================================================================== trees
def leaf_card(m, c, size, rng, mat, centre, cells=4, up_bias=0.3):
    """One alpha-tested leaf card at c, randomly oriented, normals bent outward from the crown centre."""
    n = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1) + up_bias)).normalized()
    a = n.orthogonal().normalized()
    b = n.cross(a)
    rot = rng.uniform(0, TAU)
    a, b = a * math.cos(rot) + b * math.sin(rot), -a * math.sin(rot) + b * math.cos(rot)
    h = size / 2
    pts = [c - a * h - b * h, c + a * h - b * h, c + a * h + b * h, c - a * h + b * h]
    q = rng.randrange(cells)
    u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
    uv = [(u0 + 0.005, v0 + 0.005), (u0 + 0.495, v0 + 0.005), (u0 + 0.495, v0 + 0.495), (u0 + 0.005, v0 + 0.495)]
    out = [((p - centre).normalized() * 0.75 + Z * 0.25).normalized() for p in pts]
    m.poly(pts, mat, uv, True, out)


def broadleaf(seed, height=11.0, crown=4.2, mat='CK_LeavesBroad', detail=1.0):
    rng = random.Random(seed)
    lods = []
    for lod in (0, 1):
        m = Mesh()
        rng.seed(seed)
        trunk_h = height * 0.38
        lean = Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0))
        trunk = [Vector((0, 0, -0.2)), Vector((0, 0, trunk_h * 0.5)) + lean * 0.3, Vector((0, 0, trunk_h)) + lean]
        r0 = 0.22 * height / 11
        m.tube(trunk, [r0 * 1.25, r0, r0 * 0.8], 8 if lod == 0 else 5, 'CK_Bark', cap=False, u_tiles=2, v_scale=0.5)
        centre = Vector((0, 0, height * 0.62)) + lean
        nb = 5 if lod == 0 else 3
        tips = []
        for i in range(nb):
            ang = i / nb * TAU + rng.uniform(-0.4, 0.4)
            out = Vector((math.cos(ang), math.sin(ang), 0))
            p0 = trunk[-1]
            p1 = p0 + out * crown * 0.35 + Z * height * 0.15
            p2 = p0 + out * crown * 0.75 + Z * height * 0.32 + Vector((rng.uniform(-.5, .5), rng.uniform(-.5, .5), 0))
            m.tube([p0, p1, p2], [r0 * 0.7, r0 * 0.45, r0 * 0.15], 6 if lod == 0 else 4, 'CK_Bark', u_tiles=1, v_scale=0.5)
            tips += [p1, p2]
            if lod == 0:
                for j in range(2):
                    side = out.cross(Z) * (1 if j else -1)
                    q = p1 + (p2 - p1) * 0.5
                    m.tube([q, q + side * crown * 0.35 + Z * height * 0.12 + out * crown * 0.15],
                           [r0 * 0.25, r0 * 0.06], 4, 'CK_Bark', u_tiles=1, v_scale=0.5)
                    tips.append(q + side * crown * 0.35 + Z * height * 0.12)
        count = int((150 if lod == 0 else 34) * detail)
        size = (2.2 if lod == 0 else 3.6) * height / 11
        for k in range(count):
            # leaf clumps fill an ellipsoid crown, biased toward the branch tips
            if rng.random() < 0.55 and tips:
                c = rng.choice(tips) + Vector((rng.gauss(0, crown * 0.25), rng.gauss(0, crown * 0.25), rng.gauss(0, height * 0.07)))
            else:
                d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized() * (rng.random() ** 0.4)
                c = centre + Vector((d.x * crown, d.y * crown, d.z * height * 0.28))
            leaf_card(m, c, size * rng.uniform(0.8, 1.2), rng, mat, centre)
        lods.append(m)
    return lods


def conifer(seed, height=15.0, radius=3.0):
    rng = random.Random(seed)
    lods = []
    for lod in (0, 1):
        m = Mesh()
        rng.seed(seed)
        r0 = 0.25 * height / 15
        m.tube([Vector((0, 0, -0.2)), Vector((0, 0, height * 0.5)), Vector((0, 0, height))], [r0, r0 * 0.6, 0.02],
               7 if lod == 0 else 5, 'CK_Bark', u_tiles=2, v_scale=0.4)
        tiers = 11 if lod == 0 else 6
        for t in range(tiers):
            f = t / (tiers - 1)
            z = height * (0.18 + 0.8 * f)
            rad = radius * (1 - f) ** 0.9 + 0.35
            nc = max(4, int((10 if lod == 0 else 6) * (1 - f * 0.6)))
            for i in range(nc):
                ang = i / nc * TAU + rng.uniform(-0.3, 0.3) + t * 0.7
                out = Vector((math.cos(ang), math.sin(ang), 0))
                side = out.cross(Z)
                L = rad * rng.uniform(0.9, 1.15)
                w = (1.4 if lod == 0 else 2.0) * (1 - f * 0.5)
                p0 = Vector((0, 0, z))
                p1 = p0 + out * L - Z * L * 0.35          # drooping bough
                pts = [p0 - side * w * 0.3, p1 - side * w, p1 + side * w, p0 + side * w * 0.3]
                q = rng.randrange(4)
                u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
                uv = [(u0 + 0.12, v0 + 0.02), (u0 + 0.02, v0 + 0.48), (u0 + 0.48, v0 + 0.48), (u0 + 0.38, v0 + 0.02)]
                centre = Vector((0, 0, z - L * 0.2))
                ns = [((p - centre).normalized() * 0.6 + Z * 0.4).normalized() for p in pts]
                m.poly(pts, 'CK_LeavesConifer', uv, True, ns)
                if lod == 0:
                    # a second, crossed card for volume
                    up = (p1 - p0).cross(side).normalized() * w * 0.6
                    pts2 = [p0 - up * 0.3, p1 - up, p1 + up, p0 + up * 0.3]
                    m.poly(pts2, 'CK_LeavesConifer', uv, True, ns)
        lods.append(m)
    return lods


# ============================================================================================== cars
def car(kind, burnt=False):
    """Low-poly civilian vehicles: sedan, suv, van, bus. Front = -Y. Burnt wrecks sit on their rims."""
    dims = {'sedan': (1.8, 4.6, 1.42), 'suv': (1.9, 4.7, 1.75), 'van': (2.0, 5.2, 2.25), 'bus': (2.55, 11.8, 3.1)}[kind]
    W, L, H = dims
    paint = 'CK_Burnt' if burnt else 'CK_CarPaint'
    glass = 'CK_Rubber' if burnt else 'CK_CarGlass'
    lods = []
    for lod in (0, 1):
        m = Mesh()
        wr = 0.34 if kind in ('sedan', 'suv') else (0.38 if kind == 'van' else 0.5)
        sink = 0.18 if burnt else 0.0
        zb = wr * 0.65 - sink                    # body bottom
        hw = W / 2
        # side profile (y, z) of the lower body and cabin, front at -L/2
        if kind == 'sedan':
            lower = [(-L / 2, zb + 0.1), (-L / 2 + 0.1, zb + 0.62), (L / 2 - 0.05, zb + 0.66), (L / 2, zb + 0.12)]
            cabin = [(-L / 2 + 1.25, zb + 0.66), (-L / 2 + 1.95, H - sink), (L / 2 - 1.25, H - sink), (L / 2 - 0.55, zb + 0.68)]
        elif kind == 'suv':
            lower = [(-L / 2, zb + 0.12), (-L / 2 + 0.08, zb + 0.78), (L / 2, zb + 0.8), (L / 2, zb + 0.12)]
            cabin = [(-L / 2 + 1.1, zb + 0.8), (-L / 2 + 1.75, H - sink), (L / 2 - 0.25, H - sink), (L / 2 - 0.05, zb + 0.8)]
        elif kind == 'van':
            lower = [(-L / 2, zb + 0.1), (-L / 2 + 0.05, zb + 0.9), (L / 2, zb + 0.9), (L / 2, zb + 0.1)]
            cabin = [(-L / 2 + 0.05, zb + 0.9), (-L / 2 + 0.7, H - sink), (L / 2, H - sink), (L / 2, zb + 0.9)]
        else:
            lower = [(-L / 2, zb + 0.1), (-L / 2, zb + 1.0), (L / 2, zb + 1.0), (L / 2, zb + 0.1)]
            cabin = [(-L / 2, zb + 1.0), (-L / 2 + 0.1, H - sink), (L / 2, H - sink), (L / 2, zb + 1.0)]
        inset = 0.12 if kind != 'bus' else 0.02

        def side_panel(profile, x, m_, nx):
            m.poly([(x, y, z) for y, z in profile], m_, normal=(nx, 0, 0))

        # lower body: sides, front, back, top deck
        for x, nx in ((-hw, -1), (hw, 1)):
            side_panel(lower, x, paint, nx)
        for i in range(len(lower) - 1):
            (y0, z0), (y1, z1) = lower[i], lower[i + 1]
            n = Vector((0, -(z1 - z0), (y1 - y0)))
            m.poly([(-hw, y0, z0), (hw, y0, z0), (hw, y1, z1), (-hw, y1, z1)], paint, normal=n if n.length > 0 else (0, 0, 1))
        m.poly([(-hw, lower[-1][0], lower[-1][1]), (hw, lower[-1][0], lower[-1][1]), (hw, lower[0][0], lower[0][1]),
                (-hw, lower[0][0], lower[0][1])], 'CK_Rubber', normal=(0, 0, -1))
        # cabin: glass sides (inset), roof, windscreen, rear window
        cw = hw - inset
        for x, nx in ((-cw, -1), (cw, 1)):
            side_panel(cabin, x, glass if kind != 'bus' else glass, nx)
        for i in range(len(cabin) - 1):
            (y0, z0), (y1, z1) = cabin[i], cabin[i + 1]
            n = Vector((0, -(z1 - z0), (y1 - y0)))
            mat = paint if i == 1 else glass
            m.poly([(-cw, y0, z0), (cw, y0, z0), (cw, y1, z1), (-cw, y1, z1)], mat, normal=n)
        if kind in ('sedan', 'suv', 'van') and lod == 0:
            # door pillars across the side glass
            (fy0, fz0), (fy1, fz1), (ry1, rz1), (ry0, rz0) = cabin
            for f in ((0.42,) if kind == 'sedan' else (0.38, 0.7)):
                yb = fy0 + (ry0 - fy0) * f
                yt = fy1 + (ry1 - fy1) * f
                for x, nx in ((-cw - 0.005, -1), (cw + 0.005, 1)):
                    m.poly([(x, yb - 0.06, fz0), (x, yb + 0.06, fz0), (x, yt + 0.06, fz1), (x, yt - 0.06, fz1)], paint, normal=(nx, 0, 0))
        if lod == 0:
            # dark wheel arches on the body sides
            wb0 = {'sedan': 1.35, 'suv': 1.4, 'van': 1.6, 'bus': 3.6}[kind]
            for y in (-wb0, wb0):
                for x, nx in ((-hw - 0.004, -1), (hw + 0.004, 1)):
                    pts = [(x, y + math.cos(a) * wr * 1.25, wr - sink + math.sin(a) * wr * 1.25) for a in
                           [k / 8 * math.pi for k in range(9)]]
                    pts = [(x, y - wr * 1.25, zb + 0.02)] + pts[::-1][1:-1] + [(x, y + wr * 1.25, zb + 0.02)]
                    m.poly(pts, 'CK_Rubber', normal=(nx, 0, 0))
        if kind == 'bus' and lod == 0:
            # window mullions and a paint band under the windows
            for k in range(7):
                y = -L / 2 + 1.2 + k * (L - 2.0) / 6
                for x, nx in ((-hw - 0.01, -1), (hw + 0.01, 1)):
                    m.poly([(x, y - 0.06, zb + 1.0), (x, y + 0.06, zb + 1.0), (x, y + 0.06, H - sink - 0.15), (x, y - 0.06, H - sink - 0.15)],
                           paint, normal=(nx, 0, 0))
        if not burnt:
            # lights
            for x in (-hw + 0.25, hw - 0.45):
                m.poly([(x, -L / 2 - 0.01, zb + 0.4), (x + 0.2, -L / 2 - 0.01, zb + 0.4), (x + 0.2, -L / 2 - 0.01, zb + 0.55),
                        (x, -L / 2 - 0.01, zb + 0.55)], 'CK_Lights', normal=(0, -1, 0))
                m.poly([(x, L / 2 + 0.01, zb + 0.45), (x + 0.2, L / 2 + 0.01, zb + 0.45), (x + 0.2, L / 2 + 0.01, zb + 0.6),
                        (x, L / 2 + 0.01, zb + 0.6)], 'CK_TailLights', normal=(0, 1, 0))
            # bumpers
            m.box((0, -L / 2 - 0.04, zb + 0.2), (W - 0.1, 0.12, 0.2), 'CK_Rubber' if kind != 'bus' else 'CK_Chrome')
            m.box((0, L / 2 + 0.04, zb + 0.2), (W - 0.1, 0.12, 0.2), 'CK_Rubber' if kind != 'bus' else 'CK_Chrome')
        # wheels
        wb = {'sedan': 1.35, 'suv': 1.4, 'van': 1.6, 'bus': 3.6}[kind]
        segs = 12 if lod == 0 else 6
        for y in (-wb, wb):
            for x in (-hw + 0.08, hw - 0.08):
                s = 1 if x > 0 else -1
                rr = wr * (0.65 if burnt else 1.0)
                path = [Vector((x - s * 0.1, y, wr - sink)), Vector((x + s * 0.12, y, wr - sink))]
                m.tube(path, [rr, rr], segs, 'CK_Chrome' if burnt else 'CK_Rubber', cap=True)
        lods.append(m)
    return lods


# ============================================================================================== street furniture / cover
def street_lamp():
    lods = []
    for lod in (0, 1):
        m = Mesh()
        s = 8 if lod == 0 else 5
        m.tube([(0, 0, 0), (0, 0, 7.6)], [0.11, 0.07], s, 'BLD_MetalDark', u_tiles=1, v_scale=0.3)
        m.tube([(0, 0, 7.3), (0, -0.8, 7.9), (0, -1.8, 8.0)], [0.05, 0.05, 0.045], 6 if lod == 0 else 4, 'BLD_MetalDark')
        m.box((0, -2.0, 7.95), (0.32, 0.7, 0.14), 'BLD_MetalDark')
        m.poly([(-0.14, -2.3, 7.875), (0.14, -2.3, 7.875), (0.14, -1.7, 7.875), (-0.14, -1.7, 7.875)], 'CK_Lights', normal=(0, 0, -1))
        if lod == 0:
            m.tube([(0, 0, 0), (0, 0, 0.6)], [0.18, 0.15], 8, 'BLD_MetalDark')
        lods.append(m)
    return lods


def traffic_light():
    lods = []
    for lod in (0, 1):
        m = Mesh()
        m.tube([(0, 0, 0), (0, 0, 6.2)], [0.13, 0.1], 8 if lod == 0 else 5, 'BLD_Galvanized')
        m.tube([(0, 0, 5.9), (0, -5.5, 5.9)], [0.07, 0.05], 6 if lod == 0 else 4, 'BLD_Galvanized')
        for y in (-3.0, -5.2):
            m.box((0, y, 5.5), (0.34, 0.3, 1.0), 'BLD_MetalDark')
            if lod == 0:
                for k, mat in enumerate(('CK_TailLights', 'CK_Lights', 'BLD_TrimGreen')):
                    z = 5.82 - k * 0.32
                    m.poly([(-0.1, y - 0.16, z - 0.1), (0.1, y - 0.16, z - 0.1), (0.1, y - 0.16, z + 0.1), (-0.1, y - 0.16, z + 0.1)],
                           mat, normal=(0, -1, 0))
        m.box((0, 0.0, 2.6), (0.3, 0.3, 0.5), 'BLD_MetalDark')
        lods.append(m)
    return lods


def bench():
    lods = []
    for lod in (0, 1):
        m = Mesh()
        for x in (-0.8, 0.8):
            m.box((x, 0, 0.22), (0.06, 0.5, 0.44), 'BLD_MetalDark')
        n = 4 if lod == 0 else 1
        for k in range(n):
            m.box((0, -0.18 + k * 0.12, 0.46), (1.9, 0.09 if n > 1 else 0.48, 0.04), 'BLD_Wood')
        m.box((0, 0.24, 0.75), (1.9, 0.04, 0.4), 'BLD_Wood')
        lods.append(m)
    return lods


def jersey():
    prof = [(-0.3, 0.0), (0.3, 0.0), (0.3, 0.08), (0.2, 0.25), (0.08, 0.81), (-0.08, 0.81), (-0.2, 0.25), (-0.3, 0.08)]
    prof = [(y, z) for y, z in prof]
    m = Mesh()
    m.prism([(y, z) for y, z in prof], -1.8, 1.8, 'BLD_Concrete')
    return [m, m]


def twall():
    prof = [(-0.6, 0.0), (0.6, 0.0), (0.6, 0.25), (0.14, 0.4), (0.12, 3.6), (-0.12, 3.6), (-0.14, 0.4), (-0.6, 0.25)]
    m = Mesh()
    m.prism(prof, -0.75, 0.75, 'BLD_Concrete')
    return [m, m]


MODELS = {
    'Tree_Oak': lambda: (broadleaf(11, 11.0, 4.4), dict(kind='tree', radius=0.3, height=11)),
    'Tree_Maple': lambda: (broadleaf(23, 8.5, 3.4, 'CK_LeavesAutumn'), dict(kind='tree', radius=0.25, height=8.5)),
    'Tree_Street': lambda: (broadleaf(37, 7.0, 2.6, 'CK_LeavesBroad', 0.8), dict(kind='tree', radius=0.2, height=7)),
    'Tree_Pine': lambda: (conifer(41, 15.0, 3.1), dict(kind='tree', radius=0.3, height=15)),
    'Tree_PineTall': lambda: (conifer(53, 21.0, 3.6), dict(kind='tree', radius=0.35, height=21)),
    'Car_Sedan': lambda: (car('sedan'), dict(kind='car', size=[1.8, 1.42, 4.6])),
    'Car_SUV': lambda: (car('suv'), dict(kind='car', size=[1.9, 1.75, 4.7])),
    'Car_Van': lambda: (car('van'), dict(kind='car', size=[2.0, 2.25, 5.2])),
    'Car_Bus': lambda: (car('bus'), dict(kind='car', size=[2.55, 3.1, 11.8])),
    'Wreck_Sedan': lambda: (car('sedan', True), dict(kind='wreck', size=[1.8, 1.25, 4.6])),
    'Wreck_SUV': lambda: (car('suv', True), dict(kind='wreck', size=[1.9, 1.57, 4.7])),
    'Wreck_Van': lambda: (car('van', True), dict(kind='wreck', size=[2.0, 2.07, 5.2])),
    'Wreck_Bus': lambda: (car('bus', True), dict(kind='wreck', size=[2.55, 2.92, 11.8])),
    'Prop_StreetLamp': lambda: (street_lamp(), dict(kind='lamp')),
    'Prop_TrafficLight': lambda: (traffic_light(), dict(kind='signal')),
    'Prop_Bench': lambda: (bench(), dict(kind='bench', size=[1.9, 0.95, 0.6])),
    'Prop_Jersey': lambda: (jersey(), dict(kind='barrier', size=[3.6, 0.81, 0.6])),
    'Prop_TWall': lambda: (twall(), dict(kind='twall', size=[1.5, 3.6, 1.2])),
}


def build_all(coll_name='CityKit', only=None):
    coll = get_coll(coll_name)
    out = {}
    x = 0.0
    for name, fn in MODELS.items():
        if only and name not in only:
            continue
        lods, info = fn()
        root, stats = finish(name, lods, coll, info)
        root.location = (x, 0, 0)
        x += 14.0 if 'Bus' not in name else 18.0
        out[name] = stats
    return out


def export_all(fbx_dir):
    os.makedirs(fbx_dir, exist_ok=True)
    vl = bpy.context.view_layer
    info = {}
    for name in MODELS:
        root = bpy.data.objects.get(name)
        if root is None:
            continue
        old = root.location.copy()
        root.location = (0, 0, 0)
        vl.update()
        for o in vl.objects:
            o.select_set(False)
        objs = [root] + list(root.children)
        state = [(o, o.hide_get()) for o in objs]
        for o in objs:
            o.hide_set(False)
            o.select_set(True)
        vl.objects.active = root
        bpy.ops.export_scene.fbx(filepath=os.path.join(fbx_dir, name + '.fbx'), use_selection=True,
                                 object_types={'EMPTY', 'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
                                 axis_forward='-Z', axis_up='Y', bake_space_transform=True, use_mesh_modifiers=False,
                                 mesh_smooth_type='FACE', use_tspace=False, use_triangles=True, add_leaf_bones=False,
                                 bake_anim=False, path_mode='STRIP', embed_textures=False, use_custom_props=False)
        for o, h in state:
            o.hide_set(h)
        root.location = old
        info[name] = json.loads(root['ck_info'])
    mats = {k: {'stem': v[0], 'folder': 'City' if v[1] == TEX else ('Buildings' if v[1] else None), 'tint': v[2], 'clip': v[3],
                'flat': list(FLAT.get(k, (0.5, 0.0)))} for k, v in MATS.items()}
    with open(os.path.join(fbx_dir, 'materials.json'), 'w') as f:
        json.dump(mats, f, indent=1)
    with open(os.path.join(fbx_dir, 'models.json'), 'w') as f:
        json.dump(info, f, indent=1)
    return info
