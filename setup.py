from setuptools import setup

APP = ['crimescout_mac.py']
DATA_FILES = ['chromedriver-mac']
OPTIONS = {
    'argv_emulation': True,
    'packages': ['selenium', 'pandas', 'folium'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
