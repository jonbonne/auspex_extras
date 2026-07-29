from setuptools import setup

package_name = 'snes_overlay_streamer'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=[
        'pygame',
        'numpy',
    ],
    zip_safe=True,
    maintainer='JonBonne',
    maintainer_email='jonbonne@gmail.com',
    description='SNES-style Pygame overlay updated via /video_caption topic',
    license='MIT',
    entry_points={
        'console_scripts': [
            'snes_overlay_streamer = nodes.snes_overlay_streamer:main'
        ],
    },
)
