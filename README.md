# Ericsson Cradlepoint NCOS SDK

**Extend your Ericsson routers with custom Python applications.**

The NCOS SDK enables developers to build and deploy Python applications that run directly on Ericsson Cradlepoint NetCloud OS (NCOS) routers. Create custom logic for connectivity management, IoT data collection, monitoring, automation, and more—without replacing hardware.

---

## Ready-to-Use Built Apps

Pre-built application packages (`.tar.gz`) ready to install on your router are available at:

**[Download Built Apps](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps)**

These are compiled from the sample apps in this repository and can be installed via NetCloud Manager's Tools page without any development setup.

---

## Resources

| Resource | Link |
|----------|------|
| **SDK Developer Guide** | [docs/NCOS_SDK_Developer_Guide.md](docs/NCOS_SDK_Developer_Guide.md) |
| **cp.py Methods Reference** | [docs/cp_methods_reference.md](docs/cp_methods_reference.md) |
| **NetCloud Manager — SDK apps** | [Tools Tab](https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab) |
| **Third-Party Licenses** | [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md) |

---

## Repository Structure

```
├── apps/                   # Sample applications (flat, tagged via package.ini)
│   ├── 5GSpeed/            # Each app is a self-contained folder
│   ├── hello_world/        # with package.ini, start.sh, readme.md, etc.
│   ├── mqtt_app/
│   ├── ...                 # 75+ apps total
│   ├── templates/          # app_template, web_app_template
│   └── archive/            # Retired/inactive apps
├── docs/                  # API documentation
├── make.py                # Build/deploy tool
└── sdk_settings.ini       # Router connection settings
```

Apps are categorized using the `tags` field in their `package.ini` (e.g., `tags = connectivity, speedtest`).

---

## Development Environment Setup

**Prerequisites**

- Python 3.9 or higher — Windows users, see the [Windows Python Setup Guide](docs/WINDOWS_PYTHON_SETUP.md)
- Git (optional, for cloning the repository)
- A router with **Developer Mode** enabled in NetCloud Manager (Tools > Developer Mode Devices)

### 1. Get the code into Kiro

**Have Git installed?** In Kiro, open the Command Palette and select **Git: Clone**, then paste:

```
https://github.com/cradlepoint/sdk-samples.git
```

Kiro clones the repo and opens it for you.

**No Git?** Download the repo as a ZIP instead:

1. Go to [github.com/cradlepoint/sdk-samples](https://github.com/cradlepoint/sdk-samples)
2. Click the green **Code** button, then **Download ZIP**
3. Extract the ZIP to a folder on your computer
4. In Kiro, use **File > Open Folder** (or the Command Palette's **File: Open Folder**) and select the extracted `sdk-samples` folder

Once the repo is open in Kiro, open the chat panel — that's it. Kiro builds the `.venv`
environment and installs dependencies automatically the first time a session starts, then
asks in chat for your router details. Nothing to click. Then just describe the app you want —
see [docs/SETUP.md](docs/SETUP.md).

#### Manual setup (terminal)

If you'd rather set things up from a terminal instead of letting Kiro do it:

```bash
git clone https://github.com/cradlepoint/sdk-samples.git
cd sdk-samples
```

**macOS / Linux:**

```bash
python3 setup_env.py
```

**Windows:**

```cmd
python setup_env.py
```

`setup_env.py` does the whole setup:

- creates the `.venv` virtual environment
- installs everything in `requirements.txt`
- prompts for your dev-mode router IP, username, and password and writes them to
  `sdk_settings.ini` (press Enter or type `skip` to leave it for later)
- confirms the router is reachable and Developer Mode is on
- points the IDE's Python interpreter at `.venv`

Useful flags:

| Flag | Effect |
|------|--------|
| `--configure` | Only update the router settings |
| `--skip-router` | Only build the venv and install dependencies |
| `-y` | Never prompt (CI, hooks) |
| `--quiet` | Print only problems and changes |
| `--hook` | Session-start mode used by Kiro: fixes the environment, prints one status line, always exits 0 |
| `--router-ip / --router-username / --router-password` | Set settings without prompting |

### 2. Router connection settings

`setup_env.py` writes these for you. To edit them by hand, open `sdk_settings.ini`:

```ini
[sdk]
app_name=hello_world
dev_client_ip=192.168.0.1
dev_client_username=admin
dev_client_password=your_password
```

`sdk_settings.ini` holds credentials, so it is **git-ignored and never committed**.
You do not need to create it: `setup_env.py` and `make.py` both generate it from
[sdk_settings.ini.example](sdk_settings.ini.example) the first time they run.

If you cloned this repo before the file was git-ignored, untrack your local copy once:

```bash
git rm --cached sdk_settings.ini
```

---

## Quick Start — make.py

```bash
# Create a new app
python3 make.py create my_app

# Build a single app (searches apps/ recursively)
python3 make.py build my_app

# Build all apps
python3 make.py build all

# Deploy to connected router (purge + build + install + start)
python3 make.py deploy my_app

# Check status
python3 make.py status my_app
```

| Action | Description |
|--------|-------------|
| **create** | Scaffold a new app from `app_template` |
| **build** | Package an app as `.tar.gz` for deployment |
| **deploy** | Full lifecycle: purge → build → install → verify |
| **status** | Show app state on the connected router |
| **start / stop** | Control a running app |
| **uninstall** | Remove app from router |
| **clean** | Remove local build artifacts |

---

## License Agreement

This Software Development Kit License Agreement (this "**Agreement**") is entered into by and between Ericsson Enterprise Wireless Solutions, Inc. ("**Company**"), and the individual or entity that downloads, installs, or uses the SDK ("**You**" or "**Licensee**"). By downloading, installing, accessing, or using the SDK, You agree to be bound by this Agreement. If You are accepting on behalf of an entity, You represent that You have authority to bind that entity.

**License**. Company grants You a limited, non-exclusive, non-transferable, non-sublicensable, revocable license during the term to: (a) install and use the SDK internally to develop, test, and support applications that interoperate with the Service ("Applications"); and (b) distribute the SDK's redistributable runtime components, if any and only as expressly designated as redistributable in the documentation, solely as incorporated into and as necessary to run Your Applications. You will not, and will not permit any third party to: (a) reverse engineer, decompile, or disassemble the SDK, except to the extent this restriction is prohibited by applicable law; (b) modify, translate, or create derivative works of the SDK, except as expressly permitted for redistributable components; (c) rent, lease, sell, sublicense, or distribute the SDK except as expressly permitted; (d) use the SDK to build a product or service that competes with the Service or the SDK; (e) remove or alter any proprietary notices; or (f) use the SDK other than to develop and support Applications that interoperate with the Company’s services.  

**Limitations**. Company has no obligation under this Agreement to provide support, maintenance, updates, or upgrades for the SDK. Company may modify, deprecate, or discontinue the SDK or any feature at any time. THE SDK IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTY OF ANY KIND. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, COMPANY DISCLAIMS ALL WARRANTIES, EXPRESS, IMPLIED, OR STATUTORY, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT, AND ANY WARRANTY ARISING FROM COURSE OF DEALING OR USAGE OF TRADE. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, COMPANY WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR EXEMPLARY DAMAGES, OR FOR LOST PROFITS, REVENUE, DATA, OR GOODWILL, ARISING OUT OF OR RELATED TO THIS AGREEMENT OR THE SDK, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. COMPANY'S TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT WILL NOT EXCEED USD $100. This Agreement is effective until terminated. Company may terminate this Agreement immediately if You breach it. You may terminate at any time by ceasing all use of the SDK and destroying all copies. Upon termination, the licenses herein end and You will cease using and destroy all copies of the SDK.