# Dominion I - DroneKit (Blender 5.x): three soldier-sized combat-support drones.
#   In Blender:  KIT_DIR = r'<project>\SourceArt\DroneKit'; exec(open(KIT_DIR + r'\source\dk_models.py').read()); build_all(); export_all(KIT_DIR + r'\fbx')
# Metres, Z up, front = -Y (Unity +Z), origin on the ground under the drone (landing gear touches z = 0).
# Each drone is an empty root <Name> with:
#   <Name>_Body        every static part, one mesh (paint, carbon, anodised metal, rubber, lenses, lights)
#   Rotor_<i>          spinning blades + spinner, origin on the hub (Unity spins it about the drone's up axis)
#   Blur_<i>           translucent rotor-blur disc on the same hub (shown while the rotors are spinning)
#   Gimbal             camera yoke, origin on the yaw pivot; child GimbalCam (ball + lens, origin on the pitch axis)
#   Emitter            empty at the repair projector's tip (where the repair beam starts)
#   Drone_Wasp    light X-quad: fast, small repair charge, light-weight recon camera
#   Drone_Mender  heavy hexacopter medic: underslung repair pod with twin repair arms, big repair charge
#   Drone_Kite    twin ducted-fan recon drone with V-tail and sensor mast: fastest, long-range sensors
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix

KIT_DIR = globals().get('KIT_DIR')
TEX = os.path.join(KIT_DIR, 'textures')
TAU = math.tau
I4 = Matrix.Identity(4)

# material -> (texture stem or None, tint hex, roughness, metallic, kind, uv metres per tile)
MATS = {
    'DK_PaintWasp': ('DronePaint', 'a9a58a', 0.55, 0.0, 'tex', 0.7),
    'DK_PaintMender': ('DronePaint', 'e6e8e6', 0.5, 0.0, 'tex', 0.7),
    'DK_PaintKite': ('DronePaint', '6d747a', 0.55, 0.0, 'tex', 0.7),
    'DK_Accent': ('DronePaint', 'e0892a', 0.5, 0.0, 'tex', 0.7),
    'DK_Medic': ('DronePaint', '2fa59b', 0.45, 0.0, 'tex', 0.7),
    'DK_Carbon': ('Carbon', 'ffffff', 0.3, 0.0, 'tex', 0.22),
    'DK_Anodized': ('Anodized', 'ffffff', 0.32, 0.95, 'tex', 0.35),
    'DK_Rubber': ('Rubber', 'ffffff', 0.86, 0.0, 'tex', 0.3),
    'DK_Lens': (None, '0b1016', 0.04, 0.6, 'flat', 1.0),
    'DK_GlowRed': (None, 'ff2216', 0.3, 0.0, 'glow', 1.0),
    'DK_GlowGreen': (None, '20ff48', 0.3, 0.0, 'glow', 1.0),
    'DK_GlowWhite': (None, 'fff6e8', 0.3, 0.0, 'glow', 1.0),
    'DK_GlowMedic': (None, '38fff0', 0.3, 0.0, 'glow', 1.0),
    'DK_RotorBlur': ('RotorBlur', 'ffffff', 0.5, 0.0, 'blur', 1.0),
}


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m and m.get('dk') == 1:
        return m
    m = m or bpy.data.materials.new(name)
    m['dk'] = 1
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs[0])
    stem, tint, rough, metal, kind, _ = MATS[name]
    m.diffuse_color = lin(tint)

    def img(kind_, non):
        p = os.path.join(TEX, f'T_{stem}_{kind_}.png')
        im = bpy.data.images.load(p, check_existing=True)
        im.colorspace_settings.name = 'Non-Color' if non else 'sRGB'
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = im
        return n
    if kind == 'flat':
        bs.inputs['Base Color'].default_value = lin(tint)
        bs.inputs['Roughness'].default_value = rough
        bs.inputs['Metallic'].default_value = metal
        return m
    if kind == 'glow':
        bs.inputs['Base Color'].default_value = lin(tint)
        bs.inputs['Emission Color'].default_value = lin(tint)
        bs.inputs['Emission Strength'].default_value = 8.0
        return m
    if kind == 'blur':
        bc = img('BaseColor', False)
        nt.links.new(bc.outputs['Color'], bs.inputs['Base Color'])
        nt.links.new(bc.outputs['Alpha'], bs.inputs['Alpha'])
        bs.inputs['Roughness'].default_value = rough
        m.surface_render_method = 'BLENDED'
        m.use_backface_culling = False
        return m
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
    return m


# ============================================================================================== geometry builder
def V(*a):
    return Vector(a)


def sring(y, hw, hh, zc, e=3.0, n=28, xc=0.0):
    """Superellipse cross-section in the XZ plane at y (counter-clockwise seen from -Y)."""
    pts = []
    for k in range(n):
        t = TAU * k / n
        c, s = math.cos(t), math.sin(t)
        pts.append(V(xc + hw * math.copysign(abs(c) ** (2 / e), c), y, zc + hh * math.copysign(abs(s) ** (2 / e), s)))
    return pts


def xring(x, hy, hz, yc, zc, e=2.2, n=20):
    """Superellipse cross-section in the YZ plane at x (for stub wings and pylons)."""
    pts = []
    for k in range(n):
        t = TAU * k / n
        c, s = math.cos(t), math.sin(t)
        pts.append(V(x, yc + hy * math.copysign(abs(c) ** (2 / e), c), zc + hz * math.copysign(abs(s) ** (2 / e), s)))
    return pts


class Geo:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def face(self, vs, mat):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mi(mat)
        f.smooth = True
        return f

    def cap(self, ring, mat, M=I4):
        c = self.bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        for k in range(len(ring)):
            self.face([ring[k], ring[(k + 1) % len(ring)], c], mat)

    def loft(self, rings, mat, cap0=True, cap1=True, M=I4, mats=None):
        vr = [[self.bm.verts.new(M @ Vector(p)) for p in ring] for ring in rings]
        n = len(rings[0])
        for i in range(len(vr) - 1):
            mt = mats[i] if mats else mat
            for k in range(n):
                self.face([vr[i][k], vr[i][(k + 1) % n], vr[i + 1][(k + 1) % n], vr[i + 1][k]], mt)
        if cap0:
            self.cap(vr[0], mat)
        if cap1:
            self.cap(vr[-1], mats[-1] if mats else mat)
        return vr

    def lathe(self, prof, segs, mat, M=I4, closed=False, mats=None):
        """Revolve a (r, z) profile about local Z. r == 0 points become poles. closed = profile is a loop (ring shapes)."""
        rings = []
        for r, z in prof:
            if r < 1e-6:
                rings.append([self.bm.verts.new(M @ V(0, 0, z))])
            else:
                rings.append([self.bm.verts.new(M @ V(r * math.cos(TAU * k / segs), r * math.sin(TAU * k / segs), z)) for k in range(segs)])
        pairs = list(range(len(rings) - 1)) + ([len(rings) - 1] if closed else [])
        for i in pairs:
            a, b = rings[i], rings[(i + 1) % len(rings)]
            mt = mats[i] if mats and i < len(mats) else mat
            for k in range(segs):
                k1 = (k + 1) % segs
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    self.face([a[0], b[k1], b[k]], mt)
                elif len(b) == 1:
                    self.face([a[k], a[k1], b[0]], mt)
                else:
                    self.face([a[k], a[k1], b[k1], b[k]], mt)

    def rbox(self, c, size, mat, bevel=0.008, segs=2, M=I4):
        ret = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = ret['verts']
        T = M @ Matrix.Translation(Vector(c)) @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
        bmesh.ops.transform(self.bm, matrix=T, verts=vs)
        faces = {f for v in vs for f in v.link_faces}
        for f in faces:
            f.material_index = self.mi(mat)
            f.smooth = True
        if bevel > 0:
            edges = list({e for v in vs for e in v.link_edges})
            r = bmesh.ops.bevel(self.bm, geom=edges, offset=min(bevel, min(size) * 0.45), segments=segs, profile=0.5,
                                affect='EDGES', clamp_overlap=True, material=-1)
            for f in r['faces']:
                f.smooth = True

    def tube(self, path, radii, mat, segs=12, cap=True, M=I4):
        path = [Vector(p) for p in path]
        if isinstance(radii, (int, float)):
            radii = [radii] * len(path)
        t = (path[1] - path[0]).normalized()
        ref = V(1, 0, 0) if abs(t.x) < 0.9 else V(0, 1, 0)
        nrm = t.cross(ref).normalized()
        rings = []
        for i, p in enumerate(path):
            if i > 0:
                t2 = (path[min(i + 1, len(path) - 1)] - path[i - 1]).normalized()
                ax = t.cross(t2)
                if ax.length > 1e-6:
                    nrm = Matrix.Rotation(t.angle(t2), 3, ax.normalized()) @ nrm
                t = t2
            b = t.cross(nrm).normalized()
            n2 = b.cross(t).normalized()
            rings.append([p + (n2 * math.cos(a) + b * math.sin(a)) * radii[i] for a in (k / segs * TAU for k in range(segs))])
        self.loft(rings, mat, cap, cap, M)

    def sphere(self, c, r, mat, segs=20, rings=10, M=I4, sz=1.0):
        prof = [(r * math.sin(math.pi * i / rings), -r * sz * math.cos(math.pi * i / rings)) for i in range(rings + 1)]
        self.lathe(prof, segs, mat, M @ Matrix.Translation(Vector(c)))

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)


def to_object(g, name, coll, parent=None, loc=(0, 0, 0), uv_mode='box'):
    bm = g.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        s = 1.0 / MATS[g.mats[f.material_index]][5]
        n = f.normal
        for l in f.loops:
            p = l.vert.co
            if uv_mode == 'disc':
                l[uv].uv = (0.5 + p.x * s, 0.5 + p.y * s)
            elif abs(n.z) >= abs(n.x) and abs(n.z) >= abs(n.y):
                l[uv].uv = (p.x * s, p.y * s)
            elif abs(n.x) >= abs(n.y):
                l[uv].uv = (p.y * s, p.z * s)
            else:
                l[uv].uv = (p.x * s, p.z * s)
    me = bpy.data.meshes.get(name)
    if me:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in g.mats:
        me.materials.append(get_mat(m))
    try:
        me.set_sharp_from_angle(angle=math.radians(38))
    except Exception:
        pass
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


# ============================================================================================== shared parts
def motor(g, base, r, paint, light=None):
    """Bell motor on a painted arm-end pod. base = top of the arm tip; the shaft top is base + 0.095 * (r / 0.055)."""
    k = r / 0.055
    M = Matrix.Translation(base)
    g.lathe([(0, -0.045 * k), (r * 1.08, -0.045 * k), (r * 1.18, -0.03 * k), (r * 1.15, -0.008 * k), (r * 0.9, 0.0), (0, 0.0)], 24, paint, M)
    g.lathe([(0, 0.0), (r * 0.92, 0.0), (r * 0.98, 0.006 * k), (r, 0.014 * k), (r, 0.05 * k), (r * 0.96, 0.058 * k),
             (r * 0.72, 0.066 * k), (r * 0.3, 0.07 * k), (0, 0.07 * k)], 28, 'DK_Anodized', M,
            mats=['DK_Anodized', 'DK_Anodized', 'DK_Anodized', 'DK_Carbon', 'DK_Anodized', 'DK_Anodized', 'DK_Anodized', 'DK_Anodized'])
    g.lathe([(0, 0.07 * k), (r * 0.16, 0.07 * k), (r * 0.16, 0.095 * k), (0, 0.095 * k)], 12, 'DK_Anodized', M)
    if light:
        # navigation light on the outboard underside of the pod
        out = Vector((base.x, base.y, 0)).normalized()
        g.sphere(base + out * r * 1.05 + V(0, 0, -0.03 * k), 0.012 * k, light, 10, 6)
    return base + V(0, 0, 0.095 * k)


def rotor(name, coll, parent, hub, radius, blades, ccw, chord, tip_mat='DK_Accent', blade_mat='DK_Carbon'):
    """Twisted, tapered airfoil blades with painted tips and an anodised spinner; origin on the hub."""
    g = Geo()
    hub_r = max(0.028, radius * 0.11)
    g.lathe([(0, -0.012), (hub_r, -0.012), (hub_r * 1.05, 0.004), (hub_r * 0.8, 0.02), (hub_r * 0.35, 0.03), (0, 0.032)], 20, 'DK_Anodized')
    st = 9
    for b in range(blades):
        R = Matrix.Rotation(TAU * b / blades, 4, 'Z')
        if not ccw:
            R = R @ Matrix.Scale(-1, 4, V(0, 1, 0))
        rings, mats = [], []
        for i in range(st):
            u = i / (st - 1)
            x = hub_r * 0.8 + (radius - hub_r * 0.8) * u
            c = chord * (0.75 + 0.55 * math.sin(math.pi * min(1, u * 1.25)) ** 0.7) * (1 - 0.55 * u ** 3)
            if i == st - 1:
                c *= 0.55
            th = c * (0.16 - 0.08 * u)
            tw = math.radians(24 - 16 * u)
            camber = c * 0.05
            ring = []
            for k in range(12):
                a = TAU * k / 12
                yy = c * 0.5 * math.cos(a)
                zz = th * 0.5 * math.sin(a) + camber * (1 - (2 * yy / c) ** 2)
                ring.append(V(x, yy * math.cos(tw) - zz * math.sin(tw), yy * math.sin(tw) + zz * math.cos(tw)))
            rings.append(ring)
            if i < st - 1:
                mats.append(tip_mat if u >= 0.8 else blade_mat)
        g.loft(rings, blade_mat, cap0=False, cap1=True, M=R, mats=mats)
    ob = to_object(g, name, coll, parent, hub)
    blur = Geo()
    blur.lathe([(hub_r, 0.0), (radius * 1.02, 0.0)], 40, 'DK_RotorBlur')
    to_object(blur, name.replace('Rotor', 'Blur'), coll, parent, hub, uv_mode='disc')
    # disc UVs are planar over the disc: scale them so the tip lands on the texture's edge
    bm_me = bpy.data.objects[name.replace('Rotor', 'Blur')].data
    uvl = bm_me.uv_layers[0].data
    for lp in bm_me.loops:
        co = bm_me.vertices[lp.vertex_index].co
        uvl[lp.index].uv = (0.5 + co.x / (2 * radius * 1.02), 0.5 + co.y / (2 * radius * 1.02))
    return ob


def gimbal(px, coll, parent, pivot, s, paint):
    """Two-axis camera gimbal: yoke (yaw, origin on the pivot) + camera ball with lens (pitch, origin on the ball)."""
    g = Geo()
    g.lathe([(0, 0.0), (0.05 * s, 0.0), (0.056 * s, 0.012 * s), (0.05 * s, 0.024 * s), (0, 0.024 * s)], 24, paint)
    g.lathe([(0, -0.024 * s), (0.032 * s, -0.024 * s), (0.034 * s, 0.0), (0, 0.0)], 20, 'DK_Anodized')
    g.rbox((0, 0, -0.034 * s), (0.17 * s, 0.04 * s, 0.022 * s), 'DK_Anodized', 0.006 * s)
    for sx in (-1, 1):
        g.rbox((sx * 0.077 * s, 0, -0.082 * s), (0.016 * s, 0.05 * s, 0.1 * s), 'DK_Anodized', 0.005 * s)
    yoke = to_object(g, px + '_Gimbal', coll, parent, pivot)
    c = Geo()
    c.sphere((0, 0, 0), 0.062 * s, paint, 24, 12)
    Mx = Matrix.Rotation(math.pi / 2, 4, 'Y')               # trunnions along X
    c.lathe([(0, 0.063 * s), (0.02 * s, 0.063 * s), (0.02 * s, 0.072 * s), (0, 0.072 * s)], 12, 'DK_Anodized', Mx)
    c.lathe([(0, -0.072 * s), (0.02 * s, -0.072 * s), (0.02 * s, -0.063 * s), (0, -0.063 * s)], 12, 'DK_Anodized', Mx)
    Mf = Matrix.Rotation(math.pi / 2, 4, 'X')               # lens barrel along -Y (forward)
    c.lathe([(0.04 * s, 0.03 * s), (0.044 * s, 0.062 * s), (0.04 * s, 0.07 * s), (0.032 * s, 0.07 * s)], 24, 'DK_Anodized', Mf, closed=True)
    c.lathe([(0, 0.06 * s), (0.032 * s, 0.06 * s), (0.026 * s, 0.067 * s), (0, 0.069 * s)], 24, 'DK_Lens', Mf)
    c.lathe([(0, 0.05 * s), (0.012 * s, 0.05 * s), (0.012 * s, 0.065 * s), (0, 0.065 * s)], 10, 'DK_Lens', Mf @ Matrix.Translation(V(0.035 * s, 0, 0)))
    # exported as a sibling of the yoke (the FBX axis bake breaks on nested children); Unity re-parents it to the yoke
    to_object(c, px + '_GimbalCam', coll, parent, pivot + V(0, 0, -0.095 * s))
    return yoke


def emitter(px, coll, parent, tip):
    old = bpy.data.objects.get(px + '_Emitter')
    if old:
        bpy.data.objects.remove(old)
    e = bpy.data.objects.new(px + '_Emitter', None)
    e.empty_display_size = 0.05
    coll.objects.link(e)
    e.parent = parent
    e.location = tip
    return e


def nozzle(g, base, direction, r, glow='DK_GlowMedic'):
    """Repair projector: anodised barrel ending in a glowing emitter lens, pointing along 'direction'."""
    d = Vector(direction).normalized()
    M = Matrix.Translation(base) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    g.lathe([(0, 0.0), (r * 1.25, 0.0), (r * 1.3, r * 0.6), (r, r * 1.2), (r, r * 2.6), (r * 1.2, r * 2.9), (r * 1.15, r * 3.3)], 18,
            'DK_Anodized', M)
    g.lathe([(r * 1.15, r * 3.3), (r * 0.8, r * 3.3), (0, r * 3.2)], 18, glow, M)
    return base + d * r * 3.3


# ============================================================================================== Drone_Wasp
def wasp(coll):
    name = 'Drone_Wasp'
    paint = 'DK_PaintWasp'
    sub = get_coll(name, coll)
    for o in list(sub.objects):
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new(name, None)
    sub.objects.link(root)
    g = Geo()
    # fuselage: squircle sections, nose (-Y) slightly lower than the tail
    secs = [(0.41, 0.07, 0.045, 0.445), (0.36, 0.14, 0.08, 0.445), (0.24, 0.20, 0.105, 0.44), (0.02, 0.215, 0.115, 0.43),
            (-0.18, 0.2, 0.108, 0.42), (-0.32, 0.15, 0.085, 0.41), (-0.40, 0.09, 0.06, 0.405), (-0.44, 0.03, 0.03, 0.405)]
    g.loft([sring(y, w, h, z, 3.2, 32) for y, w, h, z in secs], paint)
    # accent band and panel seam (slightly proud rings)
    g.loft([sring(y, w * 1.012 + 0.002, h * 1.012 + 0.002, z, 3.2, 32) for y, w, h, z in
            [(0.09, 0.214, 0.114, 0.432), (0.04, 0.215, 0.115, 0.431)]], 'DK_Accent', False, False)
    g.loft([sring(y, w * 1.008 + 0.0015, h * 1.008 + 0.0015, z, 3.2, 32) for y, w, h, z in
            [(-0.205, 0.198, 0.107, 0.421), (-0.195, 0.199, 0.107, 0.421)]], 'DK_Carbon', False, False)
    # battery hatch with grip and latch, GPS puck, whip antennas
    g.rbox((0, 0.05, 0.548), (0.25, 0.36, 0.03), paint, 0.012, 3)
    g.rbox((0, 0.05, 0.565), (0.06, 0.2, 0.012), 'DK_Rubber', 0.005)
    g.rbox((0, -0.135, 0.556), (0.12, 0.025, 0.014), 'DK_Anodized', 0.004)
    g.lathe([(0, 0.55), (0.045, 0.55), (0.05, 0.565), (0.04, 0.58), (0, 0.585)], 24, 'DK_Accent', Matrix.Translation(V(0, 0.3, -0.03)))
    for sx in (-1, 1):
        g.tube([(sx * 0.1, 0.33, 0.48), (sx * 0.12, 0.38, 0.62), (sx * 0.125, 0.39, 0.70)], [0.007, 0.005, 0.003], 'DK_Rubber', 8)
        # side intake grille
        for k in range(4):
            g.rbox((sx * 0.2115, 0.08 - k * 0.04, 0.43), (0.012, 0.022, 0.09), 'DK_Anodized', 0.004)
        g.rbox((sx * 0.205, 0.02, 0.43), (0.01, 0.2, 0.12), 'DK_Carbon', 0.008)
    # nose sensor window
    g.loft([sring(y, w, h, z, 2.6, 24) for y, w, h, z in [(-0.36, 0.11, 0.035, 0.452), (-0.405, 0.06, 0.022, 0.438)]], 'DK_Lens', False, True)
    # X arms with folding hinges, motor pods, motors
    motor_pos = []
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        a = V(sx * 0.175, sy * 0.13, 0.45)
        tip = V(sx * 0.5, sy * 0.47, 0.49)
        g.rbox((a.x, a.y, a.z), (0.1, 0.1, 0.07), 'DK_Anodized', 0.012, 2,
               M=Matrix.Translation(a) @ Matrix.Rotation(math.atan2(sy, sx) - math.pi / 4, 4, 'Z') @ Matrix.Translation(-a))
        g.tube([a, a.lerp(tip, 0.5) + V(0, 0, 0.012), tip], [0.03, 0.026, 0.022], 'DK_Carbon', 14)
        light = 'DK_GlowGreen' if (sy < 0 and sx < 0) else 'DK_GlowRed' if sy < 0 else 'DK_GlowWhite'
        motor_pos.append(motor(g, tip + V(0, 0, 0.03), 0.05, paint, light))
    # landing skids: carbon struts, anodised rails, rubber feet
    for sx in (-1, 1):
        for y0 in (-0.15, 0.17):
            g.tube([(sx * 0.12, y0, 0.34), (sx * 0.2, y0 - 0.01, 0.17), (sx * 0.235, y0 - 0.02, 0.05)], [0.014, 0.013, 0.012], 'DK_Carbon', 10)
        g.tube([(sx * 0.235, -0.34, 0.075), (sx * 0.235, -0.3, 0.035), (sx * 0.235, -0.24, 0.024), (sx * 0.235, 0.26, 0.024),
                (sx * 0.235, 0.31, 0.034), (sx * 0.235, 0.34, 0.07)], 0.016, 'DK_Anodized', 12)
        for y0 in (-0.17, 0.15):
            g.tube([(sx * 0.235, y0 - 0.05, 0.022), (sx * 0.235, y0 + 0.05, 0.022)], 0.022, 'DK_Rubber', 12)
    # repair projector under the tail
    tipE = nozzle(g, V(0, 0.24, 0.335), (0, 0.25, -1), 0.018)
    body = to_object(g, name + '_Body', sub, root)
    for i, p in enumerate(motor_pos):
        rotor(f'Wasp_Rotor_{i}', sub, root, p + V(0, 0, 0.012), 0.27, 2, i % 2 == 0, 0.05)
    gimbal('Wasp', sub, root, V(0, -0.29, 0.318), 0.95, paint)
    emitter('Wasp', sub, root, tipE)
    return root, {'rotors': 4, 'prop_r': 0.27, 'span': 2 * (0.5 * 1.414 + 0.27)}


# ============================================================================================== Drone_Mender
def mender(coll):
    name = 'Drone_Mender'
    paint = 'DK_PaintMender'
    sub = get_coll(name, coll)
    for o in list(sub.objects):
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new(name, None)
    sub.objects.link(root)
    g = Geo()
    # central hub: a flattened capsule with a medic band and a sensor dome
    g.lathe([(0, 0.40), (0.2, 0.40), (0.28, 0.418), (0.325, 0.452), (0.345, 0.495), (0.345, 0.545), (0.328, 0.585),
             (0.28, 0.612), (0.2, 0.626), (0, 0.63)], 48, paint)
    g.lathe([(0.336, 0.502), (0.352, 0.502), (0.352, 0.538), (0.336, 0.538)], 48, 'DK_GlowMedic', closed=True)
    g.lathe([(0.29, 0.612), (0.302, 0.61), (0.302, 0.62), (0.286, 0.622)], 48, 'DK_Medic', closed=True)
    g.lathe([(0, 0.62), (0.21, 0.62), (0.212, 0.632), (0.195, 0.655), (0.15, 0.678), (0.08, 0.694), (0, 0.698)], 40, paint,
            mats=[paint, paint, 'DK_Medic', 'DK_Medic', paint, paint])
    g.lathe([(0, 0.694), (0.035, 0.694), (0.038, 0.71), (0.026, 0.728), (0, 0.733)], 20, 'DK_GlowMedic')
    # six arms (front = -Y sits between two of them), motors, rotors
    motor_pos = []
    for i in range(6):
        ang = TAU * i / 6
        d = V(math.cos(ang), math.sin(ang), 0)
        a = d * 0.3 + V(0, 0, 0.52)
        tip = d * 0.7 + V(0, 0, 0.555)
        Mj = Matrix.Translation(d * 0.37 + V(0, 0, 0.525)) @ Matrix.Rotation(ang, 4, 'Z')
        g.rbox((0, 0, 0), (0.09, 0.075, 0.075), 'DK_Anodized', 0.012, 2, M=Mj)
        g.rbox((0, 0, 0.042), (0.05, 0.03, 0.012), 'DK_Medic', 0.004, 2, M=Mj)
        g.tube([a, a.lerp(tip, 0.5) + V(0, 0, 0.01), tip], [0.036, 0.031, 0.027], 'DK_Carbon', 16)
        front = d.y < -0.3
        light = ('DK_GlowGreen' if d.x < 0 else 'DK_GlowRed') if front else 'DK_GlowWhite'
        motor_pos.append(motor(g, tip + V(0, 0, 0.035), 0.06, paint, light))
    # repair pod underneath, with the big emitter lens and two folded repair arms
    g.lathe([(0, 0.24), (0.1, 0.24), (0.15, 0.268), (0.168, 0.32), (0.164, 0.402), (0, 0.402)], 36, paint)
    g.lathe([(0.166, 0.3), (0.172, 0.3), (0.172, 0.312), (0.166, 0.312)], 36, 'DK_GlowMedic', closed=True)
    g.lathe([(0, 0.233), (0.07, 0.233), (0.078, 0.242), (0, 0.246)], 28, 'DK_GlowMedic')
    g.lathe([(0.078, 0.236), (0.095, 0.236), (0.1, 0.246), (0.078, 0.246)], 28, 'DK_Anodized', closed=True)
    for sx in (-1, 1):
        g.sphere((sx * 0.165, 0, 0.34), 0.032, 'DK_Anodized', 16, 8)
        g.tube([(sx * 0.165, 0, 0.34), (sx * 0.24, -0.04, 0.28)], 0.02, 'DK_Anodized', 12)
        g.sphere((sx * 0.24, -0.04, 0.28), 0.026, 'DK_Anodized', 14, 7)
        g.tube([(sx * 0.24, -0.04, 0.28), (sx * 0.22, -0.16, 0.22)], 0.017, 'DK_Anodized', 12)
        g.tube([(sx * 0.21, 0.02, 0.36), (sx * 0.25, -0.03, 0.30)], 0.006, 'DK_Rubber', 6)     # hydraulic line
        nozzle(g, V(sx * 0.22, -0.16, 0.22), (sx * -0.1, -0.6, -0.8), 0.016)
    # battery packs on the hub flanks and a rear antenna pair
    for sx in (-1, 1):
        g.rbox((sx * 0.23, 0.12, 0.415), (0.13, 0.2, 0.05), 'DK_Carbon', 0.012, 2)
        g.tube([(sx * 0.12, 0.2, 0.62), (sx * 0.14, 0.24, 0.78)], [0.007, 0.003], 'DK_Rubber', 8)
    # four landing legs with rubber pads
    for i in range(4):
        ang = TAU * (i + 0.5) / 4
        d = V(math.cos(ang), math.sin(ang), 0)
        g.tube([d * 0.22 + V(0, 0, 0.42), d * 0.34 + V(0, 0, 0.22), d * 0.4 + V(0, 0, 0.05)], [0.022, 0.02, 0.018], 'DK_Carbon', 12)
        g.sphere(d * 0.34 + V(0, 0, 0.22), 0.026, 'DK_Anodized', 12, 6)
        g.lathe([(0, 0.0), (0.05, 0.0), (0.055, 0.015), (0.04, 0.035), (0.02, 0.05), (0, 0.05)], 20, 'DK_Rubber',
                Matrix.Translation(d * 0.4))
    tipE = V(0, 0, 0.232)
    to_object(g, name + '_Body', sub, root)
    for i, p in enumerate(motor_pos):
        rotor(f'Mender_Rotor_{i}', sub, root, p + V(0, 0, 0.012), 0.28, 2, i % 2 == 0, 0.058)
    gimbal('Mender', sub, root, V(0, -0.27, 0.405), 1.05, paint)
    emitter('Mender', sub, root, tipE)
    return root, {'rotors': 6, 'prop_r': 0.28, 'span': 2 * (0.7 + 0.28)}


# ============================================================================================== Drone_Kite
def duct(g, c, paint, light):
    M = Matrix.Translation(c)
    prof = [(0.272, -0.10), (0.27, 0.0), (0.272, 0.07), (0.28, 0.094), (0.295, 0.107), (0.312, 0.106), (0.323, 0.09),
            (0.327, 0.05), (0.323, -0.06), (0.312, -0.098), (0.292, -0.108)]
    g.lathe(prof, 48, paint, M, closed=True)
    g.lathe([(0.3265, 0.0), (0.331, 0.0), (0.331, 0.026), (0.3265, 0.026)], 48, 'DK_Accent', M, closed=True)
    # motor nacelle on three stators
    g.lathe([(0, -0.1), (0.045, -0.1), (0.062, -0.07), (0.066, 0.0), (0.058, 0.02), (0, 0.022)], 24, 'DK_Anodized', M)
    for k in range(3):
        a = TAU * k / 3 + math.pi / 2
        Ms = M @ Matrix.Rotation(a, 4, 'Z')
        g.rbox((0.168, 0, -0.045), (0.21, 0.014, 0.06), 'DK_Carbon', 0.004, 1, M=Ms)
    out = V(math.copysign(1, c.x), 0, 0)
    g.sphere(c + out * 0.33 + V(0, 0, 0.012), 0.013, light, 10, 6)
    return c + V(0, 0, 0.022)


def kite(coll):
    name = 'Drone_Kite'
    paint = 'DK_PaintKite'
    sub = get_coll(name, coll)
    for o in list(sub.objects):
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new(name, None)
    sub.objects.link(root)
    g = Geo()
    secs = [(-0.64, 0.02, 0.02, 0.42), (-0.6, 0.075, 0.065, 0.42), (-0.48, 0.135, 0.11, 0.43), (-0.25, 0.165, 0.135, 0.44),
            (0.02, 0.165, 0.13, 0.45), (0.25, 0.14, 0.11, 0.46), (0.45, 0.085, 0.07, 0.48), (0.6, 0.045, 0.045, 0.495),
            (0.66, 0.02, 0.025, 0.5)]
    g.loft([sring(y, w, h, z, 2.7, 32) for y, w, h, z in secs], paint)
    for y0, mat in ((-0.27, 'DK_Accent'), (0.28, 'DK_Carbon')):
        y1 = y0 + (0.04 if mat == 'DK_Accent' else 0.008)
        g.loft([sring(y, 0.168 if y < 0.1 else 0.14, 0.137 if y < 0.1 else 0.112, 0.44 if y < 0.1 else 0.46, 2.7, 32)
                for y in (y0, y1)], mat, False, False)
    # canopy-like sensor window along the nose top
    g.loft([sring(y, w, h, z, 2.4, 24) for y, w, h, z in [(-0.5, 0.07, 0.03, 0.535), (-0.34, 0.1, 0.04, 0.56), (-0.2, 0.08, 0.03, 0.565)]],
           'DK_Lens', True, True)
    # stub wings to the ducts, ducts with fans, wingtip lights
    hubs = []
    for sx in (-1, 1):
        g.loft([xring(sx * x, 0.15 - 0.03 * abs(x - 0.1) / 0.1, 0.028, -0.02, 0.46) for x in (0.1, 0.16, 0.2)], paint, True, True)
        hubs.append(duct(g, V(sx * 0.52, -0.02, 0.46), paint, 'DK_GlowGreen' if sx < 0 else 'DK_GlowRed'))
        # legs from the duct bottoms, rubber feet
        for sy in (-1, 1):
            p0 = V(sx * 0.52, -0.02 + sy * 0.2, 0.37)
            p1 = V(sx * 0.53, -0.02 + sy * 0.26, 0.04)
            g.tube([p0, p0.lerp(p1, 0.5) + V(sx * 0.02, 0, 0), p1], [0.016, 0.015, 0.014], 'DK_Carbon', 10)
            g.sphere(p1 + V(0, 0, -0.012), 0.026, 'DK_Rubber', 14, 8)
    # V-tail
    for sx in (-1, 1):
        dirv = V(sx * math.sin(math.radians(38)), 0, math.cos(math.radians(38)))
        thick = V(math.cos(math.radians(38)), 0, -sx * math.sin(math.radians(38)))
        rings, mats = [], []
        for i, s in enumerate((0.0, 0.35, 0.7, 1.0)):
            P = V(0, 0, 0.5) + dirv * (0.07 + 0.3 * s)
            yle, yte = 0.38 + 0.16 * s, 0.62 + 0.02 * s
            c, mid = yte - yle, (yte + yle) / 2
            t = 0.022 * (1 - 0.5 * s)
            rings.append([V(P.x, mid + c / 2 * math.cos(a), P.z) + thick * (t / 2 * math.sin(a)) for a in (TAU * k / 14 for k in range(14))])
            if i < 3:
                mats.append('DK_Accent' if s >= 0.7 else paint)
        g.loft(rings, paint, True, True, mats=mats)
    g.sphere((0, 0.665, 0.5), 0.012, 'DK_GlowWhite', 10, 6)
    # sensor mast with a rotating-radar style head
    g.tube([(0, -0.08, 0.57), (0, -0.07, 0.74)], [0.02, 0.016], 'DK_Anodized', 12)
    g.lathe([(0, 0.735), (0.07, 0.735), (0.105, 0.75), (0.11, 0.765), (0.09, 0.78), (0.04, 0.79), (0, 0.792)], 32, paint,
            Matrix.Translation(V(0, -0.07, 0)), mats=[paint, paint, 'DK_Lens', paint, paint, paint])
    for sx in (-1, 1):
        g.tube([(sx * 0.06, 0.3, 0.55), (sx * 0.07, 0.34, 0.68)], [0.006, 0.003], 'DK_Rubber', 8)
    tipE = nozzle(g, V(0, 0.35, 0.36), (0, 0.15, -1), 0.014)
    to_object(g, name + '_Body', sub, root)
    for i, h in enumerate(hubs):
        rotor(f'Kite_Rotor_{i}', sub, root, h + V(0, 0, 0.012), 0.252, 5, i == 0, 0.06, tip_mat='DK_Anodized', blade_mat='DK_Carbon')
    gimbal('Kite', sub, root, V(0, -0.44, 0.33), 1.0, paint)
    emitter('Kite', sub, root, tipE)
    return root, {'rotors': 2, 'prop_r': 0.252, 'span': 2 * (0.52 + 0.331)}


DRONES = {'Drone_Wasp': wasp, 'Drone_Mender': mender, 'Drone_Kite': kite}
LAYOUT = {'Drone_Wasp': (-2.4, 0, 0), 'Drone_Mender': (0, 0, 0), 'Drone_Kite': (2.4, 0, 0)}


def build_all(only=None):
    coll = get_coll('DroneKit')
    info = {}
    for nm, fn in DRONES.items():
        if only and nm not in only:
            continue
        root, inf = fn(coll)
        root.location = LAYOUT[nm]
        tris = sum(len(p.vertices) - 2 for o in root.children_recursive if o.type == 'MESH' for p in o.data.polygons)
        inf['tris'] = tris
        root['dk_info'] = json.dumps(inf)
        info[nm] = inf
    return info


def export_all(fbx_dir):
    os.makedirs(fbx_dir, exist_ok=True)
    vl = bpy.context.view_layer
    info = {}
    for name in DRONES:
        root = bpy.data.objects.get(name)
        if root is None:
            continue
        old = root.location.copy()
        root.location = (0, 0, 0)
        vl.update()
        for o in vl.objects:
            o.select_set(False)
        objs = [root] + list(root.children_recursive)
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
        info[name] = json.loads(root['dk_info'])
    mats = {k: {'stem': v[0], 'tint': v[1], 'rough': v[2], 'metal': v[3], 'kind': v[4]} for k, v in MATS.items()}
    with open(os.path.join(fbx_dir, 'materials.json'), 'w') as f:
        json.dump(mats, f, indent=1)
    with open(os.path.join(fbx_dir, 'models.json'), 'w') as f:
        json.dump(info, f, indent=1)
    return info
