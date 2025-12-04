# AutoInstall

AutoInstall automatically tests and prioritizes multiple SIMs based on TCP download speed. The application detects all available SIMs, ensures each has a unique WAN profile, runs Ookla speedtests on each SIM, and then prioritizes them by download speed.  

[Download the built app from our releases page!](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps)

## SDK Appdata Configuration

Configure these settings in System > SDK Data:

- **MIN_DOWNLOAD_SPD** - Minimum download speed in Mbps. If no SIM meets this minimum, a failure report is sent. Default: 0.0
- **MIN_UPLOAD_SPD** - Minimum upload speed in Mbps. If no SIM meets this minimum, a failure report is sent. Default: 0.0
- **SCHEDULE** - Minutes between runs. 0 = only run at boot. Default: 0
- **NUM_ACTIVE_SIMS** - Number of fastest SIMs to keep active. 0 = keep all SIMs active. Default: 0
- **ONLY_RUN_ONCE** - If true, do not run if AutoInstall has been run on this device before. Default: false

## Usage

AutoInstall runs automatically at boot (if SCHEDULE is 0) or on the configured schedule. To manually trigger a test, clear the description field in NetCloud Manager.

## Results

Results are written to the router log, set in the description field (visible in NetCloud Manager), and sent as custom alerts. Results include timestamp, carrier information, band, RSRP, and download/upload speeds for each SIM.

