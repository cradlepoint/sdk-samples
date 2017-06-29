"""

    Email.py -- Email from SDK App

    Copyright © 2015 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

    This file contains confidential information of Cradlepoint, Inc. and your
    use of this file is subject to the Cradlepoint Software License Agreement
    distributed with this file. Unauthorized reproduction or distribution of
    this file is subject to civil and criminal penalties.

    Desc:

"""

import sys
import smtplib
import socket
import time

class Email(object):
	"""Email class to send emails"""

#	USER = "nrf2016cp@gmail.com"
#	PASS = "Welcome2cp"
#
#	SERVER = "smtp.gmail.com"
#	PORT = 587
	DATE_FMT= "%a, %d %b %Y %H:%M:%S %z"

	def __init__(self, server, port, user, password):
		self.server = server
		self.port = port
		self.user = user
		self.password = password

		self.msg = ''
		self.from_addr = 'test1@test.org'
		self.to_addr = 'test2@test.org'

	def message(self, subject, from_addr, to_addr, body):
		self.from_addr = from_addr
		self.to_addr = to_addr

		template = 'Content-Type: text/plain; charset="us-ascii"\n'
		template += 'MIME-Version: 1.0\nContent-Transfer-Encoding: 7bit\n'
		template += 'Date: {}\n'
		template += 'Subject: {}\nFrom: {}\nTo: {}\n\n{}'

		self.msg = template.format(time.strftime(self.DATE_FMT), subject, from_addr, to_addr, body)

	def _send_tls(self):
		try:
			host = socket.gethostname()
			mail_server = smtplib.SMTP(self.server, self.port, host)
			mail_server.ehlo()
			mail_server.starttls()
			mail_server.ehlo()

			mail_server.login(self.user, self.password)
			mail_server.sendmail(self.from_addr, self.to_addr, self.msg)

			mail_server.quit()
		except smtplib.SMTPException as err:
			print("_send_tls failed: err=%s" % err, file=sys.stderr)
			raise

	def _send(self):
		try:
			host = socket.gethostname()
			mail_server = smtplib.SMTP(self.server, self.port, host)
			mail_server.ehlo()
			mail_server.sendmail(self.from_addr, self.to_addr, self.msg)
			mail_server.quit()

		except smtplib.SMTPException as err:
			print("_send failed: err=%s" % err, file=sys.stderr)
			raise

	def send(self):
		try:
			self._send_tls()
		except smtplib.SMTPException:
			# _send_tls() will log error
			pass
		else:
			# succes!
			return

		return

		# fall back to insecure email
		print("send falling back to unauthenticated SMTP", file=sys.stderr)
		try:
			self._send()
		except smtplib.SMTPException:
			# _send() will log error
			pass
