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

## License Agreement

This Software Development Kit License Agreement (this "**Agreement**") is entered into by and between Ericsson Enterprise Wireless Solutions, Inc. ("**Company**"), and the individual or entity that downloads, installs, or uses the SDK ("**You**" or "**Licensee**"). By downloading, installing, accessing, or using the SDK, You agree to be bound by this Agreement. If You are accepting on behalf of an entity, You represent that You have authority to bind that entity.

**License**. Company grants You a limited, non-exclusive, non-transferable, non-sublicensable, revocable license during the term to: (a) install and use the SDK internally to develop, test, and support applications that interoperate with the Service ("Applications"); and (b) distribute the SDK's redistributable runtime components, if any and only as expressly designated as redistributable in the documentation, solely as incorporated into and as necessary to run Your Applications. You will not, and will not permit any third party to: (a) reverse engineer, decompile, or disassemble the SDK, except to the extent this restriction is prohibited by applicable law; (b) modify, translate, or create derivative works of the SDK, except as expressly permitted for redistributable components; (c) rent, lease, sell, sublicense, or distribute the SDK except as expressly permitted; (d) use the SDK to build a product or service that competes with the Service or the SDK; (e) remove or alter any proprietary notices; or (f) use the SDK other than to develop and support Applications that interoperate with the Company’s services.  

**Limitations**. Company has no obligation under this Agreement to provide support, maintenance, updates, or upgrades for the SDK. Company may modify, deprecate, or discontinue the SDK or any feature at any time. THE SDK IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTY OF ANY KIND. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, COMPANY DISCLAIMS ALL WARRANTIES, EXPRESS, IMPLIED, OR STATUTORY, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT, AND ANY WARRANTY ARISING FROM COURSE OF DEALING OR USAGE OF TRADE. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, COMPANY WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR EXEMPLARY DAMAGES, OR FOR LOST PROFITS, REVENUE, DATA, OR GOODWILL, ARISING OUT OF OR RELATED TO THIS AGREEMENT OR THE SDK, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. COMPANY'S TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT WILL NOT EXCEED USD $100. This Agreement is effective until terminated. Company may terminate this Agreement immediately if You breach it. You may terminate at any time by ceasing all use of the SDK and destroying all copies. Upon termination, the licenses herein end and You will cease using and destroy all copies of the SDK.