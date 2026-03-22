# Windows 11 Python Setup Guide

This guide walks you through installing Python on Windows 11 so that `python` and `pip` work correctly from PowerShell and Command Prompt.

> **Why can I double-click .py files but `python` doesn't work in the terminal?**
> This usually means Python was installed from the Microsoft Store, which registers file associations but doesn't always add Python to your system PATH. Follow the steps below to fix this.

---

## Step 1: Uninstall Existing Python (Recommended)

To avoid conflicts, remove any existing Python installations first.

1. Open **Settings** → **Apps** → **Installed apps**
2. Search for **Python**
3. Uninstall any entries you find (e.g., "Python 3.x" or "Python 3.x (Microsoft Store)")
4. Also search for and uninstall any **Python Launcher** entries

---

## Step 2: Download Python

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Click the large **Download Python 3.x.x** button
3. Save the installer to your Downloads folder

---

## Step 3: Install Python (Important — Read Carefully)

1. Right-click the downloaded installer and select **Run as administrator**
2. **⚠️ On the very first screen, check BOTH boxes at the bottom:**
   - ✅ **Use admin privileges when installing py.exe**
   - ✅ **Add python.exe to PATH** ← **THIS IS THE CRITICAL STEP**

   ![First screen checkboxes](https://docs.python.org/3/_images/win_installer.png)

3. Click **Install Now** (the default option is fine for most users)
4. Wait for the installation to complete
5. If you see a **Disable path length limit** option at the end, click it
6. Click **Close**

---

## Step 4: Verify the Installation

**Close and reopen** any PowerShell or Command Prompt windows (they won't pick up PATH changes until restarted).

Open a **new** PowerShell window and run:

```powershell
python --version
```
You should see something like `Python 3.x.x`.

Then verify pip:
```powershell
pip --version
```
You should see something like `pip 24.x from ...`.

---

## Step 5: Verify PATH (If `python` Still Isn't Found)

If `python --version` still doesn't work after a fresh PowerShell window:

1. Open **Settings** → search for **Environment Variables** → click **Edit the system environment variables**
2. Click **Environment Variables...**
3. Under **System variables**, find and select **Path**, then click **Edit...**
4. Verify these two entries exist (the version number may differ):
   - `C:\Users\<YourUsername>\AppData\Local\Programs\Python\Python3xx\`
   - `C:\Users\<YourUsername>\AppData\Local\Programs\Python\Python3xx\Scripts\`
5. If they are missing, click **New** and add them
6. Click **OK** on all dialogs
7. **Restart PowerShell** and try again

> **Tip:** To quickly find your Python install path, open File Explorer and navigate to
> `C:\Users\<YourUsername>\AppData\Local\Programs\Python\` — you should see a folder like `Python312` or `Python313`.

---

## Troubleshooting

### `python` opens the Microsoft Store
Windows has built-in app execution aliases that redirect `python` to the Store.

1. Open **Settings** → **Apps** → **Advanced app settings** → **App execution aliases**
2. Turn **OFF** both **App Installer - python.exe** and **App Installer - python3.exe**
3. Try `python --version` again

### `pip` is not recognized
Run the following to ensure pip is installed:
```powershell
python -m ensurepip --upgrade
```

### Scripts still can't find Python after installation
If you set environment variables (like API keys) in the same PowerShell session before installing Python, you need to **close and reopen PowerShell** for PATH changes to take effect. Alternatively, run:
```powershell
refreshenv
```
(This command is available if you have Chocolatey installed. Otherwise, just restart PowerShell.)
