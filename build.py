import os
import argparse
import shutil
import subprocess
import configparser

import make

DIR_PATH = os.path.dirname(__file__)
BUILD_PATH = os.path.join(DIR_PATH, 'build')
DIST_PATH = os.path.join(DIR_PATH, 'dist')
SDK_SETTINGS_PATH = os.path.join(DIR_PATH, 'sdk_settings.ini')


def build(app_name):
    app_path = os.path.join(os.path.dirname(__file__), app_name)
    req_path = os.path.join(app_path, 'requirements.txt')
    try:
        shutil.rmtree(BUILD_PATH)
    except OSError:
        pass
    shutil.copytree(app_path, BUILD_PATH)
    sproc = subprocess.Popen(['pip', 'install', '-r', str(req_path), '-t', str(BUILD_PATH)])
    sproc.wait()
    if sproc.returncode:
        raise RuntimeError("received returncode: " + sproc.returncode)
    for dir_name, _, _ in os.walk(BUILD_PATH):
        if 'dist-info' in dir_name:
            shutil.rmtree(dir_name)


def dist(app_name):
    try:
        shutil.rmtree(DIST_PATH)
    except OSError:
        pass
    os.mkdir(DIST_PATH)
    make.new_package(BUILD_PATH, DIST_PATH)


def clean(app_name):
    try:
        shutil.rmtree(DIST_PATH)
        shutil.rmtree(BUILD_PATH)
        make.clean(app_name)
    except OSError:
        pass


def redeploy(app_name):
    clean(app_name)
    build(app_name)
    dist(app_name)
    make.uninstall()
    make.install(DIST_PATH)


def write_app_name_config_file(app_name):
    config = configparser.ConfigParser()
    config.read(SDK_SETTINGS_PATH)
    config['sdk']['app_name'] = app_name
    with open(SDK_SETTINGS_PATH, 'w') as outfile:
        config.write(outfile)


ACTIONS = {
    'build': build,
    'dist': dist,
    'clean': clean,
    'install': make.install,
    'uninstall': make.uninstall,
    'redeploy': redeploy
}


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", help="actions to execute", choices=ACTIONS.keys())
    parser.add_argument("app_name", help="app to use")
    return parser


def main():
    args = get_parser().parse_args()
    write_app_name_config_file(args.app_name)
    make.AppBuilder(False)
    ACTIONS[args.action](args.app_name)


if __name__ == "__main__":
    main()
