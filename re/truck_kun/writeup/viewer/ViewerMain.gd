extends Node3D
## Mounts a DISTRIBUTED game binary's resource pack and instantiates one
## of its scenes live, so you can fly around and look at the actual
## geometry in the actual engine -- no decompilation, no custom
## rendering code.

@export var start_position := Vector3(0, 80, 40)

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("usage: godot4 --path <this project> -- <binary_or_pck> [res://scene.tscn]")
		get_tree().quit(1)
		return

	var pck_path: String = args[0]
	var scene_path: String = "res://scenes/Main.tscn" if args.size() < 2 else args[1]

	var ok := ProjectSettings.load_resource_pack(pck_path)
	print("load_resource_pack(", pck_path, ") -> ", ok)
	if not ok:
		push_error("failed to mount '%s' -- is that really an exported Godot binary/pck?" % pck_path)
		get_tree().quit(1)
		return

	var packed := load(scene_path)
	if packed == null:
		push_error("failed to load '%s' from the mounted pack" % scene_path)
		get_tree().quit(1)
		return

	var target: Node = packed.instantiate()

	# WorldEnvironment's procedural sky needs a real GPU reflection bake;
	# under a plain/headless renderer that bake can hang indefinitely.
	# It's purely cosmetic for the purpose of inspecting geometry, so we
	# strip it rather than risk a hang -- everything else (meshes,
	# collisions, gameplay scripts) is untouched.
	var stripped := _strip_world_environment(target)
	if stripped > 0:
		print("stripped ", stripped, " WorldEnvironment node(s) (cosmetic only; avoids a headless GPU-reflection hang)")

	add_child(target)

	var cam := Camera3D.new()
	cam.set_script(load("res://ViewerFreeCamera.gd"))
	cam.position = start_position
	cam.rotation_degrees = Vector3(-35, 0, 0)
	add_child(cam)

	print("Flying camera active: WASD move, mouse look, Q/E down/up, Shift boost, Esc releases mouse.")
	print("The map's own gameplay logic (NPCs, truck physics, etc) may also be")
	print("running since we instantiated the real scene -- harmless noise, ignore")
	print("any InputMap warnings from the truck (this project doesn't define its")
	print("input actions, and doesn't need to).")

func _strip_world_environment(node: Node) -> int:
	var removed := 0
	for child in node.get_children():
		removed += _strip_world_environment(child)
	if node is WorldEnvironment:
		node.get_parent().remove_child(node)
		node.queue_free()
		removed += 1
	return removed
