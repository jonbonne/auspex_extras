from setuptools import setup

package_name = 'video_captioner'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='JonBonne',
    maintainer_email='jonbonne@gmail.com',
    description='ROS 2 node for real-time video captioning using transformer models',
    license='MIT',
    entry_points={
        'console_scripts': [
            'video_captioner_node = nodes.video_captioner_node:main'
        ],
    },
)
