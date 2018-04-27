'''
Outputs a 'Hello World!' log every 10 seconds.
'''

import cs
import time

APP_NAME = 'hello_world'


# The main entry point for hello_world.py
if __name__ == "__main__":
    while True:
        cs.CSClient().log(APP_NAME, 'Hello World!')
        time.sleep(10)

