#!python
# coding=utf-8
from functools import partial

from tornado import testing
import tornado.websocket
import tornado.web
import tornado.ioloop
import websocket


class EchoWebSocketHandler(tornado.websocket.WebSocketHandler):
    def on_message(self, message):
        self.write_message(message)


class WebSocketTest(testing.AsyncHTTPTestCase):
    """
    Example of WebSocket usage as a client
    in AsyncHTTPTestCase-based unit tests.
    """

    def get_app(self):
        app = tornado.web.Application([('/', EchoWebSocketHandler)])
        return app

    def test_echo(self):
        _self = self

        class WSClient(websocket.WebSocket):
            def on_open(self):
                self.write_message('hello')

            def on_message(self, data):
                _self.assertEquals(data, 'hello')
                _self.io_loop.add_callback(_self.stop)

        self.io_loop.add_callback(partial(WSClient, self.get_url('/'),
                                          self.io_loop))
        self.wait()
