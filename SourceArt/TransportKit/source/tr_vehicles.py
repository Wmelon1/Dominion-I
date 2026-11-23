# Transport Kit builder - 3 military transport vehicles (6x6 truck, 4x4 armoured carrier, tracked APC).
# Requires TankKit/source tk_core.py, tk_tank.py, tk_tanks.py exec'd first in the same namespace.
# Coordinates: X = left(+)/right(-), Y = back(+)/front(-), Z = up, origin on the ground at the vehicle centre.

TR_DIR = globals().get('TR_DIR')
TEX_DIR = os.path.join(TR_DIR, 'textures')
GLB_DIR = os.path.join(TR_DIR, 'glb')


class Vehicle(Tank):
    def __init__(self, name, origin, cfg):
        self.name, self.origin, self.cfg = name, Vector(origin), cfg
        self.coll = get_coll(f'Vehicle_{name}', get_coll('TransportKit'))
        self.mbs, self.objs, self.bones, self.wheel_drv = {}, [], [], []
        self.guns, self.flashes, self.tracks, self.meta, self.temp_meshes = [], [], {}, {}, []
        self.steer, self.doors, self.wheel_r, self.extra_objs = {}, {}, {}, []
        self.mats = {k: master_material(f'MM_{name}_{k}', k, cfg) for k in SLOTS}
        self.mat_list = [self.mats[k] for k in SLOTS]


# ------------------------------------------------------------------------------------- wheels
def tire_mesh(name, R, W, mats, segs=24, lugs=20):
    mb = MB()
    a = W / 2
    prof = [(0, a * 0.55 + 0.05), (0.16 * R, a * 0.55 + 0.05), (0.22 * R, a * 0.55), (0.45 * R, a * 0.58),
            (0.52 * R, a * 0.78), (0.6 * R, a * 0.9), (0.63 * R, a), (0.9 * R, a), (0.965 * R, a * 0.82),
            (0.965 * R, -a * 0.82), (0.9 * R, -a), (0.63 * R, -a), (0.55 * R, -a * 0.7), (0, -a * 0.7)]
    mb.lathe(prof, segs, mats=[WM, WM, WP, WP, WP, WP, RB, RB, RB, RB, RB, WP, WP])
    for k in range(8):
        ang = k * TAU / 8
        c = (a * 0.55 + 0.06, 0.3 * R * math.cos(ang), 0.3 * R * math.sin(ang))
        mb.cyl(0.022, 0.03, 6, WM, M=frame(c, (1, 0, 0)), x0=-0.01)
    for k in range(lugs):
        for side, off in ((1, 0.0), (-1, 0.5)):
            ang = (k + off) * TAU / lugs
            n = Vector((0, math.cos(ang), math.sin(ang)))
            t = Vector((0, -math.sin(ang), math.cos(ang)))
            c = n * (0.965 * R + 0.018) + Vector((side * a * 0.42, 0, 0))
            M = Matrix(((-1, 0, 0, c.x), (0, t.y, n.y, c.y), (0, t.z, n.z, c.z), (0, 0, 0, 1)))
            mb.box((0, 0, 0), (a * 0.78, 0.085, 0.036), RB, M=M @ Matrix.Rotation(side * 0.35, 4, 'Z'),
                   top=(0.9, 0.8), cap0=False)
    return mb.to_mesh(name, mats, sharp=40)


def wheel_set(T, ys, R, W, half_track, steer_axles=(0,), max_steer=32.0):
    me = tire_mesh(f'{T.name}_Tire', R, W, T.mat_list)
    T.temp_meshes.append(me)
    T.tire_mesh = me
    for i, y in enumerate(ys):
        for side, s in (('L', 1), ('R', -1)):
            c = Vector((s * half_track, y, R))
            wb = f'wheel_{i + 1}_{side}'
            parent = 'root'
            if i in steer_axles:
                sb = f'steer_{i + 1}_{side}'
                T.bone(sb, c, c + Vector((0, 0, 0.5)), parent='root', z=(0, -1, 0), coll='Wheels', shape='diamond',
                       sxyz=(0.15,) * 3, color='THEME03',
                       locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
                T.steer[sb] = max_steer
                parent = sb
            T.instance(me, wb, wb, tuple(c), 0.0 if s > 0 else math.pi, 'hull')
            T.bone(wb, c, c + Vector((0.25, 0, 0)), parent=parent, coll='Wheels', shape='circle',
                   sxyz=(R * 1.05,) * 3, color='THEME07',
                   locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
            T.wheel_r[wb] = R


def axle(mb, y, z, half, diff=True):
    mb.cyl(0.075, half * 2 - 0.25, 10, MT, M=frame((0, y, z), (1, 0, 0)))
    if diff:
        mb.lathe([(0, -0.22), (0.12, -0.22), (0.2, -0.1), (0.2, 0.1), (0.12, 0.22), (0, 0.22)], 12, MT,
                 M=frame((0.1, y, z), (1, 0, 0)))
        mb.cyl(0.05, 0.4, 8, MT, M=frame((0.1, y - 0.3, z + 0.05), (0, -1, 0)))
    for s in (1, -1):
        mb.box((s * half * 0.5, y, z + 0.18), (0.1, 1.15, 0.07), MT, top=(1, 0.75))
        mb.box((s * half * 0.5, y, z + 0.1), (0.14, 0.18, 0.14), MT)


def vbones(T, length, body_z):
    T.bone('root', (0, 0, 0), (0, -1.0, 0), shape='square', sxyz=(1.6, length / 2 + 0.3, 1), color='THEME09')
    T.bone('body', (0, 0, body_z), (0, -0.8, body_z), parent='root', shape='box', sxyz=(1.2, length / 2, 0.5),
           color='THEME09')


def gun_mount(T, ring_c, ring_r, trunnion, barrel_len, gmin, gmax, shield=True):
    """MG turret on a roof ring: bones turret / gun / barrel / muzzle / flash."""
    tc = Vector(ring_c)
    tur = T.mb('turret', 'turret', 'turret')
    tur.lathe([(ring_r * 0.8, 0), (ring_r + 0.06, 0), (ring_r + 0.06, 0.1), (ring_r * 0.8, 0.1)], 24, P,
              M=frame(tc, (0, 0, 1)))
    if shield:
        for ang, w in ((0.0, 1.0), (0.75, 0.55), (-0.75, 0.55)):
            d = Vector((math.sin(ang), -math.cos(ang), 0))
            c = tc + d * (ring_r + 0.02) + Vector((0, 0, 0.42))
            fs = tur.box((0, 0, 0), (w, 0.04, 0.62), P, M=Mt(*c) @ Mrz(ang), top=(0.92, 1.0))
        win = tur.box((0, 0, 0), (0.32, 0.05, 0.14), GL, M=Mt(*(tc + Vector((0.22, -ring_r - 0.03, 0.55)))))
    tr = Vector(trunnion)
    gun = T.mb('gun', 'gun', 'turret')
    gun.box(tuple(tr), (0.11, 0.42, 0.14), MT)
    gun.box(tuple(tr + Vector((0.13, 0.05, -0.02))), (0.13, 0.2, 0.16), P)
    gun.box(tuple(tr + Vector((0, 0.27, -0.04))), (0.05, 0.14, 0.12), MT)
    brl = T.mb('barrel', 'barrel', 'turret')
    brl.lathe([(0, 0.1), (0.032, 0.1), (0.032, 0.45), (0.022, 0.5), (0.02, barrel_len - 0.12), (0.03, barrel_len - 0.1),
               (0.03, barrel_len), (0.012, barrel_len), (0, barrel_len - 0.05)], 8, MT,
              M=frame(tr, (0, -1, 0)))
    muzzle = tr + Vector((0, -barrel_len, 0))
    lock_all = dict(loc=(True,) * 3, rot=(True,) * 3, scale=(True,) * 3)
    T.bone('turret', tc, tc + Vector((0, 0, 0.6)), parent='body', z=(0, -1, 0), shape='circle',
           sxyz=(ring_r * 1.4,) * 3, color='THEME01',
           locks=dict(loc=(True,) * 3, rot=(True, False, True), scale=(True,) * 3))
    T.bone('gun', tr, tr + Vector((0, -0.8, 0)), parent='turret', shape='arrow', sxyz=(1.0, barrel_len, 1.0),
           color='THEME03', locks=dict(loc=(True,) * 3, rot=(False, True, True), scale=(True,) * 3))
    T.bone('barrel', tr, tr + Vector((0, -0.5, 0)), parent='gun', shape='box', sxyz=(0.06, 0.3, 0.06),
           color='THEME04', locks=dict(loc=(True, False, True), rot=(True,) * 3, scale=(True,) * 3))
    T.bone('muzzle', muzzle, muzzle + Vector((0, -0.2, 0)), parent='barrel', deform=False, coll='Sockets',
           shape='diamond', sxyz=(0.08,) * 3, color='THEME06', locks=lock_all)
    T.bone('flash', muzzle, muzzle + Vector((0, -0.3, 0)), parent='muzzle', coll='Sockets', shape='diamond',
           sxyz=(0.05,) * 3, color='THEME06', locks=dict(loc=(True,) * 3, rot=(True, False, True)))
    T.flashes.append(('flash', tuple(muzzle), (0, -1, 0), 0.7, 0.32))
    T.guns.append(('barrel', 'flash', 0.05, [1, 4, 7, 10, 13, 16]))
    T.meta.update(turret_bone='turret', gun_bone='gun', gun_min=gmin, gun_max=gmax)


def door(T, key, hinge_head, hinge_tail, axis, angle, z_axis=(0, 0, 1), parent='body'):
    T.bone(key, hinge_head, hinge_tail, parent=parent, z=z_axis, shape='box', sxyz=(0.08, 0.3, 0.08),
           color='THEME05', locks=dict(loc=(True,) * 3, scale=(True,) * 3))
    T.doors[key] = dict(axis=axis, angle=angle)


# ------------------------------------------------------------------------------------- clips
def make_clip(T, name, f0, f1, fn, interp='LINEAR'):
    rig = T.rig
    ad = rig.animation_data_create()
    pbs = rig.pose.bones

    def reset():
        for pb in pbs:
            pb.location, pb.rotation_euler, pb.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    reset()
    act = bpy.data.actions.new(f'{T.name}_{name}')
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


def door_clips(T, made):
    for bn, d in T.doors.items():
        idx = 'xyz'.index(d['axis'])
        made.append(make_clip(T, f'{bn.title().replace("_", "")}_Open', 1, 37,
                              lambda key, bn=bn, idx=idx, d=d: (key(bn, 'rotation_euler', idx, 1, 0.0),
                                                                key(bn, 'rotation_euler', idx, 37, math.radians(d['angle']))),
                              'BEZIER'))


def wheeled_clips(T):
    made = []
    F = 24

    def drive(sign):
        def fn(key):
            for wb in T.wheel_r:
                key(wb, 'rotation_euler', 1, 1, 0.0)
                key(wb, 'rotation_euler', 1, F + 1, sign * TAU)
        return fn
    made.append(make_clip(T, 'Drive_Forward', 1, F + 1, drive(1)))
    made.append(make_clip(T, 'Drive_Reverse', 1, F + 1, drive(-1)))

    def steer(key):
        for sb, m in T.steer.items():
            for f, v in ((1, 0), (13, m), (37, -m), (49, 0)):
                key(sb, 'rotation_euler', 1, f, math.radians(v))
    made.append(make_clip(T, 'Steer_Demo', 1, 49, steer, 'BEZIER'))
    if 'turret' in T.rig.pose.bones:
        made.append(make_clip(T, 'Turret_Traverse', 1, 145, lambda key: (key('turret', 'rotation_euler', 1, 1, 0.0),
                                                                          key('turret', 'rotation_euler', 1, 145, TAU))))
        m = T.meta
        made.append(make_clip(T, 'Gun_Elevate', 1, 73, lambda key: [key('gun', 'rotation_euler', 0, f, math.radians(v))
                                                                     for f, v in ((1, 0), (19, m['gun_max']),
                                                                                  (55, m['gun_min']), (73, 0))],
                              'BEZIER'))

        def fire(key):
            S = 1.0 / FLASH_REST
            key('flash', 'scale', None, 1, (1, 1, 1))
            key('barrel', 'location', 1, 1, 0.0)
            for s in (1, 4, 7, 10, 13, 16):
                key('flash', 'scale', None, s, (S, S, S))
                key('flash', 'scale', None, s + 1, (0.6 * S,) * 3)
                key('flash', 'scale', None, s + 2, (1, 1, 1))
                key('barrel', 'location', 1, s, 0.0)
                key('barrel', 'location', 1, s + 1, -0.05)
            key('flash', 'scale', None, 25, (1, 1, 1))
            key('barrel', 'location', 1, 25, 0.0)
        made.append(make_clip(T, 'Fire', 1, 25, fire))
    door_clips(T, made)
    T.rig.animation_data.action = None
    return made


# ===================================================================================== 1. Mule 6x6 truck
def build_mule(T):
    R, W, ht = 0.55, 0.42, 1.0
    ys = [-2.55, 1.25, 2.65]
    wheel_set(T, ys, R, W, ht, steer_axles=(0,))
    ch = T.mb('chassis', 'root', 'hull')
    for s in (1, -1):
        ch.box((s * 0.48, 0.1, 0.98), (0.12, 7.4, 0.24), MT)
    for y in (-3.3, -1.0, 0.5, 2.0, 3.5):
        ch.box((0, y, 0.98), (1.08, 0.1, 0.16), MT)
    for y in ys:
        axle(ch, y, R, ht)
    ch.cyl(0.06, 4.9, 8, MT, M=frame((0.1, -0.6, 0.62), (0, 1, 0)))
    mb = T.mb('hull', 'body', 'hull')
    # front end
    mb.box((0, -3.76, 0.86), (2.46, 0.22, 0.3), P)
    mb.cyl(0.1, 0.62, 12, MT, M=frame((0, -3.78, 0.68), (1, 0, 0)))
    for s in (1, -1):
        towhook(mb, (s * 0.78, -3.92, 0.82))
    mb.box((0, -2.82, 1.32), (1.62, 1.68, 0.7), P, top=(0.94, 0.98))
    mb.box((0, -3.665, 1.3), (1.34, 0.04, 0.52), MT)
    for i in range(10):
        mb.box((-0.6 + i * 0.133, -3.69, 1.3), (0.035, 0.04, 0.5), P)
    for s in (1, -1):
        mb.box((s * 0.98, -2.55, 1.21), (0.62, 1.55, 0.07), P)
        mb.box((s * 0.98, -3.31, 1.02), (0.62, 0.06, 0.36), P)
        mb.box((s * 0.98, -1.79, 1.0), (0.62, 0.05, 0.42), RB)
        headlight(mb, (s * 0.88, -3.37, 1.37), (0, -1, 0), 0.09)
        for k in range(3):
            mb.box((s * 0.82, -2.3 + k * 0.25, 1.68), (0.06, 0.18, 0.02), MT)
    # cab
    mb.loft([ring_rect(1.15, -1.98, -0.45, 1.05, 0.05), ring_rect(1.15, -1.98, -0.45, 1.8, 0.05),
             ring_rect(1.08, -1.72, -0.48, 2.65, 0.09)], P)
    tilt = math.atan2(0.26, 0.85)
    for s in (1, -1):
        mb.box((0, 0, 0), (0.95, 0.03, 0.74), GL, M=Mt(s * 0.52, -1.87, 2.22) @ Mrx(-tilt))
        mb.box((s * 1.155, -1.25, 2.18), (0.03, 0.85, 0.5), GL)
        mb.box((s * 1.16, -1.22, 1.45), (0.03, 0.95, 0.9), P)
        mb.box((s * 1.19, -0.85, 1.6), (0.03, 0.12, 0.04), MT)
        beam(mb, (s * 1.15, -1.75, 2.0), (s * 1.42, -1.85, 2.15), 0.03, 0.03, MT)
        mf = mb.box((s * 1.45, -1.85, 2.15), (0.06, 0.22, 0.34), P)
        mf[0].material_index = GL
        mb.box((s * 1.12, -1.2, 0.82), (0.32, 0.5, 0.05), MT)
        mb.box((s * 1.12, -1.2, 0.55), (0.32, 0.5, 0.05), MT)
    mb.box((0, -0.43, 2.18), (1.2, 0.03, 0.4), GL)
    hatch(mb, (0.45, -1.1, 2.65), 0.3)
    mb.cyl(0.065, 1.75, 10, MT, M=frame((-1.27, -0.6, 1.15), (0, 0, 1)), x0=0.0)
    mb.box((-1.27, -0.6, 2.3), (0.16, 0.16, 0.5), P)
    mb.lathe([(0.065, 0), (0.09, 0.0), (0.09, 0.08), (0.0, 0.1)], 10, MT, M=frame((-1.27, -0.6, 2.9), (0, 0, 1)))
    antenna(mb, (0.95, -0.55, 2.65), 1.8)
    # tanks and boxes on the chassis
    ch.cyl(0.26, 1.0, 16, P, M=frame((0.98, -0.05, 0.8), (0, 1, 0)))
    for d in (-0.4, 0.4):
        ch.box((0.98, -0.05 + d, 0.8), (0.56, 0.04, 0.56), MT)
    storage_box(ch, (-1.0, -0.05, 0.55), (0.42, 0.9, 0.45), latch_dir=-1)
    # cargo bed
    mb.box((0, 1.75, 1.32), (2.42, 3.98, 0.1), P)
    for s in (1, -1):
        mb.box((s * 1.18, 1.75, 1.63), (0.06, 3.98, 0.52), P)
        for k in range(6):
            mb.box((s * 1.215, -0.15 + k * 0.78, 1.6), (0.04, 0.08, 0.58), P)
        mb.box((s * 0.98, 3.25, 1.0), (0.62, 0.05, 0.45), RB)
        mb.box((s * 0.98, 2.0, 1.2), (0.62, 2.2, 0.06), P)
    mb.box((0, -0.22, 1.63), (2.42, 0.06, 0.52), P)
    mb.box((0, 3.86, 0.9), (2.3, 0.14, 0.18), P)
    for s in (1, -1):
        taillight(mb, (s * 0.95, 3.94, 0.9))
        towhook(mb, (s * 0.5, 3.95, 0.78))
    # canvas cover with bows
    def arch(y, sag=0.0):
        pts = [(-1.2 + sag, 1.88), (-1.2 + sag, 2.25), (-1.2 + sag, 2.56)]
        for k in range(1, 8):
            a = math.pi - math.pi * k / 8
            pts.append(((1.2 - sag) * math.cos(a), 2.56 + (0.4 - sag) * math.sin(a)))
        pts += [(1.2 - sag, 2.56), (1.2 - sag, 2.25), (1.2 - sag, 1.88)]
        return [(x, y, z) for x, z in pts]
    bows = [-0.16, 0.8, 1.76, 2.72, 3.68]
    rings = []
    for i, y in enumerate(bows):
        rings.append(arch(y))
        if i < len(bows) - 1:
            rings.append(arch((y + bows[i + 1]) / 2, 0.025))
    mb.loft(rings, K)
    for y in bows:
        for s in (1, -1):
            mb.box((s * 1.21, y, 1.95), (0.03, 0.05, 0.1), MT)
    tg = T.mb('tailgate', 'tailgate', 'hull')
    tg.box((0, 3.73, 1.62), (2.34, 0.06, 0.5), P)
    for x in (-0.8, 0, 0.8):
        tg.box((x, 3.765, 1.62), (0.06, 0.02, 0.46), P)
    door(T, 'tailgate', (0, 3.72, 1.37), (0, 3.32, 1.37), 'x', 95.0)
    vbones(T, 7.8, 1.2)
    T.meta.update(kind='cargo_truck_6x6')


# ===================================================================================== 2. Bastion 4x4 MRAP
def build_bastion(T):
    R, W, ht = 0.62, 0.48, 1.08
    ys = [-1.95, 1.75]
    wheel_set(T, ys, R, W, ht, steer_axles=(0,), max_steer=30.0)
    ch = T.mb('chassis', 'root', 'hull')
    for y in ys:
        axle(ch, y, R, ht)
        for s in (1, -1):
            ch.cyl(0.07, 0.45, 8, MT, M=frame((s * 0.6, y + 0.25, R + 0.25), (0, 0, 1)), x0=0.0)
    mb = T.mb('hull', 'body', 'hull')

    def vring(y, top, k=1.0, apex=0.62):
        pts = [(0, apex), (0.95 * k, 0.98), (1.18 * k, 1.28), (1.05 * k, top), (-1.05 * k, top), (-1.18 * k, 1.28),
               (-0.95 * k, 0.98)]
        return [(x, y, z) for x, z in pts]
    mb.loft([vring(-3.05, 1.45, 0.84, 0.9), vring(-2.62, 1.64, 0.96, 0.75), vring(-1.08, 1.74, 1.0),
             vring(-0.55, 2.5, 1.0), vring(2.78, 2.5, 1.0), vring(3.02, 2.42, 0.98, 0.72)], P)
    tilt = math.atan2(0.53, 0.76)
    for s in (1, -1):
        mb.box((0, 0, 0), (0.92, 0.05, 0.78), GL, M=Mt(s * 0.5, -0.84, 2.13) @ Mrx(-(math.pi / 2 - tilt)))
        for y in (-0.15, 0.75, 1.7):
            mb.box((s * 1.11, y, 2.02), (0.05, 0.55, 0.42), GL)
        mb.box((s * 1.2, -0.05, 1.68), (0.04, 1.0, 1.1), P)
        mb.box((s * 1.23, 0.3, 1.7), (0.04, 0.12, 0.05), MT)
        for y in ys:
            mb.box((s * 1.2, y, 1.42), (0.3, 1.55, 0.08), P, top=(1, 0.9))
            mb.box((s * 1.2, y - 0.78, 1.15), (0.3, 0.06, 0.5), P)
            mb.box((s * 1.2, y + 0.78, 1.15), (0.3, 0.06, 0.5), RB)
        headlight(mb, (s * 0.72, -3.08, 1.3), (0, -1, 0), 0.08)
        beam(mb, (s * 1.12, -0.55, 2.3), (s * 1.42, -0.7, 2.25), 0.03, 0.03, MT)
        mf = mb.box((s * 1.45, -0.7, 2.15), (0.06, 0.24, 0.36), P)
        mf[0].material_index = GL
        mb.box((s * 1.13, 0.0, 0.86), (0.35, 0.55, 0.05), MT)
        for k in range(3):
            beam(mb, (s * 1.12, 2.35 + k * 0.18, 1.35), (s * 1.12, 2.35 + k * 0.18, 2.1), 0.025, 0.025, MT)
        jerrycan(mb, (s * 1.32, 2.55, 1.35), math.pi / 2)
        taillight(mb, (s * 0.9, 3.06, 2.0))
    # brush guard / bumper / winch
    mb.box((0, -3.2, 1.05), (2.1, 0.18, 0.22), P)
    mb.cyl(0.1, 0.55, 12, MT, M=frame((0, -3.24, 0.92), (1, 0, 0)))
    for x in (-0.7, -0.25, 0.25, 0.7):
        beam(mb, (x, -3.28, 1.15), (x, -3.15, 1.55), 0.05, 0.05, MT)
    beam(mb, (-0.85, -3.17, 1.55), (0.85, -3.17, 1.55), 0.05, 0.05, MT)
    grille(mb, (0, -2.0, 1.69), 1.2, 0.55, 8)
    for s in (1, -1):
        towhook(mb, (s * 0.6, -3.3, 0.95))
    # roof: stowage rail + antennas
    for s in (1, -1):
        beam(mb, (s * 0.85, 1.8, 2.62), (s * 0.85, 2.7, 2.62), 0.035, 0.035, MT)
        antenna(mb, (s * 0.9, 2.6, 2.5), 2.0)
    beam(mb, (-0.85, 2.7, 2.62), (0.85, 2.7, 2.62), 0.035, 0.035, MT)
    storage_box(mb, (0, 2.25, 2.5), (1.2, 0.7, 0.22))
    mb.box((0, 3.14, 0.95), (2.1, 0.18, 0.2), P)
    # rear door (hinged on the right side)
    rd = T.mb('door_rear', 'door_rear', 'hull')
    rd.box((0.05, 3.05, 1.72), (1.0, 0.07, 1.42), P)
    w = rd.box((0.05, 3.09, 2.05), (0.3, 0.02, 0.3), GL)
    rd.box((0.42, 3.1, 1.65), (0.04, 0.04, 0.16), MT)
    door(T, 'door_rear', (-0.45, 3.08, 1.0), (-0.45, 3.08, 1.5), 'y', 100.0, z_axis=(0, -1, 0))
    gun_mount(T, (0, 0.9, 2.5), 0.72, (0, 0.82, 2.92), 1.35, -10.0, 60.0)
    vbones(T, 6.4, 1.6)
    T.meta.update(kind='armoured_carrier_4x4')


# ===================================================================================== 3. Carrier tracked APC
def build_carrier(T):
    H = dict(wi=0.97, wu=1.44,
             lower=[(-2.2, 0.40), (2.25, 0.40), (2.55, 0.98), (-2.62, 0.98)],
             upper=[(1.44, -2.62, 2.55, 0.98, 0.04), (1.44, -2.6, 2.53, 1.05, 0.04), (1.40, -1.55, 2.5, 1.95, 0.06)])
    T.H = H
    rg = dict(p=0.15, tp=0.045, g=0.03, tw=0.38, tx=1.22, horn_w=0.05, horn_h=0.05,
              road=dict(r=0.30, ys=[-1.72, -0.88, -0.04, 0.8, 1.64]),
              front=dict(kind='sprocket', y=-2.45, z=0.62, Z=12),
              rear=dict(kind='idler', y=2.36, z=0.5, r=0.26))
    T.running_gear(rg)
    zd = 1.95
    hull = hull_shell(T, H)
    hull_details(T, H, rg, dict(light_in=0.2, light_r=0.065, driver_x=0.62, hatch_t=0.85, hatch_r=0.26,
                                peri_t=0.97, exhaust=False, spare_links=0,
                                grilles=[(-0.62, -1.05, 0.55, 0.65)], boxes=[], cans=[]))
    p, n, ga = glacis(H, 0.0, 0.45, 0.06)
    hull.box((0, 0, 0), (2.5, 0.85, 0.035), P, M=Mt(*p) @ Mrx(ga))
    for s in (1, -1):
        beam(hull, (s * 1.2, -2.1, 1.25), (s * 1.2, -2.0, 1.45), 0.04, 0.04, MT)
    hull.box((-1.48, -1.6, 1.62), (0.08, 0.5, 0.35), MT)
    for i in range(5):
        hull.box((-1.53, -1.8 + i * 0.1, 1.62), (0.03, 0.03, 0.33), P)
    for s in (1, -1):
        storage_box(hull, (s * 1.28, 1.2, zd), (0.28, 1.2, 0.3), latch_dir=s)
        antenna(hull, (s * 1.2, 2.25, zd), 2.0)
    hull.box((0, 1.55, zd + 0.03), (1.25, 1.3, 0.06), P)
    for x in (-0.45, 0.45):
        hull.cyl(0.04, 0.2, 8, MT, M=frame((x, 2.2, zd + 0.05), (1, 0, 0)))
    # rear ramp
    rp = T.mb('ramp', 'ramp', 'hull')
    rp.box((0, 2.6, 1.2), (1.75, 0.08, 1.5), P)
    rp.box((0.35, 2.645, 1.25), (0.6, 0.02, 1.0), P)
    rp.box((0.58, 2.66, 1.25), (0.04, 0.04, 0.14), MT)
    rp.box((0.35, 2.65, 1.55), (0.2, 0.02, 0.18), GL)
    door(T, 'ramp', (0, 2.6, 0.46), (0, 2.2, 0.46), 'x', 100.0, parent='hull')
    # commander cupola with heavy MG
    TU = dict(ty=0.3)
    ring_r = 0.45
    tur = T.mb('turret', 'turret', 'turret')
    tur.lathe([(0, 0), (ring_r, 0), (ring_r, 0.26), (ring_r * 0.92, 0.32), (0, 0.32)], 20, P,
              M=frame((0, 0.3, zd), (0, 0, 1)))
    hatch(tur, (0, 0.42, zd + 0.32), 0.3)
    for i in range(5):
        a = math.pi * 0.25 + i * math.pi * 0.125 - math.pi
        o = (0.93 * ring_r * math.cos(a), 0.3 + 0.93 * ring_r * math.sin(a), zd + 0.1)
        periscope(tur, o, a + math.pi / 2, 0.1, 0.06, 0.12)
    for ang, w in ((0.0, 0.85), (0.8, 0.5), (-0.8, 0.5)):
        d = Vector((math.sin(ang), -math.cos(ang), 0))
        c = Vector((0, 0.3, zd + 0.62)) + d * (ring_r + 0.05)
        tur.box((0, 0, 0), (w, 0.035, 0.52), P, M=Mt(*c) @ Mrz(ang), top=(0.92, 1.0))
    trunnion = (0.0, -0.1, zd + 0.62)
    gun = T.mb('gun', 'gun', 'turret')
    gun.box(trunnion, (0.14, 0.5, 0.16), MT)
    gun.box((0.16, -0.05, zd + 0.6), (0.14, 0.24, 0.18), P)
    brl = T.mb('barrel', 'barrel', 'turret')
    L = 1.55
    brl.lathe([(0, 0.15), (0.045, 0.15), (0.045, 0.5), (0.028, 0.55), (0.026, L - 0.15), (0.04, L - 0.12),
               (0.04, L), (0.015, L), (0, L - 0.06)], 10, MT, M=frame(trunnion, (0, -1, 0)))
    muzzle = (0.0, trunnion[1] - L, trunnion[2])
    std_bones(T, H, TU, zd, ring_r, trunnion, L,
              [('', (0, trunnion[1] - 0.1, trunnion[2]), muzzle, 0.06, 0.8, 0.36, [1, 4, 7, 10, 13, 16])])
    finish_meta(T, 'tracked_apc', -10.0, 55.0)


TR_DESIGNS = {
    'Mule': (build_mule, False, dict(pattern='blotch', scale=0.5, distort=0.4, dust=0.85, dust_h=1.6,
                                     stops=[(0.0, srgb('#4f5634')), (0.62, srgb('#474d2f'))],
                                     mark=srgb('#7d7656'), dust_col=srgb('#8a7a5c'))),
    'Bastion': (build_bastion, False, dict(pattern='blotch', scale=0.45, distort=0.5, dust=0.75, dust_h=1.7,
                                           stops=[(0.0, srgb('#b8a17a')), (0.6, srgb('#a99270'))],
                                           mark=srgb('#202020'), dust_col=srgb('#a28d6c'))),
    'Carrier': (build_carrier, True, dict(pattern='blotch', scale=0.5, distort=0.6, dust=0.75,
                                          stops=[(0.0, srgb('#4b5934')), (0.5, srgb('#2a2b22')),
                                                 (0.62, srgb('#5c4a30'))], mark=srgb('#202020'))),
}
TR_LINEUP = {'Mule': -9.0, 'Bastion': 0.0, 'Carrier': 8.5}


def build_vehicle(name):
    fn, tracked, cfg = TR_DESIGNS[name]
    T = Vehicle(name, (TR_LINEUP[name], 0.0, 0.0), cfg)
    fn(T)
    T.finish_parts()
    T.tracked = tracked
    return T


def vehicle_pipeline_rig(T):
    if T.tracked:
        T.build_tracks(make_track_material())
    if T.flashes:
        T.build_flash(flash_material())
    T.build_rig()
    bad = T.build_drivers() if T.tracked else []
    if T.tracked:
        clips = T.build_clips()
        door_clips(T, clips)
    else:
        clips = wheeled_clips(T)
    m = T.meta
    m.update(vehicle=T.name, doors=T.doors, steer=T.steer,
             wheels=getattr(T, 'wheel_r', {}) or m.get('wheels', {}))
    for k, v in m.items():
        T.rig[f'tk_{k}'] = v if not isinstance(v, (list, dict)) else json.dumps(v)
    return bad, clips


def vehicle_export(T):
    T.rig.hide_set(False)
    for pb in T.rig.pose.bones:
        pb.location, pb.rotation_euler, pb.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    path = os.path.join(GLB_DIR, f'Vehicle_{T.name}.glb')
    export_tank(T, path)
    w = glb_postprocess(path)
    for pb in T.rig.pose.bones:
        pb.location, pb.rotation_euler, pb.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    s = glb_summary(path)
    return dict(kb=s['size_kb'], joints=s['skins'], materials=s['materials'],
                anims={k: sum(v.values()) for k, v in s['anims'].items()})
