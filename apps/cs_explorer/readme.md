**CS Explorer** is a powerful web-based interface for exploring and visualizing your Cradlepoint router's configuration store data in real-time. Built as an Ericsson Cradlepoint SDK application, it provides an intuitive file explorer-like interface for browsing router configuration, status, control, and state data.
## ✨ Features

### 🌐 **Web Interface**
- **Modern UI**: Clean, responsive web interface accessible via browser
- **Dark/Light Mode**: Toggle between themes with persistent preferences
- **Tree Navigation**: Intuitive folder/file explorer for router data structure
- **Real-time Data**: Live router information with dynamic updates

### 🗂️ **Data Exploration**
- **Dynamic Discovery**: Automatically discovers and displays `status`, `config`, `control`, and `state` branches
- **Lazy Loading**: Efficient loading of data branches as you explore
- **Search Functionality**: Fast search across configuration paths and values
- **Data Type Recognition**: Color-coded display for strings, numbers, booleans, arrays, and objects

### 🔐 **Security & Decryption**
- **Encrypted Value Support**: Automatic detection of encrypted values (starting with `$1`)
- **One-Click Decryption**: Decrypt button for viewing sensitive configuration data
- **Secure Handling**: Safe display and management of encrypted router data

### 📊 **Data Visualization**
- **JSON Formatting**: Pretty-printed JSON with syntax highlighting
- **Raw Data View**: Toggle between formatted and raw JSON display
- **Type Indicators**: Visual indicators for different data types
- **Size Information**: Display data size and type metadata

### 🛠️ **Developer Features**
- **Copy to Clipboard**: Easy copying of configuration data
- **Download Data**: Export configuration data as JSON files
- **API Endpoints**: RESTful API for programmatic access
- **Error Handling**: Comprehensive error reporting and recovery

## 🚀 Quick Start

### Installation

1. **Download** the CS Explorer package or source files
2. **Upload** the built app to your NCM account in the Tools section
3. **Apply** to the desired group(s) in NCM
3. **Verify** via NCM at the group or device level under Extensibility

### Accessing the Interface

Once installed and running, access CS Explorer via:
```
http://<router_ip>:<port>
```

The port is shown in the app log at startup (for example `Web server started on port 9002`) and saved in the appdata field `cs_explorer_web_port`. It is usually 9002, or the next free port if 9002 is taken, and it stays the same after reboots. To change it, set `cs_explorer_web_port` in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection.

## Appdata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `cs_explorer_web_port` | No | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 9002 and saves it here. Delete it to pick a port automatically again. |

## 🎯 Usage

### Navigation
- **Sidebar**: Browse router data structure using the expandable tree
- **Content Area**: View selected data with formatting options
- **Search**: Use the search bar to quickly find specific configuration paths
- **Legend**: Toggle the color legend to understand data type indicators

### Key Actions
- **🔍 Explore**: Click folders to expand and explore nested data
- **📄 View**: Click items to display their values in the main content area
- **🔐 Decrypt**: Click the "Decrypt" button for encrypted values
- **📋 Copy**: Use toolbar buttons to copy data to clipboard
- **💾 Download**: Export data as JSON files for backup or analysis
- **🌙 Theme**: Toggle dark/light mode with the theme button

### Data Types & Colors
- **🟣 Properties**: Object keys and property names
- **🟢 Strings**: Text values and configuration strings  
- **🔴 Numbers**: Numeric values and counters
- **🟠 Booleans**: True/false configuration flags
- **⚫ Null**: Empty or undefined values
- **🔐 Encrypted**: Values requiring decryption (with decrypt button)

## 📁 File Structure

```
cs_explorer/
├── cs_explorer.py          # Main application server
├── index.html              # Web interface HTML
├── style.css               # UI styling and themes
├── script.js               # Frontend JavaScript logic
├── fontawesome.css         # Icon font (local)
├── webfonts/               # Font files for offline use
├── package.ini             # Application metadata
├── start.sh                # Application startup script
└── readme.md               # This documentation
```

## 🔧 Technical Details

### Architecture
- **Backend**: Python HTTP server with RESTful API
- **Frontend**: Vanilla JavaScript with modern CSS
- **Data Source**: Direct integration with router's configuration store via `cp` library
- **Themes**: CSS variable-based theming system

### API Endpoints
- `GET /api/tree?path={path}` - Retrieve data tree structure
- `GET /api/data?path={path}` - Get data for specific path
- `GET /api/search?q={query}` - Search configuration data
- `POST /api/decrypt` - Decrypt encrypted values

### Browser Support
- ✅ Chrome 70+
- ✅ Firefox 65+
- ✅ Safari 12+
- ✅ Edge 79+

## 🛡️ Security

- **Local Access**: Runs on router's local network interface
- **No External Dependencies**: All assets served locally for security
- **Encrypted Data Handling**: Safe viewing of sensitive configuration
- **Read-Only Operations**: Displays data without modification capabilities

## 🔍 Troubleshooting

### Common Issues

**Application won't start:**
- Check that the router meets minimum firmware requirements (7.25+)
- Check system logs for startup errors

**Application stops with a port error:**
- `cs_explorer_web_port` is not a number from 1 to 65535, or that port stayed busy
- Fix or delete the field, then start the app

**Cannot access web interface:**
- Ensure you're accessing `http://<router_ip>:<port>` with the port shown in the app log (also saved in `cs_explorer_web_port`)
- Check that the app's web port is not blocked by firewall (LAN clients need a Zone Firewall forward from the Primary LAN Zone to the Router Zone)
- Verify the application is running via NCOS application status

## 🤝 Contributing

CS Explorer is part of the Ericsson Cradlepoint SDK samples. For issues, suggestions, or contributions:

1. Review the [SDK Documentation](https://developer.cradlepoint.com)
2. Check existing [SDK Samples](https://github.com/cradlepoint/sdk-samples)
3. Follow Cradlepoint SDK development guidelines

## 📄 License

This application is provided as part of the Ericsson Cradlepoint SDK samples under the Cradlepoint SDK License Agreement.

## 🚀 Version History

### v1.0.0
- ✨ Initial release with full web interface
- 🎨 Dark/light mode theming
- 🔍 Real-time search and navigation
- 🔐 Encrypted value decryption support
- 📊 Enhanced data visualization and export

---