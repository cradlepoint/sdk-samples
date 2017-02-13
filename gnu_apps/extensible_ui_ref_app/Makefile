#
#  Router SDK Makefile
# 
#  Run 'make help' for info on the supported make targets.
#

SDK_ROOT := $(shell pwd)
include $(SDK_ROOT)/config/settings.mk

BUILD_DATE = "$(shell date)"
BUILD := .build

.PHONY: help clean status install start stop uninstall purge

default: package

clean: build-clean package-clean

build: $(BUILD)
$(BUILD): $(APP_SRC) $(TOOLS_SRC)
	touch $@

build-clean:
	rm -f $(BUILD)

package: $(VENV_INSTALL) $(APP_ARCHIVE)
$(APP_ARCHIVE): $(APP_SRC)
	$(TOOLS)/bin/package_application.py $(APP_DIR)

package-clean: 
	rm -f $(APP_ARCHIVE)
	rm -rf $(APP_DIR)/METADATA

status: $(VENV_INSTALL)
	curl -s --digest --insecure -u $(DEV_CLIENT_ADMIN):$(DEV_CLIENT_PASSWORD) \
	        -H "Accept: application/json" \
		-X GET http://$(DEV_CLIENT_IP)/api/status/system/sdk | \
		/usr/bin/env python3 -m json.tool

install: $(VENV_INSTALL) $(APP_ARCHIVE)
	scp $(APP_ARCHIVE) $(DEV_CLIENT_ADMIN)@$(DEV_CLIENT_IP):/app_upload

start: $(VENV_INSTALL)
	curl -s --digest --insecure -u $(DEV_CLIENT_ADMIN):$(DEV_CLIENT_PASSWORD) \
		-H "Accept: application/json" \
		-X PUT http://$(DEV_CLIENT_IP)/api/control/system/sdk/action \
		-d data='"start $(APP_UUID)"' | \
		/usr/bin/env python3 -m json.tool

stop: $(VENV_INSTALL)
	curl -s --digest --insecure -u $(DEV_CLIENT_ADMIN):$(DEV_CLIENT_PASSWORD) \
		-H "Accept: application/json" \
		-X PUT http://$(DEV_CLIENT_IP)/api/control/system/sdk/action \
		-d data='"stop $(APP_UUID)"' | \
		/usr/bin/env python3 -m json.tool

uninstall: $(VENV_INSTALL)
	curl -s --digest --insecure -u $(DEV_CLIENT_ADMIN):$(DEV_CLIENT_PASSWORD) \
		-H "Accept: application/json" \
		-X PUT http://$(DEV_CLIENT_IP)/api/control/system/sdk/action \
		-d data='"uninstall $(APP_UUID)"' | \
		/usr/bin/env python3 -m json.tool

purge: $(VENV_INSTALL)
	curl -s --digest --insecure -u $(DEV_CLIENT_ADMIN):$(DEV_CLIENT_PASSWORD) \
		-H "Accept: application/json" \
		-X PUT http://$(DEV_CLIENT_IP)/api/control/system/sdk/action \
		-d data='"purge"' | \
		/usr/bin/env python3 -m json.tool

help:
	cat $(ROOT)/README.md
