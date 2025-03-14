from setuptools import setup, find_packages
import sysconfig

setup(
    name="Game Helper Buddy",
    version="1.0",
    description="Child-friendly game helper application",
    author="You",
    packages=find_packages(),
    install_requires=[
        'pyttsx3',
        'requests',
        'Pillow',
        'mss',
        'python-tk'
    ],
    entry_points={
        'console_scripts': [
            'game_helper_buddy = game_helper_buddy:main'
        ]
    }
)
