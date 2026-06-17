# Containers Quick Start Guide

Source: https://docs.cradlepoint.com/r/Containers-Quick-Start-Guide

## Containers Overview

Edge compute capabilities are becoming increasingly important for IoT deployments that need to reduce latency and the amount of data going from the network edge to the cloud. To address this need, the NetCloud Container Orchestrator enables lightweight applications to run inside secure and isolated containers on endpoints. NetCloud Container Orchestrator supports both public and private container registries, thereby allowing users to deploy and run Open Container Initiative (OCI)-compatible Docker container workloads from any Docker container registry, such as Docker Hub or Amazon ECR. Depending on the use case, these container applications can be run on a wireless WAN infrastructure.
The NetCloud Container Orchestrator supports Docker Compose, which is a tool for defining and running multi-container Docker applications. With Docker Compose, customers can use YAML to configure and start application services.

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

## Enabling the NetCloud Container Orchestrator Service

The NetCloud Container Orchestrator service must be enabled for an account before containers can be deployed on a device in the account. NetCloud Container Orchestrator allows containers to be installed on routers. It only needs to be done one time to allow containers to be built at any time.
Complete the following steps to enable the NetCloud Container Orchestrator service:
- 
Log into NetCloud Manager.
- 
Click Tools in the left-side navigation panel.
- 
Click the Container Orchestration tab.
- 
Click the Enable NetCloud Container Orchestrator to toggle on.

---

## Configuring a Container

Containers can be deployed at the NetCloud Manager device or group level. This guide provides the steps to configure containers on a local device.
In the following example, a Redis:Alpine Linux container is deployed on a router. The following Compose (YAML) configuration is deployed on a router using NetCloud Manager:
version: '2.4'
services:
   Alpine:
     network_mode: bridge
     image: 'redis:alpine' 
     ports:
       - '6379:6379'

---

## Deploying a Container

Complete the following steps to deploy a container for a local device:
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
 | 
- 
Click Add to open the Project Configuration window.
- 
Enter the following information under the Config tab:
- 
Enter a name for the project in the Name field [alpine].
- 
Click the Enabled checkbox.
- 
(Optional) – Specify an interval for NetCloud Manager to check for updates to the image in the Update Interval field.
Values must be set in seconds.
If an updated image is available, it is downloaded and deployed automatically. If no value is entered, automatic updates do not occur.
## Note

Do not click save yet; additional settings are needed under the Project Builder tab.
- 
Click the Compose Builder tab.
- 
Click Add to create a new service.
 | 
- 
On the Service Configuration page, add the name for the container, the image name, the location where NetCloud OS pulls down the Docker's image to the router, and the optional Port Mapping.
An example of the Redis:alpine settings are shown in the following graphic:
 | 
## Note

The port mapping syntax is [docker host port:container port]. For example, 6379:6379. For more information, see the Docker article Container Networking.
- 
Click Save twice to return to the Compose (YAML) file screen.
The following is an example of the screen for the Redis:alpine container:
 | 
Additional options.
- 
Command – Set up commands to execute in the container upon startup and define environment variables accessible within the container.
- 
Volumes and Devices – Define volumes to share data between containers.
## Note

For security reasons, NetCloud OS does not allow mounting a volume to the host NetCloud OS file system. Volumes can be mounted and accessed between containers to share data. Devices such as USB and serial ports can be mounted and accessed from the container by clicking Add in the Devices section.
- 
Health – Configure health checks to monitor the container and act upon failure. For more information, see the Containers Advanced Configuration Guide.
- 
Click Save.
- 
Click Commit Changes in the Edit Configuration window to write the configuration to the router. After committing the changes, the following processes automatically run on the router:
- 
NetCloud Manager syncs the container changes with the host endpoint.
- 
The endpoint downloads and installs the container runtime.
- 
The container runtime begins pulling the container image or images from configured repository.
## Note

This can take a few minutes to complete and is dependent on the size of the container being downloaded.

---

## Verifying the Container

Complete the following steps to verify that the Redis:alpine container has downloaded and is up and running:
- 
Log into NetCloud Manager.
- 
Click Devices in the left-side navigation panel.
- 
Select the device name; for example, E300-dae.
- 
Click the Containers tab.
- 
Check that the container state is "running" under Projects.
- 
Click the Containers tab to view the State/CPU/Memory Usage for the container.
 | 
The container can also be verified through a console window. Complete the following steps to open a console window and verify the container:
- 
Log into NetCloud Manager.
- 
Select Devices in the left-side navigation panel.
- 
Select the desired router.
- 
Select the Remote Connect menu and then select Console.
- 
Select Open Console.
- 
Execute a command-line interface (CLI) command on the container. As shown in the following example, the ps command (container depend command) is ran on the container to verify that the user Redis is running on port 6379:
[**@E300-dae: /]$
container exec alpine_Alpine_1 ps
PID      USER     TIME COMMAND
1 redis      0:03 redis-server *:6379 
14 root      0:00 ps

---

## Configuring a Container Registry

NetCloud Manager pulls containers from the Docker Hub registry by default. You can configure a different registry for your images if necessary.
Complete the following steps to configure NetCloud Manager to pull images from a different registry:
- 
Log into NetCloud Manager.
- 
Select Devices in the left-side navigation panel.
- 
Select a router from the Routers page. Alternatively, to make configuration changes to a group, navigate to the Groups page and select a group.
- 
Select Configuration and then Edit.
- 
Navigate to SYSTEM > Containers > Registry.
- 
Click Add on the Registry page to open the Registry Configuration window.
 | 
- 
Add the URL of the registry in the Registry URL field.
- 
Type your credentials for the registry in the Username and Password fields.
## Note

For Amazon ECR registries, the username is "AWS" and the password is the authorization token retrieved from the ECR GetAuthorizationToken API. For more information, see Using an authorization token in the AWS documentation.
- 
Click Save to save the registry. The Registry Configuration window closes.
- 
Click Commit Changes. The affected container now pulls its images from this registry.

---

## Accessing Containers

Information about containers can be accessed through NetCloud Manager Remote Connect or an SSH session. Complete the following steps to access configured containers through NetCloud Manager:
- 
Log into NetCloud Manager.
- 
Select Devices in the left-side navigation panel.
- 
Select the desired router.
- 
Select the Remote Connect menu and then select Console.
- 
Select Open Console.
Some useful CLI commands for working with containers from the console include the following:
- 
View list of containers installed on the device:
# container list
- 
Change to working container directory:
# cd /status/container
- 
View information about the container:
# cat /status/container/<project name>/info
- 
View container logs:
# container logs <container name>

---

## Managing and Monitoring Containers

Once installed, containers can be monitored and managed from NetCloud Manager.
- 
Log into NetCloud Manager.
- 
Click Devices in the left-side navigation menu.
- 
On the table on the Routers tab, click the name of the device where the container is installed to open that device's dashboard.
- 
On the Home tab, click the Containers tab.
 | 
- 
To monitor a container, click the Containers subtab on the Containers tab, and then select a project from the table. The Details panel displays on the right with information about the container.
## Note

The Details panel is also available from the Projects subtab.
 | 
- 
To manage a container, select a project in the Projects subtab and use the buttons above the projects table to initiate commands.
 | 
- 
Start – Start a container that is not currently running.
- 
Stop – Stop a container that is running and close any associated resources.
- 
Force Stop – Stop a container that is running without killing associated resources.
- 
Restart – Restart a running container.
- 
Pull – Update a container to its latest version.
## Important

If a project has more than one container using the USB device, all the project's containers restart if the USB device is plugged or unplugged.
If a project has only one container using the USB device, just that container is restarted upon plug or unplug.

---

## Troubleshooting

For security purposes, containers do not have root access to the NetCloud OS. The following are CLI commands to assist with troubleshooting some container issues.
The container command (cmd) from the console lists common commands to troubleshoot containers. See the following example:
## Note

The container cmd gives shell access in the container. By default, container exec tries to execute the bash shell. If your container does not have bash, and instead has sh, you can run container <container name> sh to start an sh shell.
To enable container logs, add the logging section into the YAML config in the container Compose section (Project Configuration > Compose tab), as shown in the following example:
 | 
To view the log file from the console, enter the following:
  logging:
     driver: json-file

$ container logs <container name>
For example, to view the Alpine Container logs:
$ container logs alpine_Alpine_1

---

## File Ownership in Containers

When a file from a container's base image is replaced, the file's ownership changes to "nobody: nobody" and the file becomes effectively locked to further changes, even by the container's root user. To resolve this issue, use the following steps:
- 
Make a copy of the file you want to replace. For example:
$ cp main.py main_copy.py
- 
Make the changes to the copy (that you would have made to the original). For example:
$ echo "All the content intended for the original." > main_copy.py
- 
Replace the original file with the copy. For example:
$ mv main_copy.py main.py

---

## Frequently Asked Questions

- 1. Can Docker volumes be pruned in containers running on routers?
- 2. Do we use user namespace remapping?
- 3. When working with a new image, why isn't the volume updated?
- 4. Why does my Container data usage differ from my Client Data Usage?
 | 
1. | 
Can Docker volumes be pruned in containers running on routers?
 |  | 
Docker volumes for containers running on routers cannot be pruned.
 | 
2. | 
Do we use user namespace remapping?
 |  | 
We do employ user namespace remapping. Note the caveat for file ownership in File Ownership in Containers.
 | 
3. | 
When working with a new image, why isn't the volume updated?
 |  | 
Data on a volume is not updated with changes from a new image. To resolve this, a new project must be created; this creates a new volume that gets the changes from the new image.
 | 
4. | 
Why does my Container data usage differ from my Client Data Usage?
 |  | 
This is due to a fundamental difference in measurement layers: Client Data Usage is captured at Layer 3 (IP), while container usage is captured at Layer 2 (Ethernet). The Variance comes from removing the 14-Byte Ethernet header when processing the packet.

---

