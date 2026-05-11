import re
from datetime import datetime, timezone, timedelta

server_start_timestamp = datetime.now()

class HTTPRequest:
    def __init__(self, http_request_data = None):
        self.headers = {}
        self.method = ""
        self.path = ""
        self.http_version = ""
        self.cookies = {}
        self.populate(http_request_data)
    
    def populate(self, http_request_data):
        if http_request_data == None:
            return None
        header_dict = {}
        http_header = ""
        first = True
        # Get main line + headers
        for line in http_request_data.split("\r\n"):
            if first:
                http_header = line
                first = False
                continue
            line_parts = line.split(": ")
            if len(line_parts) > 1:
                header_dict[str(line_parts[0]).lower()] = line_parts[1]
        if http_header == None:
            return
        
        self.headers = header_dict # save headers dict
        cookie_header = self.headers.get("cookie", "") # get cookie

        for part in cookie_header.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                self.cookies[key.strip()] = value.strip()
        try:
            match = re.match(r"(\S+)\s+(\S+)\s+(\S+)", http_header)
            self.method, self.path, self.http_version = match.groups()
        except:
            return

class HTTPCookie:
    def __init__(self, name, value, http_only=False, path="/", same_site = "Lax"):
        self.name = name
        self.value = value
        self.http_only = http_only
        self.path = path
        self.same_site = same_site
    
    def __str__(self):
        cookie = f"{self.name}={self.value}; Path={self.path}; SameSite={self.same_site}"
        if self.http_only:
            cookie += "; HttpOnly"
        return cookie

class HTTPResponse:
    def __init__(self):
        self.http_version = "HTTP/1.1"
        self.body = ""
        self.status_code = 200
        self.reason_phrase = "OK"
        
        # Default headers
        self.headers = {
            "Cache-Control": "max-age=1", # Age for caching on FE
            "Content-Type": "text/html; charset=UTF-8",
            "Date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Expires": (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Last-Modified": server_start_timestamp.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Server": "Purstraction/Yarn",
            "Vary": "Accept, Accept-Encoding",
            "X-Cache": "HIT",
        }
    
    def __str__(self):
        # Format the response into something to send to client as response
        self.headers["Content-Length"] = str(len(self.body.encode("utf-8"))) # content length
        shebang = self.http_version + " " + str(self.status_code) + " " + self.reason_phrase # HTTP/1.1 200 OK -> For example
        header_lines = []
        for key, value in self.headers.items():
            if isinstance(value, list):
                header_lines.extend([f"{key}: {item}" for item in value])
            else:
                header_lines.append(f"{key}: {value}")
        headers_str = "\r\n".join(header_lines) # join all the headers
        return shebang + "\r\n" + headers_str + "\r\n\r\n" + self.body # put it all together (2 line breaks for html)
    
    def set_cookie(self, cookie:HTTPCookie):
        if cookie is None:
            return
        existing = self.headers.get("Set-Cookie")
        cookie_str = str(cookie)
        if existing is None:
            self.headers["Set-Cookie"] = [cookie_str]
        elif isinstance(existing, list):
            existing.append(cookie_str)
        else:
            self.headers["Set-Cookie"] = [existing, cookie_str]

# So that we can create/manipulate headers within routes
def make_response(body, status_code = 200, reason_phrase = "OK", http_version = "HTTP/1.1", cookies=None, headers=None):
    response = HTTPResponse()
    response.body = body
    response.status_code = status_code
    response.reason_phrase = reason_phrase
    response.http_version = http_version
    if headers:
        response.headers.update(headers)
    if cookies != None and len(cookies) > 0:
        for cookie in cookies:
            response.set_cookie(cookie)
    return response