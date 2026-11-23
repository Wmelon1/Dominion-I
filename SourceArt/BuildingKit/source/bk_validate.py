# Dominion I - BuildingKit gameplay checks on the collision meshes (run inside Blender after bk_geo + bk_buildings):
#  * every walk-through doorway is clear for the soldier capsule (radius 0.32 m, height 1.8 m)
#  * every stair route (cores, house stairs, fire escape, mezzanine) can be walked by a CharacterController with
#    stepOffset 0.4 and slopeLimit 50 deg, with 1.85 m headroom all the way
from mathutils.bvhtree import BVHTree

RADIUS, HEIGHT, STEP = 0.32, 1.8, 0.4


def tree_of(B):
    V = [v.copy() for v in B.gc.V]
    F = [list(f[0]) for f in B.gc.F]
    b = len(V)
    V += [Vector((-400, -400, 0)), Vector((400, -400, 0)), Vector((400, 400, 0)), Vector((-400, 400, 0))]   # the baseplate
    F.append([b, b + 1, b + 2, b + 3])
    return BVHTree.FromPolygons(V, F, all_triangles=False)


def check_doors(B, tree):
    bad = []
    for c, n, w, h, t in B.doors:
        n = Vector((n.x, n.y, 0)).normalized()
        e = n.cross(Z)
        if h < HEIGHT + 0.05 or w < 2 * RADIUS + 0.08:
            bad.append(('too small', tuple(round(x, 2) for x in c), round(w, 2), round(h, 2)))
            continue
        for lat in (-(w / 2 - RADIUS - 0.02), 0.0, w / 2 - RADIUS - 0.02):
            for hz in (0.35, 1.0, min(1.75, h - 0.05)):
                for s in (1, -1):
                    o = c + e * lat + Z * hz + n * s * 1.0
                    hit = tree.ray_cast(o, -n * s, 2.0)
                    if hit[0] is not None and hit[3] < 1.0 + t / 2 + 0.03:
                        bad.append(('blocked', tuple(round(x, 2) for x in c), round(lat, 2), hz, s))
    return bad


def walk(tree, route, step=0.1):
    """Follow a route over the collision mesh; returns (problems, heights visited)."""
    x, y = route[0]
    h = tree.ray_cast(Vector((x, y, 2.0)), -Z, 3.0)          # every route starts on the ground floor
    z = h[0].z if h[0] is not None else 0.0
    probs = []
    zs = [z]
    for (ax, ay), (bx, by) in zip(route[:-1], route[1:]):
        L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        n = max(1, int(L / step))
        for i in range(1, n + 1):
            px, py = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            h = tree.ray_cast(Vector((px, py, z + STEP + 0.05)), -Z, 3.0)
            if h[0] is None:
                probs.append(('no floor', round(px, 2), round(py, 2), round(z, 2)))
                continue
            nz = h[0].z
            if nz < z - 0.6:
                probs.append(('drop', round(px, 2), round(py, 2), round(z, 2), round(nz, 2)))
            z = nz
            up = tree.ray_cast(Vector((px, py, z + 0.05)), Z, 5.0)
            if up[0] is not None and up[3] < HEIGHT + 0.05 - 0.05:
                probs.append(('low headroom', round(px, 2), round(py, 2), round(z, 2), round(up[3] + 0.05, 2)))
            zs.append(z)
    return probs, zs


def validate(name, B):
    tree = tree_of(B)
    bad = check_doors(B, tree)
    out = {'doors': len(B.doors), 'door_problems': bad[:6], 'n_door_problems': len(bad), 'routes': []}
    for r in B.paths:
        probs, zs = walk(tree, r)
        out['routes'].append({'from_to_z': (round(zs[0], 2), round(zs[-1], 2)), 'problems': probs[:6], 'n': len(probs)})
    return out
