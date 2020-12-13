import http.server

class Handler(http.server.CGIHTTPRequestHandler):
    cgi_directories = ['/scgi-bin',]

PORT = 9999

httpd = http.server.HTTPServer(("", PORT), Handler)
print("serving at port", PORT)
httpd.serve_forever()

