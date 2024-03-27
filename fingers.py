import bpy
from bpy.types import Object, Armature
from .utils import BoneHolder

def generate_finger_controller(obj:Object, finger:str, side:str, bending_axis:str):
    if obj is None or obj.type != 'ARMATURE':
        raise TypeError("expected a obj type of ARMATURE")
    
    armature = Armature(obj.data)

    bone1 = BoneHolder(obj, f"{finger}1_{side}")
    bone2 = BoneHolder(obj, f"{finger}2_{side}")
    bone3 = BoneHolder(obj, f"{finger}3_{side}")
    hand = BoneHolder(obj, f"Hand_{side}")
    ctrl = BoneHolder(obj, f"{finger}Ctrl_{side}", True)

    for b in [bone1, bone2, bone3, hand]:
        if b.bone() is None:
            raise AssertionError(f"missing bone '{b.name}'")

    # enter edit mode, create control bone if neccessary
    prevmode = armature.mode
    bpy.ops.object.mode_set(mode = 'EDIT')
    try:
        b = ctrl.edit(True)
        b.head = bone1.edit().head
        b.tail = b.head + (bone3.tail - bone1.head) * 1.5
        b.parent = hand.edit()
    finally:
        bpy.ops.object.mode_set(mode = prevmode)
    
    # add rotation constraints
    def rotation_follow(bone1:BoneHolder, bone2:BoneHolder):
        bone1.constraint(
            'VRMAUTO_BendingFollow', 'COPY_ROTATION',
            target = armature,
            subtarget = bone2.name,
            target_space = 'LOCAL',
            owner_space = 'LOCAL',
        )
    rotation_follow(bone3, bone2)
    rotation_follow(bone1, ctrl)

    # limit scale of control bone
    def limit_scale(bone:BoneHolder):
        c = bone.constraint('VRMAUTO_ScaleLimit', 'LIMIT_SCALE', owner_space = 'LOCAL')
        c.use_min_x = c.use_min_y = c.use_min_z = True
        c.use_max_x = c.use_max_y = c.use_max_z = True
        c.max_x = c.max_z = c.max_y = 1
        c.min_x = c.min_z = 1
        c.min_y = 0.5
    limit_scale(ctrl)

    # add rotation driver
    def rotation_driver(bone:BoneHolder, axis:str):
        index  = {'X':1, '-X':1, 'Y':2, '-Y':2, 'Z':3, '-Z':3}[axis]
        b = bone.pose()
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
        t.bone_target = ctrl.name
        t.transform_type = 'SCALE_Y'
        t.transform_space = 'LOCAL_SPACE'
    rotation_driver(bone2, bending_axis)

    # move original finger bones to another layer
    for b in [bone1, bone2, bone3]:
        b.set_layer(1)

