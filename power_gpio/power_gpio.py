"""
Query the 2x2 power connector GPIO
"""
import json
import argparse
import cs

APP_NAME = "power_gpio"


def run_router_app():
    """
        Read the Power Connector GPIO input and output
    """

    # confirm we are running on 900/950 or 1100/1150
    result = cs.CSClient().get("status/product_info/product_name").get('data')
    if "IBR900" in result or "IBR950" in result:
        input_name = "status/gpio/CONNECTOR_INPUT"
        output_name = "status/gpio/CONNECTOR_OUTPUT"

    elif "IBR1100" in result or "IBR1150" in result:
        input_name = "status/gpio/CGPIO_CONNECTOR_INPUT"
        output_name = "status/gpio/CGPIO_CONNECTOR_OUTPUT"

    else:
        cs.CSClient().log(APP_NAME, "Inappropriate Product:{} - aborting.".format(result))
        return

    result_in = cs.CSClient().get(input_name).get('data')
    result_out = cs.CSClient().get(output_name).get('data')

    cs.CSClient().log(APP_NAME, "Product Model is: {}".format(result))
    cs.CSClient().log(APP_NAME, "GPIO 2x2: {} = {}".format(input_name, result_in))
    cs.CSClient().log(APP_NAME, "GPIO 2x2: {} = {}".format(output_name, result_out))

    return


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            run_router_app()

        elif command == 'stop':
            # Nothing on stop
            pass

    except Exception as ex:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! ex: {}'.format(APP_NAME, command, ex))
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
