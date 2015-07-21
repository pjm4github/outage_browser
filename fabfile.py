#!/usr/bin/env python
"""
@author P Moran
@date 11/04/14
@file fabfile.py
@brief Fabric deployment file for EON Outage.
@see http://www.clemesha.org/blog/modern-python-hacker-tools-virtualenv-fabric-pip/
Copied from Paul Hubbard at http://164.109.105.219:5000/static/docs/fabfile_8py_source.html

NOTES
To run this from windows type...
C:\> fab 
...from the directory where this fabfile sits

Log into the remote host and type ...
~$ virtualenv eon_outage
On subsequent calls just type ...
~$ source ./eon_outage/bin/activate
Then type...
~$ cd groomer
~$ python g_main.py > EON_GROOMER_LOG.log &
This will run the script in the background.

"""
from __future__ import with_statement

from fabric.api import local, lcd, run, cd, put, env, task, settings
from fabric.colors import green, yellow, red

import g_config
from hashlib import sha256
import sys
import getpass

# This is the dev server

if g_config.PRODUCTION:
    env.hosts = ['10.123.0.28']
else:
    env.hosts = ['10.122.116.16']
# This is the deployment (production) server
# Gateway is the jumphost - remove if using VZ cloud or other non-jumped-host

local_username = getpass.getuser()

if local_username == 'patman':
    #  env.gateway = 'pmoran@p3jump.icsl.net'
    env.gateway = 'localhost'
    env.user = 'pmoran'
elif local_username == 'PJM':
    #  env.gateway = 'pmoran@p3jump.icsl.net'
    env.gateway = 'localhost'
    env.user = 'pmoran'
else:
    print(red('Please setup local_username in fabfile.py'))
    sys.exit(1)

env.forward_agent = True

LOCAL_BASE_DIR = 'C:\\repo\\personal\\myDocs\\Aptect\\Verizon\\Workproduct\\EON-IOT\\groomer'
REMOTE_BASE_DIR = '/local/home/pmoran/groomer'


def commit():
    """
    Commit code to git. FIXME Need a way to get commit messages via Fabric.
    """
    with settings(warn_only=True):
        local("git add -p && git commit -am 'Deploying via Fabric'")


def scp_push():
    """
    @brief Alternate deployment method, with gitlab down, use put instead.
    """
    if g_config.PRODUCTION:
        print('This is being deployed to the PRODUCTION SERVER')
    else:
        print('This is being deployed to the DEVELOPMENT SERVER')

    print('Deploying to host ip = %s, Note: dev is 10.122.116.16, prod is 10.123.0.28' % env.hosts[0])
    print('If this is not what you want then change the value of PRODUCTION in the config.py file.')
    with lcd(LOCAL_BASE_DIR):
        local('tar cjf deploy.tar.bz2 *.py requirements.txt cron/watchdog.sh *.sh')
    with cd(REMOTE_BASE_DIR):
        put('deploy.tar.bz2', REMOTE_BASE_DIR + '/deploy.tar.bz2')
        run('tar xjf deploy.tar.bz2')
        run('rm deploy.tar.bz2')
        run('chmod +x cron/watchdog.sh')
        run('chmod +x *.sh')

    with lcd(LOCAL_BASE_DIR):
        print('removing local deploy.tar.bz2 file')
        local('rm deploy.tar.bz2')


def push():
    """
    Push commits to gitlab.
    """
    with settings(warn_only=True):
        local('git push')


@task
def test():
    """
    Run unit tests.
    @see http://nose.readthedocs.org/en/latest/plugins/cover.html
    """
    with lcd('api'):
        local(
            'nosetests '
            '--with-coverage '
            '--cover-html '
            '--cover-html-dir=../docs/coverage '
            '--cover-erase '
            '--cover-package=api')


def compute_checksum(filename='api/model'):
    """
    Compute the SHA256 hash of a file. Used to detect changes. More fun
    than shelling out to md5, and fewer collisions too.
    """
    return sha256(open(filename + '.py', 'rb').read()).hexdigest()


def get_old_checksum(filename='api/model'):
    try:
        fh = open(filename + '.cs', 'r')
    except IOError:
        return None

    return fh.read()


def update_checksum(checksum, filename='api/model'):
    """
    @brief Try saving checksums in .cs suffix
    """
    cs_file = open(filename + '.cs', 'w')
    cs_file.write(checksum)
    cs_file.close()


def is_model_updated():
    """
    See if model.py has changed.
    @brief Always wiping the database is a poor solution. Let's see if we can
    auto-detect changes to model.py, from which we infer the model or data has
    has changed. If model.py is the same, we skip recreating the database.
    @see http://stackoverflow.com/questions/3431825/generating-a-md5-checksum-of-a-file
    """
    if compute_checksum() == get_old_checksum():
        print(green('Data model has not changed.'))
        return False

    print(yellow('Data model has changed, updating checksum'))
    update_checksum(compute_checksum())
    return True


@task(default=True)
def gitlab_down():
    scp_push()
    print(green('Deployed OK'))


@task
def quick():
    """
    Similar to deploy, but skips the Doxygen steps for speed and ease. Install
    of Doxygen is a bit of work.
    """
    # database()
    # test()
    commit()
    push()

    with cd(REMOTE_BASE_DIR):
        run('git pull')

    print(green('Deployed OK'))


"""
@bug Problem here - if you update the schema in a way that breaks existing code,
there's a crash when the code is updated against a stale DB. Need a way to
pause the app, update the code, rebuild the data, and then restart.

Been using git pull combined with debug mode in Flask, guess that needs to evolve.
"""


@task(default=False)
def deploy():
    """
    Default task - runs the full set.
    """
    quick()
    # local_doc_dirs()
    # remote_doc_dirs()
    # doxygen()
    # coverage()

    print(green('Done OK'))
