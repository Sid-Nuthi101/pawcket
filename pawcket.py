import os.path
import inspect
import subprocess
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from http_handler import HTTPRequest, HTTPResponse, HTTPCookie, make_response
from utils import random_string
from session import Session, PawprintProxy, _current_session
import traceback

# session obj pointed through context var
pawprint = PawprintProxy()

class ReloadHandler(FileSystemEventHandler):
  def __init__(self):
    pass

  def on_any_event(self, event):
      if "__pycache__" in event.src_path:
            return
      os.environ["YARN_CHILD_KILL_FLAG"] = "1"

class yarn:
    def __init__(self, devmode = False):
        self.threads = {}
        self.devmode = devmode
        self.__base_dir__ = os.path.dirname(inspect.stack()[1].filename)

    def thread(self, path):
        def decorator(func):
            self.threads[path] = func
            return func
        return decorator
    
    def roll(self):
        if os.environ.get("YARN_CHILD", "0") == "0":
            if self.devmode:
                observer = Observer()
                event_handler = ReloadHandler()
                observer.schedule(event_handler, self.__base_dir__, recursive=True)
                observer.start()
                print("Sentry Watching directory: " + self.__base_dir__)
            while True:
                print("Starting subprocess...")
                subprocess = self.roll_start_tcp()
                while True:
                    if os.environ.get("YARN_CHILD_KILL_FLAG", "0") == "1":
                        print("Change detected - restarting server")
                        subprocess.kill()
                        os.environ["YARN_CHILD_KILL_FLAG"] = "0"
                        subprocess = self.roll_start_tcp()
                    continue
            return
        from tcp_server import start_tcp_server
        start_tcp_server(self)

    def roll_start_tcp(self):
        env = os.environ.copy()
        env["YARN_CHILD"] = "1"
        return subprocess.Popen([sys.executable, sys.argv[0]], env=env)

    def route_to_thread(self, request:HTTPRequest):
        path = request.path
        method = request.method
        cookies = request.cookies
        response_cookies = []

        # Keep auth cookie for backwards compatibility/user tracking.
        auth_cookie = cookies.get("auth")
        if auth_cookie is None:
            new_auth_cookie = HTTPCookie("auth", random_string(32))
            response_cookies.append(new_auth_cookie)
            print("Cookie not found - Setting new cookie: " + str(new_auth_cookie))

        # Session data now lives directly in a dedicated cookie payload.
        session = Session(cookies.get("pawcket_session"))
        _current_session.set(session)

        def finalize_response(body, status_code=200, reason_phrase="OK"):
            headers = {
                "X-Pawcket-Session-Accessed": str(session.accessed).lower(),
                "X-Pawcket-Session-Modified": str(session.modified).lower(),
            }
            if session.modified:
                session_cookie = HTTPCookie(
                    "pawcket_session",
                    session.as_cookie_value(),
                    http_only=True
                )
                response_cookies.append(session_cookie)
                headers["X-Pawcket-Session-Data"] = session.as_cookie_value()
            return make_response(
                body,
                status_code,
                reason_phrase,
                cookies=response_cookies,
                headers=headers
            )

        if path == None or path.strip() == "":
            print(f"Routing: Thread path not provided")
            return finalize_response("Kitty is lost. No thread path provided.", 500, "NOT FOUND")
        
        # Get function
        func = self.threads.get(path,None)
        if func == None:
            if not path.split("/")[-1].endswith(".html"):
                print(f"Routing: Loaded '{path}' from catacomb")
                return finalize_response(self.spin_yarn(path), 200)
            print(f"No thread registered for route {path}")
            return finalize_response("Curiosity killed the cat - and this webpage.", 404, "NOT FOUND")

        # Handle different methods
        if method == "GET":
            try:
                result = self.threads[path]() # run function
            except Exception:
                # Route error page - TODO make this better.
                return finalize_response(str(traceback.format_exc()), 500, "INTERNAL_SERVER_ERROR")
            if isinstance(result, tuple):
                # get status code from function if provided
                body, status_code = result
            else:
                # normally status code not provided
                body = result
                status_code = 200
            print(f"Routing: Routed '{path}' to function '{self.threads[path].__name__}'")
            return finalize_response(body, status_code)
        else:
            raise NotImplementedError()
    
    def spin_yarn(self, html_file):
        filename = self.__base_dir__+"/catacomb/"+html_file
        if os.path.isfile(filename):
            f = open(filename, "r")
            content = f.read()
            return content
        else:
            return "spin_yarn called with invalid filename: " +filename