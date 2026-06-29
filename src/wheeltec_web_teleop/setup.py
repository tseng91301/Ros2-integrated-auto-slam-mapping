import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'wheeltec_web_teleop'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Include all launch files
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        # Include templates
        (os.path.join('share', package_name, 'templates'), glob(os.path.join('templates', '*'))),
        # Include static files
        (os.path.join('share', package_name, 'static', 'css'), glob(os.path.join('static', 'css', '*'))),
        (os.path.join('share', package_name, 'static', 'js'), glob(os.path.join('static', 'js', '*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ubuntu',
    maintainer_email='ubuntu@todo.todo',
    description='Web Teleop Control package for Wheeltec Robot with Map display',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'web_server = wheeltec_web_teleop.web_server:main',
            'trajectory_tracker = wheeltec_web_teleop.trajectory_tracker:main'
        ],
    },
)
