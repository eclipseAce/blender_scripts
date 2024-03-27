import bpy
from bpy.types import Object, Armature
from .utils import BoneHolder

def generate_limbs_ik(obj:Object, finger:str, side:str, bending_axis:str)