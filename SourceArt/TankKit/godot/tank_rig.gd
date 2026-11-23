## TankKit runtime controller (Godot 4.3+).
## Attach to the root of an instanced Tank_*.glb scene (or any parent of it).
## Drives the rig procedurally: tracks + wheels, turret traverse, gun elevation, recoil and muzzle flash.
##
##   $Tank.drive(left_speed, right_speed)       # metres/second per track (call every frame)
##   $Tank.aim_at(target_global_position)       # turret + gun slew toward a point
##   $Tank.fire()                               # recoil + flash; returns muzzle Transform3D(s) via signal
##   $Tank.turret_yaw / $Tank.gun_pitch         # or set the targets directly (radians)
class_name TankRig
extends Node3D

signal fired(muzzle_transform: Transform3D, barrel_index: int)

## Leave empty to auto-detect from the "<Name>_Body" mesh.
@export var tank_name: String = ""
@export var turret_speed_deg: float = 40.0
@export var gun_speed_deg: float = 25.0
@export var auto_spin_radar: bool = true
@export var radar_speed_deg: float = 120.0

## Per-tank rig data exported from Blender (track pitch in m, gun limits in degrees,
## effective wheel radius in m by bone prefix, recoil distance in m).
const TANK_DATA := {
	"Scout": {"pitch": 0.16, "gun_min": -10.0, "gun_max": 35.0,
		"wheels": {"wheel": 0.33104, "idler": 0.21645, "sprocket": 0.28011},
		"barrels": [["barrel", "flash", "muzzle", 0.12]], "fire_interval": 0.12},
	"Medium": {"pitch": 0.18, "gun_min": -8.0, "gun_max": 20.0,
		"wheels": {"wheel": 0.32945, "idler": 0.27215, "sprocket": 0.34377, "roller": 0.11459},
		"barrels": [["barrel", "flash", "muzzle", 0.35]], "fire_interval": 4.0},
	"Heavy": {"pitch": 0.20, "gun_min": -6.0, "gun_max": 15.0,
		"wheels": {"wheel": 0.36606, "idler": 0.30239, "sprocket": 0.38197, "roller": 0.11671},
		"barrels": [["barrel", "flash", "muzzle", 0.45]], "fire_interval": 6.0},
	"Artillery": {"pitch": 0.17, "gun_min": -3.0, "gun_max": 70.0,
		"wheels": {"wheel": 0.29762, "idler": 0.25704, "sprocket": 0.32468, "roller": 0.09921},
		"barrels": [["barrel", "flash", "muzzle", 0.75]], "fire_interval": 8.0},
	"AntiAir": {"pitch": 0.17, "gun_min": -5.0, "gun_max": 85.0,
		"wheels": {"wheel": 0.32468, "idler": 0.27056, "sprocket": 0.32468, "roller": 0.09921},
		"barrels": [["barrel_L", "flash_L", "muzzle_L", 0.15], ["barrel_R", "flash_R", "muzzle_R", 0.15]],
		"fire_interval": 0.09, "radar": "radar"},
}
const FLASH_SCALE := 1000.0  # flash geometry is stored at 1/1000 size in the rest pose

var turret_yaw := 0.0        ## target yaw (radians, + = turn left)
var gun_pitch := 0.0         ## target pitch (radians, + = elevate)
var current_yaw := 0.0
var current_pitch := 0.0

var _skel: Skeleton3D
var _data: Dictionary
var _tracks := {}            # "L"/"R" -> [MeshInstance3D, blend shape index]
var _dist := {"L": 0.0, "R": 0.0}
var _wheels := []            # [bone index, side, radius, rest quaternion]
var _bones := {}
var _rest := {}
var _recoil := []            # per barrel: current recoil (m)
var _flash_t := []           # per barrel: seconds since shot
var _next_barrel := 0
var _cooldown := 0.0
var _radar_angle := 0.0


func _ready() -> void:
	_wheels.clear()
	_bones.clear()
	_rest.clear()
	_tracks.clear()
	_recoil.clear()
	_flash_t.clear()
	var found := find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		push_error("TankRig: no Skeleton3D found under %s" % name)
		set_process(false)
		return
	_skel = found[0]
	if tank_name == "":
		for m in find_children("*_Body", "MeshInstance3D", true, false):
			tank_name = String(m.name).trim_suffix("_Body")
			break
	if not TANK_DATA.has(tank_name):
		push_error("TankRig: unknown tank '%s'" % tank_name)
		set_process(false)
		return
	_data = TANK_DATA[tank_name]
	for i in _skel.get_bone_count():
		var bn := _skel.get_bone_name(i)
		_bones[bn] = i
		_rest[bn] = _skel.get_bone_rest(i)
		var prefix := bn.get_slice("_", 0)
		if _data.wheels.has(prefix):
			var side := "L" if bn.contains("_L") else "R"
			_wheels.append([i, side, float(_data.wheels[prefix]), _rest[bn].basis.get_rotation_quaternion()])
	for side in ["L", "R"]:
		for m in find_children("*Track_" + side, "MeshInstance3D", true, false):
			_tracks[side] = [m, m.find_blend_shape_by_name("track_cycle")]
	for b in _data.barrels:
		_recoil.append(0.0)
		_flash_t.append(99.0)


## Track speeds in m/s (positive = forward). Equal speeds drive straight, opposite speeds pivot.
func drive(left_speed: float, right_speed: float, delta: float = -1.0) -> void:
	var dt := delta if delta >= 0.0 else get_process_delta_time()
	_dist.L += left_speed * dt
	_dist.R += right_speed * dt


## Slew turret and gun toward a world-space point (respects elevation limits).
func aim_at(target: Vector3) -> void:
	if _skel == null:
		return
	var t_idx: int = _bones["turret"]
	var parent := _skel.get_bone_parent(t_idx)
	var base: Transform3D = _skel.global_transform * _skel.get_bone_global_pose(parent) * _rest["turret"]
	var p := base.affine_inverse() * target
	turret_yaw = atan2(p.x, p.z)
	var g_base: Transform3D = _skel.global_transform * _skel.get_bone_global_pose(t_idx) * _rest["gun"]
	var q := g_base.affine_inverse() * target
	gun_pitch = atan2(q.z, q.y)


func can_fire() -> bool:
	return _cooldown <= 0.0


func fire() -> void:
	if _skel == null or not can_fire():
		return
	var i := _next_barrel
	_next_barrel = (_next_barrel + 1) % _data.barrels.size()
	_recoil[i] = float(_data.barrels[i][3])
	_flash_t[i] = 0.0
	_cooldown = float(_data.fire_interval)
	var mz: int = _bones[_data.barrels[i][2]]
	fired.emit(_skel.global_transform * _skel.get_bone_global_pose(mz), i)


func _process(delta: float) -> void:
	_cooldown = max(_cooldown - delta, 0.0)
	# turret / gun slewing
	var max_yaw := deg_to_rad(turret_speed_deg) * delta
	current_yaw += clamp(wrapf(turret_yaw - current_yaw, -PI, PI), -max_yaw, max_yaw)
	current_yaw = wrapf(current_yaw, -PI, PI)
	var lim := clampf(gun_pitch, deg_to_rad(_data.gun_min), deg_to_rad(_data.gun_max))
	current_pitch = move_toward(current_pitch, lim, deg_to_rad(gun_speed_deg) * delta)
	_rot("turret", Vector3.UP, current_yaw)
	_rot("gun", Vector3.RIGHT, current_pitch)
	# tracks + wheels
	var pitch: float = _data.pitch
	for side in _tracks:
		var t = _tracks[side]
		if t[1] >= 0:
			t[0].set_blend_shape_value(t[1], fposmod(_dist[side] / pitch, 1.0))
	for w in _wheels:
		_skel.set_bone_pose_rotation(w[0], w[3] * Quaternion(Vector3.UP, _dist[w[1]] / w[2]))
	# recoil + flash
	for i in _data.barrels.size():
		var b = _data.barrels[i]
		var rec: float = b[3]
		_recoil[i] = move_toward(_recoil[i], 0.0, rec * 1.6 * delta)
		var r: Transform3D = _rest[b[0]]
		_skel.set_bone_pose_position(_bones[b[0]], r.origin + r.basis * Vector3(0, -_recoil[i], 0))
		_flash_t[i] += delta
		var s := 0.0
		if _flash_t[i] < 0.07:
			s = FLASH_SCALE * (1.0 - _flash_t[i] / 0.07 * 0.4)
		var fb: int = _bones[b[1]]
		_skel.set_bone_pose_scale(fb, Vector3.ONE * max(s, 1.0))
	if _data.has("radar") and auto_spin_radar:
		_radar_angle = wrapf(_radar_angle - deg_to_rad(radar_speed_deg) * delta, -PI, PI)
		_rot(_data.radar, Vector3.UP, _radar_angle)


func _rot(bone: String, axis: Vector3, angle: float) -> void:
	var r: Transform3D = _rest[bone]
	_skel.set_bone_pose_rotation(_bones[bone], r.basis.get_rotation_quaternion() * Quaternion(axis, angle))
