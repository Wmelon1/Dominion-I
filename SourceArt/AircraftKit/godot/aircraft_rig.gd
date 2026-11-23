## AircraftKit runtime controller (Godot 4.3+).
## Attach to a Node3D that has an instanced Aircraft_*.glb scene as a child (or to the scene root).
## Animates the rig only: control surfaces, propeller + blur disc, gear, canopy, guns, afterburner, stores.
##
##   $Plane.set_controls(pitch, roll, yaw)   # -1..1 each (pitch + = nose up, roll + = right, yaw + = right)
##   $Plane.throttle = 0.8                   # 0..1 (prop rpm / afterburner above afterburner_threshold)
##   $Plane.gear_down = false                # retracts over gear_time seconds (jets)
##   $Plane.canopy_open = true
##   $Plane.fire()                           # emits fired(muzzle_transform, gun_index)
##   $Plane.release_store(0)                 # hides store bone, emits store_released(transform, index)
class_name AircraftRig
extends Node3D

signal fired(muzzle_transform: Transform3D, gun_index: int)
signal store_released(store_transform: Transform3D, store_index: int)

@export var aircraft_name: String = ""        ## leave empty to auto-detect from "<Name>_Body"
@export var surface_speed: float = 4.0          ## how fast control surfaces follow input (1/s)
@export var max_prop_rps: float = 30.0          ## propeller revolutions per second at full throttle
@export var blur_threshold: float = 0.25        ## throttle above which the prop blur disc shows
@export var afterburner_threshold: float = 0.85
@export var gear_time: float = 3.0
@export var canopy_time: float = 2.0

const DATA := {
	"Kestrel": {"blades": 2, "fire_interval": 0.08,
		"controls": {"aileron_L": ["roll", 20], "aileron_R": ["roll", 20], "elevator_L": ["pitch", 25],
			"elevator_R": ["pitch", 25], "rudder": ["yaw", 25]},
		"wheels": {"wheel_L": 0.33, "wheel_R": 0.33}, "gears": {}, "canopy": {}, "stores": [],
		"muzzles": ["muzzle_1", "muzzle_2"], "afterburners": []},
	"Falcon": {"blades": 3, "fire_interval": 0.06,
		"controls": {"aileron_L": ["roll", 20], "aileron_R": ["roll", 20], "elevator_L": ["pitch", 25],
			"elevator_R": ["pitch", 25], "rudder": ["yaw", 25]},
		"wheels": {"wheel_L": 0.3, "wheel_R": 0.3, "wheel_T": 0.1}, "gears": {},
		"canopy": {"mode": "slide", "travel": 0.75}, "stores": [],
		"muzzles": ["muzzle_1", "muzzle_2", "muzzle_3", "muzzle_4"], "afterburners": []},
	"Lancer": {"blades": 0, "fire_interval": 0.05,
		"controls": {"aileron_L": ["roll", 18], "aileron_R": ["roll", 18], "elevator_L": ["pitch", 20],
			"elevator_R": ["pitch", 20], "rudder": ["yaw", 20]},
		"wheels": {"wheel_N": 0.27, "wheel_L": 0.33, "wheel_R": 0.33},
		"gears": {"gear_N": ["x", 95.0], "gear_L": ["y", -88.0], "gear_R": ["y", 88.0]},
		"canopy": {"mode": "slide", "travel": 0.85}, "stores": [],
		"muzzles": ["muzzle_1", "muzzle_2", "muzzle_3", "muzzle_4"], "afterburners": ["afterburner"]},
	"Saber": {"blades": 0, "fire_interval": 0.05,
		"controls": {"aileron_L": ["roll", 18], "aileron_R": ["roll", 18], "elevator_L": ["pitch", 20],
			"elevator_R": ["pitch", 20], "rudder": ["yaw", 20]},
		"wheels": {"wheel_N": 0.27, "wheel_L": 0.33, "wheel_R": 0.33},
		"gears": {"gear_N": ["x", 95.0], "gear_L": ["y", -88.0], "gear_R": ["y", 88.0]},
		"canopy": {"mode": "slide", "travel": 0.9}, "stores": ["store_1", "store_2"],
		"muzzles": ["muzzle_1", "muzzle_2", "muzzle_3", "muzzle_4", "muzzle_5", "muzzle_6"],
		"afterburners": ["afterburner"]},
	"Wraith": {"blades": 0, "fire_interval": 0.02,
		"controls": {"aileron_L": ["roll", 18], "aileron_R": ["roll", 18], "elevator_L": ["pitch", 20],
			"elevator_R": ["pitch", 20], "rudder_L": ["yaw", 25], "rudder_R": ["yaw", 25]},
		"wheels": {"wheel_N": 0.3, "wheel_L": 0.4, "wheel_R": 0.4},
		"gears": {"gear_N": ["x", 95.0], "gear_L": ["y", -88.0], "gear_R": ["y", 88.0]},
		"canopy": {"mode": "hinge", "travel": 32.0}, "stores": ["store_1", "store_2", "store_3", "store_4"],
		"muzzles": ["muzzle_1"], "afterburners": ["afterburner_L", "afterburner_R"]},
}
const SHOW := 1000.0  # flash / flame / blur geometry is stored at 1/1000 size in the rest pose
const HIDE := 0.001

var throttle := 0.0
var gear_down := true
var canopy_open := false
var ground_speed := 0.0      ## m/s, spins the wheels while taxiing

var _skel: Skeleton3D
var _d: Dictionary
var _bones := {}
var _rest := {}
var _input := Vector3.ZERO   # pitch, roll, yaw targets
var _surf := {}
var _prop_angle := 0.0
var _wheel_angle := 0.0
var _gear_t := 0.0          # 0 = down, 1 = up
var _canopy_t := 0.0
var _gun := 0
var _cooldown := 0.0
var _flash_t := {}
var _released := {}


func _ready() -> void:
	_bones.clear()
	_rest.clear()
	var found := find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		push_error("AircraftRig: no Skeleton3D under %s" % name)
		set_process(false)
		return
	_skel = found[0]
	if aircraft_name == "":
		for m in find_children("*_Body", "MeshInstance3D", true, false):
			aircraft_name = String(m.name).trim_suffix("_Body")
			break
	if not DATA.has(aircraft_name):
		push_error("AircraftRig: unknown aircraft '%s'" % aircraft_name)
		set_process(false)
		return
	_d = DATA[aircraft_name]
	for i in _skel.get_bone_count():
		_bones[_skel.get_bone_name(i)] = i
		_rest[_skel.get_bone_name(i)] = _skel.get_bone_rest(i)
	for c in _d.controls:
		_surf[c] = 0.0
	for m in _d.muzzles:
		_flash_t[m] = 99.0


func set_controls(pitch: float, roll: float, yaw: float) -> void:
	_input = Vector3(clampf(pitch, -1, 1), clampf(roll, -1, 1), clampf(yaw, -1, 1))


func fire() -> void:
	if _skel == null or _cooldown > 0.0 or _d.muzzles.is_empty():
		return
	var m: String = _d.muzzles[_gun]
	_flash_t[m] = 0.0
	fired.emit(_skel.global_transform * _skel.get_bone_global_pose(_bones[m]), _gun)
	_gun = (_gun + 1) % _d.muzzles.size()
	_cooldown = _d.fire_interval


func release_store(index: int) -> bool:
	if index < 0 or index >= _d.stores.size() or _released.has(index):
		return false
	var b: String = _d.stores[index]
	store_released.emit(_skel.global_transform * _skel.get_bone_global_pose(_bones[b]), index)
	_released[index] = true
	return true


func rearm() -> void:
	_released.clear()


func _process(delta: float) -> void:
	_cooldown = maxf(_cooldown - delta, 0.0)
	# control surfaces
	var k := 1.0 - exp(-surface_speed * delta)
	for c in _d.controls:
		var spec: Array = _d.controls[c]
		var v := 0.0
		match spec[0]:
			"pitch": v = _input.x
			"roll": v = -_input.y      # + bone rotation rolls left, so invert for "roll right"
			"yaw": v = _input.z
		_surf[c] = lerpf(_surf[c], v * deg_to_rad(spec[1]), k)
		_rot(c, Vector3.UP, _surf[c])
	# propeller + blur disc
	if _d.blades > 0:
		_prop_angle = wrapf(_prop_angle - TAU * max_prop_rps * throttle * delta, -PI, PI)
		_rot("prop", Vector3.UP, _prop_angle)
		_scale("prop_blur", SHOW if throttle > blur_threshold else HIDE)
	# afterburner
	for ab in _d.afterburners:
		var s := 0.0
		if throttle > afterburner_threshold:
			var f := (throttle - afterburner_threshold) / (1.0 - afterburner_threshold)
			s = SHOW * (0.6 + 0.4 * f) * randf_range(0.93, 1.05)
		_scale(ab, maxf(s, HIDE))
	# gear / canopy
	_gear_t = move_toward(_gear_t, 0.0 if gear_down else 1.0, delta / gear_time)
	var ge := smoothstep(0.0, 1.0, _gear_t)
	for g in _d.gears:
		var spec: Array = _d.gears[g]
		_rot(g, Vector3.RIGHT if spec[0] == "x" else Vector3.UP, deg_to_rad(spec[1]) * ge)
	_canopy_t = move_toward(_canopy_t, 1.0 if canopy_open else 0.0, delta / canopy_time)
	if not _d.canopy.is_empty():
		var ce := smoothstep(0.0, 1.0, _canopy_t)
		if _d.canopy.mode == "slide":
			var r: Transform3D = _rest["canopy"]
			_skel.set_bone_pose_position(_bones["canopy"], r.origin + r.basis * Vector3(0, -_d.canopy.travel * ce, 0))
		else:
			_rot("canopy", Vector3.RIGHT, deg_to_rad(_d.canopy.travel) * ce)
	# wheels
	_wheel_angle += ground_speed * delta
	for w in _d.wheels:
		_rot(w, Vector3.UP, _wheel_angle / float(_d.wheels[w]))
	# muzzle flashes
	for m in _d.muzzles:
		_flash_t[m] += delta
		var f := String(m).replace("muzzle", "flash")
		_scale(f, SHOW if _flash_t[m] < 0.04 else HIDE)
	# stores
	for i in _d.stores.size():
		_scale(_d.stores[i], HIDE if _released.has(i) else 1.0)


func _rot(bone: String, axis: Vector3, angle: float) -> void:
	if not _bones.has(bone):
		return
	var r: Transform3D = _rest[bone]
	_skel.set_bone_pose_rotation(_bones[bone], r.basis.get_rotation_quaternion() * Quaternion(axis, angle))


func _scale(bone: String, s: float) -> void:
	if _bones.has(bone):
		_skel.set_bone_pose_scale(_bones[bone], Vector3.ONE * s)
