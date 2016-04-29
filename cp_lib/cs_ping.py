"""
Issue a ping, via Router API control/ping
"""
import time
from cp_lib.app_base import CradlepointAppBase

# for now, this does NOT work!
SUPPORT_COUNT = False


def cs_ping(app_base, ping_ip, ping_count=40, loop_delay=2.5):
    """
    Issue a ping via Cradlepoint Router IP. ping_ip can be like
    "192.168.35.6" or "www.google.com".

    return is a dictionary

    if ["status"] == "success",
    - ["result'] is an array of lines (as shown below)
    - ["transmitted" == 40 (from line "40 packets transmitted, ... )
    - ["received" == 40 (from line "... 40 packets received ... )
    - ["loss" == 40 (from line "... 0% packet loss)
    - ["good" == 100 - ["loss"]

    if ["status"] == "error", ["result"] is likely the string explaining the
    error, such as "Timed out trying to send a packet to 192.168.115.3"

    if ["status"] == "key_error",
    - the cs_client response of GET "control/ping" lacked expected keys

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client,
    :param str ping_ip: the IP or DNS name to ping
    :param int ping_count: how many times to ping
    :param float loop_delay: the delay in the GET loop
    :return:
    :rtype dict:
    """

    if not SUPPORT_COUNT and ping_count != 40:
        app_base.logger.warning(
            "PING 'count' not yet supported - forced to 40")
        ping_count = 40

    app_base.logger.info("Send a PING to {}".format(ping_ip))
    put_data = '{"host":"%s", "count": %d}' % (ping_ip, ping_count)

    # we want to PUT control/ping/start {"host": "192.168.115.6"}
    result = app_base.cs_client.put("control/ping/start", put_data)
    app_base.logger.info("Start Result:{}".format(result))

    # an initial delay assume 1 second per ping_count
    app_base.logger.info("Initial Delay for {} seconds".format(ping_count + 1))
    time.sleep(ping_count + 1)

    report = []
    while True:
        result = app_base.cs_client.get("control/ping")
        app_base.logger.info("Loop Result:{}".format(result))
        # first result should be something like:
        # {'status': 'running', 'start': {'host': 'www.google.com'},
        #  'stop': '', 'result': 'PING www.google.com (216.58.193.100)'}
        try:
            value = result['status']
        except KeyError:
            app_base.logger.error("PING has no ['status'], aborting")
            return {"status": "key_error"}

        if value == "error":
            # then some error occurred
            return result

        if value == "":
            # then the cycle is complete
            break

        app_base.logger.info("PING Status:{}".format(value))

        try:
            value = result['result']
        except KeyError:
            app_base.logger.error("PING has no ['result'], aborting")
            return {"status": "key_error"}

        if value != "":
            # then we are mid-cycle
            lines = value.split('\n')
            report.extend(lines)

            for line in lines:
                app_base.logger.debug("{}".format(line))

            if report[-1].startswith("round-trip"):
                # then the cycle is complete
                break

        # else still wait - for example, when we first start the
        # ["status"] == "running" and ["result"] == ""

        # post delay if we didn't delay quite enough
        app_base.logger.info("Loop for {} seconds".format(loop_delay))
        time.sleep(loop_delay)

    result = {"status": "success", "result": report}

    for line in report:
        if line.find("packet loss") > 0:
            # 40 packets transmitted, 40 packets received, 0% packet loss
            # [0][1]     [2]         [3] [4]     [5]      [6] [7]    [8]
            value = line.split()
            if value[2].startswith('transmit'):
                result['transmitted'] = int(value[0])
                app_base.logger.debug("PING transmitted:{}".format(
                    result['transmitted']))
            if value[5].startswith('receive'):
                result['received'] = int(value[3])
                app_base.logger.debug("PING received:{}".format(
                    result['received']))
            if value[6][-1] == '%':
                result['loss'] = int(value[6][:-1])
                result['good'] = 100 - result['loss']
                app_base.logger.debug("PING loss:{}% good:{}%".format(
                    result['loss'], result['good']))

    return result

"""
PUT control/ping/start {"host": "192.168.115.6"}.

Cyclically GET control/ping, watch ['status'] goes to 'running' (or 'error')
then eventually to 'done', then after repeated GET returns to ''

I have seen ['status']:
= '' after all GETs done
= 'running' during pinging
= 'error' if
= 'sysstopped' if ??

If IP has no response - or Ip is unreachable:
{'start': {'host': '192.168.115.3'}, 'status': 'error',
 'result': 'Timed out trying to send a packet to 192.168.115.3'}

The entire collection of ['result'] lines will be like (EOL = '\n')

PING 192.168.115.6 (192.168.115.6)
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=0. time=1.080. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=1. time=0.900. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=2. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=3. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=4. time=1.020. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=5. time=0.960. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=6. time=1.000. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=7. time=1.000. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=8. time=0.980. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=9. time=1.000. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=10. time=1.040. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=11. time=0.980. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=12. time=0.960. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=13. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=14. time=1.080. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=15. time=1.000. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=16. time=1.000. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=17. time=1.040. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=18. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=19. time=0.900. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=20. time=12.440. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=21. time=0.940. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=22. time=0.900. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=23. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=24. time=1.020. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=25. time=0.940. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=26. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=27. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=28. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=29. time=0.900. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=30. time=0.940. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=31. time=0.900. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=32. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=33. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=34. time=1.020. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=35. time=0.940. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=36. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=37. time=0.940. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=38. time=0.920. ms
44 bytes from 192.168.115.6 (192.168.115.6): icmp_seq=39. time=0.900. ms
---Ping statistics---
40 packets transmitted, 40 packets received, 0% packet loss
round-trip(ms)   min/avg/max = 0.900/1.244/12.440

(eventually will be "")

"""
