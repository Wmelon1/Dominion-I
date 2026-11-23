# Dominion I - BuildingKit: the buildings. Executed after bk_geo.py (same namespace).
# Conventions: metres, Z up, the front (main entrance) faces -Y (Unity +Z after FBX export), origin on the ground at the
# footprint centre. Floors marked "open" have real interiors you can walk into; the rest are sealed behind fake windows.

WIN_V0, WIN_V1 = 0.85, 2.15          # house window sill / head above the floor
DOOR_H = 2.1


def win(u0, u1, v0=WIN_V0, v1=WIN_V1, kind='open', **kw):
    return Op(u0, u1, v0, v1, kind, **kw)


def door(u0, u1, v0=0.0, v1=DOOR_H, **kw):
    kw.setdefault('frame', 'BLD_Trim')
    return Op(u0, u1, v0, v1, 'door', **kw)


# ============================================================================================== cottage
def build_cottage():
    """One-storey 9 x 7.5 m clapboard cottage: porch, living room + kitchen, bedroom, bathroom. Fully furnished."""
    B = B3(seed=101)
    x0, y0, x1, y1 = -4.5, -3.75, 4.5, 3.75
    t = 0.25
    zf, zc, ze = 0.25, 3.0, 3.05
    H = ze - zf
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    warm, blue, tile = 'BLD_InteriorWall_Warm', 'BLD_InteriorWall_Blue', 'BLD_FloorTile'
    # plinth (solid concrete band under the floor)
    rect_walls(B, x0, y0, x1, y1, 0.0, zf, t, mo='BLD_Concrete', mi=None)
    ops = {
        'front': [win(1.0, 2.1, style='cottage'), door(3.0, 4.0, leaf='BLD_TrimGreen', side=0),
                  win(6.7, 7.4, 1.3, 2.0, style='house')],
        'right': [win(4.75, 6.05, style='cottage')],
        'back': [win(2.5, 3.5, style='cottage'), win(5.7, 6.9, 1.1, 2.15, style='house'),
                 door(3.9, 4.7, leaf='BLD_Wood', side=1)],
        'left': [win(1.35, 2.45, style='cottage'), win(4.25, 5.55, style='cottage')],
    }
    per = {'front': dict(mi=[(5.24, warm), (99, tile)]), 'right': dict(mi=[(3.09, tile), (99, blue)]),
           'back': dict(mi=[(3.76, blue), (99, warm)]), 'left': dict(mi=warm)}
    rect_walls(B, x0, y0, x1, y1, zf, H, t, ops, mo='BLD_Siding_Blue', mr='BLD_Trim', style='house', per=per)
    gable_roof(B, x0, y0, x1, y1, ze, 35, 0.45, mroof='BLD_Shingle', mgable='BLD_Siding_Blue')
    # chimney through the back slope
    for g in (B.g0, B.g1):
        g.box(-3.0, 0.8, zc, -2.3, 1.5, 6.2, 'BLD_Brick', skip=('-z',))
        g.box(-3.08, 0.72, 6.2, -2.22, 1.58, 6.32, 'BLD_Stone')
    B.gc.box(-3.0, 0.8, zc, -2.3, 1.5, 6.2, 'COL')
    # ---- interior
    px = 0.8                                   # partition between the living room and bed/bath
    py = -0.6                                  # partition between bath (front) and bedroom
    room(B, ix0, iy0, px - 0.12, 1.6, zf, zc, 'BLD_WoodFloor', 'BLD_InteriorWall')
    room(B, ix0, 1.6, px - 0.12, iy1, zf, zc, tile, 'BLD_InteriorWall')
    room(B, px, py, ix1, iy1, zf, zc, 'BLD_WoodFloor', 'BLD_InteriorWall')
    room(B, px, iy0, ix1, py - 0.12, zf, zc, tile, 'BLD_InteriorWall')
    partition(B, (px, iy0), (px, py), zf, zc - zf, 0.12,
              [Op(0.9, 1.75, 0, DOOR_H, 'door', leaf='BLD_Trim', inward=False, side=0)], ml=warm, mr_=tile, caps=(False, False))
    partition(B, (px, py), (px, iy1), zf, zc - zf, 0.12,
              [Op(1.5, 2.4, 0, DOOR_H, 'door', leaf='BLD_Trim', inward=False, side=1)], ml=warm, mr_=blue, caps=(False, False))
    partition(B, (ix1, py), (px, py), zf, zc - zf, 0.12, (), ml=tile, mr_=blue, caps=(False, False))
    # living room
    sofa(B, -3.9, -1.3, -3.0, 0.9, zf, back='-x', mat='BLD_Fabric')
    table(B, -2.2, -0.2, zf, 1.0, 0.6, h=0.42)
    furn(B, 0.1, -1.4, zf, px - 0.14, -0.2, zf + 0.5, 'BLD_Wood')                      # TV unit
    furn(B, 0.2, -1.3, zf + 0.5, 0.26, -0.3, zf + 1.1, 'BLD_MetalDark', col=False)       # TV
    # kitchen: counter along the back wall, fridge, dining table
    counter(B, ix0 + 0.02, iy1 - 0.62, -1.0, iy1 - 0.02, zf)
    furn(B, -0.95, iy1 - 0.7, zf, -0.3, iy1 - 0.02, zf + 1.9, 'BLD_Galvanized')       # fridge
    table(B, -1.2, 0.6, zf, 1.4, 0.85)
    for cx, cy, r in ((-1.6, 0.05, 0), (-0.8, 0.05, 0), (-1.6, 1.15, math.pi), (-0.8, 1.15, math.pi)):
        chair(B, cx, cy, zf, r)
    # bedroom
    bed(B, 2.2, 1.45, 3.8, iy1 - 0.02, zf, head='+y')
    furn(B, ix1 - 0.62, -0.4, zf, ix1 - 0.02, 0.8, zf + 2.0, 'BLD_Wood')             # wardrobe
    furn(B, 1.5, 2.9, zf, 2.0, iy1 - 0.02, zf + 0.5, 'BLD_Wood')                     # nightstand
    # bathroom
    furn(B, ix1 - 0.75, iy0 + 0.02, zf, ix1 - 0.02, iy0 + 1.72, zf + 0.55, 'BLD_Trim')  # tub
    furn(B, 1.0, -1.35, zf, 1.4, -0.9, zf + 0.42, 'BLD_Trim')                         # toilet
    counter(B, 1.9, -1.32, 2.9, -0.75, zf, h=0.85, body='BLD_Wood', top='BLD_Stone')
    # porch: deck, steps, posts, shed roof
    for g in (B.g0, B.g1):
        g.box(-2.6, -5.6, 0.0, 0.2, y0, 0.22, 'BLD_Wood', skip=('-z', '+y'))
        g.box(-1.55, -5.95, 0.0, -0.45, -5.6, 0.11, 'BLD_Concrete', skip=('-z', '+y'))
    B.gc.box(-2.6, -5.6, 0.0, 0.2, y0, 0.22, 'COL')
    B.gc.box(-1.55, -5.95, 0.0, -0.45, -5.6, 0.11, 'COL')
    for px_ in (-2.5, 0.0):
        B.g0.box(px_, -5.5, 0.22, px_ + 0.12, -5.38, 2.4, 'BLD_Trim', skip=('-z',))
        B.g1.box(px_, -5.5, 0.22, px_ + 0.12, -5.38, 2.4, 'BLD_Trim', skip=('-z',))
        B.gc.box(px_, -5.5, 0.22, px_ + 0.12, -5.38, 2.4, 'COL')
    railing(B, [(-2.44, -3.8), (-2.44, -5.44), (-1.6, -5.44)], 0.22, h=0.9, mat='BLD_Trim', post=0.6)
    railing(B, [(-0.4, -5.44), (0.06, -5.44), (0.06, -3.8)], 0.22, h=0.9, mat='BLD_Trim', post=0.6)
    shed_roof(B, -2.75, -5.75, 0.35, y0, 2.62, 2.4, mroof='BLD_Shingle')
    # back step
    for g in (B.g0, B.g1):
        g.box(-0.35, y1, 0.0, 0.75, y1 + 0.45, 0.13, 'BLD_Concrete', skip=('-z', '-y'))
    B.gc.box(-0.35, y1, 0.0, 0.75, y1 + 0.45, 0.13, 'COL')
    return B, dict(name='Building_Cottage', footprint=[9.0, 7.5], height=6.3, storeys=1,
                   open='whole ground floor (living room, kitchen, bedroom, bathroom)')


# ============================================================================================== house
def build_house():
    """Two-storey 11 x 8.5 m family house (brick ground floor, clapboard upper floor, hip roof) with an attached garage.
    Open: the whole ground floor (living room, hall with stairs, kitchen), the upstairs landing and the front bedroom,
    and the garage. Sealed: master bedroom and bathroom upstairs (closed doors, curtained windows)."""
    B = B3(seed=202)
    x0, y0, x1, y1 = -5.5, -4.25, 5.5, 4.25
    t = 0.25
    zf0, zf1, ze = 0.3, 3.3, 6.3
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    warm, white, green, blue = 'BLD_InteriorWall_Warm', 'BLD_InteriorWall', 'BLD_InteriorWall_Green', 'BLD_InteriorWall_Blue'
    rect_walls(B, x0, y0, x1, y1, 0.0, zf0, t, mo='BLD_ConcreteDark', mi=None)
    g_ops = {
        'front': [win(1.0, 3.0, style='brick'), door(5.0, 6.0, leaf='BLD_TrimRed', side=0), win(7.9, 9.7, style='brick')],
        'right': [win(6.95, 8.05, style='brick')],
        'back': [win(1.0, 2.5, 1.0, 2.15, style='brick'), door(3.1, 3.9, leaf='BLD_Wood', side=1),
                 win(7.5, 9.5, style='brick')],
        'left': [win(3.25, 4.85, style='brick')],
    }
    per = {'front': dict(mi=[(4.04, warm), (6.84, white), (99, green)]), 'right': dict(mi=green),
           'back': dict(mi=[(4.13, green), (6.96, white), (99, warm)]), 'left': dict(mi=warm)}
    rect_walls(B, x0, y0, x1, y1, zf0, zf1 - zf0, t, g_ops, mo='BLD_Brick', mr='BLD_Brick', style='brick', per=per)
    u_ops = {
        'front': [win(1.2, 2.6, style='house'), win(5.0, 6.0, 0.9, 2.1, style='house'), win(7.9, 9.3, kind='blind', style='house')],
        'right': [win(3.2, 4.6, kind='blind', style='house'), win(5.8, 7.2, kind='blind', style='house')],
        'back': [win(1.2, 2.6, kind='blind', style='house'), win(5.1, 6.3, style='house'),
                 win(8.5, 9.3, 1.3, 2.1, kind='blind', style='house')],
        'left': [win(1.25, 2.05, 1.3, 2.1, kind='blind', style='house'), win(5.75, 7.15, style='house')],
    }
    per = {'front': dict(mi=[(4.04, blue), (6.84, white), (99, None)]), 'right': dict(mi=None),
           'back': dict(mi=[(4.13, None), (6.96, white), (99, None)]), 'left': dict(mi=[(4.31, None), (99, blue)])}
    rect_walls(B, x0, y0, x1, y1, zf1, ze - zf1, t, u_ops, mo='BLD_Siding_White', mr='BLD_Trim', style='house', per=per)
    band(B, x0, y0, x1, y1, zf1 - 0.05, zf1 + 0.15, 'BLD_Trim', out=0.04)
    hip_roof(B, x0, y0, x1, y1, ze, 28, 0.5, mroof='BLD_Shingle')
    # ---- ground floor
    hole = (0.3, -1.8, 1.28, 2.36)
    zc0 = zf1 - 0.3
    room(B, ix0, iy0, -1.52, iy1, zf0, zc0, 'BLD_WoodFloor', white)
    hslab(B.g0, -1.4, iy0, 1.28, iy1, zf0, 'BLD_WoodFloor', True)
    hslab(B.g0, -1.4, iy0, 1.28, iy1, zc0, white, False, [hole])
    col_slab(B.gc, -1.4, iy0, 1.28, iy1, zf0 - 0.3, zf0)
    room(B, 1.4, iy0, ix1, iy1, zf0, zc0, 'BLD_FloorTile', white)
    partition(B, (-1.4, iy0), (-1.4, iy1), zf0, zc0 - zf0, 0.12, [Op(1.4, 3.0, 0, 2.3, 'door')], ml=warm, mr_=white,
              caps=(False, False))
    partition(B, (1.4, iy0), (1.4, iy1), zf0, zc0 - zf0, 0.12, [Op(0.5, 1.5, 0, DOOR_H, 'door'), Op(6.6, 7.6, 0, DOOR_H, 'door')],
              ml=white, mr_=green, caps=(False, False))
    # stairs up to the landing, with the slab edge around the stair hole and railings
    flight(B, 0.3, 1.28, -1.8, 2.36, zf0, zf1, mt='BLD_Wood', ms='BLD_Trim', mso=white, sides=(True, False))
    sloped_rail(B, 0.34, -1.8, zf0, 2.36, zf1, h=0.95, mat='BLD_Wood')
    B.g0.poly([(0.3, -1.8, zc0), (0.3, 2.36, zc0), (0.3, 2.36, zf1), (0.3, -1.8, zf1)], white, normal=(1, 0, 0))
    B.g0.poly([(0.3, -1.8, zc0), (1.28, -1.8, zc0), (1.28, -1.8, zf1), (0.3, -1.8, zf1)], white, normal=(0, 1, 0))
    # living room
    sofa(B, ix0 + 0.02, -1.0, -4.3, 1.4, zf0, back='-x', mat='BLD_Fabric')
    sofa(B, -3.6, 2.6, -2.4, 3.4, zf0, back='+y', mat='BLD_Fabric_Red')
    table(B, -3.4, 0.2, zf0, 1.0, 0.6, h=0.42)
    furn(B, -2.05, -0.2, zf0, -1.56, 1.2, zf0 + 0.5, 'BLD_Wood')
    furn(B, -1.8, -0.1, zf0 + 0.5, -1.74, 1.1, zf0 + 1.15, 'BLD_MetalDark', col=False)
    shelf(B, ix0 + 0.02, 2.0, ix0 + 0.4, 3.8, zf0, 2.0, goods=['BLD_Fabric_Red', 'BLD_Fabric', 'BLD_Trim', 'BLD_Fabric_Beige'])
    # kitchen
    counter(B, ix1 - 0.6, -3.3, ix1 - 0.02, 2.5, zf0)
    counter(B, 3.0, iy1 - 0.6, ix1 - 0.6, iy1 - 0.02, zf0)
    furn(B, ix1 - 0.7, iy0 + 0.02, zf0, ix1 - 0.02, -3.32, zf0 + 1.9, 'BLD_Galvanized')
    table(B, 2.9, -0.5, zf0, 1.6, 0.9)
    for cx, cy, r in ((2.5, -1.1, 0), (3.3, -1.1, 0), (2.5, 0.1, math.pi), (3.3, 0.1, math.pi)):
        chair(B, cx, cy, zf0, r)
    furn(B, -1.36, -3.2, zf0, -1.0, -2.4, zf0 + 0.9, 'BLD_Wood')                       # hall cabinet
    # ---- upper floor: landing + front bedroom open
    zc1 = ze - 0.05
    hslab(B.g0, -1.4, iy0, 1.28, iy1, zf1, 'BLD_WoodFloor', True, [hole])
    hslab(B.g0, -1.4, iy0, 1.28, iy1, zc1, white, False)
    col_slab(B.gc, -1.4, iy0, 1.28, iy1, zf1 - 0.3, zf1, [hole])
    room(B, ix0, iy0, -1.52, -0.12, zf1, zc1, 'BLD_Carpet', white)
    W3 = partition(B, (-1.4, iy0), (-1.4, iy1), zf1, zc1 - zf1, 0.12,
                   [Op(2.4, 3.3, 0, DOOR_H, 'door', leaf='BLD_Trim', inward=True, side=0)], ml=blue, mr_=white, caps=(False, False))
    door_on(B, W3, 5.2, 6.0, 'r')
    partition(B, (-1.52, 0.0), (ix0, 0.0), zf1, zc1 - zf1, 0.12, (), ml=blue, mr_=white, caps=(False, False))
    W5 = partition(B, (1.4, iy0), (1.4, iy1), zf1, zc1 - zf1, 0.12, (), ml=white, mr_=white, caps=(False, False))
    door_on(B, W5, 6.8, 7.7, 'l')
    railing(B, [(0.3, 2.36), (0.3, -1.8), (1.28, -1.8)], zf1, h=1.0, mat='BLD_Wood', post=1.0)
    bed(B, -4.4, -2.2, -2.8, -0.14, zf1, head='+y')
    furn(B, ix0 + 0.02, iy0 + 0.02, zf1, ix0 + 0.62, -3.2, zf1 + 2.1, 'BLD_Wood')
    desk(B, -2.3, -3.58, zf1, math.pi, w=1.2, d=0.7)
    # entrance canopy and steps
    shed_roof(B, -1.3, -5.45, 1.3, y0, 3.05, 2.85, mroof='BLD_Shingle')
    for g in (B.g0, B.g1):
        g.box(-1.0, -5.0, 0.0, 1.0, y0, 0.15, 'BLD_Concrete', skip=('-z', '+y'))
        g.box(1.4, y1, 0.0, 2.6, y1 + 0.65, 0.15, 'BLD_Concrete', skip=('-z', '-y'))
    B.gc.box(-1.0, -5.0, 0.0, 1.0, y0, 0.15, 'COL')
    B.gc.box(1.4, y1, 0.0, 2.6, y1 + 0.65, 0.15, 'COL')
    # ---- garage (open, roller door up)
    gx0, gy0, gx1, gy1 = x1, y0, 9.5, 2.25
    gh = 3.2
    plaster = 'BLD_Plaster_White'
    wall(B, (gx0, gy0), (gx1, gy0), 0.0, gh, t, [Op(0.6, 3.4, 0.0, 2.5, 'hole', reveal='BLD_Brick')], mo='BLD_Brick',
         mi=plaster, inner=(0.0, t))
    wall(B, (gx1, gy0), (gx1, gy1), 0.0, gh, t, [win(2.5, 3.7, 1.2, 2.0, style='industrial')], mo='BLD_Brick', mi=plaster)
    wall(B, (gx1, gy1), (gx0, gy1), 0.0, gh, t, (), mo='BLD_Brick', mi=plaster, inner=(t, 0.0))
    room(B, gx0, gy0 + t, gx1 - t, gy1 - t, 0.05, 3.0, 'BLD_Concrete', plaster)
    flat_roof(B, gx0, gy0, gx1, gy1, gh, t, 0.35, 'BLD_Brick', mpar='BLD_Brick')
    B.g0.box(6.1, gy0 + t, 2.5, 8.9, gy0 + t + 0.45, 2.95, 'BLD_Galvanized')           # rolled-up door
    counter(B, 6.2, gy1 - t - 0.7, 8.8, gy1 - t - 0.02, 0.05, h=0.95, body='BLD_Wood', top='BLD_Wood')
    shelf(B, gx1 - t - 0.5, -2.8, gx1 - t - 0.02, -0.6, 0.05, 2.0, mat='BLD_Galvanized',
          goods=['BLD_Fabric_Red', 'BLD_Galvanized', 'BLD_Wood'])
    B.paths.append([(0.8, -3.2), (0.8, -2.0), (0.8, 2.9), (-0.6, 3.2), (-0.6, -2.5)])
    return B, dict(name='Building_House', footprint=[15.0, 8.5], height=9.2, storeys=2,
                   open='ground floor (living room, hall, kitchen), stairs, upstairs landing + front bedroom, garage')


# ============================================================================================== shop
def build_shop():
    """Three-storey 12 x 10 m brick corner shop. Open: the shop floor (shelving, counter, fridges), its stock room and
    a steel fire escape at the back that climbs all the way to the flat roof. Sealed: two floors of flats above."""
    B = B3(seed=303)
    x0, y0, x1, y1 = -6.0, -5.0, 6.0, 5.0
    t = 0.3
    zf, z1, z2, zr = 0.15, 4.0, 7.0, 10.0
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    green = 'BLD_InteriorWall_Green'
    rect_walls(B, x0, y0, x1, y1, 0.0, zf, t, mo='BLD_Stone', mi=None)
    H0 = z1 - zf
    g_ops = {
        'front': [Op(0.6, 4.4, 0.45, 3.2, 'store', style='store', sillmat='BLD_Stone'),
                  Op(4.8, 6.4, 0.0, 2.7, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=0),
                  Op(6.8, 8.6, 0.45, 3.2, 'store', style='store', sillmat='BLD_Stone'),
                  Op(9.6, 10.6, 0.0, 2.4, 'panel', mat='BLD_TrimGreen', frame='BLD_Stone', depth=0.08)],
        'left': [Op(5.2, 9.2, 0.45, 3.2, 'store', style='store', sillmat='BLD_Stone'), win(0.8, 2.0, 1.4, 2.6, style='brick')],
        'right': [win(2.0, 3.2, 1.2, 2.8, kind='blind', style='brick'), win(8.0, 9.2, 1.4, 2.6, style='brick')],
        'back': [door(8.2, 9.2, leaf='BLD_MetalDark', side=1, frame='BLD_MetalDark'), win(6.5, 7.7, 1.4, 2.6, style='brick')],
    }
    per = {'front': dict(mi=[(8.94, green), (99, None)]), 'left': dict(mi=green),
           'right': dict(mi=[(7.56, None), (99, green)]), 'back': dict(mi=green)}
    rect_walls(B, x0, y0, x1, y1, zf, H0, t, g_ops, mo='BLD_Brick', style='brick', per=per)
    # flats above (sealed)
    for zb in (z1, z2):
        ops = {
            'front': [win(c - 0.6, c + 0.6, 0.8, 2.4, kind='blind') for c in (1.8, 4.6, 7.4, 10.2)],
            'left': [win(c - 0.6, c + 0.6, 0.8, 2.4, kind='blind') for c in (2.0, 5.0, 8.0)],
            'right': [win(c - 0.6, c + 0.6, 0.8, 2.4, kind='blind') for c in (2.0, 5.0, 8.0)],
            'back': [win(c - 0.6, c + 0.6, 0.8, 2.4, kind='blind') for c in (1.8, 4.6, 7.4, 10.2)],
        }
        rect_walls(B, x0, y0, x1, y1, zb, 3.0, t, ops, mo='BLD_Brick', style='brick')
    band(B, x0, y0, x1, y1, z1 - 0.05, z1 + 0.18, 'BLD_Stone', out=0.06)
    band(B, x0, y0, x1, y1, zr + 0.7, zr + 0.95, 'BLD_Stone', out=0.2)
    flat_roof(B, x0, y0, x1, y1, zr, t, 1.0, 'BLD_Brick', mpar='BLD_Brick', gap_back=(-1.0, 0.2))
    # ---- shop interior
    zc = z1 - 0.25
    room(B, ix0, iy0, 2.88, 2.38, zf, zc, 'BLD_FloorTile', 'BLD_CeilingTile')
    room(B, ix0, 2.5, ix1, iy1, zf, zc, 'BLD_Concrete', 'BLD_Plaster_White')
    partition(B, (ix1, 2.5), (ix0, 2.5), zf, zc - zf, 0.12,
              [Op(6.7, 7.7, 0, DOOR_H, 'door', leaf='BLD_Wood', inward=False, side=1)], ml=green, mr_=green, caps=(False, False))
    partition(B, (3.0, iy0), (3.0, 2.38), zf, zc - zf, 0.12, (), ml=green, mr_=green, caps=(False, False))
    goods = ['BLD_Fabric_Red', 'BLD_Fabric', 'BLD_Trim', 'BLD_Fabric_Beige', 'BLD_TrimGreen', 'BLD_Galvanized', 'BLD_TrimRed']
    counter(B, 1.0, -3.6, 2.6, -3.0, zf, h=1.0, body='BLD_Wood', top='BLD_Stone')
    furn(B, 1.5, -3.5, zf + 1.0, 1.9, -3.2, zf + 1.3, 'BLD_MetalDark', col=False)       # till
    for yy in (-1.6, 0.3):
        shelf(B, -4.6, yy, -1.2, yy + 0.6, zf, 1.7, goods=goods)
    shelf(B, -5.5, 1.82, -2.25, 2.36, zf, 2.2, goods=goods)
    shelf(B, -0.75, 1.82, 0.4, 2.36, zf, 2.2, goods=goods)
    for i in range(3):
        furn(B, 2.2, -1.9 + i * 1.25, zf, 2.86, -0.7 + i * 1.25, zf + 2.0, 'BLD_Galvanized')   # drinks fridges
    rng = random.Random(7)
    for cx, cy in ((-5.0, 3.6), (3.6, 3.7), (4.9, 3.4)):
        crates(B, cx, cy, zf, rng)
    shelf(B, -1.5, 4.1, 2.5, 4.68, zf, 2.2, mat='BLD_Galvanized', goods=['BLD_Wood', 'BLD_Fabric_Beige'])
    # awnings over the front windows
    for ax0, ax1 in ((-5.55, -1.45), (0.65, 2.75)):
        shed_roof(B, ax0, -6.3, ax1, y0, 3.95, 3.35, mroof='BLD_Fabric_Red', mfascia='BLD_Fabric_Red',
                  msoffit='BLD_Fabric_Red', rt=0.04)
    # ---- fire escape (back): ground -> 4.0 -> 7.0 -> roof 10.0
    m = 'BLD_MetalDark'
    fe = dict(mt=m, ms=m, mso=m, thick=0.12)
    flight_x(B, 5.1, 6.2, 5.6, 0.1, 0.0, z1, **fe)
    flight_x(B, 5.1, 6.2, -1.1, -5.1, z1, z2, **fe)
    flight_x(B, 6.2, 7.3, -5.1, -1.1, z2, zr, **fe)
    for lx0, ly0, lx1, ly1, lz in ((-1.15, 5.1, 0.15, 6.2, z1), (-5.9, 5.1, -5.05, 7.3, z2), (-1.15, y1, 0.3, 7.3, zr)):
        for g in (B.g0, B.g1):
            g.box(lx0, ly0, lz - 0.1, lx1, ly1, lz, m)
        B.gc.box(lx0, ly0, lz - 0.1, lx1, ly1, lz, 'COL')
    sloped_rail_x(B, 6.2, 5.6, 0.0, 0.1, z1)
    sloped_rail_x(B, 6.2, -1.1, z1, -5.1, z2)
    sloped_rail_x(B, 7.3, -5.1, z2, -1.1, zr)
    railing(B, [(-1.1, 6.2), (0.1, 6.2)], z1)
    railing(B, [(-5.1, 7.3), (-5.9, 7.3), (-5.9, 5.1)], z2)
    railing(B, [(-1.1, y1), (-1.1, 6.2)], zr)
    railing(B, [(-1.1, 7.3), (0.3, 7.3), (0.3, y1)], zr)
    for px, py, ph in ((0.05, 6.15, z1), (-5.85, 7.25, z2), (0.25, 7.25, zr), (-1.05, 7.25, zr), (5.55, 6.15, 0.6)):
        for g in (B.g0, B.g1):
            g.box(px - 0.05, py - 0.05, 0.0, px + 0.05, py + 0.05, ph, m, skip=('-z',))
    # ---- roof
    hvac(B, -3.5, -2.0, zr)
    hvac(B, 3.6, -2.4, zr, w=1.8, d=1.2, h=1.1, rot=math.pi / 2)
    water_tank(B, 3.4, 2.0, zr, r=1.2, h=2.2, legs=1.6)
    for g in (B.g0, B.g1):
        g.box(-4.2, 2.2, zr, -3.2, 3.2, zr + 0.7, 'BLD_Galvanized', skip=('-z',))     # roof hatch
    B.gc.box(-4.2, 2.2, zr, -3.2, 3.2, zr + 0.7, 'COL')
    antenna(B, -5.2, -4.2, zr, h=5.0)
    B.paths.append([(5.9, 5.6), (5.2, 5.65), (-0.5, 5.65), (-1.5, 5.65), (-5.5, 5.65), (-5.5, 6.75), (-4.8, 6.75),
                    (-0.6, 6.75), (-0.4, 5.6), (-0.4, 4.0)])
    return B, dict(name='Building_Shop', footprint=[12.0, 12.3], height=11.1, storeys=3,
                   open='shop floor + stock room, fire escape to the roof, roof')


# ============================================================================================== apartment block
def build_apartment():
    """Six-storey 24 x 14 m concrete apartment block with balconies. Open: the entrance lobby, the stair core from the
    lobby to the roof (closed doors on the sealed floors), the 3rd-floor corridor and one furnished flat with its
    balcony, and the roof. Sealed: every other flat."""
    B = B3(seed=404)
    x0, y0, x1, y1 = -12.0, -7.0, 12.0, 7.0
    t = 0.3
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    lv = [0.15, 3.75, 6.75, 9.75, 12.75, 15.75]
    zr = 18.75
    OPEN = 2
    warm, white, blue, tile = 'BLD_InteriorWall_Warm', 'BLD_Plaster_White', 'BLD_InteriorWall_Blue', 'BLD_FloorTile'
    rect_walls(B, x0, y0, x1, y1, 0.0, lv[0], t, mo='BLD_ConcreteDark', mi=None)
    core = stair_core(B, -1.35, 0.0, 1.35, lv + [zr], {0, OPEN}, wall_mat='BLD_Concrete', inner_mat=white,
                      floor_mat='BLD_Concrete', t=0.2, outer_mat=white)
    A = 'apartment'
    for k, z in enumerate(lv):
        H = (lv[k + 1] if k + 1 < len(lv) else zr) - z
        op = k == OPEN
        if k == 0:
            front = [win(a, a + 1.4, 1.0, 2.6, kind='blind', style=A) for a in (1.0, 3.4, 5.8, 16.8, 19.2, 21.6)]
            front += [Op(8.4, 10.2, 0.9, 2.9, 'open', style='modern'), Op(13.8, 15.6, 0.9, 2.9, 'open', style='modern'),
                      Op(10.8, 12.0, 0.0, 2.5, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=0),
                      Op(12.0, 13.2, 0.0, 2.5, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=1)]
        else:
            lk = 'open' if op else 'blind'
            front = [win(a, b, 0.9, 2.3, kind=lk, style=A) for a, b in ((0.6, 1.6), (3.6, 5.0), (6.8, 8.2), (8.8, 9.8), (11.4, 12.6))]
            front += [win(a, b, 0.9, 2.3, kind='blind', style=A) for a, b in ((14.2, 15.2), (15.8, 17.2), (19.0, 20.4), (22.4, 23.4))]
            front.append(Op(2.4, 3.3, 0.0, 2.3, 'door', frame='BLD_Trim', leaf='BLD_Glass', side=0) if op else
                         win(2.4, 3.3, 0.0, 2.3, kind='blind', style='adoor'))
            front.append(win(20.7, 21.6, 0.0, 2.3, kind='blind', style='adoor'))
        v0, v1 = (1.0, 2.6) if k == 0 else (0.9, 2.3)
        left = [win(c - 0.7, c + 0.7, v0, v1, kind='open' if op else 'blind', style=A) for c in (2.4, 5.5, 8.8, 12.0)]
        right = [win(c - 0.7, c + 0.7, v0, v1, kind='blind', style=A) for c in (2.0, 5.2, 8.5, 11.6)]
        back = []
        for c in (2.2, 5.2, 8.4, 15.6, 18.8, 21.8):
            kind = 'open' if (op and c > 13) else 'blind'
            if c == 15.6 and k >= 1:
                back.append(win(c - 0.6, c + 0.6, 1.3, 2.3, kind=kind, style=A))
            else:
                back.append(win(c - 0.7, c + 0.7, v0, v1, kind=kind, style=A))
        if k == 0:
            per = {'front': dict(mi=[(7.94, None), (16.06, white), (99, None)]),
                   'back': dict(mi=[(7.94, None), (16.06, white), (99, None)])}
        elif op:
            per = {'front': dict(mi=[(10.34, warm), (13.66, white), (99, None)]), 'left': dict(mi=[(6.56, blue), (99, warm)]),
                   'back': dict(mi=[(13.66, None), (17.76, tile), (99, blue)])}
        else:
            per = {}
        rect_walls(B, x0, y0, x1, y1, z, H, t, {'front': front, 'left': left, 'right': right, 'back': back},
                   mo='BLD_ConcreteDark' if k == 0 else 'BLD_Concrete', mr='BLD_Concrete', style=A, per=per)
        if k >= 1:
            band(B, x0, y0, x1, y1, z - 0.08, z + 0.08, 'BLD_ConcreteDark', out=0.03)
            for bx0, bx1 in ((-10.0, -6.6), (6.6, 10.0)):
                for g in (B.g0, B.g1):
                    g.box(bx0, -8.4, z - 0.22, bx1, y0, z, 'BLD_Concrete', skip=('+y',))
                    g.box(bx0, -8.4, z, bx1, -8.28, z + 1.05, 'BLD_Plaster_Terracotta')
                    g.box(bx0, -8.28, z, bx0 + 0.12, y0, z + 1.05, 'BLD_Plaster_Terracotta', skip=('+y',))
                    g.box(bx1 - 0.12, -8.28, z, bx1, y0, z + 1.05, 'BLD_Plaster_Terracotta', skip=('+y',))
                B.gc.box(bx0, -8.4, z - 0.22, bx1, y0, z, 'COL')
                B.gc.box(bx0, -8.4, z, bx1, -8.28, z + 1.05, 'COL')
                B.gc.box(bx0, -8.28, z, bx0 + 0.12, y0, z + 1.05, 'COL')
                B.gc.box(bx1 - 0.12, -8.28, z, bx1, y0, z + 1.05, 'COL')
    # ---- lobby
    zc0 = lv[1] - 0.3
    room(B, -4.0, iy0, 4.0, iy1, lv[0], zc0, 'BLD_FloorTile', white, holes=[core])
    Wl = partition(B, (-4.0, iy0), (-4.0, iy1), lv[0], zc0 - lv[0], 0.12, (), ml=white, mr_=white, caps=(False, False))
    door_on(B, Wl, 3.2, 4.1, 'r')
    Wr = partition(B, (4.0, iy1), (4.0, iy0), lv[0], zc0 - lv[0], 0.12, (), ml=white, mr_=white, caps=(False, False))
    door_on(B, Wr, 9.3, 10.2, 'r')
    furn(B, -4.0, -1.6, lv[0] + 1.0, -3.78, 0.4, lv[0] + 2.0, 'BLD_Galvanized', col=False)      # mailboxes
    furn(B, 2.6, -4.0, lv[0], 3.9, -3.4, lv[0] + 0.45, 'BLD_Wood')
    planter(B, -3.8, -6.6, -3.0, -5.8, lv[0])
    planter(B, 3.0, -6.6, 3.8, -5.8, lv[0])
    # entrance canopy
    for g in (B.g0, B.g1):
        g.box(-2.4, -8.6, 2.9, 2.4, y0, 3.1, 'BLD_Concrete', skip=('+y',))
        for px in (-2.25, 2.15):
            g.box(px, -8.5, 0.0, px + 0.1, -8.4, 2.9, 'BLD_MetalDark', skip=('-z', '+z'))
    B.gc.box(-2.4, -8.6, 2.9, 2.4, y0, 3.1, 'COL')
    # ---- the open floor: corridor + one flat
    z = lv[OPEN]
    zc = lv[OPEN + 1] - 0.3
    Hc = zc - z
    room(B, -1.6, iy0, 1.6, -0.2, z, zc, 'BLD_FloorTile', white)
    room(B, ix0, iy0, -1.6, -0.2, z, zc, 'BLD_WoodFloor', white)
    room(B, ix0, -0.2, -1.55, 0.44, z, zc, 'BLD_WoodFloor', white)
    room(B, ix0, 0.44, -5.76, iy1, z, zc, 'BLD_Carpet', white)
    room(B, -5.76, 0.44, -1.55, 5.8, z, zc, tile, white)
    room(B, -5.76, 5.8, -1.6, iy1, z, zc, tile, white)
    partition(B, (-1.6, iy0), (-1.6, -0.2), z, Hc, 0.12,
              [Op(3.3, 4.3, 0, DOOR_H, 'door', leaf='BLD_Wood', inward=True, side=0)], ml=warm, mr_=white, caps=(False, False))
    WR = partition(B, (1.6, -0.2), (1.6, iy0), z, Hc, 0.12, (), ml=white, mr_=white, caps=(False, False))
    door_on(B, WR, 2.2, 3.2, 'r')
    partition(B, (-1.6, 5.8), (-1.6, iy1), z, Hc, 0.12, (), ml=tile, mr_=white, caps=(False, False))
    partition(B, (-1.55, 0.5), (-5.82, 0.5), z, Hc, 0.12,
              [Op(0.95, 1.85, 0, DOOR_H, 'door', leaf='BLD_Trim', inward=False, side=0)], ml=warm, mr_=tile, caps=(False, False))
    partition(B, (-5.82, 0.5), (ix0, 0.5), z, Hc, 0.12,
              [Op(0.28, 1.08, 0, DOOR_H, 'door', leaf='BLD_Trim', inward=False, side=0)], ml=warm, mr_=blue, caps=(False, False))
    partition(B, (-5.82, iy1), (-5.82, 0.5), z, Hc, 0.12, (), ml=tile, mr_=blue, caps=(False, False))
    sofa(B, ix0 + 0.02, -4.2, -10.8, -2.6, z, back='-x')
    table(B, -10.0, -3.4, z, 1.0, 0.6, h=0.42)
    furn(B, -8.3, -4.0, z, -7.8, -2.8, z + 0.5, 'BLD_Wood')
    furn(B, -8.1, -3.9, z + 0.5, -8.04, -2.9, z + 1.1, 'BLD_MetalDark', col=False)
    table(B, -4.6, -3.0, z, 1.6, 0.9)
    for cx, cy, r in ((-5.0, -3.6, 0), (-4.2, -3.6, 0), (-5.0, -2.4, math.pi), (-4.2, -2.4, math.pi)):
        chair(B, cx, cy, z, r)
    counter(B, -5.6, -0.22, -3.6, 0.36, z)
    furn(B, -6.4, -0.3, z, -5.7, 0.36, z + 1.9, 'BLD_Galvanized')
    bed(B, -9.6, 0.52, -8.0, 2.6, z, head='-y')
    furn(B, -8.95, iy1 - 0.6, z, -7.65, iy1 - 0.02, z + 2.0, 'BLD_Wood')
    furn(B, -5.68, 1.0, z, -4.98, 2.7, z + 0.55, 'BLD_Trim')
    furn(B, -2.4, 4.9, z, -2.0, 5.35, z + 0.42, 'BLD_Trim')
    counter(B, -3.8, iy1 - 0.55, -2.9, iy1 - 0.02, z, h=0.85, body='BLD_Wood')
    # ---- roof
    flat_roof(B, x0, y0, x1, y1, zr, t, 1.1, 'BLD_Concrete', mpar='BLD_Concrete', holes=[core])
    hvac(B, -7.5, 2.5, zr)
    hvac(B, 7.5, 2.5, zr)
    hvac(B, 7.5, -3.5, zr, w=1.6, d=1.2, h=1.0)
    water_tank(B, -7.0, -3.0, zr, r=1.4, h=2.4, legs=1.8)
    antenna(B, 10.5, 5.5, zr, h=7.0)
    antenna(B, -10.5, 5.6, zr, h=5.0)
    return B, dict(name='Building_Apartment', footprint=[24.0, 15.6], height=22.0, storeys=6,
                   open='lobby, stair core lobby->roof, 3rd-floor corridor + one flat with balcony, roof')


# ============================================================================================== office tower
def build_office():
    """Ten-storey 30 x 22 m office tower: concrete spandrels, ribbon glazing and steel fins. Open: the double-height
    glass lobby (reception, columns, seating), the stair core all the way to the roof, the 2nd-floor open-plan office
    (48 desks), and the roof. Sealed: floors 3-10 (curtain-glass ribbons with office interiors)."""
    B = B3(seed=505)
    x0, y0, x1, y1 = -15.0, -11.0, 15.0, 11.0
    t = 0.35
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    lv = [0.15, 5.15] + [5.15 + 3.6 * i for i in range(1, 9)]
    zr = 37.55
    OPEN = 1
    white = 'BLD_Plaster_White'
    rect_walls(B, x0, y0, x1, y1, 0.0, lv[0], t, mo='BLD_ConcreteDark', mi=None)
    core = stair_core(B, -1.35, 3.0, 1.35, lv + [zr], {0, OPEN}, wall_mat='BLD_Concrete', inner_mat=white,
                      outer_mat='BLD_Stone', run_len=3.5)
    # service blocks either side of the stairs (lifts left, washrooms right), up through the roof
    top = zr + 3.5
    for bx0, bx1 in ((-6.5, core[0]), (core[2], 6.5)):
        B.g0.box(bx0, core[1], lv[0], bx1, core[3], zr, 'BLD_Stone', skip=('-z', '+z'))
        B.g0.box(bx0, core[1], zr, bx1, core[3], top, 'BLD_Concrete', skip=('-z',))
        B.g1.box(bx0, core[1], zr, bx1, core[3], top, 'BLD_Concrete', skip=('-z',))
        B.gc.box(bx0, core[1], lv[0], bx1, core[3], top, 'COL')
    for zl in (lv[0], lv[OPEN]):
        for ex in (-5.6, -3.6):
            B.g0.box(ex - 0.1, core[1] - 0.05, zl, ex + 1.3, core[1], zl + 2.4, 'BLD_MetalDark')
            B.g0.box(ex, core[1] - 0.07, zl, ex + 1.2, core[1] - 0.05, zl + 2.3, 'BLD_Galvanized')
        for dx in (2.6, 4.6):
            B.g0.box(dx - 0.07, core[1] - 0.05, zl, dx + 0.97, core[1], zl + 2.17, 'BLD_Trim')
            B.g0.box(dx, core[1] - 0.07, zl, dx + 0.9, core[1] - 0.05, zl + 2.1, 'BLD_Wood')
    side_off = {'front': 0.0, 'right': 0.37, 'back': 0.61, 'left': 0.13}
    for k, z in enumerate(lv):
        H = (lv[k + 1] if k + 1 < len(lv) else zr) - z
        if k == 0:
            ops = {'front': [Op(1.5, 13.0, 0.3, 4.6, 'store', style='store', sillmat='BLD_Stone'),
                             Op(13.4, 15.0, 0.0, 2.8, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=0),
                             Op(15.0, 16.6, 0.0, 2.8, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=1),
                             Op(17.0, 28.5, 0.3, 4.6, 'store', style='store', sillmat='BLD_Stone')],
                   'left': [Op(1.5, 20.5, 0.3, 4.6, 'store', style='store', sillmat='BLD_Stone')],
                   'right': [Op(1.5, 20.5, 0.3, 4.6, 'store', style='store', sillmat='BLD_Stone')],
                   'back': [door(3.0, 4.0, 0.0, 2.2, leaf='BLD_MetalDark', frame='BLD_MetalDark', side=1)] +
                           [Op(a, a + 2.4, 1.2, 3.6, 'open', style='modern') for a in (7.0, 20.6, 25.0)]}
            rect_walls(B, x0, y0, x1, y1, z, H, t, ops, mo='BLD_Stone', mi=white, mr='BLD_Stone', style='store')
            continue
        kind = 'open' if k == OPEN else 'cblind'
        ops = {}
        for side, L in (('front', 30.0), ('right', 22.0), ('back', 30.0), ('left', 22.0)):
            ops[side] = [Op(1.2, L - 1.2, 1.0, 3.3, kind, style='ribbon', row=k % 4, uoff=side_off[side])]
        per = {} if k != OPEN else {s: dict(mi=white) for s in ('front', 'right', 'back', 'left')}
        rect_walls(B, x0, y0, x1, y1, z, H, t, ops, mo='BLD_Concrete', mr='BLD_ConcreteDark', style='ribbon', per=per)
    # vertical steel fins over the upper facade
    for side, a, b in rect_sides(x0, y0, x1, y1):
        W = WF(a, b, 0.0, t)
        n = int(W.L / 3.0)
        for i in range(1, n):
            for g in (B.g0, B.g1):
                W.box(g, 3.0 * i - 0.07, 3.0 * i + 0.07, lv[1], zr + 1.28, -0.4, 0.0, 'BLD_MetalDark', skip=('+y',))
    # ---- lobby + open-plan floor
    cols = [(-9.0, -4.6), (-3.0, -4.6), (3.0, -4.6), (9.0, -4.6), (-9.0, 3.5), (9.0, 3.5), (-12.5, 8.0), (12.5, 8.0)]
    zc0 = lv[1] - 0.3
    room(B, ix0, iy0, ix1, iy1, lv[0], zc0, 'BLD_FloorTile', 'BLD_CeilingTile', holes=[core])
    for cx, cy in cols:
        column(B, cx, cy, lv[0], zc0)
    counter(B, -2.5, -7.2, 2.5, -6.4, lv[0], h=1.1, body='BLD_Wood', top='BLD_Stone')
    sofa(B, -12.0, -9.6, -9.6, -8.8, lv[0], back='-y', mat='BLD_Fabric')
    sofa(B, 9.6, -9.6, 12.0, -8.8, lv[0], back='-y', mat='BLD_Fabric')
    table(B, -10.8, -7.6, lv[0], 1.2, 0.7, h=0.42)
    table(B, 10.8, -7.6, lv[0], 1.2, 0.7, h=0.42)
    for gx in (-6.0, -4.8, -3.6, 3.6, 4.8, 6.0):
        furn(B, gx - 0.1, -2.6, lv[0], gx + 0.1, -1.6, lv[0] + 1.0, 'BLD_MetalDark')        # security gates
    for px, py in ((-13.5, -9.5), (13.5, -9.5), (-13.5, 9.5), (13.5, 9.5)):
        planter(B, px - 0.6, py - 0.6, px + 0.6, py + 0.6, lv[0])
    z = lv[OPEN]
    zc = lv[OPEN + 1] - 0.3
    room(B, ix0, iy0, ix1, iy1, z, zc, 'BLD_Carpet', 'BLD_CeilingTile', holes=[core])
    for cx, cy in cols:
        column(B, cx, cy, z, zc)
    for cx in (-12.0, -6.0, 0.0, 6.0, 12.0):
        for cy in (-7.6, -1.6):
            for dx in (-0.8, 0.8):
                desk(B, cx + dx, cy - 0.4, z, 0.0)
                desk(B, cx + dx, cy + 0.4, z, math.pi)
    for fx in (-13.5, -11.0, 11.0, 13.5):
        furn(B, fx - 0.6, iy1 - 0.65, z, fx + 0.6, iy1 - 0.02, z + 1.3, 'BLD_MetalDark')       # filing cabinets
    furn(B, -10.0, 5.0, z, -8.6, 5.9, z + 1.1, 'BLD_Trim')                                     # printer bench
    # ---- roof
    flat_roof(B, x0, y0, x1, y1, zr, t, 1.2, 'BLD_Concrete', mpar='BLD_Concrete', holes=[core])
    hvac(B, -10.0, -5.0, zr, w=3.0, d=1.8, h=1.6)
    hvac(B, 10.0, -5.0, zr, w=3.0, d=1.8, h=1.6)
    hvac(B, 10.0, 0.5, zr)
    for g in (B.g0, B.g1):                                                                     # cooling tower
        g.box(-12.0, 0.0, zr, -8.0, 3.0, zr + 2.6, 'BLD_Galvanized', skip=('-z',))
        g.cyl(-11.0, 1.5, zr + 2.6, zr + 3.3, 0.85, 12, 'BLD_MetalDark')
        g.cyl(-9.0, 1.5, zr + 2.6, zr + 3.3, 0.85, 12, 'BLD_MetalDark')
    B.gc.box(-12.0, 0.0, zr, -8.0, 3.0, zr + 3.3, 'COL')
    antenna(B, 4.0, 7.0, top, h=12.0, r=0.1)
    for g in (B.g0, B.g1):                                                                     # entrance canopy
        g.box(-3.0, -13.2, 3.4, 3.0, y0, 3.6, 'BLD_MetalDark', skip=('+y',))
    B.gc.box(-3.0, -13.2, 3.4, 3.0, y0, 3.6, 'COL')
    return B, dict(name='Building_Office', footprint=[30.0, 24.2], height=53.0, storeys=10,
                   open='lobby, stair core lobby->roof, 2nd-floor open-plan office, roof')


# ============================================================================================== skyscraper
def build_skyscraper():
    """150 m glass skyscraper (spire to 185 m) on a 42 x 42 m stone podium. Open: the 6 m lobby (lift core, reception,
    columns, security gates), a stair core up to the podium roof terrace (planters, benches) and the terrace.
    Sealed: the podium's 2nd floor and the 35-storey tower (curtain wall with fake office interiors)."""
    B = B3(seed=606)
    x0, y0, x1, y1 = -21.0, -21.0, 21.0, 21.0
    t = 0.4
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    lv = [0.15, 6.15]
    zp = 10.65
    white = 'BLD_InteriorWall'
    rect_walls(B, x0, y0, x1, y1, 0.0, lv[0], t, mo='BLD_ConcreteDark', mi=None)
    core = stair_core(B, 16.0, -17.6, 18.7, lv + [zp], {0}, wall_mat='BLD_Stone', inner_mat='BLD_Plaster_White',
                      outer_mat='BLD_Stone', run_len=4.0)
    ops = {'front': [Op(1.5, 18.5, 0.3, 5.4, 'store', style='store', sillmat='BLD_Stone'),
                     Op(19.0, 21.0, 0.0, 3.0, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=0),
                     Op(21.0, 23.0, 0.0, 3.0, 'door', frame='BLD_MetalDark', leaf='BLD_Glass', side=1),
                     Op(23.5, 40.5, 0.3, 5.4, 'store', style='store', sillmat='BLD_Stone')],
           'left': [Op(2.0, 40.0, 0.3, 5.4, 'store', style='store', sillmat='BLD_Stone')],
           'right': [Op(2.0, 40.0, 0.3, 5.4, 'store', style='store', sillmat='BLD_Stone')],
           'back': [door(5.0, 6.2, 0.0, 2.4, leaf='BLD_MetalDark', frame='BLD_MetalDark', side=1),
                    door(35.8, 37.0, 0.0, 2.4, leaf='BLD_MetalDark', frame='BLD_MetalDark', side=0)] +
                   [Op(a, a + 3.0, 1.5, 4.5, 'open', style='modern') for a in (10.0, 16.0, 23.0, 29.0)]}
    rect_walls(B, x0, y0, x1, y1, lv[0], lv[1] - lv[0], t, ops, mo='BLD_Stone', mi=white, mr='BLD_Stone', style='store')
    ops = {s: [Op(1.0, 41.0, 0.9, 3.9, 'cblind', row=1, uoff=o)] for s, o in
           (('front', 0.0), ('right', 0.3), ('back', 0.55), ('left', 0.8))}
    rect_walls(B, x0, y0, x1, y1, lv[1], zp - lv[1], t, ops, mo='BLD_Stone', mr='BLD_ConcreteDark')
    band(B, x0, y0, x1, y1, lv[1] - 0.1, lv[1] + 0.25, 'BLD_Stone', out=0.12)
    # ---- lobby
    zc0 = lv[1] - 0.3
    room(B, ix0, iy0, ix1, iy1, lv[0], zc0, 'BLD_FloorTile', white, holes=[core])
    lift = (-7.0, -1.0, 7.0, 11.0)
    furn(B, lift[0], lift[1], lv[0], lift[2], lift[3], zc0, 'BLD_Stone', skip=('-z', '+z'))
    for ex in (-5.1, -2.1, 0.9, 3.9):
        for yy, s in ((lift[1], -1), (lift[3], 1)):
            B.g0.box(ex - 0.1, yy - 0.05 if s < 0 else yy, lv[0], ex + 1.3, yy if s < 0 else yy + 0.05, lv[0] + 2.7, 'BLD_MetalDark')
            B.g0.box(ex, yy - 0.07 if s < 0 else yy + 0.05, lv[0], ex + 1.2, yy - 0.05 if s < 0 else yy + 0.07, lv[0] + 2.6,
                     'BLD_Galvanized')
    for cx in (-17.0, -9.0, 9.0, 17.0):
        for cy in (-15.0, -5.0, 5.0, 15.0):
            if (cx, cy) != (17.0, -15.0):
                column(B, cx, cy, lv[0], zc0, w=0.9, mat='BLD_Stone', round_=True)
    counter(B, -4.0, -8.3, 4.0, -7.5, lv[0], h=1.1, body='BLD_Wood', top='BLD_Stone')
    for gx in (-6.0, -4.8, -3.6, 3.6, 4.8, 6.0):
        furn(B, gx - 0.1, -4.6, lv[0], gx + 0.1, -3.6, lv[0] + 1.0, 'BLD_MetalDark')
    for sx in (-15.5, 12.5):
        sofa(B, sx, -18.8, sx + 3.0, -18.0, lv[0], back='-y', mat='BLD_Fabric_Beige')
        table(B, sx + 1.5, -16.8, lv[0], 1.4, 0.7, h=0.42)
    for px, py in ((-19.5, -19.5), (-19.5, 19.5), (19.5, 19.5), (-12.0, -19.5), (8.0, -19.5)):
        planter(B, px - 0.6, py - 0.6, px + 0.6, py + 0.6, lv[0])
    for g in (B.g0, B.g1):                                                                     # entrance canopy
        g.box(-5.0, -24.0, 4.2, 5.0, y0, 4.45, 'BLD_MetalDark', skip=('+y',))
    B.gc.box(-5.0, -24.0, 4.2, 5.0, y0, 4.45, 'COL')
    # ---- tower: two curtain-wall tiers and a crown
    tiers = [((-15.0, -11.0, 15.0, 19.0), zp, zp + 25 * 3.6), ((-12.0, -8.0, 12.0, 16.0), zp + 25 * 3.6, zp + 35 * 3.6)]
    flat_roof(B, x0, y0, x1, y1, zp, t, 1.1, 'BLD_Stone', mroof='BLD_FloorTile', mpar='BLD_Stone',
              holes=[tiers[0][0], core])
    for ti, ((a0, b0, a1, b1), zb, ze) in enumerate(tiers):
        par = 1.3
        for si, (side, a, b) in enumerate(rect_sides(a0, b0, a1, b1)):
            W = curtain(B, a, b, zb, ze + par, zp, uoff=0.27 * si + 0.5 * ti)
            n = int(round(W.L / 3.0))
            for i in range(1, n):
                W.box(B.g0, W.L * i / n - 0.06, W.L * i / n + 0.06, zb, ze + par, -0.45, 0.0, 'BLD_MetalDark', skip=('+y',))
            for f in range(1, int(round((ze - zb) / 3.6))):
                zz = zb + f * 3.6
                W.box(B.g0, 0.0, W.L, zz - 0.04, zz + 0.06, -0.16, 0.0, 'BLD_MetalDark', skip=('+y',))
            # parapet backing seen from the setback roof
            W.rect(B.g0, 0.0, W.L, ze, ze + par, 0.12, 'BLD_Concrete', -W.n)
        for cx, cy in ((a0, b0), (a1, b0), (a1, b1), (a0, b1)):
            for g in (B.g0, B.g1):
                g.box(cx - 0.45, cy - 0.45, zb, cx + 0.45, cy + 0.45, ze + par + 0.1, 'BLD_MetalDark', skip=('-z',))
        for g in (B.g0, B.g1):
            g.box(a0 - 0.05, b0 - 0.05, ze + par, a1 + 0.05, b0 + 0.12, ze + par + 0.1, 'BLD_MetalDark')
            g.box(a0 - 0.05, b1 - 0.12, ze + par, a1 + 0.05, b1 + 0.05, ze + par + 0.1, 'BLD_MetalDark')
            g.box(a0 - 0.05, b0 + 0.12, ze + par, a0 + 0.12, b1 - 0.12, ze + par + 0.1, 'BLD_MetalDark')
            g.box(a1 - 0.12, b0 + 0.12, ze + par, a1 + 0.05, b1 - 0.12, ze + par + 0.1, 'BLD_MetalDark')
        nxt = tiers[ti + 1][0] if ti + 1 < len(tiers) else (-8.0, -4.0, 8.0, 12.0)
        for g in (B.g0, B.g1):
            hslab(g, a0 + 0.12, b0 + 0.12, a1 - 0.12, b1 - 0.12, ze, 'BLD_Gravel', True, [nxt])
        B.gc.box(a0, b0, zb, a1, b1, ze + par, 'COL')
    # crown + spire
    zc = tiers[-1][2]
    cr = (-8.0, -4.0, 8.0, 12.0)
    for side, a, b in rect_sides(*cr):
        W = WF(a, b, zc, 0.3)
        for g in (B.g0, B.g1):
            W.rect(g, 0.0, W.L, 0.0, 14.0, 0.0, 'BLD_Corrugated', W.n)
        n = int(W.L / 2.0)
        for i in range(1, n):
            W.box(B.g0, W.L * i / n - 0.1, W.L * i / n + 0.1, 0.0, 14.0, -0.3, 0.0, 'BLD_MetalDark', skip=('+y',))
    for g in (B.g0, B.g1):
        g.box(cr[0] - 0.3, cr[1] - 0.3, zc + 14.0, cr[2] + 0.3, cr[3] + 0.3, zc + 14.5, 'BLD_MetalDark', skip=())
        g.box(-2.0, 2.0, zc + 14.5, 2.0, 6.0, zc + 17.0, 'BLD_MetalDark', skip=('-z',))
        g.cyl(0.0, 4.0, zc + 17.0, zc + 48.0, 0.9, 10, 'BLD_Galvanized', top=False, r1=0.12)
        g.box(-0.25, 3.75, zc + 48.0, 0.25, 4.25, zc + 48.6, 'BLD_TrimRed', skip=('-z',))
    B.gc.box(cr[0], cr[1], zc, cr[2], cr[3], zc + 14.5, 'COL')
    B.gc.box(-0.9, 3.1, zc + 14.5, 0.9, 4.9, zc + 48.0, 'COL')
    # ---- podium roof terrace
    for px in (-18.0, -12.0, -6.0, 6.0, 12.0):
        planter(B, px - 1.4, -19.6, px + 1.4, -18.6, zp, h=0.6)
    for bx in (-14.0, -3.0, 8.0):
        furn(B, bx - 1.0, -15.0, zp, bx + 1.0, -14.5, zp + 0.45, 'BLD_Wood')
    for px, py in ((-19.0, -6.0), (-19.0, 6.0), (19.0, 6.0)):
        planter(B, px - 0.8, py - 2.0, px + 0.8, py + 2.0, zp, h=0.6)
    hvac(B, 18.5, 15.0, zp, w=3.0, d=1.8, h=1.6, rot=math.pi / 2)
    hvac(B, -18.5, 15.0, zp, w=3.0, d=1.8, h=1.6, rot=math.pi / 2)
    return B, dict(name='Building_Skyscraper', footprint=[42.0, 45.0], height=185.0, storeys=37,
                   open='lobby, stair core lobby->podium roof, podium roof terrace')


# ============================================================================================== warehouse
def build_warehouse():
    """30 x 20 m steel-framed warehouse, open to the roof: three drive-through roller-door openings (tanks fit), pallet
    racks, a shipping container, crates, and an office with a mezzanine deck up a steel stair. Everything is open."""
    B = B3(seed=707)
    x0, y0, x1, y1 = -15.0, -10.0, 15.0, 10.0
    t = 0.25
    ze, zf = 8.0, 0.05
    ix0, iy0, ix1, iy1 = x0 + t, y0 + t, x1 - t, y1 - t
    clad = ('v', [(1.2, 'BLD_Concrete'), (99, 'BLD_Corrugated')])
    hi = [6.0, 7.4]
    ops = {
        'front': [Op(4.0, 9.5, 0.0, 5.5, 'hole', reveal='BLD_ConcreteDark', floor=True),
                  Op(20.5, 26.0, 0.0, 5.5, 'hole', reveal='BLD_ConcreteDark', floor=True),
                  door(13.5, 14.5, 0.0, 2.2, leaf='BLD_MetalDark', frame='BLD_MetalDark', side=0)] +
                 [win(a, a + 2.4, hi[0], hi[1], style='industrial') for a in (0.8, 10.5, 16.5, 27.0)],
        'back': [win(a, a + 2.4, hi[0], hi[1], style='industrial') for a in (1.5, 7.5, 13.5, 19.5, 25.5)],
        'left': [win(a, a + 2.4, hi[0], hi[1], style='industrial') for a in (2.0, 8.8, 15.6)],
        'right': [Op(7.0, 13.0, 0.0, 5.5, 'hole', reveal='BLD_ConcreteDark', floor=True),
                  win(1.5, 3.9, hi[0], hi[1], style='industrial'), win(16.1, 18.5, hi[0], hi[1], style='industrial')],
    }
    rect_walls(B, x0, y0, x1, y1, 0.0, ze, t, ops, mo=clad, mi=clad, mr='BLD_ConcreteDark', style='industrial')
    gable_roof(B, x0, y0, x1, y1, ze, 12, 0.4, mroof='BLD_Corrugated_Red', mgable='BLD_Corrugated', mfascia='BLD_Galvanized',
               msoffit='BLD_Galvanized', rt=0.2, axis='x', gable_t=t, gable_inner='BLD_Corrugated', solid=False)
    hslab(B.g0, ix0, iy0, ix1, iy1, zf, 'BLD_Concrete', True)
    col_slab(B.gc, ix0, iy0, ix1, iy1, -0.2, zf)
    # rolled-up roller doors
    for (rx0, rx1) in ((-11.0, -5.5), (5.5, 11.0)):
        B.g0.box(rx0, iy0, 5.5, rx1, iy0 + 0.55, 6.1, 'BLD_Galvanized')
    B.g0.box(ix1 - 0.55, -3.0, 5.5, ix1, 3.0, 6.1, 'BLD_Galvanized')
    # steel portal frames: columns, rafters, tie beams
    tp = math.tan(math.radians(12))
    zr = ze + (y1 - y0) / 2 * tp
    for fx in (-9.0, -3.0, 3.0, 9.0):
        for yy, s in ((iy0, 1), (iy1, -1)):
            column(B, fx, yy + s * 0.2, zf, ze, w=0.4, mat='BLD_MetalDark')
            a = Vector((fx - 0.12, yy, ze + (abs(yy - (y0 if s > 0 else y1))) * tp - 0.5))
            B.g0.obox(a, Vector((0.24, 0, 0)), Vector((0, (0 - yy), (zr - (ze + abs(yy - (y0 if s > 0 else y1)) * tp)))),
                      Vector((0, 0, 0.45)), 'BLD_MetalDark')
        B.g0.box(fx - 0.1, iy0, ze - 0.6, fx + 0.1, iy1, ze - 0.4, 'BLD_MetalDark')
    # racks, container, crates
    rk = ['BLD_Wood', 'BLD_Fabric_Beige', 'BLD_TrimRed', 'BLD_Corrugated']
    shelf(B, -12.5, iy1 - 1.8, -2.5, iy1 - 0.1, zf, 5.0, mat='BLD_Galvanized', shelves=3, goods=rk)
    shelf(B, -12.5, 3.2, -2.5, 4.8, zf, 5.0, mat='BLD_Galvanized', shelves=3, goods=rk)
    furn(B, ix0 + 0.25, -8.0, zf, ix0 + 2.69, -1.9, zf + 2.6, 'BLD_Corrugated_Red')
    rng = random.Random(77)
    for cx, cy in ((-1.0, -6.0), (1.2, -2.0), (-2.5, 0.5), (3.5, -6.8), (-13.0, 1.0), (12.0, -7.5)):
        crates(B, cx, cy, zf, rng, count=3)
    for cx, cy in ((-8.5, -1.0), (8.0, -2.5)):
        furn(B, cx - 0.6, cy - 0.5, zf, cx + 0.6, cy + 0.5, zf + 0.15, 'BLD_Wood')                 # pallets
        crates(B, cx, cy, zf + 0.15, rng, count=2, size=(0.8, 1.0))
    # office with a mezzanine deck on top, reached by a steel stair
    zd = 3.5
    wall(B, (6.0, 4.0), (ix1, 4.0), zf, zd - 0.25 - zf, 0.15,
         [door(1.0, 2.0, leaf='BLD_Wood', frame='BLD_MetalDark', side=0), win(3.0, 5.0, 0.9, 2.1, style='modern'),
          win(5.6, 7.6, 0.9, 2.1, style='modern')], mo='BLD_Plaster_White', mi='BLD_InteriorWall', inner=(0.15, 0.0), lod1=False)
    wall(B, (6.0, iy1), (6.0, 4.0), zf, zd - 0.25 - zf, 0.15, [win(1.5, 3.5, 0.9, 2.1, style='modern')],
         mo='BLD_Plaster_White', mi='BLD_InteriorWall', inner=(0.0, 0.15), lod1=False)
    hslab(B.g0, 6.15, 4.15, ix1, iy1, zf + 0.04, 'BLD_Carpet', True)
    hslab(B.g0, 6.15, 4.15, ix1, iy1, zd - 0.25, 'BLD_CeilingTile', False)
    B.g0.box(5.9, 3.9, zd - 0.25, ix1, iy1, zd, 'BLD_Concrete', skip=('-z',))
    B.gc.box(5.9, 3.9, zd - 0.25, ix1, iy1, zd, 'COL')
    desk(B, 10.5, 8.6, zf + 0.04, 0.0)
    desk(B, 12.8, 8.6, zf + 0.04, 0.0)
    for fx in (7.0, 7.7):
        furn(B, fx, iy1 - 0.65, zf, fx + 0.6, iy1 - 0.02, zf + 1.3, 'BLD_MetalDark')
    m = 'BLD_MetalDark'
    flight_x(B, 2.8, 3.9, 0.6, 5.8, zf, zd, mt=m, ms=m, mso=m, thick=0.15)
    B.g0.box(5.8, 2.8, zd - 0.2, 7.2, 3.9, zd, m)
    B.gc.box(5.8, 2.8, zd - 0.2, 7.2, 3.9, zd, 'COL')
    sloped_rail_x(B, 2.82, 0.6, zf, 5.8, zd)
    railing(B, [(5.8, 2.8), (7.2, 2.8), (7.2, 3.9), (ix1, 3.9)], zd)
    railing(B, [(5.92, 3.9), (5.92, iy1)], zd)
    crates(B, 9.5, 6.5, zd, rng, count=2)
    crates(B, 13.0, 5.5, zd, rng, count=1)
    B.paths.append([(0.0, 3.35), (0.7, 3.35), (5.9, 3.35), (6.6, 3.35), (6.6, 4.6), (10.0, 4.6)])
    return B, dict(name='Building_Warehouse', footprint=[30.8, 20.8], height=11.4, storeys=1,
                   open='everything: hall, office, mezzanine deck')


BUILDINGS = {
    'Building_Cottage': build_cottage,
    'Building_House': build_house,
    'Building_Shop': build_shop,
    'Building_Apartment': build_apartment,
    'Building_Office': build_office,
    'Building_Skyscraper': build_skyscraper,
    'Building_Warehouse': build_warehouse,
}
