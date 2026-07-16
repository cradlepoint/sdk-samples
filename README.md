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

- Python 3.9 or higher — Windows users, see the [Windows Python Setup Guide](WINDOWS_PYTHON_SETUP.md)
- Git (optional, for cloning the repository)

### 1. Clone and set up

#### Kiro IDE

In Kiro, open the Command Palette and select **Git: Clone**, then paste:

```
https://github.com/cradlepoint/sdk-samples.git
```

Once the repo opens, click the **Setup Dev Environment** hook in the Kiro sidebar. It handles everything automatically.

#### Manual setup

```bash
git clone https://github.com/cradlepoint/sdk-samples.git
cd sdk-samples
```

**macOS / Linux:**

```bash
python3 setup_env.py && source .venv/bin/activate
```

**Windows:**

```cmd
python setup_env.py && .venv\Scripts\activate
```

This creates a `.venv` virtual environment, installs all Python dependencies, and activates the venv.

### 2. Configure router connection

Edit `sdk_settings.ini` with your dev router's IP and credentials:

```ini
[sdk]
app_name=hello_world
dev_client_ip=192.168.0.1
dev_client_username=admin
dev_client_password=your_password
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

## License

This software, including any sample applications, and associated documentation (the "Software"), are subject to the Cradlepoint Terms of Service and License Agreement available at https://cradlepoint.com/terms-of-service ("TSLA").

NOTWITHSTANDING ANY PROVISION CONTAINED IN THE TSLA, CRADLEPOINT DOES NOT WARRANT THAT THE SOFTWARE OR ANY FUNCTION CONTAINED THEREIN WILL MEET CUSTOMER'S REQUIREMENTS, BE UNINTERRUPTED OR ERROR-FREE, THAT DEFECTS WILL BE CORRECTED, OR THAT THE SOFTWARE IS FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS. THE SOFTWARE IS PROVIDED "AS-IS," WITHOUT ANY WARRANTIES OF ANY KIND. ANY USE OF THE SOFTWARE IS DONE AT CUSTOMER'S SOLE RISK AND CUSTOMER WILL BE SOLELY RESPONSIBLE FOR ANY DAMAGE, LOSS OR EXPENSE INCURRED AS A RESULT OF OR ARISING OUT OF CUSTOMER'S USE OF THE SOFTWARE. CRADLEPOINT MAKES NO OTHER WARRANTY, EITHER EXPRESSED OR IMPLIED, WITH RESPECT TO THE SOFTWARE. CRADLEPOINT SPECIFICALLY DISCLAIMS THE IMPLIED WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT.

Copyright © 2018 Cradlepoint, Inc. All rights reserved.
