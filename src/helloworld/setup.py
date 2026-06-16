from setuptools import find_packages, setup

package_name = 'helloworld'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ubuntu',
    maintainer_email='you@example.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'node_helloworld = helloworld.helloworld:main',
            'node_simple_pub = helloworld.simple_pub:main',
            'node_simple_sub = helloworld.simple_sub:main',
        ],
    },
)
