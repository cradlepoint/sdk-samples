# Kiro Setup for Ericsson (Cradlepoint) SDK

## Quick Start (15 minutes)

### 1. Install Python

**Windows 11:**
- Download Python 3 from [python.org/downloads](https://www.python.org/downloads/)
- Run the installer
- **⚠️ IMPORTANT: Check the box "Add python.exe to PATH"** on the first screen before clicking Install Now. Without this, `python` and `pip` commands will not work from the terminal.
- Click **Install Now**
- Verify by opening a new terminal in Kiro and running: `python --version`
- Having trouble? See the [detailed Windows Python setup guide](../WINDOWS_PYTHON_SETUP.md)

**macOS:**
- Open Terminal and install Homebrew (if not already installed):
  ```
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```
- Install Python 3:
  ```
  brew install python3
  ```
- Verify: `python3 --version`

### 2. Install System-Level Dependencies (one-time)

These are needed for app signing and deploying to routers. Python libraries are handled automatically by Kiro in step 4.

**Windows:**
- Install OpenSSL (Light version) from [slproweb.com](https://slproweb.com/products/Win32OpenSSL.html). Choose Win64 or Win32 based on your machine.
  - **⚠️ On the final screen, the installer asks for a donation — uncheck the box and click Finish without donating.**

**macOS:**
```bash
brew install openssl
brew install hudochenkov/sshpass/sshpass
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install libffi-dev libssl-dev sshpass
```

### 3. Install Kiro

- Download Kiro from [kiro.dev](https://kiro.dev/)
- Run the installer and follow the setup prompts
- Sign in using **"Sign in with your organization identity"** — enter your Start URL and Region when prompted
  - *You can use your Google account to try it for free (500 credits to use in 30 days)*
- If you signed in using a free Google account and later want to switch to a different account that has a license, click the account panel icon at the bottom of the left sidebar to sign out and sign in with a different account.

### 4. Clone the Repository

- **⚠️ When Kiro starts and you see the Getting Started page, DO NOT click "Open a Project".**
- Click the **Source Control icon** (git) — the 3rd icon from the top in the left sidebar.
- If you see a button to download Git for Windows, click it. It will take you to the Git website — click the first link to download the latest version and install it (default settings are fine). Then click the **Reload** link in the Source Control panel where the button was.
- Click **"Clone Repository"** in the Source Control panel and paste:
  `https://github.com/cradlepoint/sdk-samples`
- Choose a folder where you want to save your code when prompted.
- Click **Open** when prompted.
- Click **"Yes, I trust the authors"** when prompted.

### 5. Python Environment (automatic)

When the chat panel comes up, go ahead and ask Kiro to build your app. The first time, Kiro will run a script to set up the environment and you will be prompted to Trust/Run the command. I recommend trusting Kiro with commands — it allows autopilot. Use at your own risk.

It automatically:
- Creates a `.venv` virtual environment
- Installs all Python dependencies from `requirements.txt` (requests, pyopenssl, cryptography, pyserial)

No manual `pip install` needed.

### 6. Configure **Developer Mode** Router Connection

- Click **Explorer icon** (file folder) in left sidebar OR press `Cmd+Shift+E` / `Ctrl+Shift+E`
- Navigate to `sdk_settings.ini` in the **file tree**
- Click to open → Edit these lines:
  ```ini
  dev_client_ip=192.168.0.1        # Your router IP
  dev_client_username=admin         # Router username
  dev_client_password=your_password # Router password
  ```
- Save with `Cmd+S` / `Ctrl+S`

### 7. Create with Kiro

- Open the Kiro chat panel from the sidebar
- In the **chat panel**, make your request. For example:
  ```
  Make a router dashboard
  ```
- Kiro will create and deploy the app, and automatically check logs for errors to fix.
- Kiro will tell you how to use the app, such as:
Access web interface at http://router_ip:8000

- Tell Kiro if there are any bugs, changes, or additions you would like. For example:
  ```
  The memory utilization is blank. Add a graph showing CPU usage over time
  ```
- Kiro will fix bugs, make changes, and deploy the app again.


## Prompt Examples

```
Make a vpn dashboard

Make a speedtest web app

Add dashboard to @my_app

Save state of @my_app to persist reboots

Show me how @5GSpeed handles speedtest data
```

## Workflow Commands

| Command | Description |
|---------|-------------|
| **deploy** | Deploy app to router using deploy.sh |
| **learn** | Update rules/docs based on what was learned |
| **rtfm** | Verify API paths/fields with curl before coding |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Deploy fails | Check `sdk_settings.ini` credentials |
| `python` not found (Windows) | Reinstall Python with "Add to PATH" checked |
| `pip` not found | Run `python -m ensurepip` or reinstall Python |
| Venv not created | Delete `.kiro/.setup_complete` and `.venv/`, then chat with Kiro |
