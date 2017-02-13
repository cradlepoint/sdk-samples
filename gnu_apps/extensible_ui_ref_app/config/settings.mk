#
#  config/settings.mk
#    
#  Build system config settings.  Many of these values can be overridden at
#  runtime or in your .bashrc.
#

ROOT := $(shell pwd)
SHELL := $(shell which bash)
TOOLS := $(abspath $(ROOT)/tools)

APP_NAME ?= hspt
APP_UUID ?= 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c
APP_ARCHIVE := $(abspath $(APP_NAME).tar.gz)

APP_DIR := $(ROOT)/$(APP_NAME)
APP_SRC := $(shell find $(APP_DIR) -type f -name '*.py')
app_deps := $(shell find $(APP_DIR) -type f)
APP_DEPS := $(foreach X, $(APP_DIR), $(call app_deps, $X))

TOOLS_DIR := $(ROOT)/tools
TOOLS_SRC := $(shell find $(TOOLS_DIR) -type f -name '*.py')
tools_deps := $(shell find $(TOOLS_DIR) -type f)

DEV_CLIENT_MAC ?= 00000000
DEV_CLIENT_IP ?= 0.0.0.0
DEV_CLIENT_ADMIN ?= admin
DEV_CLIENT_PASSWORD ?= $(DEV_CLIENT_MAC)

export SHELL
