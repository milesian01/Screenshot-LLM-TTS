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
            'title': "Game Helper Buddy",
            'install_script': None,
            'runtime_libs': ['comtypes',
                             'keyboard',
                             'pyautogui'],
            'runtime_module': ['_thread',
                             '_threading',
                             'socket',
                             'queue',
                             'time',
                             'sys',
                             'os']
        }
    }
)
