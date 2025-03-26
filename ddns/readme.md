# ddns

This application automatically updates a Dynamic DNS (DDNS) record with your router's WAN IP address.  

[**Download Built App**](https://github.com/cradlepoint/sdk-samples/releases/download/built_apps/ddns.tar.gz)  

## Required Configuration

The following SDK Appdata fields must be configured:

* `ddns_username`: Your DDNS provider username
* `ddns_password`: Your DDNS provider password
* `ddns_hostname`: The hostname to update (e.g., yourdomain.dyndns.org)
* `ddns_update_url`: The DDNS provider's update URL
* `ddns_wan_profile`: The name of your WAN profile as configured in Connection Manager

## Setup

1. Obtain your DDNS credentials and update URL from your DDNS provider
2. Note your WAN profile name from Connection Manager
3. Configure all required SDK Appdata fields

The application will check your WAN IP address every 10 seconds and update the DDNS record whenever the IP address changes.

## Troubleshooting

Check the application logs for any error messages if the DDNS updates are not working. Common issues include:
* Missing or incorrect SDK Appdata fields
* Invalid DDNS provider credentials
* Incorrect WAN profile name
