import sys

from setuptools import find_packages, setup

PY34_PLUS = sys.version_info[0] == 3 and sys.version_info[1] >= 4

exclude = ['sentinella.agent.agent2'
           if PY34_PLUS else 'sentinella.agent.agent']

install_requires = ['click==5.1',
                    'requests==2.9.1',
                    'requestsexceptions==1.1.1',
                    'pip==7.1.2',
                    'simplejson==3.8.1',
                    'python-novaclient==3.1.0', 
                    'python-neutronclient==3.1.0', 
                    'py-cpuinfo==0.1.8', 
                    'psutil==3.1.1', 
                    'watchdog==0.8.3'
                    ]

if not PY34_PLUS:
    install_requires.append('trollius==2.0')

setup(
    name='sentinella',
    version='0.4.4',
    description='A Python agent based on Tourbillon for collecting OpenStack metrics and logs'
    ' and store them into Sentinel.la',
    packages=find_packages(exclude=exclude),
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'sentinella = sentinella.agent.cli:main'
        ]
    },
    zip_safe=False,
    namespace_packages=['sentinella'],
    author='The Sentinel.la Team',
    author_email='hello@sentinel.la',
    url='http://sentinel.la',
    license='ASF',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: System :: Monitoring',
    ],
    keywords='openstack monitoring metrics agent sentinel.la',
)
