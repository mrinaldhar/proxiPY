# proxiPY
### A lightweight HTTP proxy server. Designed by Mrinal Dhar


## How to run: 
$ python main.py <optional arguments>


## Optional Arguments: 
### --external proxy.iiit.ac.in:8080
The "Proxy in Proxy" feature. If proxiPY is running inside a corportate network which also has a proxy of its own, use this argument to access websites on the internet via the corporate proxy. Deafult is none.

### --port 10010
Specify a port number for proxiPY to run on. Default is 12345. 

### --cache mylog.db
Specify a cache file for proxiPY to store and load pickled values from. 

--

# Features:

## Compatible with browsers and curl: 
proxiPY works as your browser's HTTP proxy. 

## Web UI:
proxiPY offers a web user interface at http://localhost:5005/ with realtime statistics like current load, requests served, etc. by the proxy server.

## External Proxy support:
proxiPY supports the use of corporate and educational institute's proxy servers for external requests.
