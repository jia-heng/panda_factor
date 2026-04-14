from setuptools import setup, find_packages

setup(
    name='panda_data',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'panda_data': [
            'factor/**/*',
            'market_data/**/*',
            'scripts/**/*',
            '*.yaml',
        ],
    },
    install_requires=[
        'flask',
        'pymongo',
        'redis',
        'loguru',
        'pandas',
        'panda_common',
        # 'panda_factor'  # 移除循环依赖
    ],
    entry_points={
        'console_scripts': [
            'panda_data = panda_data.__main__:main',
        ],
    },
) 