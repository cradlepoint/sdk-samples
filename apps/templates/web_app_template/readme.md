# Web App Template – Style Guide

An interactive style guide and component library for building dashboards and internal tools. Use it as a visual reference, copy/paste-ready HTML source, or a playground to explore layout ideas.

---

## Scope

The Web App Template Style Guide provides a complete design system with:

### Component Categories

| Category | Description |
|----------|-------------|
| **Starter Templates** | Pre-built page scaffolds (e.g., Your Web App) to kickstart new projects |
| **Buttons** | Primary, secondary, status, and toggle actions for CTAs and toolbars |
| **Form Elements** | Text input, number input, checkbox, textarea, radio buttons, slider, dropdown select, toggle switch |
| **Tabs** | Accessible tabbed navigation for organizing dense content |
| **Cards & Panels** | Containers for summaries, analytics, and data-driven dashboards |
| **Typography** | Heading hierarchy and text treatments for readable content |
| **Colors** | Semantic palette (primary, success, warning, danger, info, secondary, text) with accessible contrast |
| **Status Indicators** | GPS, network, modem, signal strength, connectivity, power, disk, CPU, memory, battery, temperature, Ethernet, VPN, NTP, GPIO, and generic stat items |
| **Notifications** | Success, warning, error, and info toast alerts |
| **Loading States** | Spinners, overlays, and running indicators for async work |
| **Progress Bars** | Linear indicators for completion, success, warning, and danger |
| **Search** | Basic search input and search with clear button patterns |
| **Charts** | Bar, line, pie, area, horizontal bar, and donut chart starters |

### Features

- **Dark-mode friendly** – Palettes, icons, and states designed for light and dark themes
- **Copyable markup** – Structured HTML ready for rapid prototyping
- **Consistent design language** – Shared typography, color tokens, and spacing across all components
- **Production-ready patterns** – Snapshot of UI patterns suitable for internal portals, admin consoles, and monitoring dashboards

---

## Usage

### Running the Style Guide

1. **Using the Python server** (recommended):

   ```bash
   python3 web_app_template.py
   ```

2. Open a browser and go to: **http://localhost:8000**

3. The style guide (`index.html`) loads by default, with a sidebar for browsing components and a search bar for filtering elements.

### Building Your Own App

1. **Start from the blank template** – Copy `your_web_app.html` as your entry point. It includes:
   - The same layout and design system as the style guide
   - Sidebar navigation ready for your sections and sub-items
   - Dark mode toggle and search bar wired up
   - Typography, color tokens, and spacing aligned with the style guide

2. **Copy components** – Use markup from `index.html` as a reference. Copy the HTML structure you need and paste it into your app, then adjust copy or data bindings.

3. **Assets** – Ensure your app references:
   - `static/css/style.css` – Main stylesheet
   - `static/libs/font-awesome.min.css` – Icons
   - `static/libs/jquery-3.5.1.min.js` – jQuery (if your scripts depend on it)

### Project Structure

```
web_app_template/
├── index.html              # Style guide (full component library)
├── your_web_app.html       # Starter template for new apps
├── web_app_template.py     # HTTP server
├── start.sh                # Launch script
├── static/
│   ├── css/style.css       # Design system styles
│   ├── js/script.js        # Application logic
│   └── libs/               # Font Awesome, jQuery
└── README.md
```

---

## Requirements

- Python 3 (for the built-in HTTP server)
- Modern web browser
- Compatible with Cradlepoint NetCloud firmware 7.24+

---

## Version

- **Version:** 1.0.0  
- **Status:** BETA
