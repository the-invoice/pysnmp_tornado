import socket, sys
import logging

from pysnmp.carrier import error
from pysnmp.carrier.base import AbstractTransport
from pysnmp import debug

from pysnmp_tornado.carrier.tornado.dispatch import TornadoDispatcher
from tornado.ioloop import IOLoop


LOGGER = logging.getLogger(__name__)


class AbstractSocketTransport(AbstractTransport):
    protoTransportDispatcher = TornadoDispatcher
    sockFamily = sockType = None
    retryCount = 0; retryInterval = 0
    bufferSize = 131070

    def __init__(self, sock=None, io_loop=None):
        self.connected = False
        self.io_loop = io_loop or IOLoop.current()

        if sock is None:
            if self.sockFamily is None:
                raise error.CarrierError(
                    'Address family %s not supported' % self.__class__.__name__
                    )
            if self.sockType is None:
                raise error.CarrierError(
                    'Socket type %s not supported' % self.__class__.__name__
                    )
            try:
                sock = socket.socket(self.sockFamily, self.sockType)
            except socket.error:
                raise error.CarrierError('socket() failed: %s' % sys.exc_info()[1])

            try:
                for b in socket.SO_RCVBUF, socket.SO_SNDBUF:
                    bsize = sock.getsockopt(socket.SOL_SOCKET, b)
                    if bsize < self.bufferSize:
                        sock.setsockopt(socket.SOL_SOCKET, b, self.bufferSize)
                        LOGGER.debug('%s: socket %d buffer size increased from %d to %d for buffer %d' % (self.__class__.__name__, sock.fileno(), bsize, self.bufferSize, b))
            except Exception:
                LOGGER.debug('%s: socket buffer size option mangling failure for buffer %d: %s' % (self.__class__.__name__, b, sys.exc_info()[1]))

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        self.socket = sock
        self._fileno = sock.fileno()

        self.io_loop.add_handler(self._fileno, self.event_handler, IOLoop.READ)
        self.is_writable = False
        self.connected = True

    # tornado IOLoop handler
    def event_handler(self, fd, events):
        LOGGER.debug('R: %s W: %s' % (bool(events & IOLoop.READ), bool(events & IOLoop.WRITE)))
        if events & IOLoop.READ:
            self.handle_read()
        if events & IOLoop.WRITE:
            self.handle_write()

    def set_writable(self, is_writable):
        if self.is_writable == is_writable: return
        if is_writable:
            self.io_loop.update_handler(self._fileno, IOLoop.READ | IOLoop.WRITE)
        else:
            self.io_loop.update_handler(self._fileno, IOLoop.READ)
        self.is_writable = is_writable

    # Public API

    def openClientMode(self, iface=None):
        raise error.CarrierError('Method not implemented')

    def openServerMode(self, iface=None):
        raise error.CarrierError('Method not implemented')

    def sendMessage(self, outgoingMessage, transportAddress):
        raise error.CarrierError('Method not implemented')

    def closeTransport(self):
        AbstractTransport.closeTransport(self)
        self.io_loop.remove_handler(self._fileno)
        self.socket.close()
        self.connected = False

