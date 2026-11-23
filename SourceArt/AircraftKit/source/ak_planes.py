# Aircraft Kit - the five designs (2 biplanes, 3 jets). Origin = reference point near the CG.

RED, WHITE, BLUE = srgb('#9e2a22'), srgb('#e6e2d6'), srgb('#24406e')
YEL, BLK = srgb('#d9a520'), srgb('#1a1a1a')


def roundel(x, y, z, ax, r, depth, rings):
    return (x, y, z, ax, r, depth, rings)


def cockpit_rim(mb, y, z, r=0.3):
    mb.lathe([(r * 0.82, 0.0), (r, 0.0), (r * 1.06, 0.03), (r * 0.98, 0.06), (r * 0.82, 0.05)], 16, RB,
             M=frame((0, y, z), (0, 0, 1)))
    mb.lathe([(0, -0.02), (r * 0.84, -0.02), (r * 0.84, 0.0), (0, 0.0)], 16, MT, M=frame((0, y, z), (0, 0, 1)))


# =============================================================================== 1. Kestrel (WWI)
def build_kestrel(T):
    mb = T.mb('hull', 'body', 'hull')
    st = fuselage(mb, [(-2.33, 0.02, 0.40, 0.40, 0.40, 2.0), (-1.9, 0.03, 0.39, 0.40, 0.40, 2.4),
                       (-1.3, 0.05, 0.37, 0.41, 0.42, 3.2), (-0.6, 0.05, 0.35, 0.40, 0.44, 3.6),
                       (0.2, 0.06, 0.31, 0.34, 0.40, 3.6), (1.2, 0.10, 0.23, 0.26, 0.30, 3.5),
                       (2.3, 0.16, 0.14, 0.17, 0.18, 3.0), (3.2, 0.22, 0.06, 0.10, 0.08, 2.5),
                       (3.42, 0.24, 0.02, 0.04, 0.03, 2.0)], N=24)
    # cowling ring (open front shows the rotary engine)
    mb.lathe([(0.44, 0.0), (0.455, 0.25), (0.43, 0.37), (0.36, 0.42), (0.33, 0.38), (0.33, 0.02), (0.44, 0.0)],
             24, K, M=frame((0, -2.3, 0.02), (0, -1, 0)))
    eng = T.mb('engine', 'prop', 'hull')
    radial_engine(eng, (0, -2.6, 0.02), 9, 0.34, 0.045)
    propeller(T, (0, -2.83, 0.02), 1.25, 2, 0.17, 1.7, spinner=(0.08, 0.14), blade_mat=K, spin_mat=MT)
    # wings
    lw = Planform([(0.2, -1.32, -0.36, 1.42, 0.075, 0), (3.5, -1.32, -0.25, 1.42, 0.07, 0),
                   (3.72, -1.24, -0.245, 1.2, 0.07, 0), (3.84, -1.05, -0.24, 0.75, 0.06, 0)])
    lifting(T, lw, 'wings', 'body', camber=0.035, cap_root=False)
    uw = Planform([(0.0, -1.72, 1.02, 1.5, 0.075, 0), (3.85, -1.72, 1.02, 1.5, 0.07, 0),
                   (4.05, -1.64, 1.02, 1.26, 0.07, 0), (4.16, -1.44, 1.02, 0.78, 0.06, 0)])
    lifting(T, uw, 'wings', 'body', camber=0.035, cap_root=False, ctrl=(2.35, 3.85, 'aileron'), hinge=0.76,
            ctrl_max=20, axis='roll')
    w = T.mb('wings', 'body', 'hull')
    for s in (1, -1):
        for yl, yu in ((-1.08, -1.45), (-0.25, -0.62)):
            strut(w, (s * 2.95, yl, -0.27), (s * 2.95, yu, 0.99), 0.035, 0.1)
            strut(w, (s * 0.32, yl - 0.25, 0.38), (s * 0.4, yu - 0.1, 0.98), 0.03, 0.08)
        wire(w, (s * 0.38, -1.05, -0.32), (s * 2.92, -1.42, 0.97))
        wire(w, (s * 0.38, -0.3, -0.32), (s * 2.92, -0.6, 0.97))
        wire(w, (s * 0.42, -1.4, 0.97), (s * 2.92, -1.08, -0.26))
        wire(w, (s * 0.42, -0.6, 0.97), (s * 2.92, -0.25, -0.26))
    # tail
    ht = Planform([(0.05, 2.58, 0.2, 0.82, 0.06, 0), (1.15, 2.62, 0.2, 0.75, 0.06, 0),
                   (1.38, 2.75, 0.2, 0.5, 0.05, 0)])
    lifting(T, ht, 'tail', 'body', ctrl=(0.12, 1.3, 'elevator'), hinge=0.55, ctrl_dir='+x', axis='pitch',
            ctrl_max=25, cap_root=False)
    vt = Planform([(0.15, 2.78, 0.0, 0.62, 0.07, 0), (0.75, 2.95, 0.0, 0.5, 0.065, 0),
                   (1.02, 3.1, 0.0, 0.32, 0.06, 0)])
    lifting(T, vt, 'tail', 'body', sides=('',), vertical=True, ctrl=(0.25, 0.98, 'rudder'), hinge=0.45,
            axis='yaw', ctrl_max=25)
    # gear: V struts, axle, wheels, tail skid
    g = T.mb('gear', 'body', 'hull')
    for s in (1, -1):
        strut(g, (s * 0.28, -1.7, -0.36), (s * 0.82, -1.34, -1.1), 0.04, 0.09)
        strut(g, (s * 0.28, -0.95, -0.36), (s * 0.82, -1.3, -1.1), 0.04, 0.09)
        wire(g, (s * 0.28, -1.68, -0.38), (-s * 0.8, -1.32, -1.08))
    g.cyl(0.035, 1.8, 8, MT, M=frame((0, -1.32, -1.12), (1, 0, 0)))
    g.box((0, -1.32, -1.07), (1.5, 0.22, 0.05), K)
    for side, s in (('L', 1), ('R', -1)):
        wheel(T, f'wheel_{side}', f'wheel_{side}', (s * 0.97, -1.32, -1.12), 0.33, 0.11, 'body')
    strut(g, (0, 3.05, 0.05), (0, 3.3, -0.35), 0.04, 0.06, MT)
    # guns + cockpit
    for s in (1, -1):
        gun_barrel(mb, (s * 0.13, -1.55, 0.44), 0.75, 0.017)
    mb.box((0, -1.25, 0.45), (0.12, 0.25, 0.1), MT)
    cockpit_rim(mb, -0.45, 0.39, 0.32)
    pilot(mb, (0, -0.42, 0.62), helmet_mat=RB)
    T.glass_part('body', lambda gm: gm.box((0, -0.86, 0.56), (0.36, 0.015, 0.16), 0, top=(0.8, 1.0)))
    for s in (1, -1):
        T.muzzle(s if s > 0 else 2, (s * 0.13, -2.32, 0.44), 0.45, 0.22)
    T.std_bones(6.3)
    T.meta['flight'] = dict(stall_kmh=70, max_kmh=190)
    finish_air_meta(T, 'biplane_ww1')


# =============================================================================== 2. Falcon (1930s)
def build_falcon(T):
    mb = T.mb('hull', 'body', 'hull')
    st = fuselage(mb, [(-2.55, 0.0, 0.5, 0.5, 0.5, 2.0), (-2.0, 0.0, 0.5, 0.52, 0.5, 2.1),
                       (-1.0, 0.03, 0.47, 0.52, 0.5, 2.3), (-0.2, 0.05, 0.42, 0.48, 0.5, 2.4),
                       (0.8, 0.08, 0.34, 0.38, 0.44, 2.4), (2.0, 0.14, 0.24, 0.27, 0.32, 2.3),
                       (3.4, 0.22, 0.13, 0.15, 0.17, 2.2), (4.4, 0.28, 0.05, 0.07, 0.06, 2.0),
                       (4.65, 0.3, 0.02, 0.03, 0.02, 2.0)], N=24)
    mb.lathe([(0.5, 0.0), (0.6, 0.12), (0.62, 0.4), (0.58, 0.55), (0.5, 0.6), (0.46, 0.55), (0.48, 0.2),
              (0.47, 0.0), (0.5, 0.0)], 24, K, M=frame((0, -2.5, 0.0), (0, -1, 0)))
    radial_engine(mb, (0, -2.95, 0.0), 9, 0.46, 0.055)
    mb.lathe([(0.0, 0.0), (0.3, 0.0), (0.3, 0.12), (0.0, 0.12)], 16, MT, M=frame((0, -2.55, 0.0), (0, -1, 0)))
    for k in range(4):
        a = math.radians(-60 - k * 20)
        mb.cyl(0.045, 0.5, 8, MT, M=frame((0.55 * math.cos(a) * 0.9, -2.3, 0.55 * math.sin(a)), (0, 1, 0)), x0=0)
    propeller(T, (0, -3.2, 0.0), 1.35, 3, 0.2, 2.5, spinner=(0.17, 0.42), blade_mat=MT, spin_mat=K)
    uw = Planform([(0.0, -1.62, 1.12, 1.62, 0.085, 0), (4.4, -1.62, 1.12, 1.62, 0.075, 0),
                   (4.68, -1.53, 1.12, 1.32, 0.07, 0), (4.82, -1.32, 1.12, 0.8, 0.06, 0)])
    lifting(T, uw, 'wings', 'body', camber=0.03, cap_root=False, ctrl=(2.6, 4.35, 'aileron'), hinge=0.76,
            axis='roll', ctrl_max=20)
    lw = Planform([(0.35, -1.02, -0.46, 1.34, 0.085, 0), (3.95, -1.02, -0.33, 1.34, 0.075, 0),
                   (4.2, -0.94, -0.32, 1.08, 0.07, 0), (4.32, -0.76, -0.315, 0.64, 0.06, 0)])
    lifting(T, lw, 'wings', 'body', camber=0.03, cap_root=False)
    w = T.mb('wings', 'body', 'hull')
    for s in (1, -1):
        strut(w, (s * 3.3, -0.84, -0.33), (s * 3.3, -1.3, 1.1), 0.04, 0.11)
        strut(w, (s * 3.3, -0.12, -0.33), (s * 3.3, -0.55, 1.1), 0.04, 0.11)
        strut(w, (s * 3.3, -0.84, -0.33), (s * 3.3, -0.55, 1.1), 0.03, 0.08)
        strut(w, (s * 0.35, -1.45, 0.45), (s * 0.45, -1.4, 1.08), 0.035, 0.09)
        strut(w, (s * 0.35, -0.75, 0.45), (s * 0.45, -0.65, 1.08), 0.035, 0.09)
        strut(w, (s * 0.35, -1.45, 0.45), (s * 0.45, -0.65, 1.08), 0.03, 0.07)
        wire(w, (s * 0.45, -0.9, -0.4), (s * 3.25, -1.25, 1.08))
        wire(w, (s * 0.45, -1.3, 1.08), (s * 3.25, -0.85, -0.3))
    ht = Planform([(0.1, 3.6, 0.3, 1.0, 0.06, 0), (1.45, 3.75, 0.3, 0.82, 0.055, 0), (1.7, 3.92, 0.3, 0.5, 0.05, 0)])
    lifting(T, ht, 'tail', 'body', ctrl=(0.15, 1.62, 'elevator'), hinge=0.58, ctrl_dir='+x', axis='pitch',
            ctrl_max=25, cap_root=False)
    vt = Planform([(0.22, 3.55, 0.0, 1.05, 0.07, 0), (1.05, 3.95, 0.0, 0.7, 0.065, 0), (1.32, 4.18, 0.0, 0.4, 0.06, 0)])
    lifting(T, vt, 'tail', 'body', sides=('',), vertical=True, ctrl=(0.3, 1.28, 'rudder'), hinge=0.52,
            axis='yaw', ctrl_max=25)
    # spatted cantilever gear
    g = T.mb('gear', 'body', 'hull')
    for side, s in (('L', 1), ('R', -1)):
        strut(g, (s * 0.55, -1.15, -0.48), (s * 1.12, -1.2, -1.12), 0.06, 0.16)
        fuselage(g, [(-1.62, -1.2, 0.03, 0.03, 0.03, 2.0), (-1.45, -1.2, 0.1, 0.2, 0.18, 2.0),
                     (-1.2, -1.18, 0.12, 0.27, 0.24, 2.0), (-0.9, -1.18, 0.1, 0.22, 0.2, 2.0),
                     (-0.6, -1.17, 0.03, 0.05, 0.05, 2.0)], N=16, sub=2, xc=s * 1.12)
        wheel(T, f'wheel_{side}', f'wheel_{side}', (s * 1.12, -1.2, -1.2), 0.3, 0.12, 'body')
    strut(g, (0, 4.1, 0.15), (0, 4.25, -0.2), 0.05, 0.08, MT)
    wheel(T, 'wheel_T', 'wheel_T', (0, 4.28, -0.28), 0.1, 0.06, 'body')
    # guns
    for s in (1, -1):
        gun_barrel(mb, (s * 0.12, -2.1, 0.5), 0.6, 0.016, jacket=False)
        gun_barrel(T.mb('wings', 'body', 'hull'), (s * 2.1, -0.9, -0.6), 0.75, 0.018)
    T.muzzle(1, (0.12, -2.72, 0.5), 0.45, 0.22)
    T.muzzle(2, (-0.12, -2.72, 0.5), 0.45, 0.22)
    T.muzzle(3, (2.1, -1.66, -0.6), 0.5, 0.24)
    T.muzzle(4, (-2.1, -1.66, -0.6), 0.5, 0.24)
    # cockpit with sliding hood
    zt = fuse_at(st, -0.4)
    ztop = zt[0] + zt[2]
    mb.box((0, -0.45, ztop - 0.02), (0.62, 1.4, 0.06), MT)
    pilot(mb, (0, -0.3, ztop + 0.2), helmet_mat=RB)
    can = T.mb('canopy_frame', 'canopy', 'hull')

    def hood(gm, y0, y1, h, w):
        rings = [fuse_ring(y, ztop - 0.03, w, h * (1 - ((y - (y0 + y1) / 2) / (y1 - y0) * 1.4) ** 4 * 0.4), 0.1, 2.3,
                           N=12, top_only=True) for y in (y0, (y0 * 2 + y1) / 3, (y0 + y1 * 2) / 3, y1)]
        gm.loft(rings, 0, cap0=False, cap1=False)
        return rings
    T.glass_part('body', lambda gm: gm.loft([fuse_ring(-1.15, ztop - 0.03, 0.26, 0.05, 0.1, 2.3, N=12, top_only=True),
                                             fuse_ring(-0.85, ztop - 0.03, 0.3, 0.3, 0.1, 2.3, N=12, top_only=True)],
                                            0, cap0=False, cap1=False))
    rings = []
    T.glass_part('canopy', lambda gm: rings.extend(hood(gm, -0.85, 0.15, 0.34, 0.31)))
    for r in (rings[0], rings[-1]):
        for a, b in zip(r, r[1:]):
            beam(can, a, b, 0.03, 0.03, P)
    for i in (3, 9):
        for a, b in zip([r[i] for r in rings], [r[i] for r in rings][1:]):
            beam(can, a, b, 0.025, 0.025, P)
    T.canopy = dict(mode='slide', travel=0.75)
    T.bone('canopy', (0, -0.35, ztop + 0.2), (0, -0.8, ztop + 0.2), parent='body', shape='box',
           sxyz=(0.35, 0.5, 0.2), color='THEME05', locks=dict(loc=(True, False, True), rot=(True,) * 3))
    T.std_bones(7.9)
    finish_air_meta(T, 'biplane_1930s')


# =============================================================================== jets: shared parts
def jet_gear(T, nose, mains, r_main=0.33, r_nose=0.27, nose_angle=95, main_angle=88):
    g = T.mb('gear_N', 'gear_N', 'turret')
    p, axle = Vector(nose[0]), Vector(nose[1])
    g.cyl(0.055, (p - axle).length, 10, MT, M=frame(axle, p - axle), x0=0)
    g.box((axle.x, axle.y + 0.12, axle.z + 0.25), (0.05, 0.3, 0.05), MT)
    g.box((axle.x + 0.12, axle.y - 0.05, (p.z + axle.z) / 2 + 0.1), (0.02, 0.55, (p.z - axle.z) * 0.7), P)
    T.gear_bone('gear_N', p, 'x', nose_angle)
    wheel(T, 'wheel_N', 'wheel_N', tuple(axle), r_nose, 0.16, 'gear_N')
    for side, (piv, ax) in zip(('L', 'R'), mains):
        bn = f'gear_{side}'
        g = T.mb(bn, bn, 'turret')
        p, axle = Vector(piv), Vector(ax)
        s = 1 if side == 'L' else -1
        g.cyl(0.065, (p - axle).length + 0.1, 10, MT, M=frame(axle, p - axle), x0=-0.05)
        g.cyl(0.04, 0.35, 8, MT, M=frame(axle + Vector((0, 0, 0.0)), (1, 0, 0)), x0=-0.18)
        door = g.box(((p.x + axle.x) / 2 + s * 0.09, (p.y + axle.y) / 2, (p.z + axle.z) / 2 + 0.08),
                     (0.02, 0.62, (p - axle).length * 0.9), P)
        T.gear_bone(bn, p, 'y', -main_angle * s)
        wheel(T, f'wheel_{side}', f'wheel_{side}', (axle.x + s * 0.1, axle.y, axle.z), r_main, 0.2, bn)


def bubble_canopy(T, st, y_ws0, y_ws1, y_end, w, h, mode='slide', travel=0.8, hinge_y=None, frame_mat=P):
    zt = fuse_at(st, (y_ws1 + y_end) / 2)
    z0 = zt[0] + zt[2] * 0.82
    mb = T.mb('hull', 'body', 'hull')
    mb.box((0, (y_ws0 + y_end) / 2, z0 - 0.02), (w * 1.6, y_end - y_ws0, 0.06), MT)
    pilot(mb, (0, (y_ws1 * 0.35 + y_end * 0.65), z0 + 0.32), helmet_mat=K)
    mb.box((0, y_ws1 + 0.05, z0 + 0.18), (0.4, 0.12, 0.2), MT)

    def prof(y):
        return 1 - ((y - y_ws0) / (y_end - y_ws0) * 2 - 1) ** 4
    ws_rings = [fuse_ring(y, z0, w * (0.55 + 0.45 * min(1, (y - y_ws0) / (y_ws1 - y_ws0) * 1.3)),
                          h * max(prof(y), 0.08), 0.1, 2.2, N=14, top_only=True)
                for y in (y_ws0, (y_ws0 + y_ws1) / 2, y_ws1)]
    T.glass_part('body', lambda gm: gm.loft(ws_rings, 0, cap0=False, cap1=False))
    ys = [y_ws1 + (y_end - y_ws1) * f for f in (0, 0.25, 0.5, 0.75, 1.0)]
    rings = [fuse_ring(y, z0, w * (1 - max(0, (y - ys[2]) / (y_end - ys[2])) ** 2 * 0.55),
                       h * max(prof(y), 0.06), 0.1, 2.2, N=14, top_only=True) for y in ys]
    T.glass_part('canopy', lambda gm: gm.loft(rings, 0, cap0=False, cap1=False))
    fr = T.mb('canopy_frame', 'canopy', 'hull')
    for a, b in zip(rings[0], rings[0][1:]):
        beam(fr, a, b, 0.035, 0.04, frame_mat)
    for a, b in zip(ws_rings[-1], ws_rings[-1][1:]):
        beam(mb, a, b, 0.035, 0.04, frame_mat)
    for a, b in zip(ws_rings[0], ws_rings[0][1:]):
        beam(mb, a, b, 0.03, 0.03, frame_mat)
    T.canopy = dict(mode=mode, travel=travel)
    if mode == 'slide':
        T.bone('canopy', (0, ys[2], z0 + h), (0, ys[2] - 0.5, z0 + h), parent='body', shape='box',
               sxyz=(w, 0.4, 0.15), color='THEME05', locks=dict(loc=(True, False, True), rot=(True,) * 3))
    else:
        hy = hinge_y if hinge_y is not None else y_end
        T.bone('canopy', (0, hy, z0 + 0.05), (0, hy - 0.5, z0 + 0.05), parent='body', shape='box',
               sxyz=(w, 0.3, 0.1), color='THEME05', locks=dict(loc=(True,) * 3, rot=(False, True, True)))
    return z0


def nozzle(mb, c, r, L, mat=MT):
    mb.lathe([(r, 0), (r * 1.02, L * 0.6), (r * 0.9, L), (r * 0.78, L), (r * 0.8, L * 0.3), (0, L * 0.3)], 20,
             mat, mats=[MT, MT, MT, MT, MT], M=frame(c, (0, 1, 0)))


def intake_ring(mb, c, r, L=0.3, mat=P):
    mb.lathe([(r * 0.8, -L), (r * 0.8, 0.0), (r * 0.92, 0.04), (r, 0.0), (r, -L)], 20, mat,
             M=frame(c, (0, -1, 0)))
    mb.lathe([(0, -L * 0.8), (r * 0.8, -L * 0.8), (r * 0.8, -L * 0.82), (0, -L * 0.82)], 20, MT,
             M=frame(c, (0, -1, 0)))
    mb.lathe([(0, -L * 0.75), (r * 0.25, -L * 0.75), (r * 0.18, -L * 0.45), (0, -L * 0.4)], 12, MT,
             M=frame(c, (0, -1, 0)))


# =============================================================================== 3. Lancer (early straight-wing jet)
def build_lancer(T):
    mb = T.mb('hull', 'body', 'hull')
    st = fuselage(mb, [(-5.05, -0.02, 0.02, 0.02, 0.02, 2), (-4.8, 0.0, 0.25, 0.25, 0.25, 2),
                       (-4.2, 0.02, 0.45, 0.48, 0.45, 2), (-3.2, 0.05, 0.58, 0.65, 0.58, 2.1),
                       (-2.0, 0.05, 0.66, 0.7, 0.66, 2.2), (-0.5, 0.0, 0.72, 0.68, 0.7, 2.2),
                       (1.0, 0.0, 0.68, 0.6, 0.64, 2.1), (2.6, 0.05, 0.56, 0.5, 0.52, 2.0),
                       (4.0, 0.12, 0.45, 0.45, 0.43, 2.0), (5.2, 0.15, 0.4, 0.4, 0.4, 2.0)], N=24, cap1=False)
    nozzle(mb, (0, 5.15, 0.15), 0.38, 0.25)
    for s in (1, -1):
        fuselage(mb, [(-2.45, 0.0, 0.2, 0.28, 0.26, 2.0), (-2.0, 0.0, 0.24, 0.32, 0.3, 2.2),
                      (-1.0, 0.0, 0.2, 0.28, 0.28, 2.2), (0.3, 0.0, 0.06, 0.1, 0.1, 2.0)],
                 N=16, sub=2, xc=s * 0.62)
        mb.lathe([(0, 0), (0.17, 0.0), (0.17, 0.02), (0, 0.02)], 16, MT,
                 M=frame((s * 0.64, -2.4, 0.0), (0, -1, 0)) @ Matrix.Diagonal((1, 1.0, 1.5, 1)))
    wg = Planform([(0.6, -1.55, -0.42, 2.6, 0.12, 1.0), (5.8, -0.9, -0.06, 1.35, 0.1, -1.0)])
    lifting(T, wg, 'wings', 'body', ctrl=(3.2, 5.45, 'aileron'), hinge=0.75, axis='roll', ctrl_max=18,
            cap_root=False, npts=11)
    w = T.mb('wings', 'body', 'hull')
    for s in (1, -1):
        w.lathe([(0, 0), (0.12, 0.15), (0.26, 0.7), (0.28, 1.4), (0.22, 2.2), (0.1, 2.75), (0, 2.9)], 16, K,
                M=frame((s * 5.92, -2.05, -0.06), (0, 1, 0)))
    ht = Planform([(0.3, 3.95, 0.38, 1.35, 0.09, 0), (2.45, 4.35, 0.42, 0.75, 0.08, 0)])
    lifting(T, ht, 'tail', 'body', ctrl=(0.45, 2.35, 'elevator'), hinge=0.64, ctrl_dir='+x', axis='pitch',
            ctrl_max=20, cap_root=False)
    vt = Planform([(0.35, 3.35, 0.0, 1.95, 0.09, 0), (2.05, 4.55, 0.0, 0.85, 0.08, 0)])
    lifting(T, vt, 'tail', 'body', sides=('',), vertical=True, ctrl=(0.65, 1.95, 'rudder'), hinge=0.68,
            axis='yaw', ctrl_max=20)
    bubble_canopy(T, st, -3.35, -2.85, -1.2, 0.36, 0.48, 'slide', 0.85)
    for i, (x, z) in enumerate(((0.12, 0.2), (-0.12, 0.2), (0.2, 0.02), (-0.2, 0.02))):
        mb.cyl(0.022, 0.2, 6, MT, M=frame((x, -4.55, z), (0, -1, 0)), x0=0.0)
        T.muzzle(i + 1, (x, -4.76, z), 0.5, 0.22)
    mb.cyl(0.012, 0.6, 6, MT, M=frame((5.95 * 0 + 0.0, -5.02, -0.02), (0, -1, 0)), x0=0.0)
    mb.box((0, 0.6, 0.72), (0.03, 0.4, 0.25), MT, top=(1, 0.4), top_off=(0, 0.12))
    jet_gear(T, ((0, -3.55, -0.45), (0, -3.6, -1.17)),
             [((1.75, 0.35, -0.38), (1.75, 0.45, -1.12)), ((-1.75, 0.35, -0.38), (-1.75, 0.45, -1.12))])
    T.afterburner('afterburner', (0, 5.35, 0.15), 2.2, 0.75)
    T.std_bones(10.4)
    finish_air_meta(T, 'early_jet')


# =============================================================================== 4. Saber (swept-wing jet)
def build_saber(T):
    mb = T.mb('hull', 'body', 'hull')
    st = fuselage(mb, [(-5.6, 0.0, 0.5, 0.48, 0.48, 2), (-5.2, 0.02, 0.56, 0.56, 0.54, 2),
                       (-4.0, 0.05, 0.66, 0.72, 0.62, 2.1), (-2.6, 0.05, 0.7, 0.8, 0.66, 2.2),
                       (-1.0, 0.0, 0.72, 0.7, 0.68, 2.2), (1.0, 0.0, 0.7, 0.62, 0.66, 2.1),
                       (3.0, 0.08, 0.58, 0.54, 0.54, 2.0), (4.8, 0.14, 0.44, 0.44, 0.44, 2.0),
                       (5.8, 0.16, 0.4, 0.4, 0.4, 2.0)], N=24, cap0=False, cap1=False)
    intake_ring(mb, (0, -5.6, 0.0), 0.5, 0.35)
    nozzle(mb, (0, 5.75, 0.16), 0.38, 0.25)
    sw = math.tan(math.radians(35))
    wg = Planform([(0.6, -1.9, -0.28, 3.0, 0.1, 1.0), (5.6, -1.9 + 5.0 * sw, 0.0, 1.3, 0.08, -1.0)])
    lifting(T, wg, 'wings', 'body', ctrl=(2.9, 5.3, 'aileron'), hinge=0.76, axis='roll', ctrl_max=18,
            cap_root=False, npts=11)
    w = T.mb('wings', 'body', 'hull')
    for s in (1, -1):
        x = 2.8
        _, yle, h, c, t, tw = wg.at(x)
        w.box((s * x, yle + c * 0.45, h + 0.06), (0.012, c * 0.75, 0.12), P, top=(1, 0.9))
        # drop tank on pylon (store bone)
        sb = f'store_{1 if s > 0 else 2}'
        sm = T.mb(sb, sb, 'hull')
        sm.lathe([(0, 0), (0.1, 0.12), (0.25, 0.6), (0.26, 1.4), (0.18, 2.4), (0.06, 2.9), (0, 3.0)], 16, P,
                 M=frame((s * 2.1, -1.6, -0.88), (0, 1, 0)))
        for k in range(3):
            a = k * TAU / 3 + math.pi / 2
            d = Vector((math.cos(a), 0, math.sin(a)))
            c0 = Vector((s * 2.1, 1.2, -0.88)) + d * 0.2
            sm.box((0, 0, 0), (0.25, 0.4, 0.012), P, M=Mt(*c0) @ Matrix.Rotation(-a, 4, 'Y'))
        _, yle2, h2, c2, t2, tw2 = wg.at(2.1)
        w.box((s * 2.1, -0.2, (h2 - 0.88 + 0.26) / 2 - 0.08), (0.06, 1.3, h2 + 0.62 - 0.26), P, top=(1, 0.9))
        T.bone(sb, (s * 2.1, -1.0, -0.62), (s * 2.1, -1.5, -0.62), parent='body', coll='Sockets', shape='diamond',
               sxyz=(0.15,) * 3, color='THEME06')
        T.stores.append(sb)
    ht = Planform([(0.3, 3.95, 0.48, 1.55, 0.08, 0), (2.4, 3.95 + 2.1 * sw, 0.5, 0.7, 0.07, 0)])
    lifting(T, ht, 'tail', 'body', ctrl=(0.45, 2.3, 'elevator'), hinge=0.64, ctrl_dir='+x', axis='pitch',
            ctrl_max=20, cap_root=False)
    vt = Planform([(0.35, 3.05, 0.0, 2.25, 0.09, 0), (2.15, 3.05 + 1.8 * 1.05, 0.0, 0.9, 0.08, 0)])
    lifting(T, vt, 'tail', 'body', sides=('',), vertical=True, ctrl=(0.65, 2.05, 'rudder'), hinge=0.7,
            axis='yaw', ctrl_max=20)
    bubble_canopy(T, st, -3.7, -3.2, -1.45, 0.38, 0.55, 'slide', 0.9)
    i = 1
    for s in (1, -1):
        for z in (0.22, 0.08, -0.06):
            x = s * (fuse_at(st, -3.9)[1] - 0.05)
            mb.cyl(0.02, 0.18, 6, MT, M=frame((x, -3.85, z), (0, -1, 0)), x0=0.0)
            T.muzzle(i, (x, -4.05, z), 0.45, 0.2)
            i += 1
    mb.cyl(0.012, 0.7, 6, MT, M=frame((0.0, -5.0, 0.58), (0, -1, 0)), x0=0.0)
    jet_gear(T, ((0, -4.1, -0.55), (0, -4.15, -1.27)),
             [((1.25, 0.25, -0.55), (1.6, 0.35, -1.22)), ((-1.25, 0.25, -0.55), (-1.6, 0.35, -1.22))])
    T.afterburner('afterburner', (0, 5.95, 0.16), 2.4, 0.75)
    T.std_bones(11.4)
    finish_air_meta(T, 'swept_wing_jet')


# =============================================================================== 5. Wraith (modern twin-engine)
def build_wraith(T):
    mb = T.mb('hull', 'body', 'hull')
    st = fuselage(mb, [(-9.0, -0.05, 0.02, 0.02, 0.02, 2), (-8.4, -0.03, 0.28, 0.25, 0.22, 2.2),
                       (-7.2, 0.0, 0.52, 0.48, 0.38, 2.5), (-5.8, 0.05, 0.7, 0.7, 0.48, 2.8),
                       (-4.4, 0.05, 0.85, 0.85, 0.55, 3.0), (-2.6, 0.0, 1.5, 0.75, 0.62, 3.6),
                       (0.0, 0.0, 1.85, 0.62, 0.66, 3.8), (3.0, 0.0, 1.85, 0.55, 0.6, 3.8),
                       (5.8, 0.0, 1.65, 0.48, 0.55, 3.5), (7.6, 0.0, 1.45, 0.42, 0.5, 3.0),
                       (8.2, 0.0, 1.35, 0.4, 0.45, 3.0)], N=28)
    for s in (1, -1):
        nozzle(mb, (s * 0.82, 8.15, 0.0), 0.52, 0.65)
        x = s * 1.38
        mb.loft([[(x - 0.32, y, -0.62), (x + 0.32, y, -0.62), (x + 0.32, y + 0.05, 0.05), (x - 0.32, y + 0.05, 0.05)]
                 for y in (-3.5, -3.0, -1.0, 0.6)][::1], P)
        fr = mb.box((x, -3.36, -0.28), (0.56, 0.04, 0.58), MT)
    wg = Planform([(1.6, -2.2, -0.05, 7.0, 0.05, 0.0), (6.6, 2.6, -0.12, 1.7, 0.04, -1.0)])
    lifting(T, wg, 'wings', 'body', ctrl=(4.4, 6.35, 'aileron'), hinge=0.78, axis='roll', ctrl_max=18,
            cap_root=False, npts=11)
    sp = Planform([(1.3, 6.1, 0.0, 2.8, 0.045, 0), (4.6, 8.2, -0.08, 1.0, 0.04, 0)])
    lifting(T, sp, 'tail', 'body', ctrl=(1.4, 4.6, 'elevator'), hinge=0.0, pivot=0.42, ctrl_dir='+x',
            axis='pitch', ctrl_max=20, cap_root=True)
    vt = Planform([(0.3, 4.0, 0.0, 3.1, 0.05, 0), (2.9, 6.3, 0.0, 1.15, 0.045, 0)])
    for side, s in (('L', 1), ('R', -1)):
        M = Mt(s * 1.45, 0, 0.32) @ Matrix.Rotation(s * math.radians(24), 4, 'Y')
        lifting(T, vt, 'tail', 'body', sides=(side,), vertical=True, ctrl=(0.5, 2.6, 'rudder'), hinge=0.72,
                axis='yaw', ctrl_max=25, M=M)
    bubble_canopy(T, st, -6.6, -6.0, -3.6, 0.48, 0.62, 'hinge', 32, hinge_y=-3.5)
    mb.cyl(0.04, 0.3, 8, MT, M=frame((-1.1, -3.3, 0.5), (0, -1, 0)), x0=0.0)
    T.muzzle(1, (-1.1, -3.62, 0.5), 0.9, 0.4)
    w = T.mb('wings', 'body', 'hull')
    for k, (x, y, z) in enumerate(((6.72, 1.0, -0.12), (-6.72, 1.0, -0.12), (3.7, -0.6, -0.62), (-3.7, -0.6, -0.62))):
        sb = f'store_{k + 1}'
        sm = T.mb(sb, sb, 'hull')
        missile(sm, (x, y - 1.6, z - 0.15 if k < 2 else z - 0.12))
        if k < 2:
            w.box((x, y, z), (0.08, 3.2, 0.12), MT)
        else:
            w.box((x, y, z + 0.28), (0.07, 1.8, 0.42), P, top=(1, 0.85))
        T.bone(sb, (x, y - 1.6, z - 0.15), (x, y - 2.1, z - 0.15), parent='body', coll='Sockets', shape='diamond',
               sxyz=(0.15,) * 3, color='THEME06')
        T.stores.append(sb)
    jet_gear(T, ((0, -6.0, -0.45), (0, -6.05, -1.55)),
             [((1.6, 0.6, -0.6), (1.75, 0.75, -1.5)), ((-1.6, 0.6, -0.6), (-1.75, 0.75, -1.5))],
             r_main=0.4, r_nose=0.3)
    T.afterburner('afterburner_L', (0.82, 8.75, 0.0), 3.6, 1.0)
    T.afterburner('afterburner_R', (-0.82, 8.75, 0.0), 3.6, 1.0)
    T.std_bones(18.0)
    finish_air_meta(T, 'modern_multirole')


def _ins(x, y, z, ax, r, depth, rings):
    return (x, y, z, ax, r, depth, rings)


GREY = srgb('#8d949a')
PLANES = {
    'Kestrel': (build_kestrel, 1.45, dict(
        top=srgb('#56583a'), top2=srgb('#4a4d33'), under=srgb('#d6cba6'), split=-0.35, dust=0.25, dust_h=0.3,
        mark=srgb('#6b4a2b'), rough=0.62, stops=[(0, srgb('#56583a')), (1, srgb('#56583a'))],
        height_fn=rib_height, rib=0.28, bump=0.35, wear=0.6, chips=0.25,
        insignia=[_ins(3.1, -0.97, 1.02, (0, 0, 1), 0.55, 0.15, [(0, RED), (0.36, WHITE), (0.68, BLUE)]),
                  _ins(-3.1, -0.97, 1.02, (0, 0, 1), 0.55, 0.15, [(0, RED), (0.36, WHITE), (0.68, BLUE)]),
                  _ins(3.0, -0.6, -0.27, (0, 0, 1), 0.5, 0.15, [(0, RED), (0.36, WHITE), (0.68, BLUE)]),
                  _ins(-3.0, -0.6, -0.27, (0, 0, 1), 0.5, 0.15, [(0, RED), (0.36, WHITE), (0.68, BLUE)]),
                  _ins(0, 1.6, 0.12, (1, 0, 0), 0.24, 0.5, [(0, RED), (0.36, WHITE), (0.68, BLUE)])],
        boxes=[((-0.1, 0.1, 2.85, 3.5, 0.2, 1.1, None), BLUE), ((-0.1, 0.1, 3.05, 3.5, 0.2, 1.1, None), WHITE),
               ((-0.1, 0.1, 3.25, 3.5, 0.2, 1.1, None), RED), ((-0.5, 0.5, -2.35, -1.95, -0.6, 0.6, None), RED)])),
    'Falcon': (build_falcon, 1.5, dict(
        top=srgb('#a9adb0'), under=srgb('#a9adb0'), metallic=0.55, rough=0.42, dust=0.2, dust_h=0.3,
        mark=srgb('#a2231d'), stops=[(0, srgb('#a9adb0')), (1, srgb('#a9adb0'))],
        height_fn=rib_height, rib=0.3, bump=0.25, wear=0.5, chips=0.2,
        insignia=[_ins(3.6, -0.81, 1.12, (0, 0, 1), 0.6, 0.15, [(0, BLUE), (0.3, WHITE), (0.55, BLUE)]),
                  _ins(-3.6, -0.81, 1.12, (0, 0, 1), 0.6, 0.15, [(0, BLUE), (0.3, WHITE), (0.55, BLUE)]),
                  _ins(3.4, -0.35, -0.33, (0, 0, 1), 0.52, 0.15, [(0, BLUE), (0.3, WHITE), (0.55, BLUE)]),
                  _ins(-3.4, -0.35, -0.33, (0, 0, 1), 0.52, 0.15, [(0, BLUE), (0.3, WHITE), (0.55, BLUE)]),
                  _ins(0, 2.2, 0.14, (1, 0, 0), 0.26, 0.5, [(0, BLUE), (0.3, WHITE), (0.55, BLUE)])],
        boxes=[((-5, 5, -1.8, 0.1, 0.9, 1.35, 0.25), YEL), ((-0.4, 0.4, 1.0, 1.3, -0.6, 0.8, None), RED),
               ((-0.2, 0.2, 3.5, 4.7, 0.25, 1.6, None), RED), ((-0.2, 0.2, 3.85, 4.05, 0.25, 1.6, None), WHITE),
               ((-0.2, 0.2, 4.2, 4.4, 0.25, 1.6, None), WHITE)])),
    'Lancer': (build_lancer, 1.45, dict(
        top=srgb('#b4b8bc'), under=srgb('#b4b8bc'), metallic=0.85, rough=0.3, dust=0.15, dust_h=0.2,
        mark=srgb('#b5231c'), stops=[(0, srgb('#9ea2a6')), (1, srgb('#9ea2a6'))], height_fn=panel_height,
        panel=0.9, bump=0.35, wear=0.4, chips=0.15,
        insignia=[_ins(4.3, -0.5, -0.12, (0, 0, 1), 0.48, 0.2, [(0, WHITE), (0.38, BLUE), (0.72, BLUE)]),
                  _ins(-4.3, -0.5, -0.12, (0, 0, 1), 0.48, 0.2, [(0, WHITE), (0.38, BLUE), (0.72, BLUE)]),
                  _ins(0, 2.0, 0.05, (1, 0, 0), 0.38, 0.8, [(0, WHITE), (0.38, BLUE), (0.72, BLUE)])],
        boxes=[((-0.6, 0.6, -4.3, -3.3, 0.3, 0.8, 0.3), srgb('#3c3f2c')),
               ((-0.1, 0.1, 4.0, 5.5, 1.2, 2.1, None), RED), ((-0.1, 0.1, 4.0, 5.5, 1.45, 1.6, None), WHITE)])),
    'Saber': (build_saber, 1.6, dict(
        pattern='blotch', scale=0.28, distort=0.7, under=srgb('#a7b0b4'), split=-0.3, dust=0.15, dust_h=0.2,
        stops=[(0, srgb('#6f7a5c')), (0.5, srgb('#8a8f92'))], mark=srgb('#202020'), rough=0.5,
        height_fn=panel_height, panel=1.0, bump=0.3, wear=0.5, chips=0.2,
        insignia=[_ins(4.2, 1.2, -0.05, (0, 0, 1), 0.5, 0.2, [(0, YEL), (0.4, BLK), (0.6, WHITE)]),
                  _ins(-4.2, 1.2, -0.05, (0, 0, 1), 0.5, 0.2, [(0, YEL), (0.4, BLK), (0.6, WHITE)]),
                  _ins(0, 1.8, 0.05, (1, 0, 0), 0.4, 0.8, [(0, YEL), (0.4, BLK), (0.6, WHITE)])],
        boxes=[((-0.2, 0.2, 3.3, 5.8, 1.0, 1.35, None), YEL), ((-0.7, 0.7, -5.3, -3.8, 0.25, 0.9, 0.3), BLK)])),
    'Wraith': (build_wraith, 1.95, dict(
        pattern='splinter', scale=0.18, under=srgb('#9aa2a8'), split=-0.25, dust=0.1, dust_h=0.2,
        stops=[(0, srgb('#6d757c')), (0.55, srgb('#7f878e')), (0.85, srgb('#5f676e'))], mark=srgb('#4a4f54'),
        rough=0.55, height_fn=panel_height, panel=1.2, bump=0.3, wear=0.3, chips=0.1,
        insignia=[_ins(5.0, 2.4, -0.08, (0, 0, 1), 0.5, 0.2, [(0, srgb('#4b5257')), (0.4, srgb('#b8bec2')), (0.62, srgb('#4b5257'))]),
                  _ins(-5.0, 2.4, -0.08, (0, 0, 1), 0.5, 0.2, [(0, srgb('#4b5257')), (0.4, srgb('#b8bec2')), (0.62, srgb('#4b5257'))]),
                  _ins(0, -4.6, 0.0, (1, 0, 0), 0.32, 0.95, [(0, srgb('#4b5257')), (0.4, srgb('#b8bec2')), (0.62, srgb('#4b5257'))])],
        boxes=[((-0.6, 0.6, -9.1, -7.3, -0.6, 0.6, None), srgb('#53595e'))])),
}
LINEUP = {'Kestrel': -30.0, 'Falcon': -18.0, 'Lancer': -4.0, 'Saber': 11.0, 'Wraith': 28.0}


def build_air_geometry(name):
    fn, gz, cfg = PLANES[name]
    T = Aircraft(name, (LINEUP[name], 0.0, gz), cfg)
    fn(T)
    T.finish_parts()
    return T


def tri_all(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ng, quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me)
    bm.free()
