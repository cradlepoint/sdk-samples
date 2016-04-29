
import threading
import time


class TimePeriods(threading.Thread):
    """
    Allow classes to obtain a callback at predictable time periods,
    such as every hour

    To reduce load, the minimum 'period' default is every 5 seconds.
    1 second is perhaps overly 'heavy'
    """

    # for now, this MUST be in set (2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
    # so one/1 is not supported
    MINIMUM_PERIOD = 5

    HANDLE_GARBAGE_COLLECTION = True

    # adds a variable skew seconds to avoid concurrence at midnight on
    # first date of month, when
    # callbacks for per-hour, per-day, and per-month would all fire
    SKEW_MINUTE = 3
    SKEW_HOUR = 17
    SKEW_DAY = 33
    SKEW_MONTH = 47
    SKEW_YEAR = 51

    NAME_MINUTE = 'min'
    NAME_HOUR = 'hr'
    NAME_DAY = 'day'
    NAME_MONTH = 'mon'
    NAME_YEAR = 'yr'
    NAME_LIST = (NAME_MINUTE, NAME_HOUR, NAME_DAY, NAME_MONTH, NAME_YEAR)

    def __init__(self):

        # enforce our basic design rules, which allow some basic assumptions
        assert isinstance(self.MINIMUM_PERIOD, int)
        # we don't support 1!
        assert 1 < self.MINIMUM_PERIOD <= 60
        assert is_valid_clean_period_seconds(self.MINIMUM_PERIOD)

        super().__init__(name="TimePeriods", daemon=True)

        # the event starts as False (per specs)
        self.shutdown_requested = threading.Event()

        # create a semaphore lock to detect when callbacks take too long!
        self._busy = threading.Lock()
        self._over_run = 0
        self._good_run = 0

        # here is our shared values
        self.now = time.time()
        self.now_struct = time.gmtime(self.now)

        # these will be our 'period lists' - pass in 'self' to allow
        # the periods to interact
        self.per_minute = self.OnePeriod(self)
        self.per_hour = self.OnePeriod(self)
        self.per_day = self.OnePeriod(self)
        self.per_month = self.OnePeriod(self)
        self.per_year = self.OnePeriod(self)

        # now that ALL exist, assign each one a period name (a 'role')
        self.per_minute.set_period_name(self.NAME_MINUTE)
        self.per_hour.set_period_name(self.NAME_HOUR)
        self.per_day.set_period_name(self.NAME_DAY)
        self.per_month.set_period_name(self.NAME_MONTH)
        self.per_year.set_period_name(self.NAME_YEAR)

        # assume set externally (or run() handles)
        self.logger = None

        return

    def run(self):
        """
        The THREAD main run loop:
            - Check the time
            - update the shared struct_time
            - call any callbacks
        """

        if self.logger is None:
            self.logger = get_project_logger()
            assert self.logger is not None

        while True:

            if self.shutdown_requested.is_set():
                # then we are to STOP running
                break

            self.now = time.time()
            self.now_struct = time.gmtime(self.now)

            # reschedule NEXT callback
            assert isinstance(self.now_struct, time.struct_time)
            next_delay = next_seconds_period(self.now_struct.tm_sec,
                                             self.MINIMUM_PERIOD)
            if next_delay < 1:
                # avoid it ever being zero/0
                next_delay = 1

            if not self._busy.acquire(False):
                # then we had an over-run!
                self._over_run += 1
                self.logger.warning(
                    "TimePeriod over-run #{0}( or {1}%)".format(
                        self._over_run, self._over_run / self._good_run) +
                    "; call backs taking too long")

            else:
                self._good_run += 1

                # do the callbacks
                self.per_minute.check_callbacks(self.now_struct)

                self._busy.release()

            self.logger.debug("Sleep for %d sec" % int(next_delay))
            time.sleep(next_delay)

        return

    def add_periodic_callback(self, cb, period: str):
        return

    class OnePeriod(object):

        def __init__(self, parent):

            self._parent = parent

            self.cb_list = []
            self.cb_list_skewed = []
            self.last_seen = 0
            self.do_skewed = False

            # these are fixed by a subsequent set_period_name() call
            self._get_my_value = lambda x: x
            self.period_name = None
            self.my_sub = None
            self.skew_seconds = 0
            return

        def __repr__(self):
            return "Period:%03s cb:%d skewed:%d" % (str(self.period_name),
                                                    len(self.cb_list),
                                                    len(self.cb_list_skewed))

        def get_name(self):
            return self.period_name

        def set_period_name(self, name: str):

            if name not in TimePeriods.NAME_LIST:
                raise ValueError(
                    "Period name({0}) is invalid; must be in {1}.".format(
                        name, TimePeriods.NAME_LIST))

            self.period_name = name

            assert isinstance(self._parent, TimePeriods)

            if self.period_name == TimePeriods.NAME_MINUTE:
                self._get_my_value = lambda x: x.tm_min
                self.skew_seconds = TimePeriods.SKEW_MINUTE
                self.last_seen = self._parent.now_struct.tm_min
                self.my_sub = self._parent.per_hour
                assert isinstance(self.my_sub, TimePeriods.OnePeriod)

            elif self.period_name == TimePeriods.NAME_HOUR:
                self._get_my_value = lambda x: x.tm_hour
                self.skew_seconds = TimePeriods.SKEW_HOUR
                self.last_seen = self._parent.now_struct.tm_hour
                self.my_sub = self._parent.per_day
                assert isinstance(self.my_sub, TimePeriods.OnePeriod)

            elif self.period_name == TimePeriods.NAME_DAY:
                self._get_my_value = lambda x: x.tm_mday
                self.skew_seconds = TimePeriods.SKEW_DAY
                self.last_seen = self._parent.now_struct.tm_mday
                self.my_sub = self._parent.per_month
                assert isinstance(self.my_sub, TimePeriods.OnePeriod)

            elif self.period_name == TimePeriods.NAME_MONTH:
                self._get_my_value = lambda x: x.tm_mon
                self.skew_seconds = TimePeriods.SKEW_MONTH
                self.last_seen = self._parent.now_struct.tm_mon
                self.my_sub = self._parent.per_year
                assert isinstance(self.my_sub, TimePeriods.OnePeriod)

            elif self.period_name == TimePeriods.NAME_YEAR:
                self._get_my_value = lambda x: x.tm_year
                self.skew_seconds = TimePeriods.SKEW_YEAR
                self.last_seen = self._parent.now_struct.tm_year
                self.my_sub = None  # YEAR has no next period

            # else: already handled up ub if name not in ... test

            return

        def add_callback(self, cb, skewed=False):
            """

            :param cb:
            :param skewed:
            :return:
            """
            # make sure we're not adding 'twice' - remove any existing
            self.remove_callback(cb)

            if skewed:
                self.cb_list_skewed.append(cb)
            else:
                self.cb_list.append(cb)
            return

        def remove_callback(self, cb):
            """

            :param cb:
            :return:
            """
            if cb in self.cb_list:
                self.cb_list.remove(cb)

            if cb in self.cb_list_skewed:
                self.cb_list_skewed.remove(cb)
            return

        def period_has_changed(self, now_tuple):
            """Use our 'lambda' to check is our internal last-seen
            implied period change"""
            return self.last_seen != self._get_my_value(now_tuple)

        def check_callbacks(self, now_tuple: time.struct_time):
            """
            Handle the various per callbacks this period (if any)
            """
            if self.period_has_changed(now_tuple):
                # then period has changed
                self.last_seen = self._get_my_value(now_tuple)
                if len(self.cb_list_skewed) > 0:
                    self.do_skewed = True

                # do the non-skewed callbacks
                self.process_callbacks(now_tuple)

            if self.my_sub is not None and \
                    self.my_sub.period_has_changed(now_tuple):
                # then chain to our sub - for per_year, this is still None
                self.my_sub.check_callbacks(now_tuple)

            return

        def process_callbacks(self, now_tuple: time.struct_time, skewed=False):
            """
            Handle the various per callbacks this period (if any)
            """
            if skewed:
                use_list = self.cb_list
            else:
                use_list = self.cb_list_skewed

            for cb in use_list:
                try:
                    cb(now_tuple)
                except:
                    # self.logger.error("PerMinute CB failed")
                    raise
            return

"""
What are CLEAN PERIODS? That are time slices which allow predictable
periodic repeats within scope of the next larger (encapsulating) time period.

For example, doing something every 12 seconds allows 5 periods per 1 minute
(minutes being the next larger time periods encapsulating seconds. However,
doing something every 8 or 13 seconds does NOT support this.

For example, doing something very 3 hours allows 8 periods per 1 day,
whereas doing something every 5 hours does NOT support such clean periods.
"""

_CLEAN_PERIOD_SEC_MIN = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
CLEAN_PERIOD_SECONDS = _CLEAN_PERIOD_SEC_MIN
CLEAN_PERIOD_MINUTES = _CLEAN_PERIOD_SEC_MIN
CLEAN_PERIOD_HOURS = (1, 2, 3, 4, 6, 8, 12, 24)

_CLEAN_ROUNDUP_SEC_MIN = {
    2: (0, 2, 4, 6, 8, ),
    3: (0, 3, 6, 9, 12, )
}


def is_valid_clean_period_seconds(value: int):
    """
    Given a number of seconds, detect if it is in the correct set
    for clean periods, such that doing
    something every 'X' seconds allows predictable repeats each minute.

    Example: doing something every 12 seconds allows 5 'clean periods'
    per minute, but doing something
    every 13 seconds does NOT allow such 'clean periods'

    :param value: the number of seconds (zero-based, not time.time() form!
    :rtype: bool
    """
    return int(value) in CLEAN_PERIOD_SECONDS


def is_valid_clean_period_minutes(value: int):
    """
    Given a number of minutes, detect if it is in the correct set
    for clean periods, such that doing
    something every 'X' minutes allows predictable repeats each hour.

    Example: doing something every 12 minutes allows 5 'clean periods'
    per hour, but doing something
    every 13 minutes does NOT allow such 'clean periods'

    :param value: the number of minutes (zero-based, not time.time() form!
    :rtype: bool
    """
    return int(value) in CLEAN_PERIOD_MINUTES


def is_valid_clean_period_hours(value: int):
    """
    Given a number of hours, detect if it is in the correct set for
    clean periods, such that doing
    something every 'X' hours allows predictable repeats each day.

    Example: doing something every 3 hours allows 8 'clean periods'
    per day, but doing something
    every 5 hours does NOT allow such 'clean periods'

    :param value: the number of hours (zero-based, not time.time() form!
    :rtype: bool
    """
    return int(value) in CLEAN_PERIOD_HOURS


def next_seconds_period(source: int, period: int):
    """
    Given a time as seconds, return next clean period start. For
    example, if source=37 and period=15 (secs), then return 45.

    To know the delta to next period, use delay_to_next_seconds_period()
    instead (so 45 - 37 = 8)

    If 60 is returned, then should be NEXT minute or hour (aka: next '0')
    Also, the input does NOT have to be < 60, so input 292 returns 300,
    and the caller needs to handle any side effects of this.

    :param source: the time as seconds (or minutes)
    :param period: the desired clean period
    :return: the nex period as sec/minutes
    :rtype: int
    """
    # this is same for seconds and minutes
    assert period in _CLEAN_PERIOD_SEC_MIN
    # assert 0 <= source <= 60

    if period == 1:
        # special case #1 - if period is 1, then value is as desired
        # (no round up ever)
        return source

    # we divide and allow truncation (round-down) So 17 / '5 sec' period = 3
    # (// is special integer division)
    value = source // period

    # multiple means 3 * 5 = 15
    value *= period

    # if source % period != 0:
    # then add in 1 more period make it 20, which is correct answer
    value += period

    return value


def next_minutes_period(source: int, period: int):
    """
    See docs for next_second_period() - function is the same

    :rtype: int
    """
    return next_seconds_period(source, period)


def delay_to_next_seconds_period(source: int, period: int):
    """
    Given a time as seconds, return HOW MANY seconds to delay to reach
    start of next clean period start.

    :return: the seconds to reach start of next clean period start
    :rtype: int
    """
    next_period = next_seconds_period(source, period)
    return next_period - source


def delay_to_next_minutes_period(source: int, period: int):
    """
    See docs for delay_to_next_seconds_period() - function is the same

    :rtype: int
    """
    # both minutes & seconds work the same
    next_period = next_seconds_period(source, period)
    return next_period - source
