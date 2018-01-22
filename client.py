#!/usr/bin/python

# Client program to tunnel SSH through an HTTP connection.

# Listens locally on port 8022 (change LISTEN_PORT below). Forwards data to the
# server component over HTTPS. The server component forwards the data to an SSH server
# on the target network.

# Use the native SSH port forwarding and other options to provide additional connectivity. SFTP and SCP also work through the tunnel.

# 2015-02-21 Paul T Sparks

import Queue
import base64
import configfile
import getpass
import os
import socket
import sys
import time
import threading
import traceback
import urllib
import urllib2


debugFlag= False
def setDebug(flag):
    global debugFlag
    debugFlag= flag

def debug(*args):
    if debugFlag:
        sys.stderr.write(' '.join(map(str,args))+'\n')

def log(*args):
    sys.stderr.write(' '.join(map(str,args))+'\n')

# listen for clients on this local port.
LISTEN_PORT= 8022

# read buffer from local client socket.
LOCAL_BUFFER= 4096

# Try to send at least this much data at once to HTTP server
HTTP_SEND_SIZE= 16384

# Configuration filename in users home directory.
configFilename = '.config/httpclient.conf'
config = None

# These need to be global accessible
credentials = None


class Connection():
    """ Encapsulates an entire connection between a client and the
corresponding connection to the HTTP tunnel server. """

    # Start a connection to the HTTP server for the new client
    def __init__(self, clientsocket, address):
        self.socket= clientsocket
        self.mainThread = threading.Thread(target=self.main)
        self.mainThread.start()

    # Set up the connection then wait for client input
    def main(self):
        try:
            self.cid = self.getHTTPConnection()
            debug('Got HTTP connection. id=',self.cid)
        except urllib2.HTTPError as e:
            log('Failed to establish an HTTP connection:', e)
            return

        self.sendQueue = Queue.Queue()
        self.sendThread = threading.Thread(target=self.sendHTTP, args = (self.cid, self.sendQueue))
        self.sendThread.start()
        self.recvThread = threading.Thread(target=self.recvHTTP, args = (self.cid, self.socket))
        self.recvThread.start()

        while 1:
            data = self.socket.recv(LOCAL_BUFFER)
            if not data:
                log('Got zero data. Client connection gone.')
                break
            debug('main: Got data from local client:',repr(data[:64]))
            self.sendQueue.put(data)
        self.socket.close()
        self.socket = None
        self.sendQueue.put(None) # Tell sender to shut down
        # receiver gets killed by server disconnect or seeing the client socket is gone.


    # Establish a connection with the HTTP server
    def getHTTPConnection(self):
        url = config['vpnURL'] + '?a=c'
        debug('vpn connect URL=',url)
        req = urllib2.Request(url)
        req.add_header('Authorization', 'Basic %s' % credentials)
        response = urllib2.urlopen(req)
        response_data = response.read()
        response.close()
        return response_data


    # Collect waiting data into a single buffer until we reach a threshold length
    def getAccumulatedData(self, sendQueue):
        data = sendQueue.get()
        sendQueue.task_done()
        if not data: return data # bail out. We're shutting down
        while len(data) < HTTP_SEND_SIZE and not sendQueue.empty():
            b = sendQueue.get()
            sendQueue.task_done()
            if not b: return None
            data += b
        return data


    # Handle sending data to the HTTP server
    def sendHTTP(self, connectionId, sendQueue):
        urlbase= config['vpnURL'] + '?a=r&i=%s' % connectionId
        sequence = 0
        while 1:
            data = self.getAccumulatedData(sendQueue)
            if data == None:
                break
            debug('sendHTTP: got data to send. len=', len(data))

            try:
                debug('sendHTTP: sending data to server. len=', len(data))
                url = urlbase + '&l=%d&s=%d' % (len(data), sequence)
                headers = {
                    'Content-Length':'%d' % len(data),
                    'Content-Type':'application/octet-stream',
                    'Authorization':'Basic %s' % credentials,
                    }
                req = urllib2.Request(url.encode('utf-8'), data, headers)
                response = urllib2.urlopen(req)
                response_data = response.read()
                response.close()
                sequence += 1
            except urllib2.HTTPError as e:
                log('sendHTTP:HTTPError', e)
                break
            except:
                log('sendHTTP:Unexpected error', sys.exc_info()[1],traceback.format_tb(sys.exc_info()[2]))
                break

        log('sendHTTP: Shutting down send thread')
        self.killHTTP(connectionId)


    # Get data from the HTTP server and send it to the client.
    def recvHTTP(self, connectionId, socket):
        time.sleep(2)
        url= config['vpnURL'] + '?a=r&i=%s' % connectionId
        try:
            while True:
                req = urllib2.Request(url)
                req.add_header('Authorization', 'Basic %s' % credentials)
                response = urllib2.urlopen(req)
                debug('recvHTTP: sending read request')
                response_data = response.read()
                response.close()
                debug('recvHTTP: Got data len=', len(response_data))
                if not socket:
                    break
                socket.send(response_data)
                debug('recvHTTP: Sent data to local client')
        except urllib2.HTTPError as e:
            log('recvHTTP: HTTPError on recv request. HTTP code=', response.getcode(), ' error info=',e)
        except:
            log('recvHTTP:Unexpected error', sys.exc_info()[1],sys.exc_info()[2])
        if socket: socket.close()

    # Tell the HTTP server we are disconnecting.
    def killHTTP(self, connectionId):
        url= config['vpnURL'] + '?a=d&i=%s' % connectionId
        try:
            req = urllib2.Request(url)
            req.add_header('Authorization', 'Basic %s' % credentials)
            response = urllib2.urlopen(req)
            response_data = response.read()
            response.close()
        except:
            log('killHTTP: Error on tunnel disconnect', sys.exc_info()[1],sys.exc_info()[2])

    # Close this connection
    def close(self):
        self.sendQueue.put(None) # Tell sender to shut down


# Get configuration from user. Use existing values as defaults (except passwords).
def configure(filename, pw):
    defaults = {
        'proxyIP':'.',
        'proxyID':getpass.getuser(),
        'proxyPW':'',
        'vpnURL':'https://vpnIP/vpn',
        'vpnID':getpass.getuser(),
        'vpnPW':'',
        }
    config = configfile.ConfigFile(filename, pw, defaults)

    proxyIP = raw_input("Proxy IP address. '.' for no proxy [%s] : " % config['proxyIP'])
    if proxyIP: config['proxyIP'] = proxyIP

    if config['proxyIP'] != '.':
        proxyID = raw_input("Enter proxy username [%s]: " % config['proxyID'])
        if proxyID: config['proxyID'] = proxyID
        config['proxyPW'] = getpass.getpass()
    
    vpnURL = raw_input("VPN URL [%s]: " % config['vpnURL'])
    if vpnURL: config['vpnURL'] = vpnURL
    vpnID = raw_input("VPN Username [%s]: " % config['vpnID'])
    if vpnID: config['vpnID'] = vpnID
    config['vpnPW'] = getpass.getpass()

    return config


    

if not configfile.exists(configFilename):
    msg = 'Creating config file for time. Enter password twice.'
    pw = ''
    pw2 = '.'
    while pw != pw2:
        print msg
        pw= getpass.getpass()
        pw2= getpass.getpass()
        msg = 'Passwords do not match. Re-enter.'
    config = configure(configFilename, pw)
elif len(sys.argv) > 1 and sys.argv[1] == 'config':
    pw= getpass.getpass()
    config = configure(configFilename, pw)
else:
    pw= getpass.getpass()
    config = configfile.ConfigFile(configFilename, pw)
    

connections = []
credentials = base64.encodestring('%s:%s' % (config['vpnID'], config['vpnPW'])).replace('\n', '')
debug('credentials',credentials)

if config['proxyIP'] != '.':
    proxystr='https://%s:%s@%s' % (config['proxyID'],config['proxyPW'],config['proxyIP'])
    os.environ['https_proxy'] = proxystr.replace('\n', '')
    debug('proxy URL',proxystr)

# Create our listen socket, bind to public port, and become a server
serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversocket.bind(('localhost', LISTEN_PORT))
serversocket.listen(5)
log('Listening on port', LISTEN_PORT)
try:
    while 1:    # Start accepting connections from outside
        (clientsocket, address) = serversocket.accept()
        log('Got connection from',address)
        connections.append(Connection(clientsocket, address))
except KeyboardInterrupt:
    pass
for i in connections:
    i.close()
serversocket.close()
