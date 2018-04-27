"""
This app will scan the NCOS firmware and log all the python
modules that are available along with the python version.
It is intended for use prior to app development. If an app
requires a module not in the list, it will need to be added
to the app prior to the build and installation into the NCOS
device. Import dependencies of any added module will also
need to be addressed.

PIP can be used to load python modules into the app directory.
However, any 'dist' or 'egg' directories should be removed as
they are not required for functionality and will just use up
memory in the NCOS device.

PIP example:
pip(3) install --ignore-install --target=<app directory path> <python module>
* note: use pip on Windows and pip3 on Linux or OS X
"""

# A try/except is wrapped around the imports to catch an
# attempt to import a file or library that does not exist
# in NCOS. Very useful during app development if one is
# adding python modules.
try:
    import cs
    import os
    import sys
    import shutil
    import pkgutil
    import platform
    import collections
    import traceback

    from app_logging import AppLogger
    from importlib import util

except Exception as ex:
    # Output logs indicating what import failed.
    cs.CSClient().log('python_module_list.py', 'Import failure: {}'.format(ex))
    cs.CSClient().log('python_module_list.py', 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)


# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()


def log_module_list():
    # name this file (module)
    this_module_name = os.path.basename(__file__).rsplit('.')[0]

    # dict for loaders with their modules
    loaders = collections.OrderedDict()

    # names of build-in modules
    for module_name in sys.builtin_module_names:

        # find an information about a module by name
        module_info = util.find_spec(module_name)

        # add a key about a loader in the dict, if not exists yet
        if module_info.loader not in loaders:
            loaders[module_info.loader] = []

        # add a name and a location about imported module in the dict
        loaders[module_info.loader].append((module_info.name, module_info.origin))

    # all available non-build-in modules
    for module_name in pkgutil.iter_modules():

        # ignore this module
        if this_module_name == module_name[1]:
            continue

        # find an information about a module by name
        module_info = util.find_spec(module_name[1])

        # add a key about a loader in the dict, if not exists yet
        loader = type(module_info.loader)
        if loader not in loaders:
            loaders[loader] = []

        # Add a name and a location about an imported module in the dict.
        # Don't include files that were created for this app or any
        # shared libraries.
        if this_module_name not in module_info.origin and '.so' not in module_info.origin:
            loaders[loader].append((module_info.name, module_info.origin))

    line = '-' * 10
    # Log the python version running in the device
    log.info('{0} Python Version: {1} {0}'.format(line, platform.python_version()))

    # Log the python module that were found in the device
    for loader, modules in loaders.items():
        if len(modules) != 0:
            log.info('{0} Module Count={1}: {2} {0}'.format(line, len(modules), loader))
            count = 0
            for mod in modules:
                count += 1
                log.info('|{0:>3}| {1:20}| {2}'.format(count, mod[0], mod[1]))


if __name__ == "__main__":
    try:
        log_module_list()
    except Exception as e:
        log.error('Exception occurred! exception: {}'.format(e))
