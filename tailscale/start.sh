#!/bin/bash
set -o pipefail
set -o errexit

logger -s -t tailscale -p 6 "tailscale istarting up..."

logerr() {
    if [ "$#" -gt 0 ]; then
        logger -s -t tailscale -p 3 "$*"
    else
        cat | logger -s -t tailscale -p 3
    fi
}

check_tskey() {
    tskey="$(cppython ./get_tskey.py tskey)"
    tskey_ec=$?
}

get_tsroutes() {
    tsroutes="$(cppython ./get_tskey.py tsroutes)"
}

get_tsarch() {
    arch="$(uname -m)"
    if [ "$arch" = "armv7l" ]; then
        tsarch="arm"
    elif [ "$arch" = "x86_64" ]; then
        tsarch="amd64"
    elif [ "$arch" = "aarch64" ]; then
        tsarch="arm64"
    fi
}

download() {
    cmd="cppython ./download.py $tsarch"
    tsversion="$(cppython ./get_tskey.py tsversion)"
    if [ -n "$tsversion" ]; then
        cmd+=" -v $tsversion"
    fi
    eval $cmd | logerr
    if [ $? -ne 0 ]; then
        logerr "Failed to download tailscale binary"
        exit 1
    fi
}

tskey=""
tskey_ec=0
tsroutes=""
tsarch="arm64"

check_tskey
get_tsroutes
get_tsarch
download

tsdbinary="tailscaled_$tsarch"
tsbinary="tailscale_$tsarch"

if [ $tskey_ec -ne 0 ] || [ -z "$tskey" ]; then
    sleep 10
    logerr "Couldn't get tskey. Exiting..."
    exit 1
fi

prev_tskey="$tskey"

exit_safely() {
    ./${tsbinary} --socket ./tailscaled.sock logout 2>&1 | logerr
    killall ${tsdbinary}
    exit 1
}

check_tskey_change() {
    prev_tskey=$tskey
    check_tskey
    prev_tsroutes=$tsroutes
    get_tsroutes

    if [ $tskey_ec -ne 0 ] || [ -z "$tskey" ]; then
        logerr "Couldn't get tskey. Exiting..."
        exit_safely
    fi

    if [ "$tskey" != "$prev_tskey" ]; then
        logerr "tskey has changed. Exiting..."
        exit_safely
    fi

    if [ "$tsroutes" != "$prev_tsroutes" ]; then
        logerr "tsroutes has changed. Exiting..."
        exit_safely
    fi
}

trap exit_safely SIGINT SIGTERM EXIT

HOME=$(pwd) ./${tsdbinary} --socket=./tailscaled.sock --tun=userspace-networking --socks5-server=localhost:1055 2>&1 | logerr &
sleep 2
HOME=$(pwd) ./${tsbinary} --socket ./tailscaled.sock up --auth-key="$tskey" --advertise-routes="$tsroutes" 2>&1 | logerr

tsretcode=$?
if [ $tsretcode -ne 0 ]; then
  logerr "tailscale failed to run: exit code $tsretcode"
  exit_safely
fi

logger -s -t tailscale -p 6 "tailscale should be up and running now"

while true; do
    sleep 10
    check_tskey_change
done