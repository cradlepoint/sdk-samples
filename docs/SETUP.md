# VS Code + Amazon Q Setup for Cradlepoint SDK

## Prerequisites

1. **VS Code**: Download from [code.visualstudio.com](https://code.visualstudio.com/)
2. **Amazon Q**: Install from [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=AmazonWebServices.amazon-q-vscode) or Extensions panel

## Quick Start (5 minutes)

1. **Install**: VS Code + Amazon Q extension, sign in
2. **Clone**: `Cmd+Shift+P` → "Git: Clone" → paste repo URL (https://github.com/phate999/sdk-samples)
3. **Configure**: Edit `sdk_settings.ini` with router IP/credentials
4. **Test**: Ask Amazon Q: "Create hello_router app that logs every 5 seconds" then "Deploy and show logs"

## Common Prompts

```
Make a system status dashboard

Make a vpn dashboard

Make a speedtest web app

Make a web dashboard to monitor and throttle client bandwidth with 10 Mbps default limit.

Add dashboard to @my_app

Show me how @5GSpeed handles speedtest data
```

## Workflow Commands

| Command | Description |
|---------|-------------|
| **deploy** | Deploy app to router using deploy.sh |
| **learn** | Update rules/docs based on what was learned |
| **rtfm** | Verify API paths/fields with curl before coding |

## What Amazon Q Knows Automatically

✅ Python 3.8 (no `|` operator)  
✅ Use `cp.log()` not `print()`  
✅ Use `try/except` everywhere  
✅ Never generate mock data  
✅ Use relative paths (`tmp/` not `/tmp`)  
✅ Deploy with `deploy.sh`

## Recommended Extensions

Open VS Code Extensions panel (`Cmd+Shift+X` or `Ctrl+Shift+X`) and install:

- **Amazon Q** - amazonwebservices.amazon-q-vscode
- **Python** - ms-python.python
- **Pylance** - ms-python.vscode-pylance

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Q suggests `\|` operator | Remind: "No \| operator for Python 3.8" |
| Deploy fails | Check `sdk_settings.ini` credentials |
| Need cp.py help | Ask: `@cp.py what functions handle GPS?` |

## Example Flow

```
You: Create "cell_logger" that logs signal strength every 30s to CSV
Q: [Creates app, Deploys, shows logs]

You: Add web interface showing last 100 readings
Q: [Adds static/ folder with HTML/CSS/JS]

You: Deploy
Q: [Deploys, confirms web server on port 8000]
```

---

**Remember**: `.amazonq/rules/` loads automatically - just describe what you want to build!
