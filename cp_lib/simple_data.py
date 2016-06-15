import time

import cp_lib.data.quality as qual


class SimpleData(object):

    def __init__(self, value=None, uom=None, now=None, quality=None):
        self.value = None
        self.unit = None
        self.time = None
        self.quality = None

        if value is not None:
            self.set_value(value, uom, now, quality)
        return

    def __repr__(self):
        """
        make a fancy string output
        :return:
        """
        st = str(self.value)

        if self.unit is not None:
            st += ' (' + self.unit + ')'

        if self.quality is not None and self.quality != qual.QUALITY_GOOD:
            st += ' !Quality:%s' % qual.all_bits_to_tag(self.quality)

        if self.time is not None:
            st += ' (%s)' % time.strftime("%Y-%m-%d %H:%M:%S",
                                          time.localtime(self.time))
        return st

    def set_value(self, value, uom=None, now=None, quality=None):
        """
        Set the value, with time and quality

        :param value:
        :param str uom:
        :param float now:
        :param int quality:
        :return:
        """
        self.value = value
        self.unit = uom

        if now is None:
            self.time = time.time()
        else:
            self.time = now

        if quality is None:
            self.quality = qual.QUALITY_GOOD
        else:
            self.quality = (qual.QUALITY_GOOD | quality)

        return
