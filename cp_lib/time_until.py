import time


VALID_NICE_SECOND_PERIODS = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
VALID_NICE_MINUTE_PERIODS = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
VALID_NICE_HOUR_PERIODS = (1, 2, 3, 4, 6, 8, 12, 24)


def seconds_until_next_hour(now=None):
    """
    How many seconds until next hour

    :param now:
    :return:
    """
    now = _prep_time_now(now)

    # how many second until next minute
    delay = 60 - now.tm_sec

    # add how many seconds until next hour
    delay += (60 - now.tm_min)

    return delay


def seconds_until_nice_minute_period(period, now=None):
    """
    How many seconds until next minute, when now.tm_sec == 0

    :param int period: must be in set VALID_NICE_MINUTE_PERIODS
    :param now:
    :return int:
    """
    now = _prep_time_now(now)

    return 60 - now.tm_sec


def seconds_until_next_minute(now=None, fudge=2):
    """
    How many seconds until next minute, when now.tm_sec == 0

    :param now:
    :param int fudge: to avoid too short of delays, a fudge=2 means when tm_sec > 58, go to NEXT minute (62 seconds)
    :return int:
    """
    now = _prep_time_now(now)

    if fudge > 0 and (60 - now.tm_sec) <= fudge:
        # then round up to next hour
        return (60 - now.tm_sec) + 60

    return 60 - now.tm_sec


def seconds_until_nice_second_period(period, now=None):
    """
    How many seconds until next seconds period (like 15 means hh:00, hh:15, hh:30, hh:45)

    :param int period: must be in set VALID_NICE_SECOND_PERIODS
    :param now:
    :return int:
    """
    if period not in VALID_NICE_SECOND_PERIODS:
        raise ValueError("{} seconds is not valid NICE SECONDS period".format(period))

    now = _prep_time_now(now)

    return 60 - now.tm_sec


def _prep_time_now(now=None):
    """
    make sure now is struct_time

    :param now: optional source value
    :rtype: time.struct_time
    """
    if now is None:
        # if none provided, get NOW
        now = time.time()

    if not isinstance(now, time.struct_time):
        # if now isn't float or suitable, then will throw exception
        now = time.localtime(now)

    assert isinstance(now, time.struct_time)
    return now
