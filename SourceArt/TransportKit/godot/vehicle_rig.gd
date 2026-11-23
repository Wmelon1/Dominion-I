## TransportKit runtime controller (Godot 4.3+), for wheeled and tracked vehicles.
## Attach to a Node3D that has an instanced Vehicle_*.glb scene as a child.
##
##   $Truck.drive(speed, steer, delta)      # speed m/s (+ forward); steer -1..1 (+ = right)
##   $Apc.drive_tracks(left, right, delta)  # tracked vehicles: per-track speed in m/s
##   $Mrap.aim_at(world_pos) / fire()       # gunner turret (Bastion, Carrier)
##   $Truck.set_door("tailgate", true)      # doors: tailgate / door_rear / ramp
class_name VehicleRig
extends Node3D

signal fired(muzzle_transform: Transform3D)

@export var vehicle_name: String = ""          ## leave empty to auto-detect from "<Name>_Body"
@export var turret_speed_deg: float = 90.0
@export var gun_speed_deg: float = 60.0
@export var door_time: float = 1.5

const DATA := {
	"Mule": {"tracked": false, "radius": 0.55, "steer": {"steer_1_L": 32.0, "steer_1_R": 32.0},
		"doors": {"tailgate": ["x", 95.0]}},
	"Bastion": {"tracked": false, "radius": 0.62, "steer": {"steer_1_L": 30.0, "steer_1_R": 30.0},
		"doors": {"door_rear": ["y", 100.0]}, "gun": [-10.0, 60.0], "recoil": 0.05, "fire_interval": 0.1},
	"Carrier": {"tracked": true, "pitch": 0.15,
		"wheels": {"wheel": 0.31035, "sprocket": 0.28648, "idler": 0.26261},
		"doors": {"ramp": ["x", 100.0]}, "gun": [-10.0, 55.0], "recoil": 0.06, "fire_interval": 0.11},
}
const FLASH := 1000.0

var turret_yaw := 0.0
var gun_pitch := 0.0
var _yaw := 0.0
var _pitch := 0.0
var _skel: Skeleton3D
var _d: Dictionary
var _bones := {}
var _rest := {}
var _dist := {"L": 0.0, "R": 0.0}
var _steer := 0.0
var _doors := {}       # bone -> [target_open, t]
var _tracks := {}
var _recoil := 0.0
var _flash_t := 99.0
var _cool := 0.0


func _ready() -> void:
	_bones.clear()
	_rest.clear()
	_tracks.clear()
	var found := find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		push_error("VehicleRig: no Skeleton3D under %s" % name)
		set_process(false)
		return
	_skel = found[0]
	if vehicle_name == "":
		for m in find_children("*_Body", "MeshInstance3D", true, false):
			vehicle_name = String(m.name).trim_suffix("_Body")
			break
	if not DATA.has(vehicle_name):
		push_error("VehicleRig: unknown vehicle '%s'" % vehicle_name)
		set_process(false)
		return
	_d = DATA[vehicle_name]
	for i in _skel.get_bone_count():
		_bones[_skel.get_bone_name(i)] = i
		_rest[_skel.get_bone_name(i)] = _skel.get_bone_rest(i)
	for b in _d.doors:
		_doors[b] = [false, 0.0]
	for side in ["L", "R"]:
		for m in find_children("*Track_" + side, "MeshInstance3D", true, false):
			_tracks[side] = [m, m.find_blend_shape_by_name("track_cycle")]


## Wheeled: forward speed (m/s) + steering (-1..1, + = right). Tracked: steer becomes a speed split.
func drive(speed: float, steer: float, delta: float = -1.0) -> void:
	var dt := delta if delta >= 0.0 else get_process_delta_time()
	_steer = clampf(steer, -1.0, 1.0)
	if _d.get("tracked", false):
		drive_tracks(speed - steer * 2.0, speed + steer * 2.0, dt)
	else:
		_dist.L += speed * dt
		_dist.R += speed * dt


func drive_tracks(left: float, right: float, delta: float = -1.0) -> void:
	var dt := delta if delta >= 0.0 else get_process_delta_time()
	_dist.L += left * dt
	_dist.R += right * dt


func set_door(bone: String, open: bool) -> void:
	if _doors.has(bone):
		_doors[bone][0] = open


func aim_at(target: Vector3) -> void:
	if not _bones.has("turret"):
		return
	var t_idx: int = _bones["turret"]
	var base: Transform3D = _skel.global_transform * _skel.get_bone_global_pose(_skel.get_bone_parent(t_idx)) * _rest["turret"]
	var p := base.affine_inverse() * target
	turret_yaw = atan2(p.x, p.z)
	var g: Transform3D = _skel.global_transform * _skel.get_bone_global_pose(t_idx) * _rest["gun"]
	var q := g.affine_inverse() * target
	gun_pitch = atan2(q.z, q.y)


func fire() -> void:
	if not _bones.has("muzzle") or _cool > 0.0:
		return
	_cool = _d.fire_interval
	_recoil = _d.recoil
	_flash_t = 0.0
	fired.emit(_skel.global_transform * _skel.get_bone_global_pose(_bones["muzzle"]))


func _process(delta: float) -> void:
	_cool = maxf(_cool - delta, 0.0)
	# wheels / tracks
	if _d.get("tracked", false):
		for side in _tracks:
			var t = _tracks[side]
			if t[1] >= 0:
				t[0].set_blend_shape_value(t[1], fposmod(_dist[side] / _d.pitch, 1.0))
	for bn in _bones:
		if not String(bn).contains("_"):
			continue
		var prefix := String(bn).get_slice("_", 0)
		var side := "L" if String(bn).ends_with("_L") else "R"
		if prefix == "wheel" and not _d.get("tracked", false):
			_rot(bn, Vector3.UP, _dist[side] / _d.radius)
		elif _d.get("tracked", false) and _d.wheels.has(prefix):
			_rot(bn, Vector3.UP, _dist[side] / float(_d.wheels[prefix]))
	for sb in _d.get("steer", {}):
		_rot(sb, Vector3.UP, -_steer * deg_to_rad(_d.steer[sb]))
	# doors
	for b in _doors:
		var st = _doors[b]
		st[1] = move_toward(st[1], 1.0 if st[0] else 0.0, delta / door_time)
		var spec: Array = _d.doors[b]
		var axis := Vector3.RIGHT if spec[0] == "x" else Vector3.UP
		_rot(b, axis, deg_to_rad(spec[1]) * smoothstep(0.0, 1.0, st[1]))
	# turret / gun / recoil / flash
	if _bones.has("turret"):
		_yaw += clampf(wrapf(turret_yaw - _yaw, -PI, PI), -deg_to_rad(turret_speed_deg) * delta, deg_to_rad(turret_speed_deg) * delta)
		_pitch = move_toward(_pitch, clampf(gun_pitch, deg_to_rad(_d.gun[0]), deg_to_rad(_d.gun[1])), deg_to_rad(gun_speed_deg) * delta)
		_rot("turret", Vector3.UP, _yaw)
		_rot("gun", Vector3.RIGHT, _pitch)
		_recoil = move_toward(_recoil, 0.0, 1.5 * delta)
		var r: Transform3D = _rest["barrel"]
		_skel.set_bone_pose_position(_bones["barrel"], r.origin + r.basis * Vector3(0, -_recoil, 0))
		_flash_t += delta
		_skel.set_bone_pose_scale(_bones["flash"], Vector3.ONE * (FLASH if _flash_t < 0.04 else 1.0))


func _rot(bone: String, axis: Vector3, angle: float) -> void:
	if not _bones.has(bone):
		return
	var r: Transform3D = _rest[bone]
	_skel.set_bone_pose_rotation(_bones[bone], r.basis.get_rotation_quaternion() * Quaternion(axis, angle))
