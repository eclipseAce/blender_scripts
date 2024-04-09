import bpy
import math
import re
from typing import List
from bpy.types import Object, Armature, PoseBone, Constraint, Collection, LimitRotationConstraint
from mathutils import Vector, Euler, Quaternion

def get_armature(obj:Object) -> Armature:
    if obj is None or obj.type != 'ARMATURE':
        raise TypeError("expected a obj type of ARMATURE")
    return obj.data

def add_constraint(b:Object|PoseBone, name:str, type:str, **props) -> Constraint:
    c = next((c for c in b.constraints if c.name == name), None)
    if c is None:
        c = b.constraints.new(type)
        c.name = name
    for k, v in props.items():
        c.__setattr__(k, v)
    return c

def disable_rotation(b:Object|PoseBone) -> Constraint:
    c:LimitRotationConstraint = add_constraint(b, 'VRMAUTO_DisableRotation', 'LIMIT_ROTATION')
    c.use_limit_x = c.use_limit_y = c.use_limit_z = True
    c.max_x = c.max_y = c.max_z = c.min_x = c.min_y = c.min_z = 0

def set_bone_layer(armature:Armature, layer:int, *names) -> None:
    for n in names:
        armature.bones[n].layers = [i == layer for i in range(32)]

def get_bone_shape_collection() -> Collection:
    coll = bpy.data.collections.get("VRMAUTO")
    if coll == None:
        coll = bpy.data.collections.new("VRMAUTO")
        bpy.context.scene.collection.children.link(coll)
        coll.hide_select = True
        coll.hide_viewport = True
        coll.hide_render = True
        bpy.context.view_layer.layer_collection.children["VRMAUTO"].exclude = True
    return coll

def get_bone_shape(name:str, verts:List, edges:List) -> Object:
    obj = bpy.data.objects.get(name)
    if obj == None:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        coll = get_bone_shape_collection()
        coll.objects.link(obj)
    return obj

def get_finger_bone_shape() -> Object:
    return get_bone_shape(
        "VRMAUTO_FingerBoneShape",
        [ (0, 0, 0), (0, 0.9, 0), (-0.05, 0.9, 0), (-0.05, 1, 0), (0.05, 1, 0), (0.05, 0.9, 0) ],
        [ (0, 1), (2, 3), (3, 4), (4, 5), (5, 2) ],
    )

def get_hand_bone_shape() -> Object:
    return get_bone_shape(
        "VRMAUTO_HandBoneShape",
        [ (0.66, 1, 0), (0.66, 0, 0), (-0.66, 0, 0), (-0.66, 1, 0) ],
        [ (0, 1), (1, 2), (2, 3), (3, 0) ],
    )

def get_pole_bone_shape() -> Object:
    name = "VRMAUTO_PoleBoneShape"
    obj = bpy.data.objects.get(name)
    if obj == None:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_size = 0.5
        obj.empty_display_type = 'PLAIN_AXES'
    return obj

def get_leg_ik_bone_shape() -> Object:
    name = "VRMAUTO_LegIKBoneShape"
    obj = bpy.data.objects.get(name)
    if obj == None:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_size = 0.25
        obj.empty_display_type = 'CUBE'
    return obj

def get_root_bone_shape() -> Object:
    return get_bone_shape(
        "VRMAUTO_RootBoneShape",
        [
            (0.3, 0, 0.5), (0.5, 0, 0.5), (0.5, 0, 0.3),
            (-0.3, 0, -0.5), (-0.5, 0, -0.5), (-0.5, 0, -0.3),
            (-0.3, 0, 0.5), (-0.5, 0, 0.5), (-0.5, 0, 0.3),
            (0.3, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, -0.3),
        ],
        [
            (0, 1), (1, 2),
            (3, 4), (4, 5),
            (6, 7), (7, 8),
            (9, 10), (10, 11),
        ],
    )

def symmetrize_bone_names(obj:Object):
    armature:Armature = get_armature(obj)

    left_pattern = re.compile("^J_(Adj|Bip|Opt|Sec)_L_")
    right_pattern = re.compile("^J_(Adj|Bip|Opt|Sec)_R_")
    full_pattern = re.compile("^J_(Adj|Bip|Opt|Sec)_([CLR]_)?")

    prevmode = obj.mode
    bpy.ops.object.mode_set(mode = 'EDIT')
    try:
        for bone_name, bone in armature.bones.items():
            left = left_pattern.sub("", bone_name)
            if left != bone_name:
                bone.name = left + "_L"
                continue

            right = right_pattern.sub("", bone_name)
            if right != bone_name:
                bone.name = right + "_R"
                continue

            a = full_pattern.sub("", bone_name)
            if a != bone_name:
                bone.name = a
                continue
    finally:
        bpy.ops.object.mode_set(mode = prevmode)

def gen_finger_ctrl(obj:Object, finger:str, side:str, bending_axis:str):
    armature:Armature = get_armature(obj)

    bone1_name = f"{finger}1_{side}"
    bone2_name = f"{finger}2_{side}"
    bone3_name = f"{finger}3_{side}"
    hand_name = f"Hand_{side}"
    ctrl_name = f"{finger}Ctrl_{side}"

    # get or create finger bone shape object
    bone_shape = get_finger_bone_shape()

    # check bones integrity
    for n in [bone1_name, bone2_name, bone3_name, hand_name]:
        if armature.bones.get(n) is None:
            raise AssertionError(f"missing bone '{n}'")
    
    # edit bones
    def edit_bones():
        prevmode = obj.mode
        bpy.ops.object.mode_set(mode = 'EDIT')
        try:
            bones = armature.edit_bones
            ctrl = bones.get(ctrl_name) or bones.new(ctrl_name)
            ctrl.head = bones[bone1_name].head
            ctrl.tail = ctrl.head + (bones[bone3_name].tail - bones[bone1_name].head) * 1.5
            ctrl.parent = bones[hand_name]
        finally:
            bpy.ops.object.mode_set(mode = prevmode)
        
        pbone:PoseBone = obj.pose.bones[ctrl_name]
        pbone.custom_shape = bone_shape
        if bending_axis in ['-Z', 'Z']:
            pbone.custom_shape_rotation_euler = Euler((0, 1, 0))
        else:
            pbone.custom_shape_rotation_euler = Euler((0, 0, 0))
    edit_bones()
    
    # add rotation constraints
    def set_rotation_follow(bname1, bname2):
        add_constraint(
            obj.pose.bones[bname1], 'VRMAUTO_BendingFollow', 'COPY_ROTATION',
            target = obj,
            subtarget = bname2,
            target_space = 'LOCAL',
            owner_space = 'LOCAL',
        )
    set_rotation_follow(bone3_name, bone2_name)
    set_rotation_follow(bone1_name, ctrl_name)

    # limit scale of control bone
    def set_limit_scale(bname):
        c = add_constraint(
            obj.pose.bones[bname], 'VRMAUTO_ScaleLimit', 'LIMIT_SCALE',
            owner_space = 'LOCAL'
        )
        c.use_min_x = c.use_min_y = c.use_min_z = True
        c.use_max_x = c.use_max_y = c.use_max_z = True
        c.max_x = c.max_z = c.max_y = 1
        c.min_x = c.min_z = 1
        c.min_y = 0.5
    set_limit_scale(ctrl_name)

    # add rotation driver
    def set_rotation_driver(bname, axis):
        index  = {'X':1, '-X':1, 'Y':2, '-Y':2, 'Z':3, '-Z':3}[axis]
        b = obj.pose.bones[bname]
        b.driver_remove('rotation_quaternion', index)
        drv = b.driver_add('rotation_quaternion', index).driver
        drv.type = 'SCRIPTED'
        drv.expression = '(var - 1) * 2'
        if axis.startswith('-'):
            drv.expression = '-' + drv.expression
        var = drv.variables.new()
        var.name = "var"
        var.type = 'TRANSFORMS'
        t = var.targets[0]
        t.id = obj
        t.bone_target = ctrl_name
        t.transform_type = 'SCALE_Y'
        t.transform_space = 'LOCAL_SPACE'
    set_rotation_driver(bone2_name, bending_axis)

    # move original finger bones to another layer
    set_bone_layer(armature, 1, bone1_name, bone2_name, bone3_name)

def gen_limbs_ik(obj:Object, kind:str, side:str):
    armature:Armature = get_armature(obj)

    root_name = "Root"
    upper_name = f"Upper{kind}_{side}"
    lower_name = f"Lower{kind}_{side}"
    ik_name = f"{kind}IK_{side}"
    pole_name = f"{kind}Pole_{side}"

    for n in [root_name, upper_name, lower_name]:
        if armature.bones.get(n) is None:
            raise AssertionError(f"missing bone '{n}'")
    
    def is_left() -> bool:
        return armature.bones[lower_name].vector.to_2d().cross(Vector((0, 1))) > 0

    def edit_bones():
        prevmode = obj.mode
        bpy.ops.object.mode_set(mode = 'EDIT')
        try:
            bones = armature.edit_bones
            root, upper, lower = (bones[n] for n in [root_name, upper_name, lower_name])
            ik, pole = (bones.get(n) or bones.new(n) for n in [ik_name, pole_name])

            ik_size = 0.24 # default hand length
            if kind == 'Arm':
                # determin hand length by finding closest finger
                finger_names = [f"{n}1_{side}" for n in ['Index', 'Middle', 'Ring', 'Little']]
                finger_bones = [b for b in [bones.get(n) for n in finger_names] if b != None]
                if len(finger_bones) > 0:
                    ik_size = min([(b.head - lower.tail).length for b in finger_bones])

            ik.head = lower.tail
            ik.tail = ik.head + lower.vector.normalized() * ik_size

            # determin arm pole by the angle between upper and lower arms, they must not be in parallel
            base_v = Vector((-1 if is_left() else 1, 0, 0))
            if kind == 'Leg':
                base_v = Vector((0, 0, 1))
            pole_v:Vector = upper.vector.cross(lower.vector)
            if pole_v.length == 0:
                raise AssertionError(f"bone '{upper_name}' and '{lower_name}' bone are in parallel")
            pole_v.rotate(Quaternion(base_v, math.radians(90)))
            pole_v.rotate(base_v.rotation_difference(lower.tail - upper.head))
            pole_v.normalize()

            # pole is 1.1 times length of upper bone away from joint, and the size is hardcoded as 0.12
            pole.head = lower.head + pole_v * (upper.vector.length * 1.1) 
            pole.tail = pole.head + pole_v * 0.12
            ik.parent = pole.parent = root
        finally:
            bpy.ops.object.mode_set(mode = prevmode)
    edit_bones()

    # change pole bone shape
    pole_pbone:PoseBone = obj.pose.bones[pole_name]
    pole_pbone.custom_shape = get_pole_bone_shape()
    disable_rotation(pole_pbone)

    # set ik
    def set_ik():
        c = add_constraint(
            obj.pose.bones[lower_name], 'VRMAUTO_ArmIK', 'IK',
            target = obj,
            subtarget = ik_name,
            pole_target = obj,
            pole_subtarget = pole_name,
            chain_count = 2,
        )
        if kind == 'Arm':
            c.pole_angle = math.radians(-90)
        else:
            c.pole_angle = math.radians(90)
    set_ik()
    
    if kind == 'Arm':
        # set hand bone follows arm ik bone
        hand_name = f"Hand_{side}"
        add_constraint(
            obj.pose.bones[hand_name], 'VRAMAUTO_FollowArmIK', 'COPY_TRANSFORMS',
            target = obj,
            subtarget = ik_name,
            target_space = 'LOCAL',
            owner_space = 'LOCAL',
        )

        # set original hand bone to layer 1
        set_bone_layer(armature, 1, hand_name)

        # change hand ik bone shape
        pbone:PoseBone = obj.pose.bones[ik_name]
        pbone.custom_shape = get_hand_bone_shape()

        # hand ik bone rotation limit ()
        # c:LimitRotationConstraint = add_constraint(pbone, 'VRMAUTO_HandRotationLimit', 'LIMIT_ROTATION')
        # c.use_limit_x = c.use_limit_z = True
        # c.min_x = math.radians(-80)
        # c.max_x = math.radians(80)
        # if is_left():
        #     c.min_z = math.radians(-10)
        #     c.max_z = math.radians(45)
        # else:
        #     c.min_z = math.radians(-45)
        #     c.max_z = math.radians(10)
        # c.owner_space = 'LOCAL'
    else:
        # change leg ik bone shape
        pbone:PoseBone = obj.pose.bones[ik_name]
        pbone.custom_shape = get_leg_ik_bone_shape()
        disable_rotation(pbone)

def fix_arm_twist(obj:Object, side:str):
    armature:Armature = get_armature(obj)

    hand_name = f"Hand_{side}"
    arm_name = f"LowerArm_{side}"
    subarm_names = [f"LowerArm{n+1}_{side}" for n in range(3)]

    # add sub arm bones
    def edit_bones():
        prevmode = obj.mode
        bpy.ops.object.mode_set(mode = 'EDIT')
        try:
            bones = armature.edit_bones
            arm = armature.edit_bones[arm_name]
            arm_v = (arm.tail - arm.head) / len(subarm_names)
            for i, name in enumerate(subarm_names):
                subarm = bones.get(name) or bones.new(name)
                subarm.use_deform = True
                subarm.head = arm.head + i * arm_v
                subarm.tail = subarm.head + arm_v
                subarm.parent = arm
        finally:
            bpy.ops.object.mode_set(mode = prevmode)
    edit_bones()

    # set rotation follow for each sub arm bone
    def set_rotation_follow(bname1, bname2, influence):
        add_constraint(
            obj.pose.bones[bname1], 'VRMAUTO_ArmTwistFollow', 'COPY_ROTATION',
            target = obj,
            subtarget = bname2,
            use_x = False,
            use_z = False,
            target_space = 'LOCAL',
            owner_space = 'LOCAL',
            influence = influence,
        )
    for i, n in enumerate(subarm_names):
        followed = hand_name if i == len(subarm_names) - 1 else subarm_names[i + 1]
        influcence = (i + 1) * (0.9 / len(subarm_names))
        set_rotation_follow(n, followed, influcence)
    
    # remove original arm bone weights, repaint for each sub arm bone
    def repaint_weight():
        prevmode = obj.mode
        prevactive = bpy.context.view_layer.objects.active
        try:
            for mesh in bpy.data.objects:
                if mesh.type != 'MESH' or mesh.parent != obj:
                    continue
                bpy.context.view_layer.objects.active = mesh
                
                vg = mesh.vertex_groups.get(arm_name)
                if vg != None:
                    mesh.vertex_groups.remove(vg)
                
                bpy.ops.object.mode_set(mode = 'WEIGHT_PAINT')
                prevselect = { b.name: b.select for b in armature.bones }
                try:
                    for n, b in armature.bones.items():
                        b.select = n in subarm_names
                    bpy.ops.paint.weight_from_bones(type = 'AUTOMATIC')
                finally:
                    for n, s in prevselect.items():
                        armature.bones[n].select = s
        finally:
            bpy.ops.object.mode_set(mode = prevmode)
            bpy.context.view_layer.objects.active = prevactive
    repaint_weight()

    # move sub arm bones to layer 1
    set_bone_layer(armature, 1, *subarm_names)

def change_root_bone_shape(obj:Object):
    armature:Armature = get_armature(obj)
    root_name = "Root"
    pbone:PoseBone = obj.pose.bones[root_name]
    pbone.custom_shape = get_root_bone_shape()

obj = bpy.context.active_object
if obj != None and obj.type == 'ARMATURE':
    symmetrize_bone_names(obj)

    change_root_bone_shape(obj)

    gen_finger_ctrl(obj, 'Thumb', 'L', '-Z')
    gen_finger_ctrl(obj, 'Thumb', 'R', 'Z')
    for side in ['L', 'R']:
        for finger in ['Index', 'Middle', 'Ring', 'Little']:
            gen_finger_ctrl(obj, finger, side, 'X')
        
        gen_limbs_ik(obj, 'Arm', side)
        gen_limbs_ik(obj, 'Leg', side)

        fix_arm_twist(obj, side)
