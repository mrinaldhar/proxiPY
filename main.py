import urlparse
import sys
import multiprocessing
import datetime
import argparse
import logging
import socket
import select

import requests


class Transfer(object):
    def __init__(self):
        self.headers = {}
        self.requestType = None
        self.remoteAddr = None
        self.HTTPv = None
        self.data = ""
        self.text = None
        self.valid = False

    def parse_request(self, data):
        if data != "":
            self.text = data
            print data
            data = data.split('\r\n')
            req = data[0]
            self.requestType = req.split(' ')[0]
            self.remoteAddr = req.split(' ')[1]
            self.HTTPv = req.split(' ')[2]
            for each in data[1:]:
                value = each.split(": ")
                if len(value) > 1:
                    self.headers[value[0]] = value[1]
            self.valid = True

class Proxy(object):
    def __init__(self):
        self.buffer = b''

    def process(self, request):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # request.headers["Connection"] = "keep-alive"
        request.text = self.reassemble_request(request)
        sock.connect((request.headers["Host"], 80))
        sock.send(request.text)
        response = sock.recv(8024)
        while response != "":
            self.buffer += response
            response = sock.recv(1024)
        print "Just Served!"
        return self.buffer

    def reassemble_request(self, request):
        final = b''
        final += request.requestType + " " + request.remoteAddr + " " + request.HTTPv + "\r\n"
        for key in request.headers.keys():
            final += key + ": " + request.headers[key] + "\r\n"
        final += "\r\n"
        final += request.data + "\r\n"
        return final

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_address = ('localhost', 10000)
    print >>sys.stderr, 'Starting Proxy server on %s port %s' % server_address
    sock.bind(server_address)
    sock.listen(1)
    proxy = Proxy()

    while True:
        connection, client_address = sock.accept()
        try:
            print >>sys.stderr, 'connection from', client_address

            # Receive the data in small chunks and retransmit it
            request_buffer = connection.recv(1024)
            print "Request received", request_buffer
            request = Transfer()
            request.parse_request(request_buffer)
            if request.valid:
                print request.requestType, request.remoteAddr
                response = proxy.process(request)
                connection.sendall(response)

        finally:
            # Clean up the connection
            connection.close()

if __name__=="__main__":
    main()
