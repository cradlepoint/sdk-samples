# VS Code + Amazon Q Setup for Cradlepoint SDK

## Prerequisites

1. **VS Code**: Download from [code.visualstudio.com](https://code.visualstudio.com/)
2. **Amazon Q**: Install from [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=AmazonWebServices.amazon-q-vscode) or Extensions panel

## Quick Start (15 minutes)

### 1. Install VS Code + Amazon Q

- Download VS Code from [code.visualstudio.com](https://code.visualstudio.com/)
- Open VS Code → Click **Extensions icon** (4 squares) in left sidebar OR press `Cmd+Shift+X` (Mac) / `Ctrl+Shift+X` (Windows)
- Search "Amazon Q" → Click **Install** on "Amazon Q" by AWS
- Click **Sign in** button that appears → Follow authentication flow

### 2. Clone the Repository

- Press `Cmd+Shift+P` (Mac) / `Ctrl+Shift+P` (Windows) to open **Command Palette** (search bar at top)
- Type "Git: Clone" → Select it
- Paste: `https://github.com/cradlepoint/sdk-samples`
- Choose folder location → Click **Open** when prompted

### 3. Configure **Developer Mode** Router Connection

- Click **Explorer icon** (file folder) in left sidebar OR press `Cmd+Shift+E` / `Ctrl+Shift+E`
- Navigate to `sdk_settings.ini` in the **file tree**
- Click to open → Edit these lines:
  ```ini
  dev_client_ip=192.168.0.1        # Your router IP
  dev_client_username=admin         # Router username
  dev_client_password=your_password # Router password
  ```
- Save with `Cmd+S` / `Ctrl+S`

### 4. Create with Amazon Q

- Click **Amazon Q icon** (Q logo) in left sidebar OR press `Cmd+Shift+Q` / `Ctrl+Shift+Q`
- In the **chat panel** at bottom, make your request.  For example:
  ```
  Make a router dashboard
  ```
- Q will create and deploy the app, and automatically check logs for errors to fix.
- Q will tell you how to use the app, such as:  
Access web interface at http://router_ip:8000

- Tell Q if there are any bugs, changes, or additions you would like.  For example:
  ```
  The memory utilization is blank. Add a graph showing CPU usage over time
  ```
- Q will fix bugs, make changes, and deploy the app again.


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
