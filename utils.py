from bpy.types import Object, Armature, Bone, EditBone, PoseBone, Constraint

class BoneHolder:
    def __init__(self, obj:Object, name:str):
        self.obj = obj
        self.armature = Armature(obj.data)
        self.name = name
    
    def bone(self) -> Bone|None:
        return self.armature.bones[self.name]
    
    def edit(self, auto_create:bool = False) -> EditBone|None:
        b = self.armature.edit_bones.get(self.name)
        if b == None and auto_create:
            b = self.armature.edit_bones.new(self.name)
        return b
    
    def pose(self) -> PoseBone|None:
        return self.obj.pose.bones.get(self.name)
    
    def constraint(self, name:str, type:str, **props) -> Constraint:
        b = self.pose()
        c = next((c for c in b.constraints if c.name == name), None)
        if c is None:
            c = b.constraints.new(type)
            c.name = name
        for k, v in props.items():
            c[k] = v
        return c
    
    def set_layer(self, layer) -> None:
        self.bone().layers = [i == layer for i in range(32)]