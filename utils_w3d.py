# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel
# Last Modification 08.2019
import os
import bpy
import bmesh

from mathutils import Vector, Quaternion

from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
from bpy_extras.image_utils import load_image

#######################################################################################
# helper methods
#######################################################################################


def InsensitiveOpen(path):
    # find the file on unix
    dir = os.path.dirname(path)
    name = os.path.basename(path)

    for filename in os.listdir(dir):
        if filename.lower() == name.lower():
            path = os.path.join(dir, filename)
            return open(path, "rb")


def InsensitivePath(path):
     # find the file on unix
    dir = os.path.dirname(path)
    name = os.path.basename(path)

    for filename in os.listdir(dir):
        if filename.lower() == name.lower():
            path = os.path.join(dir, filename)
    return path


def skip_unknown_chunk(self, file, chunkType, chunkSize):
    message = "WARNING: unknown chunktype in File: %s" % hex(chunkType)
    #self.report({'ERROR'}, message)
    print(message)
    file.seek(chunkSize, 1)


def link_object_to_active_scene(obj):
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

#######################################################################################
# create armature
#######################################################################################


def create_armature(self, hierarchy, amtName, subObjects):
    amt = bpy.data.armatures.new(hierarchy.header.name)
    amt.show_names = True

    rig = bpy.data.objects.new(amtName, amt)
    rig.location = hierarchy.header.center
    rig.rotation_mode = 'QUATERNION'
    #rig.show_x_ray = True
    rig.track_axis = "POS_X"

    link_object_to_active_scene(rig)
    bpy.ops.object.mode_set(mode='EDIT')

    non_bone_pivots = []

    mesh = bpy.data.meshes.new('Basic_Sphere')
    basic_sphere = bpy.data.objects.new("Basic_Sphere", mesh)

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, diameter=1)
    bm.to_mesh(mesh)
    bm.free()

    for obj in subObjects:
        non_bone_pivots.append(hierarchy.pivots[obj.boneIndex])

    # create the bones from the pivots
    for pivot in hierarchy.pivots:
        if non_bone_pivots.count(pivot) > 0:
            continue  # do not create a bone

        bone = amt.edit_bones.new(pivot.name)

        if pivot.parentID > 0:
            parent_pivot = hierarchy.pivots[pivot.parentID]
            bone.parent = amt.edit_bones[parent_pivot.name]

        bone.head = Vector((0.0, 0.0, 0.0))
        # has to point in y direction that the rotation is applied correctly
        bone.tail = Vector((0.0, 1.0, 0.0))

    # Pose the bones
    bpy.ops.object.mode_set(mode='POSE')

    for pivot in hierarchy.pivots:
        if non_bone_pivots.count(pivot) > 0:
            continue  # do not create a bone

        bone = rig.pose.bones[pivot.name]
        bone.location = pivot.position
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_euler = pivot.eulerAngles
        bone.rotation_quaternion = pivot.rotation

        bone.custom_shape = basic_sphere

    bpy.ops.object.mode_set(mode='OBJECT')

    return rig


#######################################################################################
# create material
#######################################################################################

def create_vert_material(mesh, vertMat):
    mat = bpy.data.materials.new(mesh.header.meshName + "." + vertMat.vmName)
    mat.use_nodes = True
    principled = PrincipledBSDFWrapper(mat, is_readonly=False)
    principled.base_color = (vertMat.vmInfo.diffuse.r,
                             vertMat.vmInfo.diffuse.g,
                             vertMat.vmInfo.diffuse.b)

    # mat.specular_color = (vertMat.vmInfo.specular.r,
    #                       vertMat.vmInfo.specular.g, vertMat.vmInfo.specular.b)
    # mat.diffuse_color = (vertMat.vmInfo.diffuse.r,
    #                      vertMat.vmInfo.diffuse.g, vertMat.vmInfo.diffuse.b,
    #                      vertMat.vmInfo.translucency)
    return mat


def create_bump_material(self, mesh):
    print("Create bump material")
    entries = mesh.bumpMaps.normalMap.entryStruct

    print(mesh.bumpMaps.normalMap.entryStruct.normalMap)
    print(mesh.bumpMaps.normalMap.entryStruct.diffuseTexName)

    if entries.normalMap == "":
        return None

    mat = bpy.data.materials.new(mesh.header.meshName + ".BumpMaterial")
    mat.use_nodes = True
    principled = PrincipledBSDFWrapper(mat, is_readonly=False)
    principled.base_color_texture.image = load_texture(
        self, entries.diffuseTexName, 0)
    principled.normalmap_texture.image = load_texture(
        self, entries.normalMap, 0)

    return mat

#######################################################################################
# create uvlayer
#######################################################################################


def create_uvlayer(mesh, tris, matPass):
    bm = bmesh.new()
    bm.from_mesh(mesh)

    uv_layer = mesh.uv_layers.new(name="texcoords", do_init=False)

    index = 0
    if len(matPass.txStage.txCoords) > 0:
        for f in bm.faces:
            tri = tris[index]
            for l in f.loops:
                idx = tri[l.index % 3]
                uv_layer.data[l.index].uv = matPass.txStage.txCoords[idx]
            index += 1


#######################################################################################
# load texture
#######################################################################################

def load_texture(self, texName, destBlend):
    found_img = False
    basename = os.path.splitext(texName)[0]

    # Test if the image file already exists
    for image in bpy.data.images:
        if basename == os.path.splitext(image.name)[0]:
            img = image
            found_img = True
            print("Found an existing image")

    # Try to load the image file
    if found_img == False:
        tgapath = os.path.dirname(self.filepath) + "/" + basename + ".tga"
        ddspath = os.path.dirname(self.filepath) + "/" + basename + ".dds"
        tgapath = InsensitivePath(tgapath)
        ddspath = InsensitivePath(ddspath)

        print("Trying tga: " + tgapath)
        img = load_image(tgapath)

        if img == None:
            print("Trying dds: " + ddspath)
            img = load_image(ddspath)

    return img


def load_texture_to_mat(self, texName, destBlend, mat):
    img = load_texture(self, texName, destBlend)
    principled = PrincipledBSDFWrapper(mat, is_readonly=False)
    principled.base_color_texture.image = img


#######################################################################################
# createAnimation
#######################################################################################

def create_animation(self, animation, hierarchy, rig, compressed):
    bpy.data.scenes["Scene"].render.fps = animation.header.frameRate
    bpy.data.scenes["Scene"].frame_start = 0
    bpy.data.scenes["Scene"].frame_end = animation.header.numFrames - 1

    # create the data
    translation_data = []
    for pivot in range(0, len(hierarchy.pivots)):
        pivot = []
        for frame in range(0, animation.header.numFrames - 1):
            pivot.append(None)

        translation_data.append(pivot)

    for channel in animation.channels:
        if (channel.pivot == 0):
            continue  # skip roottransform

        rest_rotation = hierarchy.pivots[channel.pivot].rotation
        pivot = hierarchy.pivots[channel.pivot]

        try:
            obj = rig.pose.bones[pivot.name]
        except:
            obj = bpy.data.objects[pivot.name]

        # X Y Z
        if channel.type == 0 or channel.type == 1 or channel.type == 2:
            for frame in range(channel.firstFrame, channel.lastFrame):
                if (translation_data[channel.pivot][frame] == None):
                    translation_data[channel.pivot][frame] = Vector((0.0, 0.0, 0.0))
                translation_data[channel.pivot][frame][channel.type] = channel.data[frame - channel.firstFrame]
        
        # ANIM_CHANNEL_Q
        elif channel.type == 6:
            obj.rotation_mode = 'QUATERNION'
            for frame in range(channel.firstFrame, channel.lastFrame):
                obj.rotation_quaternion = rest_rotation @ channel.data[frame - channel.firstFrame]
                obj.keyframe_insert(data_path='rotation_quaternion', frame=frame)

        else:
            self.report({'ERROR'}, "unsupported channel type: %s" % channel.type)
            print("unsupported channel type: %s" % channel.type)

    for pivot in range(1, len(hierarchy.pivots)):
        rest_location = hierarchy.pivots[pivot].position
        rest_rotation = hierarchy.pivots[pivot].rotation

        try:
            obj = rig.pose.bones[hierarchy.pivots[pivot].name]
        except:
            obj = bpy.data.objects[hierarchy.pivots[pivot].name]

        for frame in range(0, animation.header.numFrames - 1):
            if not translation_data[pivot][frame] == None:
                bpy.context.scene.frame_set(frame)
                pos = translation_data[pivot][frame]
                obj.location = rest_location + (rest_rotation @ pos)
                obj.keyframe_insert(data_path='location', frame=frame)

