import os
import time
import requests
from csclient import EventingCSClient
from download import download_file
from untar import extract
import shutil


class DynamicApp:

    @property
    def settings(self):
        if not self._settings:
            self._settings = self.get_settings()
        return self._settings

    @property
    def session(self):
        if not self._session:
            self._session = requests.session()
            if self.settings.get('auth'):
                self._session.auth = tuple(self.settings['auth'].split(':'))
        return self._session

    def __init__(self, c):
        self._settings = {}
        self._session = None
        self.c = c
        self.current_version = None

    def on_update_config(self, *args, **kwargs):
        self.c.log("update config")
        settings = self.get_settings()
        self.c.log('settings: %s' % settings)
        if settings != self._settings:
            self._settings = settings
            self._session = None
            self.update_app()

    def update_app(self):
        self.install_app(self.settings['url'], self.settings['name'])

    def install_app(self,url, name):
        uuid = self.get_app_holder_uuid()
        if not uuid:
            self.c.log("ERROR: app_holder app not found")
            return
        else:
            self.c.log(f"app_holder app uuid is {uuid}")

        # try to stop the app cleanly
        self.c.log("Stopping app_holder")
        self.c.put("/control/system/sdk/action", "stop %s" % uuid)

        filename = name + '.tar.gz'
        download = url + '/' + filename
        self.c.log("downloading %s" % download)
        download_file(download, self.session)
        extract(filename, '/var/mnt/sdk/%s/app_holder' % uuid)
        try:
            shutil.rmtree('/var/mnt/sdk/%s/app_holder/app' % uuid)
        except FileNotFoundError:
            pass
        shutil.move('/var/mnt/sdk/%s/app_holder/%s' % (uuid, name), '/var/mnt/sdk/%s/app_holder/app' % uuid)
        self.c.log('app %s installed' % name)

        self.c.log("Wait 3 seconds before restarting")
        time.sleep(3)
        self.c.put('/control/system/sdk/action', "restart %s" % uuid)

    def get_app_holder_uuid(self):
        for root, dirs, files in os.walk("/var/mnt/sdk"):
            if "app_holder" in dirs:
                return root.split("/")[-1]

    def get_settings(self):
        """settings names are dynamic.some_name from sdk.appdata"""
        sdk_data = self.c.get('/config/system/sdk/appdata')
        sdk_data = {v['name'].split(".")[1]: v['value'] for v in sdk_data if v['name'].startswith('dynamic')}
        return sdk_data

    def run(self):
        self.c.on('put', '/config/system/sdk/appdata', self.on_update_config)
        self.on_update_config()
        while True:
            time.sleep(60)

def main():
    c = EventingCSClient("dynamic_app")
    c.log("STARTING APPLICATION %s" % c.app_name)
    d = DynamicApp(c)
    try:
        d.run()
    except Exception as e:
        c.logger.exception(e)

if __name__ == "__main__":
    main()
