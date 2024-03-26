import bpy
import re
import math
from bpy.types import Armature, Context, Operator, PoseBone, Panel
from mathutils import Matrix, Vector

class ArmatureSupport:
    def __init__(self, armature):
        self.armature = armature
    
    def edit_mode(self, func):
        prevmode = self.armature.mode
        if prevmode != 'EDIT':
            bpy.ops.object.mode_set(mode = 'EDIT')
        try:
            func()
        finally:
            if prevmode != self.armature.mode:
                bpy.ops.object.mode_set(mode = prevmode)
    
    def get_edit_bone(self, bonename, create = False):
        edit_bones = self.armature.data.edit_bones
        bone = edit_bones.get(bonename)
        if bone is None and create:
            bone = edit_bones.new(bonename)
        return bone
    
    def get_pose_bone(self, bonename):
        return self.armature.pose.bones.get(bonename)
    
    def get_bone(self, bonename):
        return self.armature.data.bones.get(bonename)
    
    def get_bone_constraint(self, bonename, type, name):
        b = self.armature.pose.bones[bonename]
        c = next((c for c in b.constraints if c.name == name), None)
        if c is None:
            c = b.constraints.new(type)
            c.name = name
        return c

class FingerCtrl:
    bone_pattern = re.compile("^(Thumb|Index|Middle|Ring|Little)(1|2|3)_(L|R)$")

    def __init__(self, armature, side, finger, bending_axis):
        self.armature = ArmatureSupport(armature)
        self.bonename1 = f"{finger}1_{side}"
        self.bonename2 = f"{finger}2_{side}"
        self.bonename3 = f"{finger}3_{side}"
        self.hand_bonename = f"Hand_{side}"
        self.ctrl_bonename = f"{finger}Rig_{side}"
        self.bending_axis = bending_axis
    
    def new_bones(self):
        bone = self.armature.get_edit_bone(self.ctrl_bonename, True)
        bone.head = self.armature.get_edit_bone(self.bonename1).head
        bone.tail = self.armature.get_edit_bone(self.bonename3).tail
        bone.parent = self.armature.get_edit_bone(self.hand_bonename)

    def rotation_follow(self, follower, followed):
        c = self.armature.get_bone_constraint(follower, 'COPY_ROTATION', 'VRMRIG_RotationFollow')
        c.target = self.armature.armature
        c.subtarget = followed
        c.target_space = 'LOCAL'
        c.owner_space = 'LOCAL'
    
    def limit_ctrl_scale(self):
        c = self.armature.get_bone_constraint(self.ctrl_bonename, 'LIMIT_SCALE', 'VRMRIG_LimitScale')
        c.use_min_x = c.use_min_y = c.use_min_z = True
        c.use_max_x = c.use_max_y = c.use_max_z = True
        c.min_y = 0
        c.min_x = c.min_z = 1
        c.max_x = c.max_z = c.max_y = 1
        c.owner_space = 'LOCAL'
    
    def rotation_driver(self, bonename, axis):
        index  = {'X':1, '-X':1, 'Y':2, '-Y':2, 'Z':3, '-Z':3}[axis]
        bone = self.armature.get_pose_bone(bonename)
        bone.driver_remove('rotation_quaternion', index)
        drv = bone.driver_add('rotation_quaternion', index).driver
        drv.type = 'SCRIPTED'
        drv.expression = 'var - 1' if axis.startswith('-') else '1 - var'
        var = drv.variables.new()
        var.name = "var"
        var.type = 'TRANSFORMS'
        t = var.targets[0]
        t.id = self.armature.armature
        t.bone_target = self.ctrl_bonename
        t.transform_type = 'SCALE_Y'
        t.transform_space = 'LOCAL_SPACE'
    
    def set_bone_layer(self, bonenames, layer):
        layers = [i == layer for i in range(32)]
        for bonename in bonenames:
            self.armature.get_bone(bonename).layers = layers.copy()
    
    def generate(self):
        self.armature.edit_mode(self.new_bones)
        self.rotation_follow(self.bonename3, self.bonename2)
        self.rotation_follow(self.bonename1, self.ctrl_bonename)
        self.rotation_driver(self.bonename2, self.bending_axis)
        self.limit_ctrl_scale()
        self.set_bone_layer([self.bonename1, self.bonename2, self.bonename3], 1)


class LimbsCtrl:
    def __init__(self, armature, side):
        self.armature = ArmatureSupport(armature)
        self.root_bonename = 'Root'
        self.hand_bonename = f"Hand_{side}"
        self.lowerarm_bonename = f"LowerArm_{side}"
        self.armik_bonename = f"ArmIK_{side}"
        self.armpole_bonename = f"ArmPole_{side}"
        self.lowerleg_bonename = f"LowerLeg_{side}"
        self.legik_bonename = f"LegIK_{side}"
        self.legpole_bonename = f"LegPole_{side}"
    
    def new_bones(self):
        root = self.armature.get_edit_bone(self.root_bonename)
        lowerarm = self.armature.get_edit_bone(self.lowerarm_bonename)
        lowerleg = self.armature.get_edit_bone(self.lowerleg_bonename)

        bone = self.armature.get_edit_bone(self.armik_bonename, True)
        bone.head = lowerarm.tail
        bone.tail = bone.head + Vector((0.12, 0, 0))
        bone.parent = root

        bone = self.armature.get_edit_bone(self.armpole_bonename, True)
        bone.head = lowerarm.head + Vector((0, 0.24, 0))
        bone.tail = bone.head + Vector((0, 0.12, 0))
        bone.parent = root

        bone = self.armature.get_edit_bone(self.legik_bonename, True)
        bone.head = lowerleg.tail
        bone.tail = bone.head + Vector((0.12, 0, 0))
        bone.parent = root

        bone = self.armature.get_edit_bone(self.legpole_bonename, True)
        bone.head = lowerleg.head - Vector((0, 0.24, 0))
        bone.tail = bone.head - Vector((0, 0.12, 0))
        bone.parent = root
    
    def hand_transforms_follow(self):
        c = self.armature.get_bone_constraint(self.hand_bonename, 'COPY_TRANSFORMS', 'VRMRIG_TransformsFollow')
        c.target = self.armature.armature
        c.subtarget = self.armik_bonename
        c.target_space = 'LOCAL'
        c.owner_space = 'LOCAL'

    def ik(self, bonename, ik_bonename, pole_bonename, pole_angle, constraint_name):
        c = self.armature.get_bone_constraint(bonename, 'IK', constraint_name)
        c.target = self.armature.armature
        c.subtarget = ik_bonename
        c.pole_target = self.armature.armature
        c.pole_subtarget = pole_bonename
        c.chain_count = 2
        c.pole_angle = math.radians(pole_angle)
    
    def generate(self):
        self.armature.edit_mode(self.new_bones)
        self.hand_transforms_follow()
        self.ik(self.lowerarm_bonename, self.armik_bonename, self.armpole_bonename, 180, 'VRMRIG_ArmIK')
        self.ik(self.lowerleg_bonename, self.legik_bonename, self.legpole_bonename, -90, 'VRMRIG_LegIK')


class VRMRIG_AddCtrlOperator(bpy.types.Operator):
    bl_idname = "vrmrig.addctrl"
    bl_label = "Add Controller"
    bl_description = "VRMRIG: Add Controller Operator"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        for side in ['L', 'R']:
            LimbsCtrl(armature, side).generate()
            FingerCtrl(armature, side, 'Thumb', 'Z').generate()
            FingerCtrl(armature, side, 'Index', 'X').generate()
            FingerCtrl(armature, side, 'Middle', 'X').generate()
            FingerCtrl(armature, side, 'Ring', 'X').generate()
            FingerCtrl(armature, side, 'Little', 'X').generate()
        return {'FINISHED'}

class VRMRIG_Panel(bpy.types.Panel):
    bl_label = "VRMRIG"
    bl_idname = "VRMRIG_PT"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRMRIG"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("vrmrig.addctrl")


def register():
    bpy.utils.register_class(VRMRIG_AddCtrlOperator)
    bpy.utils.register_class(VRMRIG_Panel)


def unregister():
    bpy.utils.unregister_class(VRMRIG_Panel)
    bpy.utils.unregister_class(VRMRIG_AddCtrlOperator)


if __name__ == "__main__":
    register()