# DR_NMEA Application Documentation

## Overview
The DR_NMEA application is engineered to improve GPS data accuracy by using dead reckoning techniques. It processes and refines NMEA sentences to deliver reliable latitude and longitude readings, even in environments with weak or absent GPS signals.

## Key Features

### 1. NMEA Sentence Handling
- **Monitoring:** Listens for incoming NMEA sentences on a specified port.
- **Data Extraction:** Retrieves latitude and longitude information from `$PCPTMINR` sentences.

### 2. Data Correction
- **Adjustments:** Updates the position mode and quality values in `$GPRMC` and `$GPGGA` sentences based on the extracted data.

### 3. Additional Sentence Generation
- **Supplementary Data:** Can add additional NMEA sentences (such as `$GNGSA`, `$GPGSV`, `$GLGSV`, and an additional `$GPGSA`) that are not shown in the user interface. (Optional)

### 4. Data Transmission
- **Communication:** Sends both corrected and additional NMEA sentences to designated servers using TCP, UDP, or serial communication methods.

### 5. Localhost Communication
- **Send-to-Server:** Enables GPS data to be sent directly to a localhost server on TCP port 10000, ensuring that `$PCPTMINR` sentences are processed for accurate dead reckoning latitude and longitude computations.

### 6. Configuration Management
- **Settings:** Automatically loads and stores configuration details such as the listening port and server parameters.
- **Location:** Configuration data is saved under **System > SDK Appdata** in an entry labeled `"DR_NMEA"`, which can be manually edited if necessary.

### 7. Debugging
- **Logging:** Provides debugging functionality to log messages when debugging mode is enabled.

## Deployment Instructions
To deploy the DR_NMEA application using NetCloud Manager, complete the following steps:

1. **Login to NetCloud Manager:**
   - Sign in to your NetCloud Manager account.

2. **Upload the SDK App:**
   - Navigate to the **Tools** page.
   - Click **Add** to upload an SDK app.
   - Select the `.tar.gz` file for the DR_NMEA application.

3. **Manage Install Locations:**
   - After uploading, choose the DR_NMEA app.
   - Click **Manage Install Locations**.
   - Select the version you wish to deploy.
   - Click the **+** sign next to any groups to which you want to deploy the application.

4. **SDK Appdata Group-Level Editing:**
   - If you are editing SDK Appdata at the group level, it is advised to create an entry in SDK Appdata named `"DR_NMEA"` at the group level *before* deploying the app to devices. This ensures that the app does not write default settings to the device configuration, which would override the group settings.
   - **Example value for "DR_NMEA" in SDK Appdata:**  
     `{"listen_port": 10000, "servers": [{"hostname": "server.example.com", "port": 5005, "protocol": "tcp"}], "add_sentences": [], "debug": false}`

## Usage
The DR_NMEA application is ideal for situations where precise GPS data is essential. It offers a robust solution for correcting and transmitting GPS data, ensuring accuracy even in challenging signal conditions.
