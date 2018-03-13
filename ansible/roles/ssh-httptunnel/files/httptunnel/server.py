#!/usr/bin/python

# HTTP tunnel to SSH web server. This program is intended to sit behind a TLS enabled
# proxy that should also provide authentication / authorization.

# The server is multithreaded to handle multiple connections at once. This is important 
# even for a single SSH tunnel due to the nature of the HTTP requests.
# Requests are generally GET requests with parameters. All commands except the initial 
# connection require an integer connection ID.
# HTTP query parameters: 
# a=command action, i= connection ID (cid), l=data length, s=send sequence integer
# GET request Command action values:
#  c - connect. returns cid to client
#  d - disconnect. cid required. After this command the cid is no longer valid.
#  r - receive data. cid required. Client requests data from the upstream server.
# POST request to send data to SSH server
#  requires cid, data length, send sequence
#

# Paul T Sparks 2015-03-04

import BaseHTTPServer
import SocketServer
import os
import socket
import string
import sys
import threading
import time
import urlparse

# listen at this address and port for HTTP requests
HOST_NAME = 'localhost'
PORT_NUMBER = 9080

# Connect to this backend server
TARGET_HOST = '10.0.0.251'
TARGET_PORT = 389

SOCK_RECV_BUFSIZE = 16368

# recv timeout in seconds for upstream SSH server
UPSTREAM_TIMEOUT = 60.0 * 10

PIDFILE='httptunnel.pid'

debugFlag= False
def setDebug(flag):
    global debugFlag
    debugFlag= flag

def debug(*args):
    if debugFlag:
        sys.stderr.write(' '.join(map(str,args))+'\n')

def log(*args):
    sys.stderr.write(' '.join(map(str,args))+'\n')


log(str(os.getcwd()))
def writepid():
    fd = open(PIDFILE,'w')
    fd.write(str(os.getpid())+'\n')
    fd.close()

# Keep track of upstream server connection sockets in a thread safe way.
class ConnectionPool:
    def __init__(self):
        self.lock = threading.Lock()
        self.nextId = 0;
        self.pool = {};

    def new(self,val):
        with self.lock:
            cid= self.nextId
            self.pool[cid]= val
            self.nextId += 1
        return cid

    def has(self,cid):
        with self.lock:
            return (cid in self.pool)

    def get(self,cid):
        with self.lock:
            if cid in self.pool:
                return self.pool[cid]
        return None

    def remove(self,cid):
        with self.lock:
            if cid in self.pool:
                del self.pool[cid]

    def debug(self,msg):
        debug(msg,'connections:', self.pool,'nextId:',self.nextId)
    

connections= ConnectionPool()

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()


    def createConnection(s):
        """ Create a new client connection. Opens socket to target. """
        try:
            clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clientsocket.settimeout(UPSTREAM_TIMEOUT)
            clientsocket.connect((TARGET_HOST, TARGET_PORT))
            cid = connections.new(clientsocket)
            #connections.debug('after allocate')

            s.send_response(200)
            s.send_header("Content-type", "text/plain")
            s.end_headers()
            s.wfile.write(str(cid))
        except:
            e = sys.exc_info()
            log('Error:', e[0], e[1])
            s.send_response(500)
            s.send_header("Content-type", "text/plain")
            s.end_headers()


    def disconnect(s, cid):
        if not connections.has(cid):
            return  # we've already disconnected

        connections.get(cid).close()
        connections.remove(cid)
        s.send_response(200)
        s.end_headers()

    def receiveRequest(s, cid):
        socket= connections.get(cid)
        socket.settimeout(UPSTREAM_TIMEOUT)
        data= socket.recv(SOCK_RECV_BUFSIZE)
        debug('Data from server len=', len(data))
        s.send_response(200)
        s.send_header("Content-type", "application/octet-stream")
        s.end_headers()
        s.wfile.write(data)


    def do_GET(s):
        """Respond to a GET request."""
        connections.debug('got GET')
        ppath = urlparse.urlparse(s.path)
        params = urlparse.parse_qs(ppath.query)
        debug('GET request params:', params)
        command = params['a'][0]
        debug('command=',command)
        if command != 'c':
            cid = int(params['i'][0])
            debug('cid=', cid)
        if command == 'c':
            s.createConnection()
        elif command == 'd':
            if connections.has(cid):
                s.disconnect(cid)
        elif command == 'r':
            if connections.has(cid):
                s.receiveRequest(cid)

    def do_POST(s):
        """Respond to a POST request."""
        connections.debug('got POST')
        ppath = urlparse.urlparse(s.path)
        params = urlparse.parse_qs(ppath.query)
        debug('POST params:', params)
        cid = int(params['i'][0])
        length = int(params['l'][0])
        seq = int(params['s'][0])
        data = s.rfile.read(length)
        debug('cid=',cid,'len=',length,'seq=',seq, 'data=',repr(data[:64]))
        connections.debug('before connections.get')
        socket = connections.get(cid)
        debug('socket:',socket)
        totalsent = 0
        while totalsent < length:
            sent = socket.send(data[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent
           
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()


class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """ Handle requests in a seperate thread. """


if __name__ == '__main__':
    setDebug(False)
    httpd = ThreadedHTTPServer((HOST_NAME, PORT_NUMBER), MyHandler)
    log(time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER))
    writepid()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    log(time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER))
    os.remove(PIDFILE)
