# -*- coding: utf-8 -*-
"""
Websocket client for protocol version 13 using the Tornado IO loop.

http://tools.ietf.org/html/rfc6455
"""
import base64
from BaseHTTPServer import BaseHTTPRequestHandler
from functools import partial
import hashlib
import os
import re
import socket
import struct
import sys
import time
import urlparse

from tornado import ioloop, iostream
from tornado.httputil import HTTPHeaders


# The initial handshake over HTTP.
INIT = """\
GET %(path)s HTTP/1.1
Host: %(host)s:%(port)s
Upgrade: websocket
Connection: Upgrade
Sec-Websocket-Key: %(key)s
Sec-Websocket-Version: 13
"""

# Magic string defined in the spec for calculating keys.
MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def frame(data, opcode=0x01):
    """Encode data in a websocket frame."""
    # [fin, rsv, rsv, rsv] [opcode]
    frame = struct.pack('B', 0x80 | opcode)

    # Our next bit is 1 since we're using a mask.
    length = len(data)
    if length < 126:
        # If length < 126, it fits in the next 7 bits.
        frame += struct.pack('B', 0x80 | length)
    elif length <= 0xFFFF:
        # If length < 0xffff, put 126 in the next 7 bits and write the length
        # in the next 2 bytes.
        frame += struct.pack('!BH', 0x80 | 126, length)
    else:
        # Otherwise put 127 in the next 7 bits and write the length in the next
        # 8 bytes.
        frame += struct.pack('!BQ', 0x80 | 127, length)

    # Clients must apply a 32-bit mask to all data sent.
    mask = map(ord, os.urandom(4))
    frame += struct.pack('!BBBB', *mask)
    # Mask each byte of data using a byte from the mask.
    msg = [ord(c) ^ mask[i % 4] for i, c in enumerate(data)]
    frame += struct.pack('!' + 'B' * length, *msg)
    return frame


class WebSocket(object):

    def __init__(self, url):
        ports = {'ws': 80, 'wss': 443}

        self.url = urlparse.urlparse(url)
        self.host = self.url.hostname
        self.port = self.url.port or ports[self.url.scheme]
        self.path = self.url.path or '/'

        self.key = base64.b64encode(os.urandom(16))
        self.stream = iostream.IOStream(socket.socket())
        self.stream.set_close_callback(self.on_close)

    def connect(self):
        self.stream.connect((self.host, self.port), self._on_open)

    def write(self, msg, opcode=0x01):
        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')
        self.stream.write(frame(msg, opcode))

    def close(self):
        self.write('', opcode=0x08)
        self.stream.close()

    def _on_open(self):
        request = '\r\n'.join(INIT.splitlines()) % self.__dict__ + '\r\n\r\n'
        self.stream.write(request)
        self.stream.read_until('\r\n\r\n', self.on_headers)

    def on_headers(self, data):
        first, _, rest = data.partition('\r\n')
        headers = HTTPHeaders.parse(rest)
        # Expect HTTP 101 response.
        assert re.match('HTTP/[^ ]+ 101', first)
        # Expect Connection: Upgrade.
        assert headers['Connection'].lower() == 'upgrade'
        # Expect Upgrade: websocket.
        assert headers['Upgrade'].lower() == 'websocket'
        # Sec-WebSocket-Accept should be derived from our key.
        accept = base64.b64encode(hashlib.sha1(self.key + MAGIC).digest())
        assert headers['Sec-WebSocket-Accept'] == accept

        self.on_open()
        self.get_frame()

    def get_frame(self):
        self.stream.read_bytes(2, self.on_frame)

    def on_frame(self, data):
        # TODO: close, ping/pong, fragmentation
        header, length = struct.unpack('BB', data)
        assert header == 0x81, 'Expected fin + text'
        assert not length & 0x80, 'Unexpected masking'
        if length < 126:
            self.stream.read_bytes(length, self._on_message)
        elif length == 126:
            # The length is in the next two bytes.
            self.stream.read_bytes(2, partial(self._on_length, 'H'))
        elif length == 127:
            # The length is in the next eight bytes.
            self.stream.read_bytes(8, partial(self._on_length, 'Q'))

    def _on_length(self, fmt, data):
        self.stream.read_bytes(struct.unpack(fmt, data), self._on_message)

    def _on_message(self, data):
        self.get_frame()
        self.on_message(data.decode('utf-8'))

    def on_open(self):
        pass

    def on_message(self, data):
        pass

    def on_close(self):
        pass


def main(url, message='hello, world'):

    class Socket(WebSocket):

        def on_open(self):
            print '>>', message
            self.write(message)

        def on_message(self, data):
            print data
            self.write(raw_input('>> '))

        def on_close(self):
            print 'close'

    ws = Socket(url)
    ws.connect()
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        pass
    finally:
        ws.close()


if __name__ == '__main__':
    main(*sys.argv[1:])
