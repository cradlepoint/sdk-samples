# Containers Advanced Configuration Guide

Source: https://docs.cradlepoint.com/r/Containers-Advanced-Configuration-Guide

## Overview

The following expands on the Containers Quick Start Guide and provides additional instructions for container networking, volumes, the USB serial port, and health check features. The type of container determines which of these features are necessary.

---

## Minimum Requirements

Containers may be deployed at either the device or group level. Installing a Docker container on an endpoint requires the following:
- 
NetCloud OS version 7.2.20 or later
- 
Any of the following routers equipped with an Advanced license.

Router
Architecture
 | 
AER2200 | 
ARMv7 32-bit
 | 
IBR1700 | 
ARMv7 32-bit
 | 
E300 | 
ARMv8 64-bit
 | 
E3000 | 
ARMv8 64-bit
 | 
R920 | 
ARMv8 64-bit
 | 
R980 | 
ARMv8 64-bit
 | 
R1900 | 
ARMv8 64-bit
 | 
R2100 | 
ARMv8 64-bit
- 
Sufficient memory on the endpoint to run the NetCloud Container Orchestrator. For additional information, see Adjusting Memory Resources for NetCloud Container Orchestrator.
- 
A basic understanding of Docker.
## Tip

Why does my Container data usage differ from my Client Data Usage?
This is due to a fundamental difference in measurement layers: Client Data Usage is captured at Layer 3 (IP), while container usage is captured at Layer 2 (Ethernet). The Variance comes from removing the 14-Byte Ethernet header when processing the packet.

---

## Networks

## Note

The container networks configuration option is only available with NetCloud OS 7.2.50 and later.
By default, Docker Compose distributes IP addresses starting from "172.17.0.2" in the Docker LAN subnet. To change the default subnet, you can either set the IP statically or dynamically using DHCP (if your container supports it) so the Docker host effectively acts as a DHCP server for each container LAN.
In the following example, we create a dedicated IP Subnet named "Container Net" on subnet 10.99.99.0/24 and assign a DHCP IP address to a container interface from the Container Net subnet.
Use the following procedure to add a new local IP subnet and enable a DHCP range for container interfaces.
- 
Log into NetCloud Manager.
- 
Select Devices in the left-side navigation panel.
- 
Select a router from the Routers page. Alternatively, to make configuration changes to a group, navigate to the Groups page and select a group.
- 
Select Configuration and then Edit.
- 
Navigate to NETWORKING > Local Networks > Local IP Networks.
- 
Select Add.
- 
Enter the name of the new Local IP Network. For example, "Container Net".
- 
Under IPv4 Settings, enter the IP Address and Netmask of the IP network.
 | 
- 
(Optional) Configure the DHCP scope with the IP address using the Range Start and Range End fields. For example, 10.99.99.2 thru 10.99.99.9 for containers.
 | 
- 
Select Save.
- 
Navigate to SYSTEM > Containers > Projects.
- 
Select Edit if the project is already created or select Add to create a new project. See Configuring a Container for more information.Configuring a Container
- 
The network must be assigned to the Project before it can be added to the service level. In the Network section, select Add and choose from the list of available networks.
 | 
- 
Select Save.
- 
Under Services, select Add.
The Services Configuration dialog box opens.
- 
If using Static IP for containers, enter the static address and select Save.
## Note

It is recommended to reserve the Static IP via the Reservations panel in the DHCP Configuration page to avoid IP conflicts.
 | 
- 
Under the Network tab, specify the container network from the drop-down menu.
 | 
- 
Select Save.
- 
From the Devices page in NetCloud Manager, select the device name and then navigate to Home > Containers. Select the name of the container to view the IP details. Verify a container interface is getting an IP address from the 10.99.99/24 address range.
 |

### Putting a Container on the Router's Primary LAN (bridge.uuid)

To place a container directly on a router LAN (so it gets a real LAN IP and goes through the firewall like a client device), use `driver_opts` with `com.cradlepoint.network.bridge.uuid` set to the LAN's UUID from `config/lan/*/_id_`:

```yaml
version: "2.4"
services:
  unifi-network-application:
    image: lscr.io/linuxserver/unifi-network-application:latest
    container_name: unifi
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
      - MONGO_USER=unifi
      - MONGO_PASS=unifi
      - MONGO_HOST=unifi-db
      - MONGO_PORT=27017
      - MONGO_DBNAME=unifi
    volumes:
      - etc:/etc
      - usr:/usr
    restart: unless-stopped
    networks:
      lannet:
        ipv4_address: 192.168.0.2
  unifi-db:
    image: phate999/unifi-db
    container_name: unifi-db
    volumes:
      - db:/data/db
    restart: unless-stopped
    networks:
      lannet:
        ipv4_address: 192.168.0.3
volumes:
  etc:
    driver: local
  usr:
    driver: local
  db:
    driver: local
networks:
  lannet:
    driver: bridge
    driver_opts:
      com.cradlepoint.network.bridge.uuid: 00000000-0d93-319d-8220-4a1fb0372b51
    ipam:
      driver: default
      config:
        - subnet: 192.168.0.0/24
          gateway: 192.168.0.1
```

Key points:
- `com.cradlepoint.network.bridge.uuid` is the LAN UUID from `config/lan/0/_id_` (Primary LAN)
- Container gets a real LAN IP; traffic goes through zone firewall like any client
- Set static `ipv4_address` within the subnet; reserve in DHCP config to avoid conflicts
- Multiple containers can share the same LAN network with different static IPs

---

## Volumes

Containers run in a specially protected namespace within the router firmware (NetCloud OS) and may only operate within this space. This is to protect the host filesystem from containers accessing and potentially corrupting the operating files and breaking the host. There are several ways to get user files into a container, depending on which services are running in the container. One method would be to run an SSH or FTP service in the container and transfer files between an external client and the container. Another method would be to run a second container with a dedicated FTP server, mount a volume between the containers on the host, and then transfer files between the two. This latter method is used mainly in development environments.
To demonstrate how volumes work in containers, the following example shows how to create a project named shared- data-test with a volume named share-data. Two redis:alpine containers will be created under the shared-data- test project and the /var/tmp directory on each container mapped to the share-data volume on each. This shared resource could be used to copy data (from a file in this example) from one container to the other.
## Tip

Data on a volume is not updated with changes from a new image. To resolve this, a new project must be created; this creates a new volume that gets the changes from the new image.
- 
Log into NetCloud Manager.
- 
Select Devices in the left-side navigation panel.
- 
Select a router from the Routers page. Alternatively, to make configuration changes to a group, navigate to the Groups page and select a group.
- 
Select Configuration and then Edit.
- 
Navigate to SYSTEM > Containers > Projects.
## Note

See Configuring a Container for more information on setting up the new project.Configuring a Container
- 
Select Add.
- 
Enter a name (for this example, "shared-data-test") and ensure it is enabled.
 | 
- 
Select Compose Builder and add a new volume name. For example, "shared-data".
 | 
- 
Select Save.
- 
From the Project Builder window, select Add under Services.
- 
Select the Basic tab and enter the container name (redis1), an image (redis:alpine), and other information needed for the container.
 | 
- 
Select Volumes & Devices to map the volume to the service (container).
- 
Under Volumes, select Add and select the volume name created earlier from the drop-down menu (for this example, we used shared-data).
## Note

Selecting the Config Store option exposes cs.sock and allows a container to communicate with its host device's Config Store.
Selecting the USB Storage option allows containers to use devices connected to USB ports on the router for storage.
- 
Append ":/var/tmp" to the end of the volume name (for example, shared-data:/var/tmp). This is where the container mounts the volume.
- 
Select Save.
 | 
Repeat steps 12 through 16 to create a second container service named redis2:alpine and map the shared-data volume to it.
 | 
- 
Select Save.
- 
Navigate to Project Configuration > Compose and review the generated compose yaml.
 | 
- 
Select Save.
- 
Select Commit to write the config to the router.
- 
To verify the volume is accessible from each container, open the console to run the container exec commands and create a file under the /var/tmp directory in redis1 container. Once the file is created, log into the second container, redis2, and verify the file is visible in the /var/tmp directory. See the following for the CLI commands:
[admin@E300-dae: /]$ container list

Project: shared-data-test

Containers: shared-data-test_redis2_1 shared-data-test_redis1_1

[admin@E300-dae: /]$ container exec shared-data-test_redis1_1 sh

/data # cd /var/tmp

/var/tmp # ls

/var/tmp # touch shared-file.txt

/var/tmp # ls

shared-file.txt

/var/tmp # exit

shared-data-test_redis1_1 exec done.

[admin@E300-dae: /]$ 

[admin@E300-dae: /]$ 

[admin@E300-dae: /]$ container exec shared-data-test_redis2_1 sh

/data # cd /var/tmp

/var/tmp # ls

shared-file.txt

/var/tmp # 

/var/tmp # 

/var/tmp # exit

shared-data-test_redis2_1 exec done.

[admin@E300-dae: /]$
For more information on Docker Hub volumes, See Docker Volumes.

---

## Mapping a USB Serial Port

To map a USB serial port for Out-of-Band Management (OOBM) to a container, go to System > Containers > Projects > Volumes & Devices.
 | 
Select the USB Serial Port from the Device drop-down menu and then select Save and Save again.

---

## USB Storage for Containers

Using USB devices as storage for containers is supported beginning with NetCloud OS 7.23.20. Use the following procedure to enable storage to a USB device for a container.
- 
Log into NetCloud Manager.
- 
Select Devices in the left-side navigation panel.
- 
Select a router from the Routers page. Alternatively, to make configuration changes to a group, navigate to the Groups page and select a group.
- 
Select Configuration and then Edit.
- 
Navigate to SYSTEM > Containers > Projects.
- 
Select a container and then select Edit.
- 
Select Compose Builder.
- 
Select a service and then select Edit.
- 
Select Volumes & Devices.
- 
From the Volumes drop-down menu, select USB Storage. Selecting USB Storage allows for containers to use USB storage devices as a valid volume locations.
- 
Select Save on the Volumes & Devices screen.
- 
Select Save on the Project Builder screen.
- 
Select Save on the Project on the Configuration screen.

---

## Considerations When Using USB Devices for Container Storage

- 
If a project has more than one container using the USB device, all the project's containers restart if the USB device is plugged or unplugged.
- 
If a project has only one container using the USB device, just that container is restarted upon plug or unplug.
- 
The container mounts the USB device at var/media.
- 
Multiple containers can simultaneously use the USB device for storage.
- 
It is not recommended to write NetCloud OS logs to USB storage while containers use the USB device. Writing to USB is time-intensive; NetCloud OS logs may delay data writes from containers and vice versa.

---

## Constraints with Using USB Devices

- 
NetCloud OS mounts the USB storage device as a FAT32 filesystem.
- 
Max partition size: 32GB
- 
Max file size: 4GB
- 
One USB storage device is supported at a time. Multiple USB storage devices plugged via USB hub is not supported.
- 
It takes a few seconds for the kernel to notify NetCloud OS of a USB device plug/unplug. Rapidly plugging and unplugging a USB device may cause the USB storage volume to be out of sync with the actual state of the USB device.
## Note

If a corrupted or unrecognized USB storage device is plugged in while a containerized project is already running, the container may log timeout or restart errors. These errors do not impact normal operation and the container continues running. To avoid messages like this, it is recommended to plug in a valid USB device before starting the project.

---

## Health Check

The health check is a feature of the container runtime that can be used to check on the health of an application running within the container and restart the container if it is not healthy. For example, if a web server is running inside of a container, the curl command could be used to ensure the web server is running and healthy. This is what the configuration would look like:
 | 
In this example, the Test field is set to the command that will be executed inside of the container. The specified command is application-specific:
curl -f https://localhost || exit 1
Any exit value from the test command that is not zero tells the container runtime that the test was not successful. An exit value of zero is considered a successful test.
The Interval specifies the duration between test executions. Retries specify the number of test failures that constitutes an unhealthy container. The Timeout is the time duration the test must execute within before it is considered a failed test. Finally, the Condition specifies under what condition the container should be restarted. For further information on health checks, see the Docker Compose documentation.

---

