from setuptools import setup, find_packages

setup(
    name="Game Helper Buddy",
    version="1.0",
    description="Child-friendly game helper application",
    author="You",
    packages=find_packages(),
    install_requires=[
        'keyboard',
        'pyttsx3==2.90',
        'requests==2.31.0',
        'Pillow==10.2.0',
        'comtypes',
        'pyautogui'
    ],
    entry_points={
        'console_scripts': [
            'game_helper_buddy = game_helper_buddy:main'
        ]
    },
    options={
        'bdist_wininst': {
            'title': "Game Helper Buddy Installer",
            'install_script': None  # Use default install script; customize if needed
        }
    }
)
