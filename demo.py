import panda3d
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, PointLight
from panda3d.core import TextNode, NodePath, LightAttrib
from panda3d.core import LVector3
from direct.actor.Actor import Actor
from direct.task.Task import Task
from direct.showbase.DirectObject import DirectObject
from direct.gui.DirectGui import *
from direct.interval.IntervalGlobal import *

from panda3d.bullet import BulletWorld, BulletCharacterControllerNode, BulletCapsuleShape, BulletPlaneShape, ZUp, BulletRigidBodyNode, BulletDebugNode
from panda3d.bullet import BulletTriangleMesh, BulletTriangleMeshShape, BulletBoxShape, BulletSphereShape, BulletGhostNode

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
#loadPrcFileData("", "win-size 1920 1080")
#loadPrcFileData("", "fullscreen t")

class Player():
    def __init__(self, base, render, world, loader, camera):
        self.base = base
        self.render = render
        self.world = world
        self.loader = loader
        self.camera = camera
        
        # --- initialize CharacterController ---
        self.spawn_point=(0,0,0)
        self.prev_velocity = Vec3(0, 0, 0)
        radius=0.15
        height=1.5
        playerShape = BulletCapsuleShape(radius, height, ZUp)
        self.PlayerController = BulletCharacterControllerNode(playerShape, 1, "PlayerMain")
        #self.PlayerMain.setPos(self.spawn_point)
        #self.world.attachCharacter(self.PlayerController)
        self.PlayerController.setJumpSpeed(2.0)
        #self.PlayerController.setMaxSlope(60.0)
        #self.PlayerController.setMaxJumpHeight(3.0)
        
        # --- load the player model and set collisions ---
        model_path = loader.load_model('sci_models/astronaut.glb')
        #model_path.setH(180)
        self.PlayerActor = Actor(model_path)
        self.PlayerActor.setScale(1.5)
        self.PlayerActor.setPos(0,0,-1.8)
        self.PlayerActor.setH(180)
        self.PlayerMain = self.render.attachNewNode(self.PlayerController)
        self.world.attachCharacter(self.PlayerController)
        #self.PlayerActor.setPos(0,0,1)
        self.PlayerActor.reparent_to(self.PlayerMain)
        
        self.first_person_view_NP = self.PlayerMain.attachNewNode('first_person_view')
        self.first_person_view_NP.setPos(0,0.45,-0.65)#0,0.35,-0.65
        self.camera.reparentTo(self.first_person_view_NP)
        self.third_person_view_NP = self.PlayerMain.attachNewNode('third_person_view')
        self.third_person_view_NP.setPos(0,-4,-0.1)#0,-2,-0.1
        self.camera_view=0
        
        #self.camera.reparentTo(self.third_person_view_NP)
        self.PlayerMain.setPos(self.spawn_point)#actor starting position
        
        # --- set player animations ---
        self.player_anim_walking = self.PlayerActor.getAnimControl('Walking')
        self.player_anim_boxing = self.PlayerActor.getAnimControl('Boxing_Practice')
        self.player_anim_running = self.PlayerActor.getAnimControl('Running')
        self.player_anim_behit = self.PlayerActor.getAnimControl('BeHit_FlyUp')
        self.player_anim_dead = self.PlayerActor.getAnimControl('Dead')
        self.player_anim_arise = self.PlayerActor.getAnimControl('Arise')
        self.player_anim_attack = self.PlayerActor.getAnimControl('Skill_03') #(one hand slice attack with rotation)
        
    def toggle_camera_view(self):
        self.camera_view = (self.camera_view + 1) % 2
        if self.camera_view == 0:
            self.camera.reparentTo(self.first_person_view_NP)
        else:
            self.camera.reparentTo(self.third_person_view_NP)
            
    def start_attack(self):
        self.PlayerActor.setPos(1,0.1,-1.8)
        self.player_anim_boxing.play()

    def stop_attack(self):
        if self.player_anim_boxing.isPlaying():
            self.player_anim_boxing.stop()
            self.PlayerActor.setPos(0,0,-1.8)

    def start_walk(self):
        if not self.player_anim_walking.isPlaying():
            self.player_anim_walking.loop(0)
            self.PlayerActor.setPos(0,0,-1.8)

    def stop_walk(self):
        if self.player_anim_walking.isPlaying():
            self.player_anim_walking.stop()
            
    def jump(self):
        if self.PlayerController.isOnGround():
            self.PlayerController.doJump()

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.destroy()

    def destroy(self):
        self.player_anim_dead.play()
        print("player dead")
        
class Enemy():
    def __init__(self, base, render):
        self.base = base
        self.render = render
        
        model_path = loader.load_model('sci_models/robo_anim.glb')
        self.EnemyActor = Actor(model_path)
        self.EnemyActor.setScale(1.8)
        #self.EnemyActor.setPos(1.934,64.853,-0.9)
        #self.EnemyActor.setH(180)
        self.model=self.render.attachNewNode('EnemyMain')
        self.EnemyActor.reparentTo(self.model)
        self.model.setPos(1.934,64.853,-0.8)

        # Enemy stats
        self.health = 100
        self.speed = 2

        # animations
        self.robo_anim_attack = self.EnemyActor.getAnimControl('Arise') #(one hand slice attack with rotation)
        self.robo_anim_dead = self.EnemyActor.getAnimControl('Skill_01') #dead
        self.robo_anim_angry = self.EnemyActor.getAnimControl('Walking') #(get angry)
        self.robo_anim_walking = self.EnemyActor.getAnimControl('BeHit_FlyUp') #Walking
        self.robo_anim_boxing = self.EnemyActor.getAnimControl('Running') #Boxing_Practice
        self.robo_anim_behit = self.EnemyActor.getAnimControl('Dead') #BeHit_FlyUp
        self.robo_anim_running = self.EnemyActor.getAnimControl('Skill_03') #Running
        self.robo_anim_arise = self.EnemyActor.getAnimControl('Boxing_Practice') #Arise (getup from ground)
        
    def start_attack(self):
        self.robo_anim_attack.play()

    def stop_attack(self):
        if self.robo_anim_attack.isPlaying():
            self.robo_anim_attack.stop()

    def start_walk(self):
        if not self.robo_anim_walking.isPlaying():
            self.robo_anim_walking.loop(0)

    def stop_walk(self):
        if self.robo_anim_walking.isPlaying():
            self.robo_anim_walking.stop()
            
    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.destroy()

    def destroy(self):
        self.robo_anim_dead.play()
        
        print("Enemy Destroyed")
        #self.model.removeNode()
         
class GameMain(ShowBase):

    def __init__(self):
        ShowBase.__init__(self)

        # --- disable the default camera mouse controller ---
        self.disable_mouse()
        
        # --- initializations ---
        self.FilterManager_1 = FilterManager(base.win, base.cam)
        self.Filters=CommonFilters(base.win, base.cam)
        self.pipeline = simplepbr.init(use_normal_maps=True)
        self.props = WindowProperties()
        
        # --- parameters ---
        self.mouse_sensitivity=10
        self.move_speed=18#8

        # --- set loading label at start---
        self.CenterLabel=DirectLabel(text='Loading...',pos=(0,0,0),scale=0.07,text_align=TextNode.ACenter,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0),frameColor=(0, 0, 0, 0))
        base.graphicsEngine.renderFrame() #render a frame otherwise the screen will remain black
        base.graphicsEngine.renderFrame() 

        # --- load scene data from json ---
        base_path = os.path.dirname(os.path.abspath(__file__))
        json_file = os.path.join(base_path, 'sci_models', 'scene_params3.json') # Sets absolute file path to avoid file not found errors
        self.scene_data_filename= json_file

        # --- Camera param initializations ---
        self.cameraHeight = 1     # camera Height above ground
        self.cameraAngleH = 0     # Horizontal angle (yaw)
        self.cameraAngleP = 0   # Vertical angle (pitch)
        self.camLens.setNear(0.01)
        self.camLens.setFar(5500)
        self.camera.setPos(0,0,1)
        
        # --- initialize the bottom left label ---
        self.bottom_cam_label=DirectLabel(text='CamPos: ',pos=(-1,1,-0.9),scale=0.05,text_align=TextNode.ACenter,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0.2),frameColor=(0, 0, 0, 0.1))
        self.bottom_cam_label.setText('press f to punch')
        
        # --- load some important functions ---
        self.set_keymap()
        self.load_environment_models()
        self.setupLights()
        self.set_cubemap()
        
        # --- add tasks ---
        taskMgr.add(self.actor_rotate, "camera_rotateTask")
        #taskMgr.add(self.actor_move, "camera_move")
        #taskMgr.add(self.initial_loading_tasks, "initial_loading_tasks")
        #taskMgr.add(self.general_tasks, "general_tasks")
        self.taskMgr.add(self.update, "update")
        
        base.accept('tab', base.bufferViewer.toggleEnable)

        # --- initialize bullet world ---
        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -9.81))
        
        # --- initialize player ---
        self.player=Player(base,self.render, self.bullet_world, self.loader, self.camera)
        
        # --- initialize enemy robot ---
        self.robot=Enemy(base,self.render)
        
        # --- load and set satellite dish and animation---
        model_path = loader.load_model('sci_models/Satellite_dish_anim_L.bam')
        self.actor_sat = Actor(model_path)
        self.actor_sat.reparent_to(self.render)
        self.actor_sat.setPos(55.5859375,95.69079,0.0866)
        self.actor_sat.setScale(1.82116,1.82116,1.82116)
        self.sat_anim_1 = self.actor_sat.getAnimControl('scanning_120_deg_horizontal')
        self.sat_anim_1.loop(0)
        
        # --- load game sounds ---
        self.event_1_started=False
        self.event_1_finished=False
        self.mySound1 = base.loader.loadSfx("sci_models/Uncertain-Future.mp3")
        self.mySound2 = base.loader.loadSfx("sci_models/Dark-Future-Theme.mp3")
        self.mySound1.setLoop(True)
        self.mySound1.play()
        
        # -------------------------
        # FLOOR COLLISION
        # -------------------------
        groundShape = BulletBoxShape(Vec3(100, 100, 1))
        groundNode = BulletRigidBodyNode("Ground")
        groundNode.addShape(groundShape)
        groundNP = self.render.attachNewNode(groundNode)
        groundNP.setPos(0, 0, -1)
        self.bullet_world.attachRigidBody(groundNode)

        ground_plane = self.models_all[self.models_names_all.index('ground_metal')]
        ground_plane.reparentTo(groundNP)
        
        # -------------------------
        # CREATE WALLS
        # -------------------------
        self.createWall(0, 100, 5, 200, 1, 10)    # Front
        self.createWall(0, -100, 5, 200, 1, 10)   # Back
        self.createWall(100, 0, 5, 1, 200, 10)    # Right
        self.createWall(-100, 0, 5, 1, 200, 10)   # Left
        
        # --- set triggers ---
        triggerShape = BulletSphereShape(5)
        self.triggerNode_1 = BulletGhostNode("Plant_Trigger")
        self.triggerNode_1.addShape(triggerShape)
        pot_plant = self.models_all[self.models_names_all.index('sci_models_pot_plant_1')]
        self.triggerNP_1 = self.render.attachNewNode(self.triggerNode_1)
        self.triggerNP_1.setPos(pot_plant.getPos(self.render))
        self.bullet_world.attachGhost(self.triggerNode_1)

        triggerShape = BulletSphereShape(3)
        self.triggerNode_2 = BulletGhostNode("Robot_Trigger")
        self.triggerNode_2.addShape(triggerShape)
        self.triggerNP_2 = self.render.attachNewNode(self.triggerNode_2)
        self.triggerNP_2.setPos(self.robot.model.getPos(self.render))
        self.bullet_world.attachGhost(self.triggerNode_2)

        # -------------------------
        # DEBUG VIEW
        # -------------------------
        """
        debugNode = BulletDebugNode('Debug')
        debugNode.showWireframe(True)

        debugNP = self.render.attachNewNode(debugNode)
        debugNP.show()

        self.bullet_world.setDebugNode(debugNode)
        """
        
        # --- loading complete ---
        self.CenterLabel["text"] = "Loading Completed."
        Sequence(Wait(1.5),Func(self.CenterLabel.hide)).start()
        
        # --- temp vars initialization ---
        self.saved_hpr=[0,0,0]
            
    def createWall(self, x, y, z, sx, sy, sz):
        shape = BulletBoxShape(Vec3(sx/2, sy/2, sz/2))
        node = BulletRigidBodyNode("Wall")
        node.addShape(shape)

        wallNP = self.render.attachNewNode(node)
        wallNP.setPos(x, y, z)

        self.bullet_world.attachRigidBody(node)
        
    def update(self, task):

        dt = globalClock.getDt()
        move = Vec3(0, 0, 0)
        speed = self.move_speed

        if self.keyMap["move_forward"]:
            move.y += speed
            self.player.start_walk()
        elif self.keyMap["move_backward"]:
            move.y -= speed
            self.player.start_walk()
        elif self.keyMap["move_left"]:
            move.x -= speed
            self.player.start_walk()
        elif self.keyMap["move_right"]:
            move.x += speed
            self.player.start_walk()
        else:
            self.player.stop_walk()

        self.player.PlayerController.setLinearMovement(move, True)
        self.triggerNP_2.setPos(self.robot.model.getPos(self.render))
        self.bullet_world.doPhysics(dt, 10, 1.0/180.0)  # Substeps for stability
        #pos=self.PlayerMain.getPos()
        #self.bottom_cam_label.setText('ActorPos: %0.2f,%0.2f,%0.2f'%(pos[0],pos[1],pos[2]))
                
        return task.cont  

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
        
    def show_info_gui_box(self,msg):
        # Create a frame (the "GUI box")
        self.gui_box = DirectFrame(
            frameSize=(-0.5, 0.5, -0.3, 0.3),
            frameColor=(1, 1, 1, 0.8),
            pos=(0, 0, 0)
        )

        # Add a label (text) inside the box
        self.gui_box_label = DirectLabel(
            text=msg,
            parent=self.gui_box,
            pos=(0, 0, 0.1),
            scale=0.1,
            text_fg=(0, 0, 0, 1),
            frameColor=(1, 0.9, 0.9, 0.9),
        )

        # Add a button to the box
        self.gui_box_button = DirectButton(
            text="OK",
            parent=self.gui_box,
            pos=(0, 0, -0.1),
            scale=0.1,                        
            command=self.on_gui_box_button_click,
            frameColor=(1, 1, 1, 0.9),
        )
        taskMgr.remove("camera_rotateTask")
        self.props.setCursorHidden(False)
        base.win.requestProperties(self.props)

    def on_gui_box_button_click(self):
        if self.gui_box is not None:
            self.gui_box.destroy()
            self.gui_box = None
            taskMgr.add(self.actor_rotate, "camera_rotateTask")
            #sys.exit
            self.props.setCursorHidden(True)
            base.win.requestProperties(self.props)
            self.move_speed=30
    
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
        self.keyMap = {"move_forward": 0, "move_backward": 0, "move_left": 0, "move_right": 0,"gravity_on":1,
        "right_click":0,"punch":0,"Start":0,"space_key":0,"camera_view":0}
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
        self.accept("g", self.setKey, ["Start", True]) 
        self.accept("space", self.setKey, ["space_key", True])
        self.accept("v", self.setKey, ["camera_view", True])
        
    # Records the state of the keys
    def setKey(self, key, value):
        
        if key=="gravity_on":
            self.keyMap[key] = not self.keyMap[key]
            
        elif key=="space_key":
            self.player.jump()
            if self.event_1_started:
                self.event1_seq.finish()
                self.event_1_finished=True
            self.keyMap[key] = False
            
        elif key=="punch":
            if value==True:
                self.player.start_attack()
                if not self.event_1_finished:
                    self.run_event_1()
            else:
                pass
                #self.player.stop_attack() 
                
        elif key=="camera_view":
            self.player.toggle_camera_view()
            self.keyMap[key] = not self.keyMap[key]
            
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
        self.render.setLight(self.dlight1)
        self.filter_lens_flare()

        plight = PointLight('plight1')
        plight.setColor((200,200,200, 1))
        plight.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        plnp = self.render.attachNewNode(plight)
        plnp.setPos(-48, 74, 14)
        self.render.setLight(plnp)
        
        plight1b = PointLight('plight1b')
        plight1b.setColor((200,200,200, 1))
        plight1b.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        plnp1b = self.render.attachNewNode(plight1b)
        plnp1b.setPos(-48, 74, 6)
        self.render.setLight(plnp1b)

        plight2 = PointLight('plight2')
        plight2.setColor((500,500,500, 1))
        plight2.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        plnp2 = self.render.attachNewNode(plight2)
        plnp2.setPos(-66, 74, 17)
        self.render.setLight(plnp2)
        
        plight3 = PointLight('plight3')
        plight3.setColor((300,300,300, 1))
        plight3.setAttenuation(LVector3(0, 0, 1))# (constant,linear,quadratic attenuation)
        plnp3 = self.render.attachNewNode(plight3)
        plnp3.setPos(-87, 74, 17)
        self.render.setLight(plnp3)
        
    def filter_lens_flare(self):
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
            self.win.movePointer(0, int(self.win.getXSize() / 2), int(self.win.getYSize() / 2))

            # Calculate mouse delta
            dx = mx - int(self.win.getXSize() / 2)
            dy = my - int(self.win.getYSize() / 2)

            # Update camera angles based on mouse movement
            self.cameraAngleH -= dx * self.mouse_sensitivity * globalClock.getDt()
            self.cameraAngleP -= dy * self.mouse_sensitivity * globalClock.getDt()

            # Clamp pitch to avoid flipping
            self.cameraAngleP = max(-90, min(90, self.cameraAngleP))
            
            self.player.PlayerMain.setH(self.cameraAngleH)
            self.camera.setP(self.cameraAngleP)

        return Task.cont  # Task continues infinitely
            
    def run_event_1(self):

        pot_plant = self.models_all[self.models_names_all.index('sci_models_pot_plant_1')]
        #self.robot = self.models_all[self.models_names_all.index('sci_models_robot')]
        mega_structure = self.models_all[self.models_names_all.index('Mega_Structure_T_shape')]
        
        event_flag=0
        overlapping = self.triggerNode_1.getOverlappingNodes()
        for node in overlapping:
            if node==self.player.PlayerController:
                event_flag=1
                
        if not event_flag==1: return
        
        # disable controls
        self.ignoreAll()

        for key in ['move_forward', 'move_backward', 'move_left', 'move_right']:
            self.keyMap[key] = False

        self.accept('escape', sys.exit)
        taskMgr.remove("camera_rotateTask")
        self.reset_mouse()

        # sounds
        self.mySound1.stop()
        self.mySound2.setLoop(True)
        self.mySound2.play()
        
        self.bottom_cam_label.setText('press space to skip')
        self.accept("space", self.setKey, ["space_key", True]) 

        # main cinematic sequence
        self.event1_seq = Sequence(

            Wait(1),

            Func(self.player.PlayerMain.lookAt, pot_plant),
            Func(self.camera.setP, 20),
            Func(pot_plant.setColorScale, 1, 0, 0, 1),

            Wait(2),

            Func(self.robot.start_walk),
            Func(self.robot.model.lookAt, (-7.67,75.02,self.cameraHeight)),
            Func(self.robot.model.setH, self.robot.model.getH()-90),
            #Func(self.robot.setY, self.robot.getY() + 8),
            Func(self.player.PlayerMain.lookAt, self.robot.model),
            Func(self.camera.setP, 0),

            Wait(1),

            Func(mega_structure.hide),

            # anim_seq_1
            Parallel(
                LerpPosInterval(
                    self.player.PlayerMain,
                    5,
                    (
                        self.player.PlayerMain.getX() + 5 * 0.03 * 60,
                        self.player.PlayerMain.getY(),
                        self.player.PlayerMain.getZ()
                    )
                ),

                LerpPosInterval(
                    self.robot.model,
                    5,
                    (
                        self.robot.model.getX() - 5 * 0.01 * 60,
                        self.robot.model.getY(),
                        self.robot.model.getZ()
                    )
                )
            ),

            # anim_seq_2
            LerpPosInterval(
                self.robot.model,
                5,
                (
                    -7.67,
                    75.02,
                    self.robot.model.getZ()
                )
            ),

            # anim_seq_3
            Func(
                self.robot.model.scaleInterval(
                    2,
                    (
                        self.robot.model.getScale()[0] + 0.7,
                        self.robot.model.getScale()[1] + 0.7,
                        self.robot.model.getScale()[2] + 0.7
                    )
                ).start
            ),

            Wait(3),
            
            Func(setattr, self, "event_1_finished", True),
            Func(self.set_keymap),
            Func(self.reset_mouse),
            Func(taskMgr.add, self.actor_rotate, "camera_rotateTask"),
            Func(self.player.PlayerMain.setH, 0),
            Func(taskMgr.add, self.anim_seq_4_chase, "anim_seq_4_chase"),

            Wait(30),

            Func(mega_structure.show)

        )
        
        self.event_1_started=True
        self.event1_seq.start()

    def reset_mouse(self):
        self.win.movePointer(0, int(self.win.getXSize() / 2), int(self.win.getYSize() / 2))
        
    def anim_seq_4_chase(self, task):

        robot_pos = self.robot.model.getPos()
        player_pos = self.player.PlayerMain.getPos()


        # direction vector
        direction = player_pos - robot_pos
        direction.setZ(0)

        # distance check
        dist = direction.length()
        
        # normalize
        if direction.length() > 0:
            direction.normalize()

        speed = 0.1

        # move robot
        self.robot.model.setPos( robot_pos + direction * speed )

        # look at player
        self.robot.model.lookAt(self.player.PlayerMain)
        self.robot.model.setH(self.robot.model.getH() + 180)
        
        # to avoid robot rotation when lookat player 
        if 6 < dist < 7:
            self.saved_hpr = self.robot.model.getHpr()
        if dist<6:
            hpr=self.robot.model.getHpr()
            self.robot.model.setHpr(hpr[0],self.saved_hpr[1],self.saved_hpr[2])
            
        if dist < 2:
            taskMgr.remove('anim_seq_4_chase')
            self.robot.start_attack()
            print('you lose')
            self.show_info_gui_box('You Lose')
            return Task.done

        if task.time >= 1.5 * 60:
            print('you win')
            self.show_info_gui_box('You Win!')
            return Task.done

        return Task.cont
        
demo=GameMain()
demo.run()


