"""
    inetline.py -- State machine to parse CR,CRLF,LF style lines.
        Also handles delimited lines (e.g., TAIP ><)
        No, readline() isn't sufficient.

    Copyright © 2018 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

    This file contains confidential information of Cradlepoint, Inc. and your
    use of this file is subject to the Cradlepoint Software License Agreement
    distributed with this file. Unauthorized reproduction or distribution of
    this file is subject to civil and criminal penalties.
"""

STATE_RECV_LINE = 1
STATE_WAIT_LF = 2
STATE_WAIT_SOL = 3

CR = '\x0d'
LF = '\x0a'


class ReadLine(object):
    """State machine to read CR/LF style line. Input controlled from outside. """

    # Keeping the read or recv or whatever outside the class allows me to handle
    # weird conditions around sockets, serial ports, etc.

    def __init__(self, maxlen=256):
        self.maxlen = maxlen
        self.state = STATE_RECV_LINE
        self.s = str()
        self.len_s = 0

    def recv(self, c):
        return_s = None

        assert type(c) == type(str()), type(c)

        if self.state == STATE_RECV_LINE:
            if c == CR:
                # CR; could be a bare CR or a CRLF
                return_s = self.s
                # restart capture
                self.s = str()
                self.len_s = 0
                self.state = STATE_WAIT_LF
            elif c == LF:
                # bare LF (unusual)
                return_s = self.s

                # restart capture
                self.s = str()
                self.len_s = 0
            else:
                self.s += c
                self.len_s += 1

                # protection from evil input; if we don't see a CRLF before
                # maxlen, throw away our current input and start over
                if self.len_s >= self.maxlen:
                    # throw away current input; start over
                    self.s = str()
                    self.len_s = 0

        elif self.state == STATE_WAIT_LF:
            #           return_s = self.s

            if c == LF:
                # saw CRLF; capture was restarted in the previous state
                assert self.len_s == 0, self.len_s
            else:
                # raw CR! save what we've seen and start parsing again
                # (note: this won't handle weird cases like CRCRCR)
                self.s = c
                self.len_s = 1

            # start capturing line again
            self.state = STATE_RECV_LINE

        else:
            # WTF?
            assert 0, self.state

        return return_s

    def __len__(self):
        return self.len_s
