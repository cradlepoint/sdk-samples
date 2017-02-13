"""
Copyright (c) 2016 CradlePoint, Inc. <www.cradlepoint.com>.  All rights
reserved.

This file contains confidential information of CradlePoint, Inc. and your use
of this file is subject to the CradlePoint Software License Agreement
distributed with this file. Unauthorized reproduction or distribution of this
file is subject to civil and criminal penalties.
"""

import re
import json
import socket
import subprocess

def log(msg):
	subprocess.run(['logger', msg])

class CSClient(object):
	"""Wrapper for the TCP interface to the router config store."""

	def get(self, base, query='', tree=0):
		"""Send a get request."""
		cmd = "get\n{}\n{}\n{}\n".format(base, query, tree)
		return self._dispatch(cmd)

	def put(self, base, value='', query='', tree=0):
		"""Send a put request."""
		value = json.dumps(value).replace(' ', '')
		cmd = "put\n{}\n{}\n{}\n{}\n".format(base, query, tree, value)
		return self._dispatch(cmd)

	def append(self, base, value='', query=''):
		"""Send an append request."""
		value = json.dumps(value).replace(' ', '')
		cmd = "post\n{}\n{}\n{}\n".format(base, query, value)
		return self._dispatch(cmd)

	def delete(self, base, query=''):
		"""Send a delete request."""
		cmd = "delete\n{}\n{}\n".format(base, query)
		return self._dispatch(cmd)

	def alert(self, name='', value=''):
		"""Send a request to create an alert."""
		cmd = "alert\n{}\n{}\n".format(name, value)
		return self._dispatch(cmd)

	def log(self, name='', value=''):
		"""Send a request to create a log entry."""
		cmd = "log\n{}\n{}\n".format(name, value)
		return self._dispatch(cmd)

	def _dispatch(self, cmd):
		"""Send the command and return the response."""
		resl = ''
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
			sock.connect('/var/tmp/cs.sock')
			sock.sendall(bytes(cmd, 'ascii'))

			if str(sock.recv(1024), 'ascii').strip() == 'status: ok':
				recv_mesg = str(sock.recv(1024), 'ascii').strip().split(' ')[1]
				try:
					mlen = int(recv_mesg)
				except ValueError:
					m = re.search("([0-9]*)", recv_mesg)
					mlen = int(m.group(0))
				if str(sock.recv(1024), 'ascii') == '\r\n\r\n':
					while mlen > 0:
						resl += str(sock.recv(1024), 'ascii')
						mlen -= 1024
		return resl
