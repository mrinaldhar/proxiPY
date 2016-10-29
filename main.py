import urlparse
import sys
import multiprocessing
import datetime
import argparse
import logging
import socket
import select

import thread
import requests
import pickle
import datetime
import hashlib
import signal

CACHE = {}

class Transfer(object):
    def __init__(self):
        self.headers = {}
        self.requestType = None
        self.remoteAddr = None
        self.HTTPv = None
        self.data = ""
        self.text = None
        self.valid = False
        self.status_code = None

    def parse_request(self, data):
        if data != "":
            self.text = data
            # self.data = data.split('\n\n')[1]
            data = data.split('\r\n')
            req = data[0]
            self.requestType = req.split(' ')[0]
            self.remoteAddr = req.split(' ')[1]
            self.HTTPv = req.split(' ')[2]
            for each in data[1:]:
                if each == "":
                    break
                value = each.split(": ")
                if len(value) > 1:
                    self.headers[value[0]] = value[1]
            self.valid = True
        else:
            print "Failed"

    def parse_response(self, data):
        if data != "":
            self.text = data
            # self.data = data.split('\n\n')[1]
            data = data.split('\r\n')
            res = data[0]
            self.HTTPv = res.split(' ')[0]
            self.status_code = res.split(' ')[1]
            for each in data[1:]:
                if each == "":
                    break
                value = each.split(": ")
                if len(value) > 1:
                    self.headers[value[0]] = value[1]
            self.valid = True
        else:
            print "Failed"

    def reassemble(self):
        self.text = b''
        self.text += self.requestType + " " + self.remoteAddr + " " + self.HTTPv + "\r\n"
        for key in self.headers.keys():
            self.text += key + ": " + self.headers[key] + "\r\n"
        self.text += "\r\n"
        self.text += self.data + "\r\n"

    def invalidate(self):
        self.text = b''
        self.text += "HTTP/1.1" + " " + "404" + " Not Found" + "\r\n\r\n"

class Proxy(object):
    def __init__(self):
        self.buffer = b''

    def process(self, request):
        self.buffer = b''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # request.headers["Connection"] = "keep-alive"
        request.reassemble()
        try:
            sock.connect((request.headers["Host"], 80))     # Use persistent connections here maybe?
            sock.send(request.text)
            response = sock.recv(8024)
            while response != "":
                self.buffer += response
                response = sock.recv(1024)
            print "Just Served!"
            return (True, self.buffer)

        except socket.error:
            return (False, "")

def write_to_cache(URL, response):
    URL_hash = hashlib.md5(URL).hexdigest()
    CACHE[URL_hash] = datetime.datetime.now()
    fp = open("cache/"+URL_hash, "w")
    fp.write(response)
    fp.close()

def fetch_from_cache(URL):
    URL_hash = hashlib.md5(URL).hexdigest()
    if CACHE.has_key(URL_hash):
        fp = open("cache/"+URL_hash, "r")
        data = fp.read()
        fp.close()
        return (True, data)
    else:
        return (False, None)

def proxy_worker(connection):
    proxy = Proxy()
    try:
        request_buffer = connection.recv(1024)
        print "Request received", request_buffer
        request = Transfer()
        request.parse_request(request_buffer)
        if request.valid:
            cached = fetch_from_cache(request.remoteAddr)
            if cached[0] == True:
                print "Just Served from Cache!!"
                connection.sendall(cached[1])
            else:
                response = Transfer()
                success, response_buffer = proxy.process(request)
                if success:
                    response.parse_response(response_buffer)
                    # response.headers["Served by"] = "ProxiPY: Developed by Mrinal Dhar"
                    connection.sendall(response.text)
                    write_to_cache(request.remoteAddr, response.text)
                else:
                    response.invalidate()
                    connection.sendall(response.text)

    finally:
        # Clean up the connection
        connection.close()

def on_exit(signal, frame):
    global CACHE
    cache_file = open("cache/proxy_cache.db", "w")
    pickle.dump(CACHE, cache_file)
    print "\nExiting..."
    sys.exit(0)

def main():
    global CACHE
    try:
        cache_file = open("cache/proxy_cache.db", "r")
        CACHE = pickle.load(cache_file)
    except IOError:
        CACHE = {}

    signal.signal(signal.SIGINT, on_exit)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_address = ('localhost', 10000)
    print >>sys.stderr, 'Starting Proxy server on %s port %s' % server_address
    sock.bind(server_address)
    sock.listen(10)
    while True:
        connection, client_address = sock.accept()
        thread.start_new_thread( proxy_worker, (connection, ) )

if __name__=="__main__":
    main()
