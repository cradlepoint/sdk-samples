# python_module_list
Scans the router's NCOS firmware and logs all available Python modules along with the Python version. Use this before developing an app to check which modules are available without needing to bundle them.

## How It Works

The app uses `pkgutil.iter_modules()` and `sys.builtin_module_names` to enumerate all Python modules available in the router's firmware. It categorizes them by loader type and logs each module's name and file location.

## Purpose

Before developing an SDK app, run this to answer:
- What Python version is running on the router?
- Is a specific module available in the firmware?
- Do I need to bundle a library with my app, or is it already present?

If a required module is not in the list, you must include it in your app directory using pip:
```
pip3 install --ignore-installed --target=<app_directory> <module_name>
```

## Sample Output

```
---------- Python Version: 3.8.x ----------
---------- Module Count=45: <class 'importlib.machinery.BuiltinImporter'> ----------
|  1| _abc                | built-in
|  2| _codecs             | built-in
|  3| _collections        | built-in
...
---------- Module Count=120: <class 'importlib.machinery.SourceFileLoader'> ----------
|  1| asyncio             | /usr/lib/python3.8/asyncio/__init__.py
|  2| collections         | /usr/lib/python3.8/collections/__init__.py
...
```

## Notes

- The app runs once and exits (restart is set to false)
- Only pure Python (`.py`) modules are listed — shared libraries (`.so`) are excluded
- The list varies by firmware version — re-run after firmware upgrades
- Remove any `dist` or `egg` directories from bundled libraries to save flash storage

## Requirements

- Router firmware 7.26 or later
- No additional dependencies
