import bpy
import re
import math
from bpy.types import Armature, Context, Operator, PoseBone, Panel
from mathutils import Matrix, Vector

class ArmatureSupport:
    def __init__(self, armature:Armature):
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
    
    def get_bone_constraint(self, bonename, type, name):
        b = self.armature.pose.bones[bonename]
        c = next((c for c in b.constraints if c.name == name), None)
        if c is None:
            c = b.constraints.new(type)
            c.name = name
        return c
    
    def set_bone_layer(self, bonenames, layer):
        layers = [i == layer for i in range(32)]
        for bonename in bonenames:
            self.armature.data.bones[bonename].layers = layers.copy()

class FingerCtrl:
    def __init__(self, armature, side, finger, bending_axis):
        self.armature = ArmatureSupport(armature)
        self.bone1 = f"{finger}1_{side}"
        self.bone2 = f"{finger}2_{side}"
        self.bone3 = f"{finger}3_{side}"
        self.hand = f"Hand_{side}"
        self.ctrl = f"{finger}Ctrl_{side}"
        self.bending_axis = bending_axis
    
    def new_bones(self):
        bone1 = self.armature.get_edit_bone(self.bone1)
        bone3 = self.armature.get_edit_bone(self.bone3)
        bone = self.armature.get_edit_bone(self.ctrl, True)
        bone.head = bone1.head
        bone.tail = bone.head + (bone3.tail - bone1.head) * 1.5
        bone.parent = self.armature.get_edit_bone(self.hand)

    def rotation_follow(self, follower, followed):
        c = self.armature.get_bone_constraint(follower, 'COPY_ROTATION', 'VRMRIG_RotationFollow')
        c.target = self.armature.armature
        c.subtarget = followed
        c.target_space = 'LOCAL'
        c.owner_space = 'LOCAL'
    
    def limit_ctrl_scale(self):
        c = self.armature.get_bone_constraint(self.ctrl, 'LIMIT_SCALE', 'VRMRIG_LimitScale')
        c.use_min_x = c.use_min_y = c.use_min_z = True
        c.use_max_x = c.use_max_y = c.use_max_z = True
        c.min_x = c.min_z = 1
        c.max_x = c.max_z = c.max_y = 1
        c.min_y = 0.5
        c.owner_space = 'LOCAL'
    
    def rotation_driver(self, bonename, axis):
        index  = {'X':1, '-X':1, 'Y':2, '-Y':2, 'Z':3, '-Z':3}[axis]
        bone = self.armature.armature.pose.bones[bonename]
        bone.driver_remove('rotation_quaternion', index)
        drv = bone.driver_add('rotation_quaternion', index).driver
        drv.type = 'SCRIPTED'
        drv.expression = '(var - 1) * 2'
        if axis.startswith('-'):
            drv.expression = '-' + drv.expression
        var = drv.variables.new()
        var.name = "var"
        var.type = 'TRANSFORMS'
        t = var.targets[0]
        t.id = self.armature.armature
        t.bone_target = self.ctrl
        t.transform_type = 'SCALE_Y'
        t.transform_space = 'LOCAL_SPACE'
    
    def generate(self):
        self.armature.edit_mode(self.new_bones)
        self.rotation_follow(self.bone3, self.bone2)
        self.rotation_follow(self.bone1, self.ctrl)
        self.rotation_driver(self.bone2, self.bending_axis)
        self.limit_ctrl_scale()
        self.armature.set_bone_layer([self.bone1, self.bone2, self.bone3], 1)


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
        bone.tail = bone.head + Vector((0, 0.12, 0))
        bone.parent = root

        bone = self.armature.get_edit_bone(self.armpole_bonename, True)
        bone.head = lowerarm.head + Vector((0, 0.24, 0))
        bone.tail = bone.head + Vector((0, 0.12, 0))
        bone.parent = root

        bone = self.armature.get_edit_bone(self.legik_bonename, True)
        bone.head = lowerleg.tail
        bone.tail = bone.head + Vector((0, 0.12, 0))
        bone.parent = root

        bone = self.armature.get_edit_bone(self.legpole_bonename, True)
        bone.head = lowerleg.head - Vector((0, 0.24, 0))
        bone.tail = bone.head - Vector((0, 0.12, 0))
        bone.parent = root

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
        
        arm = self.armature.armature.data.bones[self.lowerarm_bonename]
        dir = (arm.tail - arm.head).to_2d().cross(Vector((0, 1)))
        self.ik(self.lowerarm_bonename, self.armik_bonename, self.armpole_bonename, 180 if dir > 0 else 0, 'VRMRIG_ArmIK')
        self.ik(self.lowerleg_bonename, self.legik_bonename, self.legpole_bonename, -90, 'VRMRIG_LegIK')

class SpringBone:
    def __init__(self, armature, bone_pattern):
        self.armature = ArmatureSupport(armature)
        self.bone_pattern = re.compile(bone_pattern)
    
    def enable(self):
        for bonename, bone in self.armature.armature.pose.bones.items():
            if self.bone_pattern.match(bonename) is None:
                continue
            bone.sb_bone_spring = True
            bone.sb_bone_rot = True
            bone.sb_stiffness = 0.3
            bone.sb_gravity = 0
            bone.sb_damp = 0.5

class ArmTwist:
    def __init__(self, armature, side):
        self.armature = ArmatureSupport(armature)
        self.hand = f"Hand_{side}"
        self.arm = f"LowerArm_{side}"
        self.subarms = [f"LowerArm{n+1}_{side}" for n in range(3)]
    
    def new_bones(self):
        arm = self.armature.get_edit_bone(self.arm)
        v = (arm.tail - arm.head) / len(self.subarms)
        for i, name in enumerate(self.subarms):
            bone = self.armature.get_edit_bone(name, True)
            bone.head = arm.head + i * v
            bone.tail = bone.head + v
            bone.parent = arm
            bone.use_deform = True
    
    def rotation_follow(self, follower, followed, influence):
        c = self.armature.get_bone_constraint(follower, 'COPY_ROTATION', 'VRMRIG_ArmTwistFollow')
        c.target = self.armature.armature
        c.subtarget = followed
        c.use_x = c.use_z = False
        c.target_space = 'LOCAL'
        c.owner_space = 'LOCAL'
        c.influence = influence
    
    def generate(self):
        self.armature.edit_mode(self.new_bones)
        
        followed = self.subarms[1:] + [self.hand]
        for i, n in enumerate(self.subarms):
            influcence = (i + 1) * (0.9 / len(self.subarms))
            self.rotation_follow(n, followed[i], influcence)
        
        self.armature.armature.data.bones[self.arm].use_deform = False
        
        prevmode = self.armature.armature.mode
        prevactive = bpy.context.view_layer.objects.active
        try:
            for mesh in bpy.data.objects:
                if mesh.type != 'MESH' or mesh.parent != self.armature.armature:
                    continue
                bpy.context.view_layer.objects.active = mesh
                
                vg = mesh.vertex_groups.get(self.arm)
                if vg != None:
                    mesh.vertex_groups.remove(vg)
                
                bones = self.armature.armature.data.bones
                bpy.ops.object.mode_set(mode = 'WEIGHT_PAINT')
                prevselect = { b.name: b.select for b in bones }
                for n in self.subarms:
                    bones[n].select = True
                bpy.ops.paint.weight_from_bones(type = 'AUTOMATIC')
                for n, s in prevselect.items():
                    bones[n].select = s
        finally:
            bpy.ops.object.mode_set(mode = prevmode)
            bpy.context.view_layer.objects.active = prevactive
        
        self.armature.set_bone_layer(self.subarms, 1)

class ShoulderCtrl:
    def __init__(self, armature, side):
        self.armature = ArmatureSupport(armature)
        self.hand = f"Hand_{side}"
        self.arm = f"LowerArm_{side}"
        self.shoulder = f"Shoulder_{side}"
        self.twist = f"ShoulderTwist_{side}"
        self.ctrl = f"ShoulderCtrl_{side}"
    
    def new_bones(self):
        shoulder = self.armature.get_edit_bone(self.shoulder)
        arm = self.armature.get_edit_bone(self.arm)
        hand = self.armature.get_edit_bone(self.hand)

        twist = self.armature.get_edit_bone(self.twist, True)
        twist.head = shoulder.head
        twist.tail = twist.head + (shoulder.tail - shoulder.head) * 0.7
        twist.parent = shoulder.parent
        shoulder.parent = twist

        ctrl = self.armature.get_edit_bone(self.ctrl, True)
        ctrl.head = shoulder.tail + (shoulder.tail - shoulder.head).normalized() * (arm.head - shoulder.tail).length
        ctrl.tail = ctrl.head + Vector((0, 0.12, 0))
        ctrl.parent = hand
    
    def damped_follow(self, follower, followed, influence):
        c = self.armature.get_bone_constraint(follower, 'DAMPED_TRACK', 'VRMRIG_ShoulderFollow')
        c.target = self.armature.armature
        c.subtarget = followed
        c.track_axis = 'TRACK_Y'
        c.influence = influence
        
    def generate(self):
        self.armature.edit_mode(self.new_bones)
        self.damped_follow(self.twist, self.ctrl, 0.5)
        

class VRMRIG_FixArmTwist(bpy.types.Operator):
    bl_idname = "vrmrig.fix_arm_twist"
    bl_label = "Fix arm twist"
    bl_description = "VRMRIG: Fix arm twist"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        ArmTwist(armature, 'L').generate()
        ArmTwist(armature, 'R').generate()
        return {'FINISHED'}

class VRMRIG_AddShoulderControllerOperator(bpy.types.Operator):
    bl_idname = "vrmrig.add_shoulder_ctrl"
    bl_label = "Add shoulder controller"
    bl_description = "VRMRIG: Add shoulder controller"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        ShoulderCtrl(armature, 'L').generate()
        ShoulderCtrl(armature, 'R').generate()
        return {'FINISHED'}

class VRMRIG_AddControllerOperator(bpy.types.Operator):
    bl_idname = "vrmrig.add_controller"
    bl_label = "Add Controller"
    bl_description = "VRMRIG: Add Controller Operator"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        LimbsCtrl(armature, 'L').generate()
        LimbsCtrl(armature, 'R').generate()
        FingerCtrl(armature, 'L', 'Thumb', '-Z').generate()
        FingerCtrl(armature, 'R', 'Thumb', 'Z').generate()
        FingerCtrl(armature, 'L', 'Index', 'X').generate()
        FingerCtrl(armature, 'R', 'Index', 'X').generate()
        FingerCtrl(armature, 'L', 'Middle', 'X').generate()
        FingerCtrl(armature, 'R', 'Middle', 'X').generate()
        FingerCtrl(armature, 'L', 'Ring', 'X').generate()
        FingerCtrl(armature, 'R', 'Ring', 'X').generate()
        FingerCtrl(armature, 'L', 'Little', 'X').generate()
        FingerCtrl(armature, 'R', 'Little', 'X').generate()
        return {'FINISHED'}

class VRMRIG_EnableSpringBoneOperator(bpy.types.Operator):
    bl_idname = "vrmrig.enable_spring_bone"
    bl_label = "Enable spring bone"
    bl_description = "VRMRIG: Enable hair spring bone"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        SpringBone(armature, "^(Hair|Bust)\\d+_(L|R|\d+)$").enable()
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
        row.operator("vrmrig.add_controller")
        row = layout.row()
        row.operator("vrmrig.enable_spring_bone")
        row = layout.row()
        row.operator("vrmrig.fix_arm_twist")
        row = layout.row()
        row.operator("vrmrig.add_shoulder_ctrl")


def register():
    bpy.utils.register_class(VRMRIG_AddControllerOperator)
    bpy.utils.register_class(VRMRIG_EnableSpringBoneOperator)
    bpy.utils.register_class(VRMRIG_FixArmTwist)
    bpy.utils.register_class(VRMRIG_AddShoulderControllerOperator)
    bpy.utils.register_class(VRMRIG_Panel)


def unregister():
    bpy.utils.unregister_class(VRMRIG_Panel)
    bpy.utils.unregister_class(VRMRIG_AddShoulderControllerOperator)
    bpy.utils.unregister_class(VRMRIG_FixArmTwist)
    bpy.utils.unregister_class(VRMRIG_EnableSpringBoneOperator)
    bpy.utils.unregister_class(VRMRIG_AddControllerOperator)


if __name__ == "__main__":
    register()