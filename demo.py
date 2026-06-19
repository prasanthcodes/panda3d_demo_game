import sys
import traceback

def log_crash(exc_type, exc_value, exc_traceback):
    # This forces Python to write the full crash report to a text file
    with open("crash_report.txt", "w") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    # Still show it in console if available
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Register the crash hook
sys.excepthook = log_crash

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
from direct.showbase.Audio3DManager import Audio3DManager

import os
import math
import datetime
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
    stm-max-views 1

    # Further optimize the performance by reducing this to the max
    # number of chunks that will be visible at any given time.
    stm-max-chunk-count 2048
    #textures-power-2 up
    view-frustum-cull True
""")

#panda3d.core.load_prc_file_data('', 'framebuffer-srgb true')
#panda3d.core.load_prc_file_data('', 'load-display pandadx9')#pandagl,p3tinydisplay,pandadx9,pandadx8
#panda3d.core.load_prc_file_data('', 'show-frame-rate-meter true')
#panda3d.core.load_prc_file_data('', 'fullscreen true')
#loadPrcFileData('', 'coordinate-system y-up-left')

#loadPrcFileData("", "basic-shaders-only #t")
#loadPrcFileData("", "gl-version 3 2")
#loadPrcFileData("", "notify-level-glgsg debug")
loadPrcFileData("", "win-size 1280 720")
loadPrcFileData("", "fullscreen t")
#loadPrcFileData("", "win-size 800 600")
#loadPrcFileData("", "fullscreen f")
loadPrcFileData("", "icon-filename sci_models/icon.ico")
loadPrcFileData("", "window-title Project: Flora Guard")

# Redirect all stdout and stderr to a log file
loadPrcFileData("", "notify-output logs.log")

# Optional: Choose how detailed you want the logs to be 
# (info, warning, error, or debug)
loadPrcFileData("", "notify-level error")
loadPrcFileData("", "model-path $MAIN_DIR/sci_models/")

import sys
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import (DirectFrame, DirectLabel, DirectOptionMenu, 
                                  DirectCheckButton, DirectButton, DirectEntry, DirectSlider, OnscreenImage, OnscreenText, DGG)
from panda3d.core import WindowProperties, TextNode

class GameMenuSystem:
    def __init__(self, app_instance, first_time=True):
        self.app = app_instance
        self.first_time = first_time
        
        # --- 0. Video / Display State Tracking ---
        # Cache initial settings based on current running configuration
        init_w = self.app.win.getXSize()
        init_h = self.app.win.getYSize()
        
        self.resolutions = ["800 x 600", "1024 x 768", "1280 x 720", "1600 x 900", "1920 x 1080"]
        self.current_resolution = f"{init_w} x {init_h}" if f"{init_w} x {init_h}" in self.resolutions else "1280 x 720"
        self.is_fullscreen = True
        
        # Backups used to revert settings automatically if things go wrong
        self.backup_resolution = self.current_resolution
        self.backup_fullscreen = self.is_fullscreen
        
        # Timers and handles
        self.countdown_time = 15
        self.countdown_task = None
        
        # --- 1. Audio Configurations ---
        try:
            self.hover_sound = self.app.loader.loadSfx("sci_models/res/hover.wav")
            self.click_sound = self.app.loader.loadSfx("sci_models/res/click.wav")
            self.bgm_sound = self.app.loader.loadMusic("sci_models/Future-Industry-1.ogg")
            self.bgm_sound.setLoop(True)
            self.bgm_sound.play()
        except:
            print("Note: Audio assets missing. Running in silent mode.")
            self.hover_sound = None
            self.click_sound = None

        # --- 2. Global Background Setup ---
        try:
            self.background = OnscreenImage(image='sci_models/res/background.jpg', pos=(0, 0, 0), parent=self.app.render2d)
        except:
            # Fallback color background if image doesn't exist
            self.background = OnscreenImage(image='', pos=(0, 0, 0), scale=(2, 1, 1),
                                            color=(0.12, 0.14, 0.18, 1), parent=self.app.render2d)

        # Lists to keep track of active UI elements for easy cleanup
        self.main_menu_elements = []
        self.settings_elements = []
        self.about_elements = []
        self.confirm_elements = []  # Tracking for the 15-second warning frame

        # Reusable shared styling for standard buttons
        self.button_style = {
            "frameSize": (-3.5, 3.5, -0.6, 0.6), 
            "scale": 0.1,                        
            "borderWidth": (0.05, 0.05),
            "text_scale": 0.55,
            "text_fg": (1, 1, 1, 1),
            "text_pos": (0, -0.15),
            "frameColor": (
                (0.2, 0.4, 0.6, 0.8),  # Normal
                (0.1, 0.2, 0.4, 1.0),  # Pressed
                (0.3, 0.6, 0.9, 0.9),  # Hovered
                (0.5, 0.5, 0.5, 1.0)   # Disabled
            )
        }

        # Load the initial main menu
        self.create_main_menu()
        
        # Set initial sound volume
        volume = self.app.bgm_volume / 100.0  # Standardize to 0.0 - 1.0 for audio engines
        self.app.musicManager.setVolume(volume)

        volume = self.app.sfx_volume / 100.0
        self.app.sfxManagerList[0].setVolume(volume)

    # --- UI Sound Management ---
    def bind_sounds(self, element):
        element.bind(DGG.B1PRESS, self.play_click_sound)
        element.bind(DGG.WITHIN, self.play_hover_sound)

    def play_hover_sound(self, entry=None):
        if self.hover_sound: self.hover_sound.play()

    def play_click_sound(self, entry=None):
        if self.click_sound: self.click_sound.play()

    # ==========================================
    # SCREEN 1: MAIN MENU
    # ==========================================
    def create_main_menu(self):
        self.clear_all_screens()

        # Core Game Title (Flora Theme: Neon Bio-Green)
        title = OnscreenText(
            text="PROJECT: FLORA GUARD", 
            pos=(0, 0.75), 
            scale=0.13, 
            fg=(0.0, 0.9, 0.4, 1.0), 
            bg=(0.1, 0.1, 0.1, 0.75),
            align=TextNode.ACenter, 
            mayChange=False
        )
        self.main_menu_elements.append(title)

        # Tactical Subtitle (Automata Theme: Warning Orange)
        subtitle = OnscreenText(
            text="AUTOMATA INCURSION", 
            pos=(0, 0.63), 
            scale=0.06, 
            fg=(1.0, 0.5, 0.0, 1.0), 
            bg=(0.1, 0.1, 0.1, 0.75),
            align=TextNode.ACenter, 
            mayChange=False
        )
        self.main_menu_elements.append(subtitle)

        # Main Menu Buttons
        btn_start = DirectButton(text="Start Game", pos=(0, 0, 0.3), command=self.start_game, **self.button_style)
        btn_resume = DirectButton(text="Resume Game", pos=(0, 0, 0.3), command=self.resume_game, **self.button_style)
        if self.first_time:
            btn_start.show()
            btn_resume.hide()
        else:
            btn_start.hide()
            btn_resume.show()
        btn_settings = DirectButton(text="Settings", pos=(0, 0, 0.0), command=self.open_settings, **self.button_style)
        btn_about = DirectButton(text="About", pos=(0, 0, -0.3), command=self.open_about, **self.button_style)
        btn_exit = DirectButton(text="Exit", pos=(0, 0, -0.6), command=self.exit_game, **self.button_style)

        # Track and assign sound effects
        for btn in [btn_start, btn_resume, btn_settings, btn_about, btn_exit]:
            self.main_menu_elements.append(btn)
            self.bind_sounds(btn)

    def start_game(self):
        self.clear_all_screens()
        if hasattr(self, 'background') and self.background:
            self.background.destroy()
            self.background = None
        self.bgm_sound.stop()
        self.app.start_game_world()

    def resume_game(self):
        self.clear_all_screens()
        if hasattr(self, 'background') and self.background:
            self.background.destroy()
            self.background = None
        self.bgm_sound.stop()
        self.app.resume_game_world()
        
    def pause_game(self):
        self.clear_all_screens()
        if hasattr(self, 'background') and self.background:
            self.background.destroy()
            self.background = None
        self.app.pause_game_world()
        
    # ==========================================
    # SCREEN 2: SETTINGS SCREEN
    # ==========================================
    def open_settings(self):
        self.clear_all_screens()

        # Settings Screen Title
        title = OnscreenText(text="SETTINGS", pos=(0, 0.8), scale=0.12, fg=(1, 0.8, 0.2, 1), bg=(0.1, 0.1, 0.1, 0.75), mayChange=False)
        self.settings_elements.append(title)
        
        # --- MOUSE SENSITIVITY INPUT ---
        sensitivity_label = OnscreenText(text="Mouse Sensitivity:", pos=(-0.6, 0.5), scale=0.05, fg=(1, 1, 1, 1), align=TextNode.ALeft)
        self.settings_elements.append(sensitivity_label)
        
        self.sensitivity_entry = DirectEntry(
            pos=(0.15, 0, 0.49),
            scale=0.05,
            numLines=1,
            focus=0,
            frameColor=(0.1, 0.1, 0.1, 0.75),
            text_fg=(1, 1, 1, 1),
            width=5, 
            command=self.adjust_sensitivity
        )
        self.sensitivity_entry.set(str(self.app.mouse_sensitivity)) 
        self.settings_elements.append(self.sensitivity_entry)
        
        # --- BGM VOLUME SLIDER ---
        bgm_label = OnscreenText(text="BGM Volume:", pos=(-0.6, 0.35), scale=0.05, fg=(1, 1, 1, 1), align=TextNode.ALeft)
        self.settings_elements.append(bgm_label)

        self.bgm_slider = DirectSlider(
            range=(0, 100), 
            value=self.app.bgm_volume, 
            pos=(0.28, 0, 0.36), 
            scale=0.35, 
            command=self.adjust_bgm_volume
        )
        self.settings_elements.append(self.bgm_slider)

        # --- SFX VOLUME SLIDER ---
        sfx_label = OnscreenText(text="SFX Volume:", pos=(-0.6, 0.2), scale=0.05, fg=(1, 1, 1, 1), align=TextNode.ALeft)
        self.settings_elements.append(sfx_label)

        self.sfx_slider = DirectSlider(
            range=(0, 100), 
            value=self.app.sfx_volume, 
            pos=(0.28, 0, 0.21), 
            scale=0.35, 
            command=self.adjust_sfx_volume
        )
        self.settings_elements.append(self.sfx_slider)

        # --- VIDEO RESOLUTION OPTIONS ---
        res_label = OnscreenText(text="Screen Resolution:", pos=(-0.6, 0.05), scale=0.05, fg=(1, 1, 1, 1), align=TextNode.ALeft)
        self.settings_elements.append(res_label)
        
        initial_res_index = self.resolutions.index(self.current_resolution) if self.current_resolution in self.resolutions else 2
        self.res_menu = DirectOptionMenu(
            items=self.resolutions,
            initialitem=initial_res_index,
            scale=0.07,
            pos=(-0.1, 0, 0.04),
            frameColor=(0.1, 0.1, 0.1, 0.75),
            text_fg=(1, 1, 1, 1),
            highlightColor=(0.3, 0.6, 0.9, 1),
            command=self.set_resolution
        )
        self.settings_elements.append(self.res_menu)

        # --- WINDOW MODE OPTION (FULLSCREEN) ---
        self.fullscreen_checkbox = DirectCheckButton(
            text="Display Fullscreen",
            scale=0.05,
            pos=(0.15, 0, -0.12),
            text_fg=(1, 1, 1, 1),
            text_bg=(0.1, 0.1, 0.1, 0.75),
            frameColor=(0.1, 0.1, 0.1, 0.75),
            command=self.set_fullscreen
        )
        # Setup starting visual checked state
        self.fullscreen_checkbox['indicatorValue'] = int(self.is_fullscreen)
        self.settings_elements.append(self.fullscreen_checkbox)

        # --- ACTION BUTTONS (APPLY / BACK) ---
        btn_apply = DirectButton(text="Apply Graphics", pos=(-0.4, 0, -0.45), command=self.apply_video_settings, **self.button_style)
        btn_back = DirectButton(text="Back", pos=(0.4, 0, -0.45), command=self.create_main_menu, **self.button_style)
        
        for btn in [btn_apply, btn_back]:
            self.settings_elements.append(btn)
            self.bind_sounds(btn)

    def adjust_sensitivity(self, text_entered):
        try:
            sens_value = float(text_entered)
            formatted_sens = float(f"{sens_value:.2f}")
            self.app.mouse_sensitivity = formatted_sens
        except ValueError:
            self.sensitivity_entry.set("10") 

    def adjust_bgm_volume(self):
        self.app.bgm_volume = self.bgm_slider.getValue()
        volume = self.app.bgm_volume / 100.0 
        self.app.musicManager.setVolume(volume)

    def adjust_sfx_volume(self):
        self.app.sfx_volume = self.sfx_slider.getValue()
        volume = self.app.sfx_volume / 100.0
        self.app.sfxManagerList[0].setVolume(volume)

    def set_resolution(self, selected_res):
        self.current_resolution = selected_res

    def set_fullscreen(self, status):
        self.is_fullscreen = bool(status)

    # ==========================================
    # GRAPHICS CONTEXT RECOVERY TIMERS
    # ==========================================
    def apply_video_settings(self):
        """ Fires requested display modifications and builds confirmation prompt """
        # 1. Mutate Window Framework Properties
        width, height = map(int, self.current_resolution.split(" x "))
        props = WindowProperties()
        props.setSize(width, height)
        props.setFullscreen(self.is_fullscreen)
        self.app.win.requestProperties(props)
        
        # 2. Halt settings display access interaction 
        for elem in self.settings_elements:
            elem.hide()
            
        # 3. Create Safe Confirmation Modal Framework
        self.confirm_frame = DirectFrame(
            frameColor=(0.08, 0.09, 0.12, 0.98),
            frameSize=(-0.8, 0.8, -0.4, 0.4),
            pos=(0, 0, 0)
        )
        self.confirm_elements.append(self.confirm_frame)
        
        self.confirm_label = DirectLabel(
            parent=self.confirm_frame,
            text="",
            scale=0.05, pos=(0, 0, 0.12),
            frameColor=(0, 0, 0, 0), text_fg=(1, 1, 1, 1)
        )
        self.confirm_elements.append(self.confirm_label)

        # Build dialog buttons using styles
        btn_keep = DirectButton(parent=self.confirm_frame, text="Keep Settings", pos=(-0.4, 0, -0.15), command=self.keep_settings, **self.button_style)
        btn_revert = DirectButton(parent=self.confirm_frame, text="Revert Now", pos=(0.4, 0, -0.15), command=self.revert_settings, **self.button_style)
        
        for btn in [btn_keep, btn_revert]:
            self.confirm_elements.append(btn)
            self.bind_sounds(btn)

        # 4. Trigger countdown logic execution loop
        self.countdown_time = 15
        self.update_confirm_text()
        
        if self.countdown_task:
            self.app.taskMgr.remove(self.countdown_task)
        self.countdown_task = self.app.taskMgr.doMethodLater(1.0, self.timer_tick_task, "DisplayCountdownTask")

    def timer_tick_task(self, task):
        self.countdown_time -= 1
        self.update_confirm_text()
        
        if self.countdown_time <= 0:
            self.revert_settings()
            return task.done
            
        return task.again

    def update_confirm_text(self):
        self.confirm_label["text"] = f"Video configurations updated.\nKeep these settings?\nReverting in {self.countdown_time} seconds..."

    def keep_settings(self):
        """ Settings working as expected, lock changes in as new restoration targets """
        self.clear_countdown_and_overlay()
        self.backup_resolution = self.current_resolution
        self.backup_fullscreen = self.is_fullscreen
        
        # Restore access to parameters window
        for elem in self.settings_elements:
            elem.show()

    def revert_settings(self):
        """ Restore device parameters dynamically back to prior saved profiles """
        self.clear_countdown_and_overlay()
        
        # Restore values inside trackers
        self.current_resolution = self.backup_resolution
        self.is_fullscreen = self.backup_fullscreen
        
        # Re-apply window configuration parameters explicitly
        width, height = map(int, self.backup_resolution.split(" x "))
        props = WindowProperties()
        props.setSize(width, height)
        props.setFullscreen(self.backup_fullscreen)
        self.app.win.requestProperties(props)
        
        # Redraw standard settings panel elements with verified attributes applied
        self.open_settings()

    def clear_countdown_and_overlay(self):
        if self.countdown_task:
            self.app.taskMgr.remove(self.countdown_task)
            self.countdown_task = None
            
        for element in self.confirm_elements:
            element.destroy()
        self.confirm_elements.clear()

    # ==========================================
    # SCREEN 3: ABOUT SCREEN
    # ==========================================
    def open_about(self):
        self.clear_all_screens()

        # About Screen Title
        title = OnscreenText(text="ABOUT", pos=(0, 0.7), scale=0.12, fg=(1, 0.8, 0.2, 1), mayChange=False)
        self.about_elements.append(title)

        # Description text blocks
        about_info = (
            "Developed with Panda3D Engine\n\n"
            "Developer: Prasanth\n"
            "Version: 3.0.0 (2026)\n\n"
            "Thank you for playing."
        )
        
        info_text = OnscreenText(text=about_info, pos=(0, 0.2), scale=0.06, 
                                 fg=(0.9, 0.9, 0.9, 1), bg=(0.1, 0.1, 0.1, 0.75), align=TextNode.ACenter, wordwrap=20)
        self.about_elements.append(info_text)

        # Back Button to return to Main Menu
        btn_back = DirectButton(text="Back", pos=(0, 0, -0.6), command=self.create_main_menu, **self.button_style)
        self.about_elements.append(btn_back)
        self.bind_sounds(btn_back)

    # ==========================================
    # UI CLEANUP UTILITIES
    # ==========================================
    def clear_all_screens(self):
        self.clear_countdown_and_overlay()
        
        for element in self.main_menu_elements:
            element.destroy()
        for element in self.settings_elements:
            element.destroy()
        for element in self.about_elements:
            element.destroy()
            
        self.main_menu_elements.clear()
        self.settings_elements.clear()
        self.about_elements.clear()

    def exit_game(self):
        self.app.exit_game()
        self.app.exit_game()

class Player():
    def __init__(self, base, render, world, loader, camera, sfx_all):
        self.base = base
        self.render = render
        self.world = world
        self.loader = loader
        self.camera = camera
        self.sfx_all = sfx_all
        
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
        model_path = self.loader.loadModel('sci_models/astronaut.glb')
        #model_path.setH(180)
        self.PlayerActor = Actor(model_path)
        self.PlayerActor.setScale(1.5)
        self.PlayerActor.setPos(0,0,-1.8)
        self.PlayerActor.setH(180)
        self.PlayerActor.pose('Walking', 0)
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
        
        self.health=100
        
    def toggle_camera_view(self):
        self.camera_view = (self.camera_view + 1) % 2
        if self.camera_view == 0:
            self.camera.reparentTo(self.first_person_view_NP)
        else:
            self.camera.reparentTo(self.third_person_view_NP)
            
    def start_attack(self):
        #self.PlayerActor.setPos(1,0.1,-1.8)
        self.player_anim_attack.play()
        self.sfx_all['attack'].play()

    def stop_attack(self):
        if self.player_anim_attack.isPlaying():
            self.player_anim_attack.stop()
            self.PlayerActor.setPos(0,0,-1.8)

    def start_punch(self):
        self.player_anim_boxing.play(0, 25)
        self.sfx_all['punch'].play()
        
    def stop_punch(self):
        if self.player_anim_boxing.isPlaying():
            self.player_anim_boxing.stop()
            
    def start_boxing(self):
        self.PlayerActor.setPos(1,0.1,-1.8)
        self.player_anim_attack.play()
        sound_sequence = Sequence(
            Func(self.sfx_all['boxing'].play),
            Wait(3.0),
            Func(self.sfx_all['boxing'].stop)
        )
        sound_sequence.start()

    def stop_boxing(self):
        if self.player_anim_boxing.isPlaying():
            self.player_anim_boxing.stop()
            self.PlayerActor.setPos(0,0,-1.8)
        
    def start_walk(self):
        if not self.player_anim_walking.isPlaying():
            if self.health>0:
                self.player_anim_walking.loop(0)
                self.PlayerActor.setPos(0,0,-1.8)
                self.sfx_all['player_walk'].setLoop(True)
                self.sfx_all['player_walk'].play()

    def stop_walk(self):
        if self.player_anim_walking.isPlaying():
            self.player_anim_walking.stop()
            self.sfx_all['player_walk'].stop()

    def standing_pose(self):
        if not self.player_anim_walking.isPlaying():
            if self.health>0:
                self.player_anim_walking.pose(0)
                self.PlayerActor.setPos(0,0,-1.8)
            
    def jump(self):
        if self.PlayerController.isOnGround():
            self.PlayerController.doJump()

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.die()

    def die(self):
        self.stop_walk()
        self.player_anim_dead.play()
        self.sfx_all['player_dead'].play()
        
class Enemy():
    def __init__(self, base, render, loader, sfx_all, audio3d):
        self.base = base
        self.render = render
        self.sfx_all=sfx_all
        self.audio3d=audio3d
        self.loader = loader
        
        model_path = self.loader.loadModel('sci_models/robo_anim.glb')
        self.EnemyActor = Actor(model_path)
        self.EnemyActor.setScale(1.8)
        #self.EnemyActor.setPos(1.934,64.853,-0.9)
        self.EnemyActor.setH(180)
        self.model=self.render.attachNewNode('EnemyMain')
        self.EnemyActor.reparentTo(self.model)
        self.model.setPos(1.934,64.853,-0.8)
        self.model.setH(180)

        # Enemy stats
        self.health = 100
        self.speed = 2

        # animations
        self.robo_anim_attack = self.EnemyActor.getAnimControl('Arise') #(one hand slice attack with rotation)
        self.robo_anim_dead = self.EnemyActor.getAnimControl('Skill_01') #dead
        self.robo_anim_angry = self.EnemyActor.getAnimControl('Walking') #(get angry, can also used as laughing)
        self.robo_anim_walking = self.EnemyActor.getAnimControl('BeHit_FlyUp') #Walking
        self.robo_anim_boxing = self.EnemyActor.getAnimControl('Running') #Boxing_Practice
        self.robo_anim_behit = self.EnemyActor.getAnimControl('Dead') #BeHit_FlyUp
        self.robo_anim_running = self.EnemyActor.getAnimControl('Skill_03') #Running
        self.robo_anim_arise = self.EnemyActor.getAnimControl('Boxing_Practice') #Arise (getup from ground)
        
    def start_punch(self):
        self.robo_anim_boxing.play()

    def stop_punch(self):
        if self.robo_anim_boxing.isPlaying():
            self.robo_anim_boxing.stop()
            
    def start_attack(self):
        self.robo_anim_attack.play()

    def stop_attack(self):
        if self.robo_anim_attack.isPlaying():
            self.robo_anim_attack.stop()

    def start_walk(self):
        if not self.robo_anim_walking.isPlaying():
            self.robo_anim_walking.loop(0)
            self.audio3d.attachSoundToObject(self.sfx_all['robot_walk'], self.model)
            self.audio3d.setDropOffFactor(0.3)
            self.sfx_all['robot_walk'].setLoop(True)
            self.sfx_all['robot_walk'].play()

    def stop_walk(self):
        if self.robo_anim_walking.isPlaying():
            self.robo_anim_walking.stop()
            self.sfx_all['robot_walk'].stop()

    def start_run(self):
        if not self.robo_anim_running.isPlaying():
            self.robo_anim_running.loop(0)
            self.sfx_all['robot_running'].setLoop(True)
            self.sfx_all['robot_running'].setVolume(0.4)
            self.sfx_all['robot_running'].play()

    def stop_run(self):
        if self.robo_anim_running.isPlaying():
            self.robo_anim_running.stop()
            self.sfx_all['robot_running'].stop()
            
    def take_damage(self, damage):
        self.health -= damage
        #if self.health <= 0:
        #    self.die()

    def die(self):
        self.robo_anim_dead.play()
        self.sfx_all['robot_dead'].play()
        sound_sequence = Sequence(
            Func(self.sfx_all['robot_impact'].play),
            Wait(1.0),
            Func(self.sfx_all['robot_dead'].play)
        )
        sound_sequence.start()

class HealthHUD():
    def __init__(self,aspect2d,taskMgr,start_x,pos_z,max_health,current_health):
        
        self.aspect2d = aspect2d
        self.taskMgr = taskMgr
        # Core Health Variables
        self.max_health = max_health#100.0
        self.current_health = current_health#100.0
        self.ghost_health = self.current_health
        self.ghost_speed = 50.0 # How fast the ghost bar catches up per second
        
        # Base UI Configuration
        # (X_scale, Y_scale, Z_scale) -> Y is depth, X is width, Z is height
        self.bar_width = 0.25
        self.bar_height = 0.015
        self.start_x = start_x #-0.8 # Left-aligned positioning on screen
        self.pos_z = pos_z #0.8    # Top of the screen
        
        self.setup_health_bar()
        
        # Add the update loop to the task manager
        self.taskMgr.add(self.update_ghost_bar, "UpdateGhostBarTask")

    def setup_health_bar(self):
        # CardMaker creates clean, solid-colored geometric cards 
        cm = CardMaker("hud_card")
        cm.setFrame(-1, 1, -1, 1) # Sets local bounds from center
        
        # 1. Background Bar (Dark Gray)
        self.bg_bar = self.aspect2d.attachNewNode(cm.generate())
        self.bg_bar.setPos(self.start_x + self.bar_width, 0, self.pos_z)
        self.bg_bar.setScale(self.bar_width, 1, self.bar_height)
        self.bg_bar.setColor(0.2, 0.2, 0.2, 0.7)

        # 2. Ghost Bar (Yellow/White)
        self.ghost_bar = self.aspect2d.attachNewNode(cm.generate())
        self.ghost_bar.setPos(self.start_x + self.bar_width, 0, self.pos_z)
        self.ghost_bar.setScale(self.bar_width, 1, self.bar_height)
        self.ghost_bar.setColor(0.9, 0.8, 0.2, 0.7)

        # 3. Current Health Bar (Green)
        self.health_bar = self.aspect2d.attachNewNode(cm.generate())
        self.health_bar.setPos(self.start_x + self.bar_width, 0, self.pos_z)
        self.health_bar.setScale(self.bar_width, 1, self.bar_height)
        self.health_bar.setColor(0.1, 0.8, 0.1, 0.7)

    def update_bar_display(self, bar_element, health_value):
    
        if health_value < 0: health_value = 0
        
        # Calculate percentage
        pct = health_value / self.max_health
        
        # Calculate new width scale
        new_scale_x = self.bar_width * pct
        
        # Shift the X position so the left side stays anchored in place
        new_pos_x = self.start_x + new_scale_x
        
        # Apply transformations
        self.health_bar.setScale(new_scale_x, 1, self.bar_height)
        self.health_bar.setX(new_pos_x)

    def update_ghost_bar(self, task):
        # Delta time ensures smooth tracking independent of framerate
        dt = globalClock.getDt()
        
        # If ghost bar is ahead of actual health, slide it down
        if self.ghost_health > self.current_health:
            self.ghost_health -= self.ghost_speed * dt
            
            # Clamp it so it doesn't overshoot actual health
            if self.ghost_health < self.current_health:
                self.ghost_health = self.current_health
                
            self.update_bar_display(self.ghost_bar, self.ghost_health)
            
        return Task.cont
        
    def take_damage(self, amount):
        self.current_health -= amount
        if self.current_health < 0: 
            self.current_health = 0
            
        # Update the green bar immediately
        self.update_bar_display(self.health_bar, self.current_health)
         
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
        self.props.setCursorHidden(False)
        self.win.requestProperties(self.props)
        # Intercept the window-close event
        self.win.set_close_request_event('window-close-clicked')
        self.accept('window-close-clicked', self.exit_game)
        
        self.game_is_running=False
        self.mouse_sensitivity=10
        self.bgm_volume=50
        self.sfx_volume=90
        
        self.menu = GameMenuSystem(self,True)

    def start_game_world(self):
        """This function will execute the moment 'Start Game' is clicked."""

        # --- hide mouse cursor ---
        self.props.setCursorHidden(True)
        self.win.requestProperties(self.props)
        
        # --- parameters ---
        #self.mouse_sensitivity=10
        self.move_speed=8#8

        # --- set loading label at start---
        self.CenterLabel=DirectLabel(text='Loading...',pos=(0,0,0),scale=0.07,text_align=TextNode.ACenter,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0),frameColor=(0, 0, 0, 0))
        base.graphicsEngine.renderFrame() #render a frame otherwise the screen will remain black
        base.graphicsEngine.renderFrame() 

        # --- load scene data from json ---
        # Get the directory where the main binary/script resides
        json_file = os.path.join('sci_models', 'scene_params3.json') # Sets absolute file path to avoid file not found errors
        clean_path = Filename.fromOsSpecific(json_file).getFullpath()
        self.scene_data_filename= clean_path

        # --- Camera param initializations ---
        self.cameraHeight = 1     # camera Height above ground
        self.cameraAngleH = 0     # Horizontal angle (yaw)
        self.cameraAngleP = 0   # Vertical angle (pitch)
        self.camLens.setNear(0.01)
        self.camLens.setFar(5500)
        self.camera.setPos(0,0,1)
        
        # --- initialize the bottom left label ---
        self.bottom_cam_label=DirectLabel(text='',pos=(-1.3,1,-0.8),scale=0.05,text_align=TextNode.ALeft,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0.2),frameColor=(0, 0, 0, 0.1))
        self.bottom_cam_label.setText('Goto Robot')
        
        # --- initialize the bottom right label ---
        self.bottom_right_label=DirectLabel(text='',pos=(1,1,-0.7),scale=0.05,text_align=TextNode.ACenter,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0.2),frameColor=(0, 0, 0, 0.1))
        #self.bottom_right_label.setText('press space key to skip')
        self.dialogue_text = "You: Why are you here? \n Robot: I have been sent here to destroy a rare plant. \n   It is located in that building.. \n   Mission Started ..."
        self.current_index = 0

        # --- initialize the timer label ---
        self.timer_label = OnscreenText(
            text="02:00",
            pos=(0.0, 0.95),  # Top center of the screen
            scale=0.05,
            fg=(1, 1, 1, 1),  # White text
            align=TextNode.ACenter,  # Center-aligned so it scales evenly
            mayChange=True,  # Optimizes performance for changing strings
            parent=self.aspect2d
        )
        self.timer_label.hide()
        
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
        self.taskMgr.add(self.run_event_1, "event_1_task")
        
        base.accept('tab', base.bufferViewer.toggleEnable)
        
        # --- initialize sound manager ---
        self.audio3d = Audio3DManager(self.sfxManagerList[0], self.camera)
        
        self.sfx_all = {
            "punch":base.loader.loadSfx("sci_models/sounds/universfield-punch-04-383965.ogg"),
            "boxing":base.loader.loadSfx("sci_models/sounds/muhammad_ayman-punch-95294.ogg"),
            "attack":base.loader.loadSfx("sci_models/sounds/taolao111-punch-sound-effect-7ehhx2evi5k-500092.ogg"),
            "robot_dead":base.loader.loadSfx("sci_models/sounds/freesound_community-dead-robot-01-82175.ogg"),
            "robot_laugh":base.loader.loadSfx("sci_models/sounds/diff_style-robot-laughing-1-344762.ogg"),
            "robot_damage_1":base.loader.loadSfx("sci_models/sounds/freesound_community-damage-40114.ogg"),
            "robot_running":base.loader.loadSfx("sci_models/sounds/flutie8211-running-steps-amp-loud-alarm-469367.ogg"),
            "robot_processing":base.loader.loadSfx("sci_models/sounds/greenstarfire-robot-processing-sound-fx-197857.ogg"),
            "robot_statement":base.loader.loadSfx("sci_models/sounds/freesound_community-robot-statements-31911.ogg"),
            "player_run":base.loader.loadSfx("sci_models/sounds/spinopel-run-fast-on-asphalt-393096.ogg"),
            "robot_walk":self.audio3d.loadSfx("sci_models/sounds/freesounds123-heavy-character-walk-363348_mono.ogg"),
            "player_walk":base.loader.loadSfx("sci_models/sounds/freesound_community-walking-on-hard-surface-25350.ogg"),
            "player_dead":base.loader.loadSfx("sci_models/sounds/cryptowista-human-body-fall-crashing-down-on-pavement-corpse-drop-315338.ogg"),
            "robot_impact":base.loader.loadSfx("sci_models/sounds/dragon-studio-impact-406635.ogg"),
            "player_impact":base.loader.loadSfx("sci_models/sounds/lucas_lesc-impact-clothes-308657.ogg")
        }
        
        # --- initialize bullet world ---
        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -9.81))
        
        # --- initialize player ---
        self.player=Player(base,self.render, self.bullet_world, self.loader, self.camera, self.sfx_all)
        
        # --- initialize enemy robot ---
        self.robot=Enemy(base,self.render, self.loader, self.sfx_all, self.audio3d)
        
        # --- load and set satellite dish and animation---
        model_path = self.loader.loadModel('sci_models/satellite_dish/satellite_antenna_anim.bam')
        self.actor_sat = Actor(model_path)
        self.actor_sat.reparent_to(self.render)
        self.actor_sat.setPos(55.5859375,95.69079,-0.9)
        self.actor_sat.setScale(5)
        self.sat_anim_1 = self.actor_sat.getAnimControl('Action')
        self.sat_anim_1.loop(0)
        
        
        # --- load game sounds ---
        self.event_1_started=False
        self.event_1_finished=False
        self.event_3_finished=False
        self.anim_seq_4_started=False
        self.mySound1 = base.loader.loadMusic("sci_models/Uncertain-Future.ogg")
        self.mySound2 = base.loader.loadMusic("sci_models/Dark-Future-Theme.ogg")
        self.current_bgm=self.mySound1
        self.current_bgm.setLoop(True)
        self.current_bgm.play()
        self.bgm_pause_time =0

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
        
        # --- vars initializations ---
        self.saved_hpr=[0,0,0]
        # Store the timestamp of when the player can punch next (0 means immediately)
        self.next_punch_time = 0.0
        self.punch_cooldown = 1.0 # 1 second cooldown
        # Store the timestamp of when the enemy can punch next (0 means immediately)
        self.next_punch_time_2 = 0.0
        self.punch_cooldown_2 = 1.0 # 1 second cooldown
        
        self.total_match_time=2*60 #minutes
        self.game_is_running=True
        self.you_win=False
        self.robot_walking = True
        
        pass

    def handle_escape_press(self):
        """Handles what happens when the player presses the ESCAPE key."""
        if self.game_is_running:
            self.exit_to_menu()

    def exit_to_menu(self):
        self.game_is_running = False

        self.props.setCursorHidden(False)
        self.win.requestProperties(self.props)
        
        # to pause the bgm
        self.bgm_pause_time = self.current_bgm.getTime()
        self.current_bgm.stop()

        self.menu = GameMenuSystem(self,False)
        self.pause_game_world()

    def pause_game_world(self):
        taskMgr.remove("camera_rotateTask")
        self.game_is_running=False
    
    def resume_game_world(self):
        taskMgr.add(self.actor_rotate, "camera_rotateTask")
        self.props.setCursorHidden(True)
        self.win.requestProperties(self.props)

        # to resume the bgm
        self.current_bgm.setTime(self.bgm_pause_time)
        self.current_bgm.play()
        
        self.game_is_running=True
    
    def exit_game(self):
        sys.exit()
        
    def start_typing_effect(self, label, text, speed=0.05):

        data = {
            "index": 0,
            "text": text,
            "label": label
        }

        def update(task):

            if data["index"] <= len(data["text"]):

                data["label"]["text"] = data["text"][:data["index"]]
                data["index"] += 1

                return Task.again

            return Task.done

        taskMgr.doMethodLater(speed, update, f"typing_task")
        
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
        if self.keyMap["move_backward"]:
            move.y -= speed
        if self.keyMap["move_left"]:
            move.x -= speed
        if self.keyMap["move_right"]:
            move.x += speed

        # Handle animation state: if any movement key is pressed, walk; otherwise, stop.
        # (Checking if 'move' vector has changed from its initial zero state)
        if self.player.health > 0 and (move.x != 0 or move.y != 0):
            self.player.start_walk()
        else:
            self.player.stop_walk()
            
        if self.player.health>0:
            self.player.PlayerController.setLinearMovement(move, True)
        else:
            # --- PLAYER IS DEAD ---
            # 1. Detach the camera if it hasn't been detached yet
            # Checking if the camera's parent is still the player
            if self.camera.getParent() == self.player.PlayerMain: # Or self.player.node() depending on your setup
                # Get the camera's current absolute position/rotation in the world
                cam_pos = self.camera.getPos(self.render)
                cam_hpr = self.camera.getHpr(self.render)
                
                # Reparent to render so it stays independent in the world
                self.camera.reparentTo(self.render)
                
                # Re-apply the world transformation so it doesn't snap to a different spot
                self.camera.setPos(cam_pos)
                self.camera.setHpr(cam_hpr)

            # 2. Apply the same movement vector directly to the camera
            # We use base.camera.getMat().xform() so "forward" matches where the camera is looking
            move_dir = self.camera.getMat().xform(move).getXyz()
            #move_dir.z = self.cameraHeight
            new_pos = self.camera.getPos() + move_dir * dt
            if not self.you_win:
                cam_heading = base.camera.getH()
                pure_heading_mat = LRotationf()
                pure_heading_mat.setHpr(Vec3(cam_heading, 0, 0))
                move_dir = pure_heading_mat.xform(move)
                new_pos.z = self.cameraHeight
            self.camera.setPos(new_pos)
            
            # Optional: Stop any player physics/movement completely
            self.player.PlayerController.setLinearMovement(Vec3(0, 0, 0), True)
            #self.player.stop_walk()
            
        self.triggerNP_2.setPos(self.robot.model.getPos(self.render))
        self.bullet_world.doPhysics(dt, 10, 1.0/180.0)  # Substeps for stability
        #pos=self.PlayerMain.getPos()
        #self.bottom_cam_label.setText('ActorPos: %0.2f,%0.2f,%0.2f'%(pos[0],pos[1],pos[2]))
                
        return task.cont  

    def look_at_smooth(self, node, target_pos, duration, task_name="smooth_look"):
        """
        Smoothly rotate a node toward a world position over time.
        
        Args:
            node        : NodePath to rotate
            target_pos  : Point3 target world position
            duration    : Time in seconds
        """
        start_h = node.getH(self.render)
        start_p = node.getP(self.render)

        # Direction vector
        dir_vec = target_pos - node.getPos(self.render)

        # Calculate heading (Y forward in Panda3D)
        target_h = math.degrees(math.atan2(-dir_vec.x, dir_vec.y))

        # Calculate pitch
        horizontal_dist = (dir_vec.x**2 + dir_vec.y**2) ** 0.5
        target_p = math.degrees(math.atan2(dir_vec.z, horizontal_dist))

        # Shortest angle interpolation
        dh = ((target_h - start_h + 180) % 360) - 180
        dp = target_p - start_p

        elapsed = 0.0

        def update_look(task):
            nonlocal elapsed

            dt = globalClock.getDt()
            elapsed += dt

            t = min(elapsed / duration, 1.0)

            # Smooth interpolation
            new_h = start_h + dh * t
            new_p = start_p + dp * t

            node.setH(self.render, new_h)
            node.setP(self.render, new_p)

            if t >= 1.0:
                return task.done

            return task.cont

        taskMgr.remove(task_name)
        taskMgr.add(update_look, task_name)
    
    def player_look_at_smooth(self, node, target_pos, duration, task_name="smooth_look"):
        """
        Smoothly rotate a node toward a world position over time.
        
        Args:
            node        : NodePath to rotate
            target_pos  : Point3 target world position
            duration    : Time in seconds
        """
        start_h = node.getH(self.render)
        start_p = self.camera.getP(self.render)

        # Direction vector
        dir_vec = target_pos - node.getPos(self.render)

        # Calculate heading (Y forward in Panda3D)
        target_h = math.degrees(math.atan2(-dir_vec.x, dir_vec.y))

        # Calculate pitch
        horizontal_dist = (dir_vec.x**2 + dir_vec.y**2) ** 0.5
        target_p = math.degrees(math.atan2(dir_vec.z, horizontal_dist))

        # Shortest angle interpolation
        dh = ((target_h - start_h + 180) % 360) - 180
        dp = target_p - start_p

        elapsed = 0.0

        def update_look(task):
            nonlocal elapsed

            dt = globalClock.getDt()
            elapsed += dt

            t = min(elapsed / duration, 1.0)

            # Smooth interpolation
            new_h = start_h + dh * t
            new_p = start_p + dp * t

            node.setH(self.render, new_h)
            self.camera.setP(self.render, new_p)

            if t >= 1.0:
                return task.done

            return task.cont

        taskMgr.remove(task_name)
        taskMgr.add(update_look, task_name)
    
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

        skybox = loader.loadModel('sci_models/sphere.bam')
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
        
    def show_info_gui_box(self,msg,status_flag):
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
            extraArgs=[status_flag],
            frameColor=(1, 1, 1, 0.9),
        )
        if self.game_is_running:
            taskMgr.remove("camera_rotateTask")
            self.props.setCursorHidden(False)
            base.win.requestProperties(self.props)

    def on_gui_box_button_click(self,status_flag): 
        if self.gui_box is not None:
            self.gui_box.destroy()
            self.gui_box = None
            if self.game_is_running:
                taskMgr.add(self.actor_rotate, "camera_rotateTask")
                self.props.setCursorHidden(True)
                base.win.requestProperties(self.props)
            if status_flag:
                self.move_speed=30 #if you win
                self.you_win=True
            else:
                self.move_speed=20 #if you lose
    
    def load_environment_models(self):
        json_file=self.scene_data_filename
        with open(json_file) as json_data:
            self.data_all = json.load(json_data)

        self.models_all=[]
        self.models_names_all=[]
        self.models_names_enabled=[]
        self.ModelTemp=""
        len_data_all=len(self.data_all)
        for i in range(len_data_all):
            data=self.data_all[i]
            self.models_names_all.append(data["uniquename"])
            if data["enable"]:
                self.ModelTemp=loader.loadModel(data["filename"])
                print(f"loading={i+1}/{len_data_all}")
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
        "right_click":0,"punch":0,"Start":0,"space_key":0,"camera_view":0,"take_screenshot":0}
        self.accept('escape', self.handle_escape_press)
        self.accept("w", self.setKey, ["move_forward", True])
        self.accept("s", self.setKey, ["move_backward", True])
        self.accept("w-up", self.setKey, ["move_forward", False])
        self.accept("s-up", self.setKey, ["move_backward", False])
        self.accept("a", self.setKey, ["move_left", True])
        self.accept("d", self.setKey, ["move_right", True])
        self.accept("a-up", self.setKey, ["move_left", False])
        self.accept("d-up", self.setKey, ["move_right", False])
        #self.accept("g", self.setKey, ["gravity_on", None])
        self.accept("mouse3", self.setKey, ["right_click", True])
        self.accept("mouse3-up", self.setKey, ["right_click", False])
        self.accept("f", self.setKey, ["punch", True])
        self.accept("f-up", self.setKey, ["punch", False])
        self.accept("c", self.setKey, ["attack", True])
        self.accept("c-up", self.setKey, ["attack", False]) 
        self.accept("g", self.setKey, ["Start", True]) 
        self.accept("space", self.setKey, ["space_key", True])
        self.accept("v", self.setKey, ["camera_view", True])
        self.accept("x", self.setKey, ["take_screenshot", True])   
        
    # Records the state of the keys
    def setKey(self, key, value):
        
        if key=="gravity_on":
            self.keyMap[key] = not self.keyMap[key]
            
        elif key=="space_key":
            self.player.jump()
            if self.event_1_started and not self.event_1_finished:
                self.event1_seq.finish()
                self.event_1_finished=True
                taskMgr.remove("typing_task")
                self.bottom_cam_label.setText('')
                self.bottom_right_label.setText('')
            self.keyMap[key] = False
            
        elif key=="punch":
            if value==True:
                self.keyMap[key]=True
                if not self.anim_seq_4_started:
                    self.player.start_punch()
                if not self.event_3_finished:
                    self.run_event_3()
            else:
                self.keyMap[key] = False
                #self.player.stop_attack() 
                
        elif key=="camera_view":
            self.player.toggle_camera_view()
            self.keyMap[key] = not self.keyMap[key]
        elif key=="take_screenshot":
            self.take_screenshot()
            self.keyMap[key]=False
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
        #self.directionalLight.setShadowCaster(True, 1024, 1024)
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
        #self.dlight1.node().show_frustum()
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
        plight1b.setAttenuation(LVector3(0, 0, 1))
        plnp1b = self.render.attachNewNode(plight1b)
        plnp1b.setPos(-48, 74, 6)
        self.render.setLight(plnp1b)
        
        self.spotLight_1 = Spotlight("main_spotlight")
        self.spotLight_1.setColor(Vec4(900,900,900, 1)) 
        self.spotLight_1.setAttenuation(Point3(1, 0.0, 1))
        lens = PerspectiveLens()
        lens.setFov(90, 90) 
        lens.setNearFar(1, 75) 
        self.spotLight_1.setLens(lens)
        #self.spotLight_1.setShadowCaster(True, 1048, 1048)
        self.spotNP = self.render.attachNewNode(self.spotLight_1)
        self.spotNP.setPos(-66, 74, 17)
        self.spotNP.lookAt(self.models_all[self.models_names_all.index('sci_models_pot_plant_1')]) 
        self.render.setLight(self.spotNP)
        #self.spotLight_1.showFrustum()
        
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
            
            if self.player.health>0:
                self.player.PlayerMain.setH(self.cameraAngleH)
            else:
                self.camera.setH(self.cameraAngleH)
            self.camera.setP(self.cameraAngleP)

        return Task.cont  # Task continues infinitely

    def start_camera_rotateTask(self):
            if self.game_is_running:
                taskMgr.add(self.actor_rotate, "camera_rotateTask")

    def stop_camera_rotateTask(self):
            if self.game_is_running:
                taskMgr.remove("camera_rotateTask")
                
    def run_event_1(self,task):
    
        event_flag=0
        overlapping = self.triggerNode_2.getOverlappingNodes()
        for node in overlapping:
            if node==self.player.PlayerController:
                event_flag=1
                
        if not event_flag==1: return Task.cont
        
        taskMgr.remove("event_1_task")
        
        # disable controls
        self.ignoreAll()

        for key in ['move_forward', 'move_backward', 'move_left', 'move_right']:
            self.keyMap[key] = False

        self.accept('escape', self.handle_escape_press)
        self.stop_camera_rotateTask()
        self.reset_mouse()

        # sounds
        #self.mySound1.stop()
        #self.mySound2.setLoop(True)
        #self.mySound2.play()
        
        self.bottom_right_label.setText('press space to skip')
        self.accept("space", self.setKey, ["space_key", True]) 
        
        # main cinematic sequence
        self.event1_seq = Sequence(
            Wait(1),
            Func(self.player_look_at_smooth, self.player.PlayerMain,self.robot.model.getPos(),1),
            #Func(self.player.PlayerMain.lookAt, (1.934,57,self.player.PlayerMain.getZ())),
            LerpPosInterval(self.player.PlayerMain,1,(1.934,57,self.player.PlayerMain.getZ())),
            Func(self.player_look_at_smooth, self.player.PlayerMain,LPoint3f(self.robot.model.getX(),self.robot.model.getY(),self.robot.model.getZ()+1),1),
            
            Wait(1),
            Func(self.start_typing_effect,self.bottom_cam_label,self.dialogue_text,0.03),
            
            Wait(8),
            Func(setattr, self, "event_1_finished", True),
            Func(self.set_keymap),
            Func(self.reset_mouse),
            Func(self.start_camera_rotateTask),
            Func(self.bottom_cam_label.setText,''),
            Func(self.bottom_right_label.setText,''),
            Func(self.run_event_2),
            
        )
        
        self.event_1_started=True
        self.event1_seq.start()
        return Task.cont
        
    def run_event_2(self):
        pot_plant = self.models_all[self.models_names_all.index('sci_models_pot_plant_1')]
        self.event2_seq = Sequence(
            Wait(0.5),
            Func(self.look_at_smooth, self.robot.model,pot_plant.getPos(),1),
            Func(self.robot.start_walk),
            Func(self.bottom_cam_label.setText,'stop the robot from destroying the plant.'),
            LerpPosInterval(self.robot.model,35,(pot_plant.getX(),pot_plant.getY(),self.robot.model.getZ())),
            Func(self.robot.start_attack),
            Wait(2),
            Func(self.show_info_gui_box,'Plant destroyed. You Lose',0),
            Func(setattr, self, "event_3_finished", True),#to prevent running of event_3
        )
        self.event2_seq.start()
        
    def run_event_3(self):
        event_flag=0
        overlapping = self.triggerNode_2.getOverlappingNodes()
        for node in overlapping:
            if node==self.player.PlayerController:
                event_flag=1
                self.event_3_finished=True#to prevent rerun of this event
                
        if not event_flag==1: return
        
        self.event2_seq.pause()
        self.event3_seq = Sequence(
        Func(self.bottom_cam_label.setText,''),
        Func(self.bottom_right_label.setText,''),
        Func(self.robot.stop_walk),
        Wait(0.5),
        Func(self.look_at_smooth, self.robot.model,LPoint3f(self.player.PlayerMain.getX(),self.player.PlayerMain.getY(),self.robot.model.getZ()),1),
        Wait(2),
        Func(self.robot.start_walk),
        Func(self.initialize_anim_seq_4),
        Func(taskMgr.add,self.anim_seq_4_chase, "anim_seq_4_chase"),
        )
        self.event3_seq.start()
        
    def reset_mouse(self):
        self.win.movePointer(0, int(self.win.getXSize() / 2), int(self.win.getYSize() / 2))

    def initialize_anim_seq_4(self):
        # initialize healthHUD
        self.playerhud_label=DirectLabel(text='Your Health:',pos=(-1.3,1,0.943),scale=0.04,text_align=TextNode.ALeft,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0),frameColor=(0, 0, 0, 0))
        self.enemyhud_label=DirectLabel(text='Robot Health:',pos=(0.47,1,0.943),scale=0.04,text_align=TextNode.ALeft,text_fg=(1, 1, 1, 0.8),text_bg=(0,0,0,0),frameColor=(0, 0, 0, 0))

        self.player_hud=HealthHUD(self.aspect2d,taskMgr,-1.05,0.95,100,100)
        self.enemy_hud=HealthHUD(self.aspect2d,taskMgr,0.75,0.95,100,100)
        
        self.timer_label.show()
        
        dialog_timings=[0,4,7,12,17,23] #seconds
        rn=random.randint(0,4)
        self.sfx_all['robot_statement'].setTime(dialog_timings[rn])
        Sequence(
        Func(self.sfx_all['robot_statement'].play),
        Wait(dialog_timings[rn+1]-dialog_timings[rn]),
        Func(self.sfx_all['robot_statement'].stop),
        ).start()
        #self.sfx_all['robot_statement'].play()
        self.current_bgm=self.mySound2
        self.current_bgm.setLoop(True)
        self.current_bgm.setVolume(0.8)
        self.current_bgm.play()
        
        self.anim_seq_4_started=True

    def player_punch_sequence(self, robot_pos, direction, damage_value):
        """Handles everything that happens when the player hits the robot."""
        # Calculate the knockback position for the robot
        knockback_pos = robot_pos - direction * 2
        
        # Fire a clean animation and event sequence
        seq = Sequence(
            Func(self.player.start_punch),
            Func(self.robot.take_damage, damage_value),
            Func(self.enemy_hud.take_damage, damage_value),
            # Animate the robot backwards
            ProjectileInterval(self.robot.model, endPos=knockback_pos, duration=0.2),
        )
        seq.start()

    def player_attack_sequence(self, robot_pos, direction, damage_value):
        """Handles everything that happens when the player hits the robot."""
        # Calculate the knockback position for the robot
        knockback_pos = robot_pos - direction * 15
        
        # Fire a clean animation and event sequence
        seq = Sequence(
            Func(self.player.start_attack),
            Func(self.robot.take_damage, damage_value),
            Func(self.enemy_hud.take_damage, damage_value),
            Func(self.sfx_all['robot_impact'].play),
            Func(self.robot.robo_anim_behit.play),
            ProjectileInterval(self.robot.model, endPos=knockback_pos, duration=1),
            Wait(0.5),
            Func(self.robot.start_walk),
            Func(self.sfx_all['robot_processing'].play),
            Wait(5),
            Func(self.sfx_all['robot_processing'].stop),
        )
        seq.start()
        
    def robot_punch_sequence(self, player_pos, direction, damage_value):
        """Handles everything that happens when the robot hits the player."""
        # Calculate the knockback position for the player
        knockback_pos = player_pos + direction * 2
        
        seq = Sequence(
            Func(self.robot.start_punch),
            Func(self.player.take_damage, damage_value),
            Func(self.player_hud.take_damage, damage_value),
            #ProjectileInterval(self.player.PlayerMain, endPos=knockback_pos, duration=0.2),
            Wait(1),
            Func(self.robot.start_walk),
        )
        seq.start()
        
    def robot_attack_sequence(self, player_pos, direction, damage_value):
        """Handles everything that happens when the robot hits the player."""
        # Calculate the knockback position for the player
        knockback_pos = player_pos + direction * 10
        
        seq = Sequence(
            Func(self.robot.start_attack),
            Func(self.player.take_damage, damage_value),
            Func(self.player_hud.take_damage, damage_value),
            # Animate the player backwards
            #ProjectileInterval(self.player.PlayerMain, endPos=knockback_pos, duration=1),
            Func(self.player.player_anim_behit.play),
            Wait(2),
            Func(self.player.standing_pose),
            Func(self.robot.start_walk),
        )
        seq.start()
        
    def anim_seq_4_chase(self, task):

        robot_pos = self.robot.model.getPos()
        player_pos = self.player.PlayerMain.getPos()
        current_time = globalClock.getFrameTime()

        # direction vector
        direction = player_pos - robot_pos
        direction.setZ(0)

        # distance check
        dist = direction.length()
        
        # normalize
        if direction.length() > 0:
            direction.normalize()

        # move the robot
        if dist>=1:
            if self.robot_walking:
                speed = 0.1
                self.robot.model.setPos( robot_pos + direction * speed )
                if dist>=50:
                    if random.random()<0.01:
                        seq = Sequence(
                            Func(setattr, self, "robot_walking", False),
                            Func(self.robot.stop_walk),
                            Func(self.robot.start_run),
                            Wait(2+3*random.random()),
                            Func(self.robot.stop_run),
                            Func(self.robot.start_walk),
                            Func(setattr, self, "robot_walking", True),
                        ).start()
            else:
                # running
                speed = 0.13
                self.robot.model.setPos( robot_pos + direction * speed )

        random_1=random.random()
        random_2=random.random()
        
        # to avoid the robot skewing when lookat the player 
        if 6 < dist < 7:
            self.saved_hpr = self.robot.model.getHpr()
        if dist<6:
            hpr=self.robot.model.getHpr()
            self.robot.model.setHpr(hpr[0],self.saved_hpr[1],self.saved_hpr[2])
        else:
            # look at player
            self.robot.model.lookAt(self.player.PlayerMain)
        
        damage_value = 5+2*random.random()
        # default punch anim
        if dist>=4:
            if self.keyMap['punch'] == True:
                self.player.start_punch()
        # you punch enemy
        if (dist<4)&(random_1>=0.3):
            if self.keyMap['punch'] == True:
                if current_time >= self.next_punch_time:
                    # Set the timestamp for when player can punch NEXT
                    self.next_punch_time = current_time + self.punch_cooldown
                    # Run the player_punch sequence
                    self.player_punch_sequence(robot_pos, direction, damage_value)
                    
        # if close, enemy punch you
        if (dist < 3)&(random_2>=0.3):
            if current_time >= self.next_punch_time_2:
                # Set the timestamp for when they can punch NEXT
                self.next_punch_time_2 = current_time + self.punch_cooldown_2
                # Run the robot attack sequence
                if self.player.health>0:
                    self.robot_punch_sequence(player_pos, direction, damage_value)
                    
        damage_value = 15+2*random.random()
        # you attack enemy
        if (dist<4)&(random_1<0.3):
            if self.keyMap['punch'] == True:
                if current_time >= self.next_punch_time:
                    # Set the timestamp for when player can punch NEXT
                    self.next_punch_time = current_time + self.punch_cooldown
                    # Run the player_punch sequence
                    self.player_attack_sequence(robot_pos, direction, damage_value)
                    
        # if too close, enemy attack you
        if (dist < 2)&(random_2<0.3):
            if current_time >= self.next_punch_time_2:
                # Set the timestamp for when they can punch NEXT
                self.next_punch_time_2 = current_time + self.punch_cooldown_2
                # Run the robot attack sequence
                if self.player.health>0:
                    self.robot_attack_sequence(player_pos, direction, damage_value)

        # if player health is zero, game end.
        if self.player.health <= 0:
            seq = Sequence(
                Wait(3),
                Func(self.robot.stop_walk),
                Func(self.robot.robo_anim_angry.play),
                Func(self.sfx_all['robot_laugh'].play),
                Wait(3),
                Func(self.show_info_gui_box,'You Lose',0)
            )
            seq.start()
            return Task.done
            
        # if robot health is zero, game end.
        if self.robot.health <= 0:
            seq = Sequence(
                Wait(2.1),
                Func(self.robot.stop_walk),
                Func(self.robot.die),
                Wait(3),
                Func(self.show_info_gui_box,'You Win',1)
            )
            seq.start()
            return Task.done
            
        # Calculate remaining time. if time is up, game end.
        time_remaining = self.total_match_time - task.time
        if time_remaining <= 0:
            self.timer_label.setText("00:00")
            self.robot.stop_walk()
            self.show_info_gui_box("Time's Up.",0)
            return Task.done
            
        # Format seconds into Minutes:Seconds format
        minutes = int(time_remaining) // 60
        seconds = int(time_remaining) % 60
        time_string = f"{minutes:02d}:{seconds:02d}"
        
        # Update HUD text
        self.timer_label.setText(time_string)
        
        # Optional: Make text turn red when under 10 seconds remaining
        if time_remaining <= 10.0:
            self.timer_label.setFg((1, 0.2, 0.2, 1)) # Red text
            
        return Task.cont

    def take_screenshot(self):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        filename = Filename(f"screenshot_{timestamp}.jpg")
        base.win.saveScreenshot(filename)
        
demo=GameMain()
demo.run()


