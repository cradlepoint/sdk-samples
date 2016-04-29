"""
Send a single email
"""
from cp_lib.app_base import CradlepointAppBase
from cp_lib.cp_email import cp_send_email


def send_one_email(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    if "send_email" not in app_base.settings:
        raise ValueError("settings.ini requires [send_email] section")

    local_settings = dict()
    # we default to GMAIL, assume this is for testing
    local_settings['smtp_url'] = app_base.settings["send_email"].get(
        "smtp_url", 'smtp.gmail.com')
    local_settings['smtp_port'] = int(app_base.settings["send_email"].get(
        "smtp_port", 587))

    for value in ('username', 'password', 'email_to', 'email_from'):
        if value not in app_base.settings["send_email"]:
            raise ValueError(
                "settings [send_email] section requires {} data".format(value))
        # assume all are 'strings' - no need for INT
        local_settings[value] = app_base.settings["send_email"][value]

    local_settings['subject'] = app_base.settings["send_email"].get(
        "subject", "test-Subject")
    local_settings['body'] = app_base.settings["send_email"].get(
        "body", "test-body")

    app_base.logger.debug("Send Email To:({})".format(
        local_settings['email_to']))
    result = cp_send_email(local_settings)

    app_base.logger.debug("result({})".format(result))

    return result

# Required keys
# ['smtp_tls]   = T/F to use TLS, defaults to True
# ['smtp_url']  = URL, such as 'smtp.gmail.com'
# ['smtp_port'] = TCP port like 587 - be careful, as some servers have more
#                 than one, with the number defining the security demanded.
# ['username']  = your smtp user name (often your email acct address)
# ['password']  = your smtp acct password
# ['email_to']  = the target email address, as str or list
# ['subject']   = the email subject

# Optional keys
# ['email_from'] = the from address - any smtp server will ignore, and force
#                  this to be your user/acct email address; def = ['username']
# ['body']       = the email body; def = ['subject']


if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("network/send_email")

    _result = send_one_email(my_app)

    my_app.logger.info("Exiting, status code is {}".format(_result))

    sys.exit(_result)
