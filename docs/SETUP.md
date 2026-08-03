# Kiro Setup for Ericsson (Cradlepoint) SDK

## Quick Start (15 minutes)

### 1. Install Python

**Windows 11:**
- Download Python 3 from [python.org/downloads](https://www.python.org/downloads/)
- Run the installer — **check "Add python.exe to PATH"** on the first screen
- Click **Install Now**
- Verify in a new terminal: `python --version`
- For detailed steps, troubleshooting, and PATH issues see [WINDOWS_PYTHON_SETUP.md](WINDOWS_PYTHON_SETUP.md)

**macOS (recommended — Homebrew):**
- Install Homebrew if you don't have it:
  ```
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```
- Install Python 3:
  ```
  brew install python3
  ```
- Verify: `python3 --version`
- Alternatively, download from [python.org/downloads](https://www.python.org/downloads/) if you prefer not to use Homebrew.

### 2. Install Kiro

- Download Kiro from [kiro.dev](https://kiro.dev/)
- Run the installer and follow the setup prompts
- Click **"Sign in with your organization identity"**
- On the next page, **DO NOT enter your email address**. Click the link below that says **"Sign in via IAM Identity Center instead"**
- On the next page, enter the **Start URL** and **Region** provided by your IT department
- *You can use your Google account to try it for free (500 credits to use in 30 days)*
- If you signed in using a free Google account and later want to switch to a different account that has a license, click the account panel icon at the bottom of the left sidebar to sign out and sign in with a different account.

### 3. Clone the Repository

- **⚠️ When Kiro starts and you see the Getting Started page, DO NOT click "Open a Project".**
- Click the **Source Control icon** (git) — the 3rd icon from the top in the left sidebar.
- If you see a button to download Git for Windows, click it. It will take you to the Git website — click the first link to download the latest version and install it (default settings are fine). Then click the **Reload** link in the Source Control panel where the button was.
- Click **"Clone Repository"** in the Source Control panel and paste:
  `https://github.com/cradlepoint/sdk-samples`
- Choose a folder where you want to save your code when prompted.
- Click **Open** when prompted.
- Click **"Yes, I trust the authors"** when prompted.

### 4. Run the Setup Dev Environment hook

- Open the **Agent Hooks** panel in the Kiro sidebar and run **Setup Dev Environment**
  (or type `/setup` in the chat panel).
- Kiro runs `setup_env.py`, which creates the `.venv` virtual environment and installs
  all Python dependencies.
- Kiro then asks for your **dev-mode router IP, username, and password** and saves them
  to `sdk_settings.ini`. Reply **skip** if you want to do it later.
- Kiro verifies the router answers and that Developer Mode is on.

**Prefer a terminal?** Open a terminal in the repo folder and run `python3 setup_env.py`
(macOS) or `python setup_env.py` (Windows). It asks the same questions.

**Developer Mode is enabled in NetCloud Manager, not in the router UI.** In NCM go to
**Tools > Developer Mode Devices** and add your device. Without it, installs are rejected.

**Your credentials stay local.** `sdk_settings.ini` is git-ignored, so it is never
committed. It is created for you from `sdk_settings.ini.example` on first run — there is
nothing to copy. If you cloned this repo before that change, run
`git rm --cached sdk_settings.ini` once to untrack your local copy (the file and its
contents stay on disk).

### 5. Create with Kiro

- Open the Kiro chat panel from the sidebar
- Describe what you want to build. Kiro will create the app, deploy it to your router, and check logs for errors automatically.
- Kiro will tell you how to access the app (e.g., `http://192.168.0.1:8000`)
- Keep chatting to add features, fix issues, or change behavior — Kiro redeploys after each change.

**Build something new:**
```
Build a web app that shows WAN connection status and signal strength for all modems

Create a dashboard showing active VPN tunnels, their uptime, and bytes transferred

Make a web UI that lets me toggle WiFi radios on and off

Create an app that runs a speedtest every hour and logs the results to a CSV file

Build a site survey app that logs GPS coordinates and signal metrics to a CSV
```

**Iterate on an app:**
```
Add auto-refresh every 30 seconds and show a banner when a WAN link goes down

Add a dark mode toggle to #my_app

Make #my_app persist its data across reboots using appdata

Add alerts to #my_app when a WAN link goes down
```

**Learn from existing code:**
```
Explain how #5GSpeed runs periodic speedtests

What API endpoints does #Mobile_Site_Survey use?
```

## Workflow Commands

| Command | Description |
|---------|-------------|
| **deploy** | Deploy app to router using `make.py deploy` |
| **learn** | Update rules/docs based on what was learned |
| **rtfm** | Verify API paths/fields with curl before coding |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Deploy fails | Run `python setup_env.py --configure` to re-enter router IP and credentials |
| "Developer Mode is NOT enabled" | Add the device in NCM under **Tools > Developer Mode Devices** |
| "No response from \<ip\>" | Confirm you are on the same network as the router and the IP is right |
| `python` not found (Windows) | Reinstall Python with "Add to PATH" checked — see [WINDOWS_PYTHON_SETUP.md](WINDOWS_PYTHON_SETUP.md) |
| `pip` not found | Run `python -m ensurepip` or reinstall Python |
| Venv not created or broken | Delete `.venv/`, then run the **Setup Dev Environment** hook again |
| Wrong interpreter in the editor | `setup_env.py` sets it; otherwise pick `.venv` via **Python: Select Interpreter** |
