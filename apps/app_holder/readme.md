# app_holder
A placeholder SDK app used with the `dynamic_app` application for remote app deployment. This app contains no Python code — it simply provides a container that `dynamic_app` can download and install apps into.

## How It Works

The `dynamic_app` SDK application downloads app packages from a URL and installs them into the `app_holder` app directory. Once installed, `app_holder` runs the downloaded app via its `start.sh` script.

The flow is:
1. `dynamic_app` fetches an app package from a configured URL
2. The package is extracted into the `app_holder/app/` directory
3. `app_holder`'s `start.sh` runs `cd app && ./start.sh` to launch the installed app

This allows remote deployment of SDK apps without needing to manually upload them through NCM or the router UI.

## Contents

- `start.sh` — Launches the installed app by running `./start.sh` in the `app/` subdirectory
- `package.ini` — App metadata for the SDK framework

There is no Python code in this app. All logic lives in the companion `dynamic_app`.

## Installation

1. Install both `app_holder` and `dynamic_app` on the router
2. Configure `dynamic_app` with the URL of the app package to deploy
3. `dynamic_app` will download and install the app into `app_holder`
4. `app_holder` will automatically start the deployed app

## Requirements

- Must be used together with `dynamic_app`
- The deployed app must include its own `start.sh` in its package
- Router firmware 7.26 or later
