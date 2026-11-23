## SoldierKit player-model helper (Godot 4.3+) for Soldier_Male.glb / Soldier_Female.glb.
## Attach to a Node3D that has the instanced GLB as a child (e.g. inside your CharacterBody3D).
##
##   $Model.update_locomotion(velocity.length(), is_crouching, is_aiming)   # call every frame
##   $Model.show_backpack = false                                         # gear toggles
##   $Model.muzzle_transform()                                            # spawn bullets / flashes here
##
## Bones use Godot's SkeletonProfileHumanoid names, so any humanoid animation library retargets onto
## both soldiers (Import dock > Skeleton3D > Retarget > Bone Map > SkeletonProfileHumanoid).
class_name SoldierRig
extends Node3D

@export var show_helmet := true:
	set(v):
		show_helmet = v
		_apply_gear()
@export var show_vest := true:
	set(v):
		show_vest = v
		_apply_gear()
@export var show_belt := true:
	set(v):
		show_belt = v
		_apply_gear()
@export var show_backpack := true:
	set(v):
		show_backpack = v
		_apply_gear()
@export var show_pads := true:
	set(v):
		show_pads = v
		_apply_gear()
@export var show_rifle := true:
	set(v):
		show_rifle = v
		_apply_gear()
@export var walk_speed_ref := 1.05   ## ground speed (m/s) of the Walk clip at speed_scale 1
@export var run_speed_ref := 2.7     ## ground speed (m/s) of the Run clip at speed_scale 1
@export var run_threshold := 1.8
@export var blend_time := 0.2

const LOOPS := ["Idle", "Walk", "Run", "Crouch", "Rifle_Aim"]
var anim: AnimationPlayer
var skeleton: Skeleton3D


func _ready() -> void:
	var aps := find_children("*", "AnimationPlayer", true, false)
	if not aps.is_empty():
		anim = aps[0]
		for n in LOOPS:
			if anim.has_animation(n):
				anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR
		anim.play("Idle")
	var sk := find_children("*", "Skeleton3D", true, false)
	if not sk.is_empty():
		skeleton = sk[0]
	_apply_gear()


func _apply_gear() -> void:
	if not is_inside_tree():
		return
	var want := {"_Helmet": show_helmet, "_Vest": show_vest, "_Belt": show_belt, "_Backpack": show_backpack,
		"_Pads": show_pads, "_Rifle": show_rifle}
	for m in find_children("Soldier*", "MeshInstance3D", true, false):
		for suffix in want:
			if String(m.name).ends_with(suffix):
				m.visible = want[suffix]


## Picks Idle / Walk / Run / Crouch / Rifle_Aim and matches playback speed to movement speed.
func update_locomotion(speed: float, crouching := false, aiming := false) -> void:
	if anim == null:
		return
	var target := "Idle"
	var scale := 1.0
	if aiming:
		target = "Rifle_Aim"
	elif crouching:
		target = "Crouch"
	elif speed > run_threshold:
		target = "Run"
		scale = speed / run_speed_ref
	elif speed > 0.1:
		target = "Walk"
		scale = speed / walk_speed_ref
	if anim.current_animation != target:
		anim.play(target, blend_time)
	anim.speed_scale = clampf(scale, 0.3, 2.5)


func muzzle_transform() -> Transform3D:
	if skeleton == null:
		return global_transform
	return skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("Muzzle"))


## Global transform of the right-hand weapon socket (use a BoneAttachment3D on "WeaponR" for other weapons).
func weapon_transform() -> Transform3D:
	if skeleton == null:
		return global_transform
	return skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("WeaponR"))
