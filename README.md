Websocket client for protocol version 13 using the Tornado IO loop.

<http://tools.ietf.org/html/rfc6455>


```python
import websocket

class HelloSocket(websocket.WebSocket):

    def on_open(self):
        self.write('hello, world')

    def on_message(self, data):
        print data

    def on_ping(self):
        print 'I was pinged'

    def on_pong(self):
        print 'I was ponged'

    def on_close(self):
        print 'Socket closed.'
        

ws = HelloSocket('ws://echo.websocket.org')
ws.connect()
```
