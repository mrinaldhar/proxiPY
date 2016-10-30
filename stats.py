from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import SocketServer
import cgi
import urllib2
import thread
import json


'''
Handler for the integrated web server interface
'''
class S(BaseHTTPRequestHandler):
	def _set_headers(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()


	def log_message(self, format, *args):
		return

	'''
	Handles GET requests for the server
	'''
	def do_GET(self):
		self._set_headers()
		args = {}
		idx = self.path.find('?')
		if idx >= 0:
			rpath = self.path[:idx]
			args = cgi.parse_qs(self.path[idx+1:])
		else:
			rpath = self.path

		if rpath == '/activeThreads':										# If the request is for a search process, read the query term.
			# reqPath[1] = urllib.unquote(reqPath[1]).decode('utf8')		# For URL decoding
			self.wfile.write(json.dumps({"threads": weblog.activeThreads}))

		elif rpath == '/getRequests':
			self.wfile.write(json.dumps({"requests": weblog.served}))
			weblog.served = []
		else:
			try:												# Request for all other files
				self.wfile.write(open("stats/"+rpath[1:]).read())
			except IOError:
				pass

	def do_HEAD(self):
		self._set_headers()

'''
Starts the HTTP server
'''
def run_server(server_class=HTTPServer, handler_class=S, port=5000):
	server_address = ('0.0.0.0', port)
	httpd = server_class(server_address, handler_class)
	httpd.serve_forever()


class WebStats(object):
	def __init__(self):
		self.served = []
		self.activeThreads = 0
		thread.start_new_thread( run_server, () )


	def addActive(self):
		self.activeThreads += 1

	def delActive(self):
		self.activeThreads -= 1

	def logRequest(self, request):
		result = {"remoteAddr":request.remoteAddr}
		self.served.append(result)

weblog = WebStats()
