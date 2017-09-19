
import sys
import argparse
import smtplib
import cs

APP_NAME = 'email'

# This application will send a single email when it is started.


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        email_username = '<username>'
        email_password = '<password>'

        email_from = '<email>'
        email_to = '<email>'
        email_subject = 'This is the subject line for the test email.'
        email_body = ' This is the body of the test email.'

        if command == 'start':
            cs.CSClient().log(APP_NAME, 'Logging into email server')

            try:
                # If you are using gmail, then the login account will need to
                # turn 'Allow less secure apps' in the 'Sign-in & security'
                # setting for the Google account.
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.ehlo()
                server.starttls()
                server.login(email_username, email_password)

                the_email = '\r\n'.join(['TO: %s' % email_to,
                                         'FROM: %s' % email_from,
                                         'SUBJECT: %s' % email_subject, '',
                                         email_body])

                cs.CSClient().log(APP_NAME, 'Sending email to: {}'.format(email_to))
                server.sendmail(email_from, email_to, the_email)
            except:
                e = sys.exc_info()[0]
                cs.CSClient().log(APP_NAME, 'Could not send email! exception: {}'.format(e))
            finally:
                if server:
                    server.quit()

        elif command == 'stop':
            # Nothing on stop
            pass
    except Exception as e:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! exception: {}'.format(APP_NAME, command, e))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    cs.CSClient().log(APP_NAME, 'args: {})'.format(args))
    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(opt))
        exit()

    action(opt)
