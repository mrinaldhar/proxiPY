import urlparse
import sys
import multiprocessing
import datetime
import logging
import socket
import select

import thread
import requests
import pickle
import datetime
import hashlib
import signal
import argparse
from stats import *

CACHE = {}
FILE_CACHE = "cache/proxy_cache.db"
EXTERNAL_PROXY = None
PROXY_PORT = 10000


class bcolors:
    EXTERNAL = '\033[96m'
    OKBLUE = '\033[90m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def prettyprint(string, category):
    if category == "ok":
        print bcolors.OKGREEN + "[OKAY]\t" + string + bcolors.ENDC
    elif category == "warn":
        print bcolors.WARNING + "[WARN]\t" + string + bcolors.ENDC
    elif category == "fatal":
        print bcolors.FAIL + "[ERROR]\t" + string + bcolors.ENDC
    elif category == "cache":
        print bcolors.OKBLUE + "[LOG]\t" + string + bcolors.ENDC
    elif category == "bold":
        print bcolors.BOLD + string + bcolors.ENDC
    elif category == "log":
        print "[LOG]\t" + string
    elif category == "external":
        print bcolors.EXTERNAL + "[LOG]\t" + string + bcolors.ENDC


class Transfer(object):
    def __init__(self, client_address):
        self.headers = {}
        self.requestType = None
        self.remoteAddr = None
        self.HTTPv = None
        self.data = ""
        self.text = None
        self.valid = False
        self.status_code = None
        self.port = None
        self.client = client_address

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
            pass

    def parse_response(self, data):
        if data != "":
            self.text = data
            # self.data = data.split('\n\n')[1]
            data = data.split('\r\n')
            res = data[0]
            self.HTTPv = res.split(' ')[0]
            self.status_code = res.split(' ')[1]
            index = 1
            for each in data[1:]:
                if each == "":
                    break
                index += 1
                value = each.split(": ")
                if len(value) > 1:
                    self.headers[value[0]] = value[1]
            self.data = ""
            for each in data[index:]:
                if each == "":
                    break
                self.data += each
            self.valid = True
        else:
            pass

    def reassemble(self):
        self.text = b''
        self.text += self.requestType + " " + self.remoteAddr + " " + self.HTTPv + "\r\n"
        for key in self.headers.keys():
            self.text += key + ": " + self.headers[key] + "\r\n"
        self.text += "\r\n"
        self.text += self.data + "\r\n"

    # def reassemble_using(self, HTTPv, status, )

    def invalidate(self):
        self.text = b''
        self.text += "HTTP/1.1" + " " + "500" + " Internal Server Error" + "\r\n\r\n"

class Proxy(object):
    def __init__(self):
        self.buffer = b''

    def process(self, request):
        self.buffer = b''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # request.headers["Connection"] = "keep-alive"
        request.reassemble()
        if request.requestType in "CONNECT POST DELETE":
            return (False, "")
        try:
            sock.connect((request.headers["Host"], 80))     # Use persistent connections here maybe?
            sock.send(request.text)
            response = sock.recv(8024)
            while response != "":
                self.buffer += response
                response = sock.recv(1024)
            # print "Just Served!"
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
        if (CACHE[URL_hash] - datetime.datetime.now()).total_seconds() > 86400:
            del CACHE[URL_hash]
            return (False, None)
        fp = open("cache/"+URL_hash, "r")
        data = fp.read()
        fp.close()
        return (True, data)
    else:
        return (False, None)

def proxy_worker(connection, client):
    proxy = Proxy()
    try:
        request_buffer = connection.recv(1024)
        # print "Request received", request_buffer
        request = Transfer(client)
        request.parse_request(request_buffer)
        if request.valid:
            if EXTERNAL_PROXY is not None and "iiit.ac.in" not in request.headers["Host"]:
                # print "OUTSIDE REQUEST~~~~~~~~~~", request.headers["Host"]
                response = use_external_proxy((EXTERNAL_PROXY.split(":")[0], EXTERNAL_PROXY.split(":")[1]), (request.headers["Host"], 80))
                connection.sendall(response)
                weblog.logRequest(request)
                prettyprint(str(datetime.datetime.now()) + "\t" + request.client[0] + "\t" + request.requestType + "\t" + request.remoteAddr, "external")
            else:
                cached = fetch_from_cache(request.remoteAddr)
                if cached[0] == True:
                    # print "Just Served from Cache!!"
                    weblog.logRequest(request)
                    prettyprint(str(datetime.datetime.now()) + "\t" + request.client[0] + "\t" + request.requestType + "\t" + request.remoteAddr, "cache")
                    connection.sendall(cached[1])
                else:
                    response = Transfer(request.headers["Host"])
                    success, response_buffer = proxy.process(request)
                    if success:
                        response.parse_response(response_buffer)
                        connection.sendall(response.text)
                        weblog.logRequest(request)
                        prettyprint(str(datetime.datetime.now()) + "\t" + request.client[0] + "\t" + request.requestType + "\t" + request.remoteAddr, "log")
                        write_to_cache(request.remoteAddr, response.text)
                    else:
                        response.invalidate()
                        connection.sendall(response.text)

    finally:
        # Clean up the connection
        weblog.delActive()
        connection.close()

def on_exit(signal, frame):
    global CACHE
    print "\r"
    prettyprint("Saving cache to disk", "warn")
    cache_file = open("cache/proxy_cache.db", "w")
    pickle.dump(CACHE, cache_file)
    prettyprint("Cache has been preserved.", "ok")
    prettyprint("Proxy server has been stopped.", "ok")
    sys.exit(0)


def use_external_proxy(eproxy, address):
    s = socket.socket()
    s.connect(eproxy)
    fp = s.makefile('r+')
    headers = {}
    fp.write('CONNECT %s:%d HTTP/1.1\r\n' % address)
    fp.write('\r\n'.join('%s: %s' % (k, v) for (k, v) in headers.items()) + '\r\n\r\n')
    fp.flush()
    s.send("")
    # statusline = fp.readline().rstrip('\r\n')
    # print statusline
    # if statusline.count(' ') < 2:
    #     fp.close()
    #     s.close()
    #     raise IOError('Bad response')
    # version, status, statusmsg = statusline.split(' ', 2)
    # if not version in ('HTTP/1.0', 'HTTP/1.1'):
    #     fp.close()
    #     s.close()
    #     raise IOError('Unsupported HTTP version')
    # try:
    #     status = int(status)
    # except ValueError:
    #     fp.close()
    #     s.close()
    #     raise IOError('Bad response')

    # response_headers = {}
    # while True:
    #     tl = ''
    #     l = fp.readline().rstrip('\r\n')
    #     if l == '':
    #         break
    #     if not ':' in l:
    #         continue
    #     k, v = l.split(':', 1)
    #     response_headers[k.strip().lower()] = v.strip()
    # # length = response_headers["content-length"]
    # received = 0



    # response_data = ""
    # while True:
    #     tl = ''
    #     l = fp.read(1024)
    #     response_data += l
    #     print "LOL"
    #     if l == "":
    #         break
    # print response_data
    # while True:
    #     tl = ''
    #     l = fp.readline()
    #     response_data += l
    #     print "OK"
    #     if l == "\r\n":
    #         break




    # data = fp.read()
    fp.close()
    # print (s, status, response_headers)
    return response_data

    # s.send("GET http://facebook.com HTTP/1.1")
    # response = s.recv(1024)
    # while response != "" or response != "\r\n":
    #     response_data += response
    #     response = s.recv(1024)
    #     print response
    # print response

def manage_clArguments():
    args = argparse.ArgumentParser()
    args.add_argument("--external", help="Enable proxy-in-proxy feature.")
    args.add_argument("--port", help="Port number for ProxiPy to run on.")
    args.add_argument("--cache", help="Locally stored cache database for the proxy.")
    return args

def main():
    prettyprint("\nWelcome to ProxiPY", "bold")
    prettyprint("Designed by Mrinal Dhar\n", "bold")
    clParser = manage_clArguments()
    args = clParser.parse_args()
    global CACHE, EXTERNAL_PROXY, PROXY_PORT, FILE_CACHE
    if args.external:
        EXTERNAL_PROXY = args.external
    if args.port:
        PROXY_PORT = args.port
    if args.cache:
        FILE_CACHE = args.cache
    try:
        prettyprint("Loading cache from disk", "warn")
        cache_file = open(FILE_CACHE, "r")
        CACHE = pickle.load(cache_file)
        prettyprint("Cache is ready for use", "ok")
    except IOError:
        CACHE = {}

    prettyprint("Starting Web server for Stats UI", "warn")
    prettyprint("Web Server started. You can access ProxyPY stats at http://localhost:5005/", "ok")

    signal.signal(signal.SIGINT, on_exit)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_address = ('localhost', int(PROXY_PORT))

    prettyprint("Starting ProxiPY on localhost, port " + str(PROXY_PORT), "warn")

    sock.bind(server_address)
    sock.listen(10)

    prettyprint("Proxy is now running and ready to serve requests", "ok")

    while True:
        connection, client_address = sock.accept()
        weblog.addActive()
        thread.start_new_thread( proxy_worker, (connection, client_address, ) )

if __name__=="__main__":
    main()
