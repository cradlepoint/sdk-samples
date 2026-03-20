# Kiro Setup for Ericsson (Cradlepoint) SDK

## Quick Start (15 minutes)

### 1. Install Python

**Windows 11:**
- Download Python 3 from [python.org/downloads](https://www.python.org/downloads/)
- Run the installer
- **⚠️ IMPORTANT: Check the box "Add python.exe to PATH"** on the first screen before clicking Install Now. Without this, `python3` and `pip` commands will not work from the terminal.
- Click **Install Now**
- Verify by opening a new terminal in Kiro and running: `python --version`

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

### 2. Install Kiro

- Download Kiro from [kiro.dev](https://kiro.dev/)
- Run the installer and follow the setup prompts
- Sign in using **IAM Identity Center** — enter your Start URL and Region when prompted
  - *Note: You can also sign in with an AWS Builder ID for personal use*

### 3. Clone the Repository

- Press `Cmd+Shift+P` (Mac) / `Ctrl+Shift+P` (Windows) to open **Command Palette** (search bar at top)
- Type "Git: Clone" → Select it
- Paste: `https://github.com/cradlepoint/sdk-samples`
- Choose folder location → Click **Open** when prompted

### 4. Configure **Developer Mode** Router Connection

- Click **Explorer icon** (file folder) in left sidebar OR press `Cmd+Shift+E` / `Ctrl+Shift+E`
- Navigate to `sdk_settings.ini` in the **file tree**
- Click to open → Edit these lines:
  ```ini
  dev_client_ip=192.168.0.1        # Your router IP
  dev_client_username=admin         # Router username
  dev_client_password=your_password # Router password
  ```
- Save with `Cmd+S` / `Ctrl+S`

### 5. Create with Kiro

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
