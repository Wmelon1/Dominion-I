## AirshipKit runtime controller (Godot 4.3+) for Airship_Leviathan.glb.
## Attach to a Node3D that has the instanced GLB as a child (or to the GLB scene root).
##
##   $Ship.throttle = 0.7                       # 0..1 propeller speed (6 engines)
##   $Ship.set_controls(pitch, yaw)             # -1..1  (pitch + = nose up, yaw + = right)
##   $Ship.ramp_open = true / doors_open = true # rear cargo ramp, side troop doors
##   $Ship.aim_turrets(world_pos) / fire_turret(i) / fire_all()
##   $Ship.get_seat_transform(i)                # 200 troop seats (global Transform3D, +Z = facing)
##   interior lamps: OmniLight3D nodes are spawned at the 42 "LightSocket_##" nodes on ready.
class_name AirshipRig
extends Node3D

signal fired(muzzle_transform: Transform3D, turret_index: int)

@export var spawn_interior_lights := true
@export var light_energy := 1.4
@export var light_range := 7.0
@export var interior_visibility_range := 160.0   ## hide interior meshes beyond this distance (0 = off)
@export var max_prop_rps := 4.0
@export var turret_speed_deg := 60.0
@export var fire_interval := 0.09
@export var ramp_time := 4.0
@export var door_time := 1.5

const PROPS := ["prop_1", "prop_2", "prop_3", "prop_4", "prop_5", "prop_6"]
const CONTROLS := {"elevator_L": "pitch", "elevator_R": "pitch", "rudder_U": "yaw", "rudder_D": "yaw"}
const CONTROL_MAX_DEG := 22.0
const TURRETS := [
	{"turret": "turret_1", "gun": "gun_1", "min": -5.0, "max": 80.0, "muzzles": ["muzzle_1L", "muzzle_1R"]},
	{"turret": "turret_2", "gun": "gun_2", "min": -5.0, "max": 80.0, "muzzles": ["muzzle_2L", "muzzle_2R"]},
	{"turret": "turret_3", "gun": "gun_3", "min": -5.0, "max": 85.0, "muzzles": ["muzzle_3L", "muzzle_3R"]},
	{"turret": "turret_4", "gun": "gun_4", "min": -5.0, "max": 85.0, "muzzles": ["muzzle_4L", "muzzle_4R"]},
]
const FLASH := 1000.0
## 200 troop seats in ship-local space: Vector4(x, y, z, yaw). Lower troop deck, 4 rows x 50.
const SEATS := [
	Vector4(5.300, 0.530, 20.400, -1.5708), Vector4(5.300, 0.530, 19.800, -1.5708), Vector4(5.300, 0.530, 19.200, -1.5708), Vector4(5.300, 0.530, 18.600, -1.5708),
	Vector4(5.300, 0.530, 18.000, -1.5708), Vector4(5.300, 0.530, 17.400, -1.5708), Vector4(5.300, 0.530, 16.800, -1.5708), Vector4(5.300, 0.530, 16.200, -1.5708),
	Vector4(5.300, 0.530, 15.600, -1.5708), Vector4(5.300, 0.530, 15.000, -1.5708), Vector4(5.300, 0.530, 14.400, -1.5708), Vector4(5.300, 0.530, 13.800, -1.5708),
	Vector4(5.300, 0.530, 13.200, -1.5708), Vector4(5.300, 0.530, 12.600, -1.5708), Vector4(5.300, 0.530, 12.000, -1.5708), Vector4(5.300, 0.530, 11.400, -1.5708),
	Vector4(5.300, 0.530, 10.800, -1.5708), Vector4(5.300, 0.530, 10.200, -1.5708), Vector4(5.300, 0.530, 9.600, -1.5708), Vector4(5.300, 0.530, 9.000, -1.5708),
	Vector4(5.300, 0.530, 8.400, -1.5708), Vector4(5.300, 0.530, 7.800, -1.5708), Vector4(5.300, 0.530, 4.300, -1.5708), Vector4(5.300, 0.530, 3.700, -1.5708),
	Vector4(5.300, 0.530, 3.100, -1.5708), Vector4(5.300, 0.530, 2.500, -1.5708), Vector4(5.300, 0.530, 1.900, -1.5708), Vector4(5.300, 0.530, 1.300, -1.5708),
	Vector4(5.300, 0.530, 0.700, -1.5708), Vector4(5.300, 0.530, 0.100, -1.5708), Vector4(5.300, 0.530, -0.500, -1.5708), Vector4(5.300, 0.530, -1.100, -1.5708),
	Vector4(5.300, 0.530, -1.700, -1.5708), Vector4(5.300, 0.530, -2.300, -1.5708), Vector4(5.300, 0.530, -2.900, -1.5708), Vector4(5.300, 0.530, -3.500, -1.5708),
	Vector4(5.300, 0.530, -4.100, -1.5708), Vector4(5.300, 0.530, -4.700, -1.5708), Vector4(5.300, 0.530, -5.300, -1.5708), Vector4(5.300, 0.530, -5.900, -1.5708),
	Vector4(5.300, 0.530, -6.500, -1.5708), Vector4(5.300, 0.530, -7.100, -1.5708), Vector4(5.300, 0.530, -7.700, -1.5708), Vector4(5.300, 0.530, -8.300, -1.5708),
	Vector4(5.300, 0.530, -8.900, -1.5708), Vector4(5.300, 0.530, -9.500, -1.5708), Vector4(5.300, 0.530, -10.100, -1.5708), Vector4(5.300, 0.530, -10.700, -1.5708),
	Vector4(5.300, 0.530, -11.300, -1.5708), Vector4(5.300, 0.530, -11.900, -1.5708), Vector4(-5.300, 0.530, 20.400, 1.5708), Vector4(-5.300, 0.530, 19.800, 1.5708),
	Vector4(-5.300, 0.530, 19.200, 1.5708), Vector4(-5.300, 0.530, 18.600, 1.5708), Vector4(-5.300, 0.530, 18.000, 1.5708), Vector4(-5.300, 0.530, 17.400, 1.5708),
	Vector4(-5.300, 0.530, 16.800, 1.5708), Vector4(-5.300, 0.530, 16.200, 1.5708), Vector4(-5.300, 0.530, 15.600, 1.5708), Vector4(-5.300, 0.530, 15.000, 1.5708),
	Vector4(-5.300, 0.530, 14.400, 1.5708), Vector4(-5.300, 0.530, 13.800, 1.5708), Vector4(-5.300, 0.530, 13.200, 1.5708), Vector4(-5.300, 0.530, 12.600, 1.5708),
	Vector4(-5.300, 0.530, 12.000, 1.5708), Vector4(-5.300, 0.530, 11.400, 1.5708), Vector4(-5.300, 0.530, 10.800, 1.5708), Vector4(-5.300, 0.530, 10.200, 1.5708),
	Vector4(-5.300, 0.530, 9.600, 1.5708), Vector4(-5.300, 0.530, 9.000, 1.5708), Vector4(-5.300, 0.530, 8.400, 1.5708), Vector4(-5.300, 0.530, 7.800, 1.5708),
	Vector4(-5.300, 0.530, 4.300, 1.5708), Vector4(-5.300, 0.530, 3.700, 1.5708), Vector4(-5.300, 0.530, 3.100, 1.5708), Vector4(-5.300, 0.530, 2.500, 1.5708),
	Vector4(-5.300, 0.530, 1.900, 1.5708), Vector4(-5.300, 0.530, 1.300, 1.5708), Vector4(-5.300, 0.530, 0.700, 1.5708), Vector4(-5.300, 0.530, 0.100, 1.5708),
	Vector4(-5.300, 0.530, -0.500, 1.5708), Vector4(-5.300, 0.530, -1.100, 1.5708), Vector4(-5.300, 0.530, -1.700, 1.5708), Vector4(-5.300, 0.530, -2.300, 1.5708),
	Vector4(-5.300, 0.530, -2.900, 1.5708), Vector4(-5.300, 0.530, -3.500, 1.5708), Vector4(-5.300, 0.530, -4.100, 1.5708), Vector4(-5.300, 0.530, -4.700, 1.5708),
	Vector4(-5.300, 0.530, -5.300, 1.5708), Vector4(-5.300, 0.530, -5.900, 1.5708), Vector4(-5.300, 0.530, -6.500, 1.5708), Vector4(-5.300, 0.530, -7.100, 1.5708),
	Vector4(-5.300, 0.530, -7.700, 1.5708), Vector4(-5.300, 0.530, -8.300, 1.5708), Vector4(-5.300, 0.530, -8.900, 1.5708), Vector4(-5.300, 0.530, -9.500, 1.5708),
	Vector4(-5.300, 0.530, -10.100, 1.5708), Vector4(-5.300, 0.530, -10.700, 1.5708), Vector4(-5.300, 0.530, -11.300, 1.5708), Vector4(-5.300, 0.530, -11.900, 1.5708),
	Vector4(0.750, 0.530, 20.400, 1.5708), Vector4(0.750, 0.530, 19.800, 1.5708), Vector4(0.750, 0.530, 19.200, 1.5708), Vector4(0.750, 0.530, 18.600, 1.5708),
	Vector4(0.750, 0.530, 18.000, 1.5708), Vector4(0.750, 0.530, 17.400, 1.5708), Vector4(0.750, 0.530, 16.800, 1.5708), Vector4(0.750, 0.530, 16.200, 1.5708),
	Vector4(0.750, 0.530, 15.600, 1.5708), Vector4(0.750, 0.530, 15.000, 1.5708), Vector4(0.750, 0.530, 14.400, 1.5708), Vector4(0.750, 0.530, 13.800, 1.5708),
	Vector4(0.750, 0.530, 13.200, 1.5708), Vector4(0.750, 0.530, 12.600, 1.5708), Vector4(0.750, 0.530, 12.000, 1.5708), Vector4(0.750, 0.530, 11.400, 1.5708),
	Vector4(0.750, 0.530, 10.800, 1.5708), Vector4(0.750, 0.530, 10.200, 1.5708), Vector4(0.750, 0.530, 9.600, 1.5708), Vector4(0.750, 0.530, 9.000, 1.5708),
	Vector4(0.750, 0.530, 8.400, 1.5708), Vector4(0.750, 0.530, 7.800, 1.5708), Vector4(0.750, 0.530, 4.300, 1.5708), Vector4(0.750, 0.530, 3.700, 1.5708),
	Vector4(0.750, 0.530, 3.100, 1.5708), Vector4(0.750, 0.530, 2.500, 1.5708), Vector4(0.750, 0.530, 1.900, 1.5708), Vector4(0.750, 0.530, 1.300, 1.5708),
	Vector4(0.750, 0.530, 0.700, 1.5708), Vector4(0.750, 0.530, 0.100, 1.5708), Vector4(0.750, 0.530, -0.500, 1.5708), Vector4(0.750, 0.530, -1.100, 1.5708),
	Vector4(0.750, 0.530, -1.700, 1.5708), Vector4(0.750, 0.530, -2.300, 1.5708), Vector4(0.750, 0.530, -2.900, 1.5708), Vector4(0.750, 0.530, -3.500, 1.5708),
	Vector4(0.750, 0.530, -4.100, 1.5708), Vector4(0.750, 0.530, -4.700, 1.5708), Vector4(0.750, 0.530, -5.300, 1.5708), Vector4(0.750, 0.530, -5.900, 1.5708),
	Vector4(0.750, 0.530, -6.500, 1.5708), Vector4(0.750, 0.530, -7.100, 1.5708), Vector4(0.750, 0.530, -7.700, 1.5708), Vector4(0.750, 0.530, -8.300, 1.5708),
	Vector4(0.750, 0.530, -8.900, 1.5708), Vector4(0.750, 0.530, -9.500, 1.5708), Vector4(0.750, 0.530, -10.100, 1.5708), Vector4(0.750, 0.530, -10.700, 1.5708),
	Vector4(0.750, 0.530, -11.300, 1.5708), Vector4(0.750, 0.530, -11.900, 1.5708), Vector4(-0.750, 0.530, 20.400, -1.5708), Vector4(-0.750, 0.530, 19.800, -1.5708),
	Vector4(-0.750, 0.530, 19.200, -1.5708), Vector4(-0.750, 0.530, 18.600, -1.5708), Vector4(-0.750, 0.530, 18.000, -1.5708), Vector4(-0.750, 0.530, 17.400, -1.5708),
	Vector4(-0.750, 0.530, 16.800, -1.5708), Vector4(-0.750, 0.530, 16.200, -1.5708), Vector4(-0.750, 0.530, 15.600, -1.5708), Vector4(-0.750, 0.530, 15.000, -1.5708),
	Vector4(-0.750, 0.530, 14.400, -1.5708), Vector4(-0.750, 0.530, 13.800, -1.5708), Vector4(-0.750, 0.530, 13.200, -1.5708), Vector4(-0.750, 0.530, 12.600, -1.5708),
	Vector4(-0.750, 0.530, 12.000, -1.5708), Vector4(-0.750, 0.530, 11.400, -1.5708), Vector4(-0.750, 0.530, 10.800, -1.5708), Vector4(-0.750, 0.530, 10.200, -1.5708),
	Vector4(-0.750, 0.530, 9.600, -1.5708), Vector4(-0.750, 0.530, 9.000, -1.5708), Vector4(-0.750, 0.530, 8.400, -1.5708), Vector4(-0.750, 0.530, 7.800, -1.5708),
	Vector4(-0.750, 0.530, 4.300, -1.5708), Vector4(-0.750, 0.530, 3.700, -1.5708), Vector4(-0.750, 0.530, 3.100, -1.5708), Vector4(-0.750, 0.530, 2.500, -1.5708),
	Vector4(-0.750, 0.530, 1.900, -1.5708), Vector4(-0.750, 0.530, 1.300, -1.5708), Vector4(-0.750, 0.530, 0.700, -1.5708), Vector4(-0.750, 0.530, 0.100, -1.5708),
	Vector4(-0.750, 0.530, -0.500, -1.5708), Vector4(-0.750, 0.530, -1.100, -1.5708), Vector4(-0.750, 0.530, -1.700, -1.5708), Vector4(-0.750, 0.530, -2.300, -1.5708),
	Vector4(-0.750, 0.530, -2.900, -1.5708), Vector4(-0.750, 0.530, -3.500, -1.5708), Vector4(-0.750, 0.530, -4.100, -1.5708), Vector4(-0.750, 0.530, -4.700, -1.5708),
	Vector4(-0.750, 0.530, -5.300, -1.5708), Vector4(-0.750, 0.530, -5.900, -1.5708), Vector4(-0.750, 0.530, -6.500, -1.5708), Vector4(-0.750, 0.530, -7.100, -1.5708),
	Vector4(-0.750, 0.530, -7.700, -1.5708), Vector4(-0.750, 0.530, -8.300, -1.5708), Vector4(-0.750, 0.530, -8.900, -1.5708), Vector4(-0.750, 0.530, -9.500, -1.5708),
	Vector4(-0.750, 0.530, -10.100, -1.5708), Vector4(-0.750, 0.530, -10.700, -1.5708), Vector4(-0.750, 0.530, -11.300, -1.5708), Vector4(-0.750, 0.530, -11.900, -1.5708),
]

var throttle := 0.0
var ramp_open := false
var doors_open := false
var _skel: Skeleton3D
var _bones := {}
var _rest := {}
var _ctl := Vector2.ZERO
var _surf := {}
var _prop := 0.0
var _ramp_t := 0.0
var _door_t := 0.0
var _aim := []          # per turret: [yaw, pitch] targets
var _cur := []
var _flash_t := {}
var _barrel := []
var _cool := []


func _ready() -> void:
	_bones.clear(); _rest.clear(); _aim.clear(); _cur.clear(); _barrel.clear(); _cool.clear(); _flash_t.clear()
	var found := find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		push_error("AirshipRig: no Skeleton3D found")
		set_process(false)
		return
	_skel = found[0]
	for i in _skel.get_bone_count():
		_bones[_skel.get_bone_name(i)] = i
		_rest[_skel.get_bone_name(i)] = _skel.get_bone_rest(i)
	for c in CONTROLS:
		_surf[c] = 0.0
	for t in TURRETS:
		_aim.append([0.0, 0.0])
		_cur.append([0.0, 0.0])
		_barrel.append(0)
		_cool.append(0.0)
		for m in t.muzzles:
			_flash_t[m] = 99.0
	if spawn_interior_lights:
		for n in find_children("LightSocket_*", "", true, false):
			if not n.find_children("*", "OmniLight3D", false, false).is_empty():
				continue
			var l := OmniLight3D.new()
			l.light_color = Color(1.0, 0.8, 0.58)
			l.light_energy = light_energy
			l.omni_range = light_range
			l.shadow_enabled = false
			n.add_child(l)
	if interior_visibility_range > 0.0:
		for m in find_children("Airship_Interior_*", "MeshInstance3D", true, false):
			m.visibility_range_end = interior_visibility_range


func set_controls(pitch: float, yaw: float) -> void:
	_ctl = Vector2(clampf(pitch, -1, 1), clampf(yaw, -1, 1))


func seat_count() -> int:
	return SEATS.size()


func get_seat_transform(i: int) -> Transform3D:
	var s: Vector4 = SEATS[i]
	var local := Transform3D(Basis(Vector3.UP, s.w), Vector3(s.x, s.y, s.z))
	return _skel.global_transform * local if _skel else global_transform * local


func aim_turret(i: int, target: Vector3) -> void:
	var t: Dictionary = TURRETS[i]
	var ti: int = _bones[t.turret]
	var base: Transform3D = _skel.global_transform * _skel.get_bone_global_pose(_skel.get_bone_parent(ti)) * _rest[t.turret]
	var p := base.affine_inverse() * target
	_aim[i][0] = atan2(p.x, p.z)
	var g: Transform3D = _skel.global_transform * _skel.get_bone_global_pose(ti) * _rest[t.gun]
	var q := g.affine_inverse() * target
	_aim[i][1] = atan2(q.z, q.y)


func aim_turrets(target: Vector3) -> void:
	for i in TURRETS.size():
		aim_turret(i, target)


func fire_turret(i: int) -> void:
	if _cool[i] > 0.0:
		return
	var t: Dictionary = TURRETS[i]
	var m: String = t.muzzles[_barrel[i]]
	_barrel[i] = (_barrel[i] + 1) % t.muzzles.size()
	_flash_t[m] = 0.0
	_cool[i] = fire_interval
	fired.emit(_skel.global_transform * _skel.get_bone_global_pose(_bones[m]), i)


func fire_all() -> void:
	for i in TURRETS.size():
		fire_turret(i)


func _process(delta: float) -> void:
	_prop = wrapf(_prop - TAU * max_prop_rps * throttle * delta, -PI, PI)
	for p in PROPS:
		_rot(p, Vector3.UP, _prop)
	var k := 1.0 - exp(-3.0 * delta)
	for c in CONTROLS:
		var v := _ctl.x if CONTROLS[c] == "pitch" else _ctl.y
		_surf[c] = lerpf(_surf[c], v * deg_to_rad(CONTROL_MAX_DEG), k)
		_rot(c, Vector3.UP, _surf[c])
	_ramp_t = move_toward(_ramp_t, 1.0 if ramp_open else 0.0, delta / ramp_time)
	_rot("ramp", Vector3.RIGHT, deg_to_rad(105.0) * smoothstep(0.0, 1.0, _ramp_t))
	_door_t = move_toward(_door_t, 1.0 if doors_open else 0.0, delta / door_time)
	for d in ["door_L", "door_R"]:
		var r: Transform3D = _rest[d]
		_skel.set_bone_pose_position(_bones[d], r.origin + r.basis * Vector3(0, -2.35 * smoothstep(0.0, 1.0, _door_t), 0))
	var step := deg_to_rad(turret_speed_deg) * delta
	for i in TURRETS.size():
		var t: Dictionary = TURRETS[i]
		_cool[i] = maxf(_cool[i] - delta, 0.0)
		_cur[i][0] += clampf(wrapf(_aim[i][0] - _cur[i][0], -PI, PI), -step, step)
		_cur[i][1] = move_toward(_cur[i][1], clampf(_aim[i][1], deg_to_rad(t.min), deg_to_rad(t.max)), step)
		_rot(t.turret, Vector3.UP, _cur[i][0])
		_rot(t.gun, Vector3.RIGHT, _cur[i][1])
		for m in t.muzzles:
			_flash_t[m] += delta
			var f := String(m).replace("muzzle", "flash")
			if _bones.has(f):
				_skel.set_bone_pose_scale(_bones[f], Vector3.ONE * (FLASH if _flash_t[m] < 0.04 else 1.0))


func _rot(bone: String, axis: Vector3, angle: float) -> void:
	if not _bones.has(bone):
		return
	var r: Transform3D = _rest[bone]
	_skel.set_bone_pose_rotation(_bones[bone], r.basis.get_rotation_quaternion() * Quaternion(axis, angle))
