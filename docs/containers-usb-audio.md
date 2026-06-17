# USB Audio Support for Containers

Source: https://docs.cradlepoint.com/r/USB-Audio-Support-for-Containers

## Overview

USB audio support on Ericsson Cradlepoint routers is available in containers beginning with NetCloud OS 7.25.20. USB audio support allows containerized applications on Ericsson Cradlepoint routers to interact with external USB audio devices and react to audio commands.

---

## Prerequisites

The following prerequisites are required for using USB audio devices to interact with containers on an Ericsson Cradlepoint routers.
- 
A USB audio device (microphone, headphones, etc).
- 
An Ericsson Cradlepoint router with NetCloud OS 7.25.20 or newer that supports the Container Orchestrator feature. See the Minimum Requirements section of the Containers Quick Start Guide for a list of supported Ericsson Cradlepoint routers.
- 
A Docker container. The following is an example of Dockerfile settings for building an image for a container that interacts with a USB audio device.
# Use the Alpine Linux base image
FROM alpine:3.14

# Set the working directory
WORKDIR /app

# Install alsa-utils for the aplay command
RUN apk add --no-cache alsa-utils

# Copy the .wav file into the Docker image
COPY audio-file.wav /app

# Command to play the .wav file using aplay
CMD ["aplay", "audio-file.wav"]
- 
An application running in the Docker container that can interact with the USB audio device.

---

## Configuring USB Audio Support

USB audio support in containers allows for the processing of voice commands by applications running in a container.
Use the following procedure to make the necessary configuration changes to use USB audio with a container on an Ericsson Cradlepoint router.Configuring USB audio support
- 
Log into NetCloud Manager.
- 
Select Devices > Routers.
- 
Select a router from the Routers page.
- 
Select Configuration > Edit.
- 
Select System > Containers > Projects.
- 
Select Add to add a new configuration. To modify an existing configuration, select the configuration and then select Edit.
- 
Configure the following on the Project Configuration > Config tab in the Project Configuration dialog.
- 
Name: A name for the project.
- 
Enabled: This must be selected to enable the container and ensure it can run.
- 
Update Interval (Optional): How often, in seconds, NetCloud OS should check for and apply service-image updates. NetCloud OS will not update images after pulling them if this is set to 0 or left blank.
- 
Select the Compose Builder tab and then select Add in the Services section.
- 
On the Service Configuration > Basic page, add the following.name for the container, the image name used by the container, the location where NetCloud OS pulls down the Docker's image to the router, and the optional Port Mapping.
- 
A name for the service.
- 
The image name used by the container. This can either be a repository/tag or a partial image ID. For example, 'username/repo/image:tag' or 'ubuntu:18.04'.
- 
Use Bridge for the Network Mode.
- 
The Capabilities field is optional. This allows the container to perform various network-related operations including:
- 
interface configuration
- 
binding to any address for transparent proxying
- 
setting type-of-service (TOS)
- 
clearing driver statistics
- 
setting promiscuous mode
- 
enabling multicasting
- 
setting various network-related socket options
- 
A port mapping is optional.
- 
Select Save twice to return to the Compose (YAML) file screen.
- 
Select the Compose tab and enter the following.
version: '3'
services:
  container:
    image: username/image:tag
    devices:
     - /dev/snd:/dev/snd
- 
Select Save.
## Important

If a project has more than one container using the USB device, all the project's containers restart if the USB device is plugged or unplugged.
If a project has only one container using the USB device, just that container is restarted upon plug or unplug.

---

