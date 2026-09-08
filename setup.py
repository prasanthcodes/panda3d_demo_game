from setuptools import setup

setup(
    name="Project_FloraGuard",
    version="3.2.0",
    options={
        "build_apps": {
            'requirements_path': 'requirements.txt',
            # Fix: Provide it as a dictionary where the key is the exe name
            # and the value is the script, explicitly wrapped.
            "gui_apps": {
                "Project_FloraGuard": "demo.py",
            },
            "icons" : {
                "Project_FloraGuard" : [
                    "sci_models/icon.png",
            ],
            },
            # Add this to satisfy Panda3D's multiple-app logic parser
            #"macos_main_app": "MyGame",
            
            'exclude_patterns': [
                '**/*.tmp',
                '**/*.bak',
            ],
            
            # Asset Patterns to Include
            "include_patterns": [
                "**/*.glb",
                "**/*.png",
                "**/*.jpg",
                "**/*.egg",
                "**/*.bam",
                "**/*.mp3",
                "**/*.ogg",
                "**/*.wav",
                "**/*.prc",
                "**/*.json", 
                "**/*.sha", 
                "**/*.vert", 
                "**/*.frag", 
                "sci_models/**/*",
                "README.txt",
                "LICENSE.txt",
            ],
            
            "include_modules": [
                "panda3d",
                "direct",
                "panda3d-gltf",
                #"numpy",
                #"numpy.*",
            ],
            # Engine Plugins
            "plugins": [
                "pandagl",
                "p3display",
                "p3openal_audio",
                "p3tinydisplay",  # Add this fallback software renderer
            ],
            
            #'use_optimized_wheels': False,
            #'prefer_discrete_gpu': True,
             'bam_model_extensions': ['.glb'],
            
            # Target Platforms
            "platforms": [
                "win_amd64",
                # 'manylinux1_x86_64', 
                # 'manylinux2014_aarch64',
                # 'macosx_10_9_x86_64',
            ],
        }
    }
)