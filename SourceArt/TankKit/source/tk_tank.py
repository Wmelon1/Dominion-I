# Tank Kit builder - Tank assembly: parts, running gear, tracks, rig, drivers, clips, bake, export.
# Requires tk_core.py to be exec'd first in the same namespace.


class Tank:
    def __init__(self, name, origin, paint_cfg):
        self.name = name
        self.origin = Vector(origin)
        self.cfg = paint_cfg
        self.coll = get_coll(f'Tank_{name}', get_coll('TankKit'))
        self.mbs = {}
        self.objs = []          # (object, bone, bake_group)
        self.bones = []
        self.wheel_drv = []     # (bone, side, effective radius)
        self.guns = []          # (barrel bone, flash bone, recoil, shot frames)
        self.flashes = []       # (flash bone, muzzle pos, fwd, length, width)
        self.tracks = {}
        self.meta = {}
        self.mats = {k: master_material(f'MM_{name}_{k}', k, paint_cfg) for k in SLOTS}
        self.mat_list = [self.mats[k] for k in SLOTS]
        self.temp_meshes = []

    # ------------------------------------------------------------------ parts
    def mb(self, key, bone, group):
        if key not in self.mbs:
            self.mbs[key] = (MB(), bone, group)
        return self.mbs[key][0]

    def instance(self, mesh, key, bone, loc, rz=0.0, group='hull'):
        ob = bpy.data.objects.new(f'{self.name}_{key}', mesh)
        self.coll.objects.link(ob)
        ob.location = self.origin + Vector(loc)
        ob.rotation_euler = (0.0, 0.0, rz)
        self.objs.append((ob, bone, group))
        return ob

    def finish_parts(self):
        for key, (mb, bone, group) in self.mbs.items():
            if len(mb.bm.faces) == 0:
                mb.bm.free()
                continue
            ob = mb.finish(f'{self.name}_{key}', self.mat_list, self.coll)
            ob.location = self.origin
            self.objs.append((ob, bone, group))
        self.mbs = {}

    def bone(self, name, head, tail, parent=None, z=(0, 0, 1), deform=True, coll='Controls',
             shape=None, sxyz=(1, 1, 1), color=None, locks=None):
        self.bones.append(dict(name=name, head=Vector(head), tail=Vector(tail), parent=parent, z=Vector(z),
                               deform=deform, coll=coll, shape=shape, sxyz=sxyz, color=color, locks=locks))

    # ------------------------------------------------------------------ running gear
    def running_gear(self, rg):
        sol = solve_running_gear(rg)
        self.sol, self.rg = sol, rg
        tx, tw = rg['tx'], rg['tw']
        hw = rg.get('horn_w', 0.06)
        ww, gap = tw * 0.82, hw + 0.04
        ml = self.mat_list
        road_me = road_wheel_mesh(f'{self.name}_RoadWheel', sol['road'][0]['r'], ww, gap, sol['road'][0]['segs'], ml)
        self.temp_meshes.append(road_me)
        ends = []
        for e in (sol['front'], sol['rear']):
            if e['kind'] == 'sprocket':
                me = sprocket_mesh(f'{self.name}_Sprocket', e['rp'], tw, e['Z'], ml)
            else:
                me = road_wheel_mesh(f'{self.name}_Idler', e['r'], ww * 0.95, gap, e['segs'], ml, steel=True)
            self.temp_meshes.append(me)
            ends.append((e, me))
        roller_me = None
        if sol['rollers']:
            r0 = sol['rollers'][0]
            roller_me = roller_mesh(f'{self.name}_Roller', r0['r'], tw * 0.62, gap, r0['segs'], ml)
            self.temp_meshes.append(roller_me)
        for side, sx in (('L', tx), ('R', -tx)):
            rz = 0.0 if side == 'L' else math.pi
            for i, w in enumerate(sol['road']):
                self._wheel(road_me, f'wheel_{side}_{i + 1}', side, sx, w, rz)
            for e, me in ends:
                self._wheel(me, f"{e['kind']}_{side}", side, sx, e, rz)
            for i, w in enumerate(sol['rollers']):
                self._wheel(roller_me, f'roller_{side}_{i + 1}', side, sx, w, rz)
        # static suspension parts (on the root bone so they stay put if the hull rocks)
        mb = self.mb('suspension', 'root', 'hull')
        wi = self.H['wi']
        for side, s in (('L', 1), ('R', -1)):
            inner = s * (tx - ww / 2 + 0.01)
            for w in sol['road']:
                a = Vector((s * (wi - 0.02), w['y'] + 0.34, w['z'] + 0.12))
                b = Vector((inner, w['y'], w['z']))
                beam(mb, a, b, 0.09, 0.11, P)
                mb.cyl(0.07, abs(b.x - a.x) + 0.04, 8, MT, M=frame(((a.x + b.x) / 2, w['y'], w['z']), (1, 0, 0)))
                mb.box((s * (wi + 0.03), w['y'] + 0.34, w['z'] + 0.22), (0.1, 0.16, 0.14), P)
            for e in (sol['front'], sol['rear']):
                if e['kind'] == 'sprocket':
                    mb.lathe([(0, s * (wi - 0.02)), (0.24, s * (wi - 0.02)), (0.22, inner + s * 0.0),
                              (0, inner)], 16, P, M=Mt(0, e['y'], e['z']) @ frame((0, 0, 0), (1, 0, 0)))
                else:
                    a = Vector((s * (wi - 0.02), e['y'] - math.copysign(0.3, e['y']), e['z'] + 0.05))
                    b = Vector((inner, e['y'], e['z']))
                    beam(mb, a, b, 0.1, 0.12, P)
                    mb.cyl(0.075, abs(b.x - a.x), 8, MT, M=frame(((a.x + b.x) / 2, e['y'], e['z']), (1, 0, 0)))
            for w in sol['rollers']:
                mb.cyl(0.05, abs(inner - s * wi) + 0.02, 8, MT,
                       M=frame(((inner + s * wi) / 2, w['y'], w['z']), (1, 0, 0)))

    def _wheel(self, me, bn, side, sx, w, rz):
        self.instance(me, bn, bn, (sx, w['y'], w['z']), rz, 'hull')
        r = w['r'] + 0.06
        self.bone(bn, (sx, w['y'], w['z']), (sx + 0.25, w['y'], w['z']), parent='root', coll='Wheels',
                  shape='circle', sxyz=(r, r, r), color='THEME07',
                  locks=dict(loc=(True, True, True), rot=(True, False, True), scale=(True, True, True)))
        self.wheel_drv.append((bn, side, w['reff']))

    def build_tracks(self, track_mat):
        rg, sol = self.rg, self.sol
        tpl = link_template(sol['p'], rg['tp'], rg['g'], rg['tw'], rg.get('horn_w', 0.06), rg.get('horn_h', 0.065))
        N, links = sol['N'], sol['links']
        for side, sx in (('L', rg['tx']), ('R', -rg['tx'])):
            def place(i, sx=sx):
                (py, pz), (ty, tz), (ny, nz) = links[i % N]
                return [(sx - x, py + u * ty + w * ny, pz + u * tz + w * nz) for (x, u, w) in tpl['verts']]
            me = mesh_from_template(f'{self.name}_Track_{side}', tpl, [track_mat], place, N)
            ob = bpy.data.objects.new(f'{self.name}_Track_{side}', me)
            self.coll.objects.link(ob)
            ob.location = self.origin
            ob.shape_key_add(name='Basis', from_mix=False)
            kb = ob.shape_key_add(name='track_cycle', from_mix=False)
            nxt = [c for i in range(N) for v in place(i + 1) for c in v]
            kb.data.foreach_set('co', nxt)
            kb.slider_min, kb.slider_max = 0.0, 1.0
            ob.data.shape_keys.use_relative = True
            self.tracks[side] = ob

    def build_flash(self, mat):
        verts, faces, uvs, groups = [], [], [], []
        for (bn, muzzle, fwd, Lf, Wf) in self.flashes:
            v, f, u = flash_quads(muzzle, fwd, Lf, Wf)
            base = len(verts)
            verts += v
            faces += [tuple(i + base for i in ff) for ff in f]
            uvs += u
            groups += [bn] * len(v)
        me = bpy.data.meshes.new(f'{self.name}_MuzzleFlash')
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', [c for fu in uvs for uv in fu for c in uv])
        me.materials.append(mat)
        ob = bpy.data.objects.new(f'{self.name}_MuzzleFlash', me)
        self.coll.objects.link(ob)
        ob.location = self.origin
        for bn in sorted(set(groups)):
            vg = ob.vertex_groups.new(name=bn)
            vg.add([i for i, g in enumerate(groups) if g == bn], 1.0, 'REPLACE')
        self.flash_obj = ob

    # ------------------------------------------------------------------ rig
    def build_rig(self):
        arm = bpy.data.armatures.new(f'{self.name}_Rig')
        rig = bpy.data.objects.new(f'{self.name}_Rig', arm)
        self.coll.objects.link(rig)
        rig.location = self.origin
        arm.display_type = 'OCTAHEDRAL'
        rig.show_in_front = True
        vl = bpy.context.view_layer
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in vl.objects:
            o.select_set(False)
        vl.objects.active = rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.edit_bones
        for b in self.bones:
            e = eb.new(b['name'])
            e.head, e.tail = b['head'], b['tail']
            e.align_roll(b['z'])
            e.use_deform = b['deform']
        for b in self.bones:
            if b['parent']:
                eb[b['name']].parent = eb[b['parent']]
                eb[b['name']].use_connect = False
        bpy.ops.object.mode_set(mode='OBJECT')
        for b in self.bones:
            bc = arm.collections.get(b['coll']) or arm.collections.new(b['coll'])
            bc.assign(arm.bones[b['name']])
            pb = rig.pose.bones[b['name']]
            pb.rotation_mode = 'XYZ'
            if b['shape']:
                pb.custom_shape = widget(b['shape'])
                pb.use_custom_shape_bone_size = False
                pb.custom_shape_scale_xyz = b['sxyz']
            if b['color']:
                arm.bones[b['name']].color.palette = b['color']
            lk = b['locks']
            if lk:
                pb.lock_location = lk.get('loc', (False, False, False))
                pb.lock_rotation = lk.get('rot', (False, False, False))
                pb.lock_scale = lk.get('scale', (False, False, False))
        wc = bpy.context.view_layer.layer_collection.children.get('TK_Widgets')
        if wc:
            wc.exclude = True
        self.rig = rig
        m = self.meta
        gun = rig.pose.bones.get(m.get('gun_bone', ''))
        if gun:
            c = gun.constraints.new('LIMIT_ROTATION')
            c.owner_space = 'LOCAL'
            c.use_limit_x = True
            c.min_x, c.max_x = math.radians(m['gun_min']), math.radians(m['gun_max'])
            c.use_transform_limit = True
        for (bb, fb, rec, shots) in self.guns:
            if rec <= 0:
                continue
            c = rig.pose.bones[bb].constraints.new('LIMIT_LOCATION')
            c.owner_space = 'LOCAL'
            c.use_min_y, c.use_max_y = True, True
            c.min_y, c.max_y = -rec, 0.0
            c.use_transform_limit = True
        for k, v in m.items():
            rig[f'tk_{k}'] = v if not isinstance(v, (list, dict)) else json.dumps(v)

    def build_drivers(self):
        rig, p = self.rig, self.sol['p']

        def var(drv, side):
            v = drv.variables.new()
            v.name, v.type = 'd', 'TRANSFORMS'
            t = v.targets[0]
            t.id = rig
            t.bone_target = f'track_{side}'
            t.transform_type = 'LOC_Y'
            t.transform_space = 'TRANSFORM_SPACE'

        bad = []
        for (bn, side, reff) in self.wheel_drv:
            fc = rig.pose.bones[bn].driver_add('rotation_euler', 1)
            for mo in list(fc.modifiers):
                fc.modifiers.remove(mo)
            d = fc.driver
            d.type = 'SCRIPTED'
            var(d, side)
            d.expression = f'd*{1.0 / reff:.6f}'
            if not d.is_simple_expression:
                bad.append(bn)
        for side, ob in self.tracks.items():
            kb = ob.data.shape_keys.key_blocks['track_cycle']
            fc = kb.driver_add('value')
            for mo in list(fc.modifiers):
                fc.modifiers.remove(mo)
            d = fc.driver
            d.type = 'SCRIPTED'
            var(d, side)
            d.expression = f'd/{p:.6f} - floor(d/{p:.6f})'
            if not d.is_simple_expression:
                bad.append(ob.name)
        return bad

    # ------------------------------------------------------------------ animation clips
    def build_clips(self):
        rig, p = self.rig, self.sol['p']
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

        a, b = EPS * p, (1 - EPS) * p
        F = 1 + LINK_FRAMES

        def drive(l0, l1, r0, r1):
            def fn():
                key('track_L', 'location', 1, 1, l0)
                key('track_L', 'location', 1, F, l1)
                key('track_R', 'location', 1, 1, r0)
                key('track_R', 'location', 1, F, r1)
            return fn

        clip('Drive_Forward', 1, F, drive(a, b, a, b))
        clip('Drive_Reverse', 1, F, drive(b, a, b, a))
        clip('Pivot_Left', 1, F, drive(b, a, a, b))
        clip('Pivot_Right', 1, F, drive(a, b, b, a))

        def fire():
            import random
            rnd = random.Random(7)
            for (bb, fb, rec, shots) in self.guns:
                burst = len(shots) > 1
                key(bb, 'location', 1, 1, 0.0)
                key(fb, 'scale', None, 1, (1, 1, 1))
                S = 1.0 / FLASH_REST
                for s in shots:
                    key(fb, 'scale', None, s, (S, S, S))
                    key(fb, 'rotation_euler', 1, s, rnd.uniform(0, TAU))
                    key(fb, 'scale', None, s + 1, (0.7 * S, 0.7 * S, 0.7 * S))
                    key(fb, 'scale', None, s + 2, (1, 1, 1))
                    if burst:
                        key(bb, 'location', 1, s, 0.0)
                        key(bb, 'location', 1, s + 1, -rec)
                        key(bb, 'location', 1, s + 3, 0.0)
                    else:
                        for f, k in ((s, 0.0), (s + 1, -1.0), (s + 2, -0.97), (s + 5, -0.75), (s + 9, -0.42),
                                     (s + 13, -0.18), (s + 17, -0.05), (s + 21, 0.0)):
                            key(bb, 'location', 1, f, k * rec)
                key(bb, 'location', 1, 25, 0.0)
                key(fb, 'scale', None, 25, (1, 1, 1))
        clip('Fire', 1, 25, fire)

        tb, gb = self.meta['turret_bone'], self.meta['gun_bone']
        clip('Turret_Traverse', 1, 193, lambda: (key(tb, 'rotation_euler', 1, 1, 0.0),
                                                 key(tb, 'rotation_euler', 1, 193, TAU)))

        def elev():
            key(gb, 'rotation_euler', 0, 1, 0.0)
            key(gb, 'rotation_euler', 0, 25, math.radians(self.meta['gun_max']))
            key(gb, 'rotation_euler', 0, 73, math.radians(self.meta['gun_min']))
            key(gb, 'rotation_euler', 0, 97, 0.0)
        clip('Gun_Elevate', 1, 97, elev, interp='BEZIER')
        if 'radar' in pbs:
            clip('Radar_Spin', 1, 73, lambda: (key('radar', 'rotation_euler', 1, 1, 0.0),
                                               key('radar', 'rotation_euler', 1, 73, -TAU)))
        ad.action = None
        return made

    # ------------------------------------------------------------------ UV + bake
    def unwrap(self):
        uniq = {}
        for ob, bone, group in self.objs:
            uniq.setdefault(ob.data.name, ob)
        objs = list(uniq.values())
        vl = bpy.context.view_layer
        for o in vl.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        vl.objects.active = objs[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.0, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=0.004, shape_method='CONCAVE')
        bpy.ops.object.mode_set(mode='OBJECT')
        return len(objs)

    def bake(self, size=2048, samples=16):
        setup_cycles_gpu()
        sc = bpy.context.scene
        sc.cycles.samples = samples
        imgs = {'COLOR': new_image(f'T_{self.name}_BaseColor', size, (0.25, 0.25, 0.25), False),
                'ORM': new_image(f'T_{self.name}_ORM', size, (1.0, 0.6, 0.0), True),
                'NORMAL': new_image(f'T_{self.name}_Normal', size, (0.5, 0.5, 1.0), True)}
        rep = {}
        for ob, bone, group in self.objs:
            rep.setdefault(ob.data.name, (ob, group))
        gA = [o for o, g in rep.values() if g == 'hull']
        gB = [o for o, g in rep.values() if g == 'turret']
        allB = [o for o, b, g in self.objs if g == 'turret']
        mine = set(self.coll.all_objects)
        hidden = [o for o in sc.objects if o.type == 'MESH' and o not in mine and not o.hide_render]
        if getattr(self, 'flash_obj', None):
            hidden.append(self.flash_obj)
        for o in hidden:
            o.hide_render = True
        vl = bpy.context.view_layer
        times = {}
        try:
            for mode, img in imgs.items():
                for m in self.mat_list:
                    set_bake_mode(m, mode, img)
                for sel, hide in ((gA, allB), (gB, [])):
                    if not sel:
                        continue
                    for o in hide:
                        o.hide_render = True
                    for o in vl.objects:
                        o.select_set(False)
                    for o in sel:
                        o.select_set(True)
                    vl.objects.active = sel[0]
                    t0 = time.time()
                    if mode == 'NORMAL':
                        bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=6, margin_type='EXTEND',
                                            use_clear=False, target='IMAGE_TEXTURES')
                    else:
                        bpy.ops.object.bake(type='EMIT', margin=6, margin_type='EXTEND', use_clear=False,
                                            target='IMAGE_TEXTURES')
                    times[f'{mode}{len(times)}'] = round(time.time() - t0, 1)
                    for o in hide:
                        o.hide_render = False
        finally:
            for o in hidden:
                o.hide_render = False
            for m in self.mat_list:
                set_bake_mode(m, 'NORMAL', imgs['COLOR'])
        for mode, img in imgs.items():
            save_image(img, f'{img.name}.png')
        self.imgs = imgs
        return times

    # ------------------------------------------------------------------ final assembly
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
        main = next(o for o in parts if o.name.endswith('_hull'))
        vl.objects.active = main
        bpy.ops.object.join()
        body = vl.objects.active
        body.name = f'{self.name}_Body'
        body.data.name = f'{self.name}_Body'
        for ob in [body] + list(self.tracks.values()) + ([self.flash_obj] if getattr(self, 'flash_obj', None) else []):
            mw = ob.matrix_world.copy()
            ob.parent = rig
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.matrix_world = mw
            mo = ob.modifiers.new('Armature', 'ARMATURE')
            mo.object = rig
        for ob in self.tracks.values():
            vg = ob.vertex_groups.new(name='root')
            vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
        self.body = body
        # cleanup: master materials + template meshes
        for m in self.mat_list:
            bpy.data.materials.remove(m)
        for me in self.temp_meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        self.objs = []
        return body

    def stats(self):
        out = {}
        for ob in [self.body] + list(self.tracks.values()) + ([self.flash_obj] if getattr(self, 'flash_obj', None) else []) + getattr(self, 'extra_objs', []):
            me = ob.data
            me.calc_loop_triangles()
            out[ob.name] = len(me.loop_triangles)
        out['bones'] = len(self.rig.data.bones)
        return out


def beam(mb, a, b, w, h, mat):
    a, b = Vector(a), Vector(b)
    d = b - a
    mb.box((0, 0, 0), (d.length, w, h), mat, M=frame((a + b) / 2, d))


def export_tank(T, path):
    rig = T.rig
    old = rig.location.copy()
    rig.location = (0, 0, 0)
    bpy.context.view_layer.update()
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    rig.select_set(True)
    for c in rig.children:
        c.select_set(True)
    vl.objects.active = rig
    try:
        bpy.ops.export_scene.gltf(
            filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
            export_animations=True, export_animation_mode='NLA_TRACKS', export_force_sampling=True,
            export_frame_step=1, export_optimize_animation_size=True,
            export_optimize_animation_keep_anim_armature=False, export_def_bones=False, export_morph=True,
            export_morph_normal=True, export_morph_animation=True, export_skins=True, export_extras=True,
            export_tangents=True, export_image_format='AUTO', export_materials='EXPORT',
            export_rest_position_armature=True, export_anim_slide_to_zero=True, export_reset_pose_bones=True,
            export_cameras=False, export_lights=False)
    finally:
        rig.location = old
        bpy.context.view_layer.update()


def glb_summary(path):
    import struct
    with open(path, 'rb') as f:
        data = f.read()
    jlen = struct.unpack_from('<I', data, 12)[0]
    js = json.loads(data[20:20 + jlen])
    anims = {}
    for a in js.get('animations', []):
        paths = {}
        for ch in a['channels']:
            paths[ch['target']['path']] = paths.get(ch['target']['path'], 0) + 1
        anims[a['name']] = paths
    meshes = [(m['name'], len(m['primitives']), [list(p.get('targets', [])) and len(p['targets']) for p in m['primitives']])
              for m in js.get('meshes', [])]
    return dict(size_kb=round(len(data) / 1024), meshes=meshes, materials=[m['name'] for m in js.get('materials', [])],
                skins=[len(s['joints']) for s in js.get('skins', [])], anims=anims,
                images=len(js.get('images', [])))


def glb_postprocess(path, drive_prefixes=('Drive_', 'Pivot_')):
    """Remove constant morph-weight channels from non-drive clips so Fire/Turret clips never
    override script-driven tracks. Returns sampled track weights of Drive_Forward for checking."""
    import struct
    with open(path, 'rb') as f:
        data = f.read()
    jlen = struct.unpack_from('<I', data, 12)[0]
    js = json.loads(data[20:20 + jlen])
    bin_chunk = data[20 + jlen:]
    blen = struct.unpack_from('<I', bin_chunk, 0)[0]
    binb = bin_chunk[8:8 + blen]
    sample = None
    for a in js.get('animations', []):
        if a['name'].startswith(drive_prefixes):
            if a['name'] == 'Drive_Forward':
                for ch in a['channels']:
                    if ch['target']['path'] == 'weights':
                        acc = js['accessors'][a['samplers'][ch['sampler']]['output']]
                        bv = js['bufferViews'][acc['bufferView']]
                        off = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
                        sample = list(struct.unpack_from(f"<{acc['count']}f", binb, off))
                        break
            continue
        keep = [ch for ch in a['channels'] if ch['target']['path'] != 'weights']
        used = sorted({ch['sampler'] for ch in keep})
        remap = {old: new for new, old in enumerate(used)}
        a['samplers'] = [a['samplers'][i] for i in used]
        for ch in keep:
            ch['sampler'] = remap[ch['sampler']]
        a['channels'] = keep
    js['animations'] = [a for a in js.get('animations', []) if a['channels']]
    jb = json.dumps(js, separators=(',', ':')).encode()
    jb += b' ' * ((4 - len(jb) % 4) % 4)
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(jb) + len(bin_chunk))
    out += struct.pack('<II', len(jb), 0x4E4F534A) + jb + bin_chunk
    with open(path, 'wb') as f:
        f.write(out)
    return sample
