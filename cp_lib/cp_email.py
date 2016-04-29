"""
Send a single email
"""

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

EMAIL_REQUIRED_KEYS = ('smtp_url', 'smtp_port', 'smtp_tls',
                       'username', 'password', 'email_to', 'subject')

EMAIL_OPTIONAL_KEYS = ('email_from', 'body', 'logger')


def cp_send_email(sets):
    """

    :param dict sets: the various settings
    :return:
    """
    import smtplib

    for key in EMAIL_REQUIRED_KEYS:
        if key not in sets:
            raise KeyError('cp_send_email() requires ["%s"] key' % key)

    # handle the two optional keys
    if 'email_from' not in sets:
        sets['email_from'] = sets['username']
    if 'body' not in sets:
        sets['body'] = sets['subject']

    email_list = sets['email_to']
    # if isinstance(email_list, str):
    #     # if already string, check if like '["add1@c.com","add2@d.com"]
    #     email_list = email_list.strip()
    #     if email_list[0] in ("[", "("):
    #         email_list = eval(email_list)

    email = smtplib.SMTP(sets['smtp_url'], sets['smtp_port'])
    # TODO handle ['smtp_tls'] for optional TLS or not
    email.ehlo()
    email.starttls()
    email.login(sets['username'], sets['password'])

    assert isinstance(email_list, list)
    for send_to in email_list:
        if 'logger' in sets:
            sets['logger'].debug("Send email to {}".format(send_to))

        email_body = '\r\n'.join(['TO: %s' % send_to,
                                  'FROM: %s' % sets['email_from'],
                                  'SUBJECT: %s' % sets['subject'], '',
                                  sets['body']])

        # try: TODO - better understand hard & soft failure modes.
        email.sendmail(sets['email_from'], [send_to], email_body)

        # except:
        #     logging.error("Email send failed!")

    email.quit()
    return 0
