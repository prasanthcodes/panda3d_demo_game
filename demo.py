import panda3d
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, PointLight
from panda3d.core import TextNode, NodePath, LightAttrib
from panda3d.core import LVector3
from direct.actor.Actor import Actor
from direct.task.Task import Task
from direct.showbase.DirectObject import DirectObject
from direct.gui.DirectGui import *
from panda3d.core import Texture, TexturePool, LoaderOptions, TextureStage, TexGenAttrib, TransformState
from direct.filter.FilterManager import FilterManager
import random

import sys
import os
import math
from direct.filter.CommonFilters import CommonFilters
from panda3d.core import ClockObject

from panda3d.core import *
from panda3d.core import SamplerState

import simplepbr
import gltf
import json


panda3d.core.load_prc_file_data("", """
    textures-power-2 none
    gl-coordinate-system default
    filled-wireframe-apply-shader true
    cursor-hidden true
    
    # As an optimization, set this to the maximum number of cameras
    # or lights that will be rendering the terrain at any given time.
    stm-max-views 16

    # Further optimize the performance by reducing this to the max
    # number of chunks that will be visible at any given time.
    stm-max-chunk-count 2048
    #textures-power-2 up
    view-frustum-cull false
""")

#panda3d.core.load_prc_file_data('', 'framebuffer-srgb true')
#panda3d.core.load_prc_file_data('', 'load-display pandadx9')#pandagl,p3tinydisplay,pandadx9,pandadx8
panda3d.core.load_prc_file_data('', 'show-frame-rate-meter true')
#panda3d.core.load_prc_file_data('', 'fullscreen true')
#loadPrcFileData('', 'coordinate-system y-up-left')

loadPrcFileData("", "basic-shaders-only #t")
#loadPrcFileData("", "gl-version 3 2")
#loadPrcFileData("", "notify-level-glgsg debug")       
loadPrcFileData("", "win-size 1920 1080")
#loadPrcFileData("", "fullscreen t")
                                  
class LookingDemo(ShowBase):

    def __init__(self):
        ShowBase.__init__(self)

        self.disable_mouse()
        
        self.FilterManager_1 = FilterManager(base.win, base.cam)
        self.Filters=CommonFilters(base.win, base.cam)                                       
        self.pipeline = simplepbr.init(use_normal_maps=True,exposure=0.8,sdr_lut_factor=0,max_lights=8)
        #---adjustable parameters---
        self.mouse_sensitivity=50
        self.move_speed=0.2
        self.scene_data_filename='sci_models/scene_params3.json'

        # Camera param initializations
        self.cameraHeight = 1.5     # camera Height above ground
        self.cameraAngleH = 0     # Horizontal angle (yaw)
        self.cameraAngleP = 0   # Vertical angle (pitch)
        self.camLens.setNear(0.01)
        self.camLens.setFar(5500)
        self.camera.setPos(0,0,1)
        
        self.first_person_view_flag=True#True,False
        self.bottom_cam_label=DirectLabel(text='CamPos: ',pos=(-1,1,-0.9),scale=0.05,text_align=TextNode.ACenter,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0.2),frameColor=(0, 0, 0, 0.1))
        self.bottom_cam_label.setText('press f to punch')

        
        self.set_keymap()
        self.load_environment_models()
        self.setupLights()
        
        taskMgr.add(self.actor_rotate, "camera_rotateTask")
        taskMgr.add(self.actor_move, "camera_move")
        #taskMgr.add(self.general_tasks, "general_tasks")
        
        base.accept('tab', base.bufferViewer.toggleEnable)

        self.set_cubemap()
        #self.filter_lens_flare()
        model_path = loader.load_model('sci_models/MaleSurvivor1.glb')
        model_path.setH(180)
        self.actor_1 = Actor(model_path)
        #self.actor_1.setPos(0, 3, 0)
        self.actor_1.setScale(0.1, 0.1, 0.1)
        self.actor_1.setH(180)

        self.actor_0 = self.render.attachNewNode('actor_0')
        self.actor_1.reparent_to(self.actor_0)
        if self.first_person_view_flag:
            self.camera.setPos(0,0.35,0.35)
        else:
            self.camera.setPos(0,-2,0.9)
        self.camera.reparent_to(self.actor_0)

        self.animation1 = self.actor_1.getAnimControl('NlaTrack')#rest
        self.animation2 = self.actor_1.getAnimControl('NlaTrack.001')#walk
        self.animation3 = self.actor_1.getAnimControl('NlaTrack.004')#attack
        self.animation1.loop(0)
        
        model_path = loader.load_model('sci_models/Satellite_dish_anim_L.glb')
        self.actor_sat = Actor(model_path)
        self.actor_sat.reparent_to(self.render)
        self.actor_sat.setPos(55.5859375,95.69079,0.0866)
        self.actor_sat.setScale(1.82116,1.82116,1.82116)
        #anim_names = self.actor_sat.getAnimNames()
        #print(anim_names)
        self.sat_anim_1 = self.actor_sat.getAnimControl('scanning_120_deg_horizontal')
        self.sat_anim_1.loop(0)
        
        #self.run_count = 0  # Track number of runs
        #self.max_runs = 3   # Stop after 3 runs (15 seconds total)
        #self.schedule_task()
        #self.run_event_1()
        self.run_count = 0  # Track number of runs
        self.max_runs = 100   # Stop after 3 runs (15 seconds total)
        self.robot_1=self.models_all[self.models_names_all.index('sci_models_Robot_1')]
        #taskMgr.doMethodLater(1, self.anim_seq_4_chase, "anim_seq_4_chase")
        self.event_1_finished=False
        self.mySound1 = base.loader.loadSfx("sci_models/Uncertain-Future.mp3")
        self.mySound2 = base.loader.loadSfx("sci_models/Dark-Future-Theme.mp3")
        self.mySound1.setLoop(True)
        self.mySound1.play()
        

    def startAnimation(self):
        self.animation3.play()
        if not(self.event_1_finished):
            self.run_event_1()

            
    def stopAnimation(self):
        # Check if animation is already playing, if so, stop it
        if self.animation2.isPlaying():
            self.animation2.stop()
            self.animation1.loop(0)
            
    def startAnimation2(self):
        if self.animation2.isPlaying():
            pass
        else:
            self.animation2.loop(0)

    def stopAnimation2(self):
        # Check if animation is already playing, if so, stop it
        if self.animation2.isPlaying():
            self.animation2.stop()
            self.animation1.loop(0)
        if self.animation3.isPlaying():
            self.animation3.stop()
            self.animation1.loop(0)
        print('kk')        

    def set_cubemap(self):

        # The options when loading the texture, in this case, does not make any sense, just for demonstration.
        lo = LoaderOptions(flags = LoaderOptions.TF_generate_mipmaps)

        # Let's create a texture named "world_cube_map" and configure it.
        texture_cube_map = Texture("world_cube_map")
        texture_cube_map.setup_cube_map()
        texture_cube_map.read(fullpath = 'sci_models/right.jpg',  z = 0, n = 0, read_pages = False, read_mipmaps = False, options = lo)
        texture_cube_map.read(fullpath = 'sci_models/left.jpg',   z = 1, n = 0, read_pages = False, read_mipmaps = False, options = lo)
        texture_cube_map.read(fullpath = 'sci_models/bottom.jpg', z = 2, n = 0, read_pages = False, read_mipmaps = False, options = lo)
        texture_cube_map.read(fullpath = 'sci_models/top.jpg',    z = 3, n = 0, read_pages = False, read_mipmaps = False, options = lo)
        texture_cube_map.read(fullpath = 'sci_models/front.jpg',  z = 4, n = 0, read_pages = False, read_mipmaps = False, options = lo)
        texture_cube_map.read(fullpath = 'sci_models/back.jpg',   z = 5, n = 0, read_pages = False, read_mipmaps = False, options = lo)

        # You can add texture to the pool if you need to.
        TexturePool.add_texture(texture_cube_map)

        skybox = loader.load_model('sci_models/sphere.bam')
        skybox.reparentTo(self.render)
        skybox.set_texture(texture_cube_map)
        
        # Necessary manipulations with the transformation of texture coordinates.
        ts = TextureStage.get_default()
        skybox.set_tex_gen(ts, TexGenAttrib.M_world_cube_map)
        skybox.set_tex_hpr(ts, (0, 90, 180))
        skybox.set_tex_scale(ts, (1, -1))
        # We will remove rendering effects that will be unnecessary.
        skybox.set_light_off()
        skybox.set_material_off()
        skybox.setShaderOff()
        skybox.setScale(4500,4500,4500)
        #skybox.setHpr(0,90,0)                             
         # Create and configure an ambient light
        #ambientLight = AmbientLight("ambient_light")
        #ambientLight.set_color((.9, .9, .9, 1))  # RGBA: full white light, fully opaque
        #ambient_light_node = self.render.attach_new_node(ambientLight)

        # Apply the light to the loaded model
        #skybox.set_light(ambient_light_node)          
        
    def show_info_gui_box(self,msg):
        # Create a frame (the "GUI box")
        self.gui_box = DirectFrame(
            frameSize=(-0.5, 0.5, -0.3, 0.3),
            frameColor=(0.8, 0.8, 0.8, 1),
            pos=(0, 0, 0)
        )

        # Add a label (text) inside the box
        self.gui_box_label = DirectLabel(
            text=msg,
            parent=self.gui_box,
            pos=(0, 0, 0.1),
            scale=0.1,
            text_fg=(0, 0, 0, 1)
        )

        # Add a button to the box
        self.gui_box_button = DirectButton(
            text="OK",
            parent=self.gui_box,
            pos=(0, 0, -0.1),
            scale=0.1,                        
            command=self.on_gui_box_button_click
        )

    def on_gui_box_button_click(self):
        if self.gui_box is not None:
            self.gui_box.destroy()
            self.gui_box = None
            sys.exit
    
    def load_environment_models(self):
        json_file=self.scene_data_filename
        with open(json_file) as json_data:
            self.data_all = json.load(json_data)

        self.models_all=[]
        self.models_names_all=[]
        self.models_names_enabled=[]
        self.ModelTemp=""
        for i in range(len(self.data_all)):
            data=self.data_all[i]
            self.models_names_all.append(data["uniquename"])
            if data["enable"]:
                self.ModelTemp=loader.loadModel(data["filename"])
                self.models_names_enabled.append(data["uniquename"])
                d=data["pos"][1]
                if data["pos"][0]: self.ModelTemp.setPos(d[0],d[1],d[2])
                d=data["scale"][1]
                if data["scale"][0]: self.ModelTemp.setScale(d[0],d[1],d[2])
                d=data["hpr"][1]
                if data["hpr"][0]: self.ModelTemp.setHpr(d[0],d[1],d[2])
                d=data["color"][1]
                if data["color"][0]: self.ModelTemp.setColorScale(d[0],d[1],d[2],d[3])
                #self.ModelTemp.clearLight()
                
                self.models_all.append(self.ModelTemp)
                self.models_all[-1].reparentTo(self.render)
                if data['show']==True:
                    self.models_all[-1].show()
                else:
                    self.models_all[-1].hide()
            else:
                self.models_all.append("")

    def set_keymap(self):
        self.keyMap = {"move_forward": 0, "move_backward": 0, "move_left": 0, "move_right": 0,"gravity_on":1,"right_click":0,"punch":0}
        self.accept('escape', sys.exit)
        self.accept("w", self.setKey, ["move_forward", True])
        self.accept("s", self.setKey, ["move_backward", True])
        self.accept("w-up", self.setKey, ["move_forward", False])
        self.accept("s-up", self.setKey, ["move_backward", False])
        self.accept("a", self.setKey, ["move_left", True])
        self.accept("d", self.setKey, ["move_right", True])
        self.accept("a-up", self.setKey, ["move_left", False])
        self.accept("d-up", self.setKey, ["move_right", False])
        self.accept("g", self.setKey, ["gravity_on", None])
        self.accept("mouse3", self.setKey, ["right_click", True])
        self.accept("mouse3-up", self.setKey, ["right_click", False])
        self.accept("f", self.setKey, ["punch", True])
        self.accept("f-up", self.setKey, ["punch", False])          
       
        
        
    # Records the state of the keys
    def setKey(self, key, value):
        
        if key=="gravity_on":
            self.keyMap[key]=not(self.keyMap[key])
        elif key=="punch":
            if value==True:
                self.startAnimation()
            else:
                self.stopAnimation() 
        else:
            self.keyMap[key] = value

        
    def setupLights(self):  # Sets up some default lighting
        self.ambientLight = AmbientLight("ambientLight")
        self.ambientLight_Intensity=0.2
        self.ambientLight.setColor((self.ambientLight_Intensity,self.ambientLight_Intensity,self.ambientLight_Intensity, 1))
        self.render.setLight(self.render.attachNewNode(self.ambientLight))
        self.directionalLight = DirectionalLight("directionalLight_1")
        self.directionalLight_intensity=3
        self.directionalLight.setColor((self.directionalLight_intensity,self.directionalLight_intensity,self.directionalLight_intensity, 1))
        #self.directionalLight.setSpecularColor((.1, .1, .1, .1))
        self.directionalLight.setShadowCaster(True, 512, 512)
        self.dlight1=self.render.attachNewNode(self.directionalLight)
        self.dlight1.setHpr(0, -45, 0)
        self.dlight1.setPos(0,0,20)
        #self.dlight1.look_at(0, 0, 0)
        
        cm = CardMaker('card')
        card = self.render.attachNewNode(cm.generate())
        card.setBillboardPointEye()
        card.setTexture(loader.loadTexture('sci_models/flare5.png'))
        #card.setColor(color)
        card.setPos(0,-1200,90)
        card.setScale(150)
        card.setTransparency(TransparencyAttrib.MAlpha)
        card.setLightOff()                           
        self.dlight1.setPos(0,-50,50)
        self.dlight1.look_at(0, 0, 0)        

        self.dlight1.node().get_lens().set_film_size(250, 250)
        self.dlight1.node().get_lens().setNearFar(1, 150)
        #self.dlight1.node().show_frustum()
        self.render.setLight(self.dlight1)
        self.filter_lens_flare()
        #self.Filters.setVolumetricLighting(self.dlight1 )#32, 5.0, 0.1, 0.1                                 
        
        plight = PointLight('plight1')
        plight.setColor((200,200,200, 1))
        plight.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        #plight.setShadowCaster(True, 512, 512)
        plnp = self.render.attachNewNode(plight)
        plnp.setPos(-48, 74, 14)
        self.render.setLight(plnp)
        
        plight1b = PointLight('plight1b')
        plight1b.setColor((200,200,200, 1))
        plight1b.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        #plight.setShadowCaster(True, 512, 512)
        plnp1b = self.render.attachNewNode(plight1b)
        plnp1b.setPos(-48, 74, 6)
        self.render.setLight(plnp1b)

        plight2 = PointLight('plight2')
        plight2.setColor((500,500,500, 1))
        plight2.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        #plight.setShadowCaster(True, 512, 512)
        plnp2 = self.render.attachNewNode(plight2)
        plnp2.setPos(-66, 74, 17)
        self.render.setLight(plnp2)
        
        plight3 = PointLight('plight3')
        plight3.setColor((300,300,300, 1))
        plight3.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        #plight.setShadowCaster(True, 512, 512)
        plnp3 = self.render.attachNewNode(plight3)
        plnp3.setPos(-87, 74, 17)
        self.render.setLight(plnp3)
        
    def filter_lens_flare(self):
        #self.setBackgroundColor(0.1,0.1,0.1)
        # ATI video cards (or drivers) are not too frendly with the input 
        # variables, so I had to transfer most of parameters to the shader
        # code.

        # Threshold (x,y,z) and brightness (w) settings
        threshold = Vec4(0.4, 0.4, 0.4, 0.3) # <----
        
        # FilterManager
        manager = self.FilterManager_1
        tex1 = Texture()
        tex2 = Texture()
        tex3 = Texture()
        finalquad = manager.renderSceneInto(colortex=tex1)
        # First step - threshold and radial blur
        interquad = manager.renderQuadInto(colortex=tex2)
        interquad.setShader(Shader.load("sci_models/invert_threshold_r_blur.sha"))
        interquad.setShaderInput("tex1", tex1)
        interquad.setShaderInput("threshold", threshold)
        # Second step - hardcoded fast gaussian blur. 
        # Not very important. This step can be omitted to improve performance
        # with some minor changes in lens_flare.sha
        interquad2 = manager.renderQuadInto(colortex=tex3)
        interquad2.setShader(Shader.load("sci_models/gaussian_blur.sha"))
        interquad2.setShaderInput("tex2", tex2)
        # Final - Make lens flare and blend it with the main scene picture
        finalquad.setShader(Shader.load("sci_models/lens_flare.sha"))
        finalquad.setShaderInput("tex1", tex1)
        finalquad.setShaderInput("tex2", tex2)
        finalquad.setShaderInput("tex3", tex3)
        #lf_settings = Vec3(lf_samples, lf_halo_width, lf_flare_dispersal)
        #finalquad.setShaderInput("lf_settings", lf_settings)
        #finalquad.setShaderInput("lf_chroma_distort", lf_chroma_distort)                                              

    def actor_rotate(self,task):
        # Check to make sure the mouse is readable
        if self.mouseWatcherNode.hasMouse():
            #if self.keyMap['right_click']==True:
            mpos = self.mouseWatcherNode.getMouse()
            mouse = self.win.getPointer(0)
            mx, my = mouse.getX(), mouse.getY()
            # Reset mouse to center to prevent edge stopping
            self.win.movePointer(0, int(800 / 2), int(600 / 2))
            #self.win.movePointer(0, int(self.win.getXSize() / 2), int(self.win.getYSize() / 2))

            # Calculate mouse delta
            dx = mx - 800 / 2
            dy = my - 600 / 2

            # Update camera angles based on mouse movement
            self.cameraAngleH -= dx * self.mouse_sensitivity * globalClock.getDt()
            self.cameraAngleP -= dy * self.mouse_sensitivity * globalClock.getDt()

            # Clamp pitch to avoid flipping
            self.cameraAngleP = max(-90, min(90, self.cameraAngleP))
            
            #self.camera.setPos(camX, camY, camZ)
            #self.camera.setHpr(self.cameraAngleH, self.cameraAngleP, 0)
            self.actor_0.setH(self.cameraAngleH)
            self.camera.setP(self.cameraAngleP)

        return Task.cont  # Task continues infinitely
    
    def actor_move(self,task):
        pos_val=self.actor_0.getPos()
        heading=(math.pi*(self.actor_0.getH()))/180
        pitch=(math.pi*(self.camera.getP()))/180
        newval_1=pos_val[1]
        newval_2=pos_val[0]
        newval_3=pos_val[2]
        if self.keyMap['move_forward']==True:#forward is y direction
            newval_1=pos_val[1]+self.move_speed*math.cos(heading)*math.cos(pitch)
            newval_2=pos_val[0]-self.move_speed*math.sin(heading)*math.cos(pitch)
            newval_3=pos_val[2]+self.move_speed*math.sin(pitch)
            #print([newval_2,newval_1,newval_3])
            #print(self.cam_node.getPos())
            #print(self.render.getRelativePoint(self.camera, Vec3(0, 0, 0)))
            self.startAnimation2()
        elif self.keyMap['move_backward']==True:
            newval_1=pos_val[1]-self.move_speed*math.cos(heading)*math.cos(pitch)
            newval_2=pos_val[0]+self.move_speed*math.sin(heading)*math.cos(pitch)
            newval_3=pos_val[2]-self.move_speed*math.sin(pitch)
            self.startAnimation2()
        elif self.keyMap['move_left']==True:
            newval_1=pos_val[1]+self.move_speed*math.cos(heading+(math.pi/2))
            newval_2=pos_val[0]-self.move_speed*math.sin(heading+(math.pi/2))
            self.startAnimation2()
        elif self.keyMap['move_right']==True:#right is x direction
            newval_1=pos_val[1]-self.move_speed*math.cos(heading+(math.pi/2))
            newval_2=pos_val[0]+self.move_speed*math.sin(heading+(math.pi/2))
            self.startAnimation2()
        else:
            self.stopAnimation()
        if self.keyMap['gravity_on']==True:
            newval_3=1
        
        (newval_2,newval_1)=self.uphold_arena_boundary(newval_2,newval_1)
        self.actor_0.setPos(newval_2,newval_1,newval_3)
        #print([newval_2,newval_1,newval_3])
        #tempos=self.get_an_point_front_of_camera(3,self.camera.getH(),self.camera.getP())
        #self.actor_1.setPos(tempos[0],tempos[1],1)
        #self.actor_1.setH(self.camera.getH()+180)
        
        return Task.cont
    
    def get_an_point_front_of_camera(self,distance,H,P):
        pos_val=self.camera.getPos()
        #pos_val=self.render.getRelativePoint(self.camera, Vec3(0,0,0))
        heading=(math.pi*(H))/180
        pitch=(math.pi*(P))/180
        newval_1=pos_val[1]+distance*math.cos(heading)*math.cos(pitch)
        newval_2=pos_val[0]-distance*math.sin(heading)*math.cos(pitch)
        newval_3=pos_val[2]+distance*math.sin(pitch)
        return [newval_2,newval_1,newval_3]

    def uphold_arena_boundary(self,x,y):
        if x>100: x=100
        if x<-100: x=-100
        if y>100: y=100
        if y<-100: y=-100
        return (x,y)

    def run_satellite_antenna_anim(self):
        idx=self.models_names_all.index('Satellite_dish_anim_L')
        self.actor_sat=Actor(self.models_all[idx])
        anim_names = self.actor_sat.getAnimNames()
        print(anim_names)
        self.sat_anim_1 = self.actor_sat.getAnimControl('scanning_120_deg_horizontal')
        self.sat_anim_1.loop(0)
        
    def run_event_1(self):
        self.edata1=[]
        self.edata1.append(self.actor_0)#0
        self.edata1.append(self.camera)#1
        pot_plant=self.models_all[self.models_names_all.index('sci_models_pot_plant_1')]
        self.edata1.append(pot_plant)#2
        self.robot_1=self.models_all[self.models_names_all.index('sci_models_Robot_1')]
        self.edata1.append(self.robot_1)#3
        mega_structure=self.models_all[self.models_names_all.index('Mega_Structure_T_shape')]
        self.edata1.append(mega_structure)#4
        
        pos_val=self.actor_0.getPos()
        pos2=pot_plant.getPos()
        distance=math.sqrt(abs(pos_val[0]-pos2[0])**2+abs(pos_val[1]-pos2[1])**2)
        def temp_func_1(actor):
            actor.lookAt(pot_plant)
            self.camera.setP(20)
            # changes pot color when punch
            pot_plant.setColorScale(1,0,0,1)
        def temp_func_1b(self):
            self.ignoreAll()
            self.accept('escape', sys.exit)
        def temp_func_1c(func):
            func()
        def temp_func_1d(actor):
            # stop the actor movement and look at robot
            self.robot_1.setH(-90)
            self.robot_1.setY(self.robot_1.getY()+8)
            actor.lookAt(self.robot_1)
            self.camera.setP(0)

        def temp_func_2(self):
            mega_structure.hide()
        def temp_func_3(self):
            mega_structure.show()
        def temp_func_4(func_1):
            taskMgr.add(func_1, "anim_seq_1")
        def temp_func_5(func_1):
            taskMgr.add(func_1, "anim_seq_2")
        def temp_func_6(func_1):
            taskMgr.add(func_1, "anim_seq_3")
            
        if distance<5:
            #pot_plant.setColorScale(1,0,0,1)
            temp_func_1b(self)
            taskMgr.doMethodLater(1, temp_func_1, 'temp_func_1',extraArgs=[self.actor_0])
            taskMgr.doMethodLater(3, temp_func_1d, 'temp_func_1d',extraArgs=[self.actor_0])
            
            taskMgr.doMethodLater(4, temp_func_2, 'temp_func_2')
            
            taskMgr.doMethodLater(7, temp_func_4, 'temp_func_4',extraArgs=[self.anim_seq_1])
            taskMgr.doMethodLater(12, self.anim_seq_1_remove, 'anim_seq_1_remove')
            taskMgr.doMethodLater(12, temp_func_5, 'temp_func_5',extraArgs=[self.anim_seq_2])
            taskMgr.doMethodLater(20, self.anim_seq_2_remove, 'anim_seq_2_remove')
            taskMgr.doMethodLater(20, temp_func_6, 'temp_func_6',extraArgs=[self.anim_seq_3])
            taskMgr.doMethodLater(22, self.anim_seq_3_remove, 'anim_seq_3_remove')
            
            taskMgr.doMethodLater(25, temp_func_1c, 'temp_func_1c',extraArgs=[self.set_keymap])
            taskMgr.doMethodLater(25, self.anim_seq_4_chase, "anim_seq_4_chase")
            taskMgr.doMethodLater(55, temp_func_3, 'temp_func_3')
            
            self.event_1_finished=True
            self.mySound1.setLoop(False)
            self.mySound1.stop()
            self.mySound2.setLoop(True)
            self.mySound2.play()
        
        
    def schedule_task(self,model):
        def interval_task(self,model):
            posY=model.getX()
            model.setX(posY+0.1)
            self.run_count += 1
            # Only reschedule if we haven't hit the max
            if self.run_count < self.max_runs:
                taskMgr.doMethodLater(5.0, interval_task, "IntervalTask",extraArgs=[model])
            else:
                print("Task stopped after reaching max runs!")
        
        taskMgr.doMethodLater(0.5, interval_task, "IntervalTask",extraArgs=[model])
        
    def anim_seq_1(self,task):
        posX=self.actor_0.getX()
        self.actor_0.setX(posX+0.03)
        self.robot_1.setX(self.robot_1.getX()-0.01)
        return Task.cont
    def anim_seq_1_remove(self,task):
        taskMgr.remove("anim_seq_1")

    def anim_seq_2(self,task):
        self.robot_1.setX(self.robot_1.getX()-0.01)
        return Task.cont
    def anim_seq_2_remove(self,task):
        taskMgr.remove("anim_seq_2")

    def anim_seq_3(self,task):
        sca=self.robot_1.getScale()
        self.robot_1.setScale(sca[0]+0.02,sca[1]+0.02,sca[2]+0.02)
        return Task.cont
    def anim_seq_3_remove(self,task):
        taskMgr.remove("anim_seq_3")
        
    def anim_seq_4_chase(self,task):
        pos=self.robot_1.getPos()
        pos2=self.actor_0.getPos()
        self.robot_1.lookAt(self.actor_0)
        self.robot_1.setH(self.robot_1.getH()+180)
        if pos[0]<pos2[0]: pos[0]=pos[0]+0.15
        if pos[0]>pos2[0]: pos[0]=pos[0]-0.15
        if pos[1]<pos2[1]: pos[1]=pos[1]+0.15
        if pos[1]>pos2[1]: pos[1]=pos[1]-0.15
        self.robot_1.setPos(pos)
        dist=math.sqrt(abs(pos[0]-pos2[0])**2+abs(pos[1]-pos2[1])**2)
        if dist<2:
            taskMgr.remove('anim_seq_4_chase')
            print('you lose')
            self.show_info_gui_box('You Lose')
        if task.time >= 5*60:  # 5 minutes
            print('you win')
            self.show_info_gui_box('You Win!')
            return Task.done  # Stops the task
        #print('ll')
        return Task.cont
        

demo=LookingDemo()
demo.run()


