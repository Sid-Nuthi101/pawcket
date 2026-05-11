# L5 session layer
from persistence import LocalPersistence
import json
import contextvars
from urllib.parse import quote, unquote

class Session(dict):
    def __init__(self, serialized_data=None):
        super().__init__()

        self.modified = False
        self.accessed = False
        self._load(serialized_data)

    def _load(self, serialized_data):
        if serialized_data is None or serialized_data.strip() == "":
            return
        try:
            loaded_data = json.loads(unquote(serialized_data))
            if isinstance(loaded_data, dict):
                for key, value in loaded_data.items():
                    super().__setitem__(key, value)
        except (json.JSONDecodeError, TypeError):
            # Invalid cookie payload should not break request handling.
            return

    def __getitem__(self, key):
        self.accessed = True
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        self.modified = True
        self.accessed = True
        super().__setitem__(key, value)

    def get(self, key, default=None):
        self.accessed = True
        return super().get(key, default)

    def pop(self, key, default=None):
        self.modified = True
        self.accessed = True
        return super().pop(key, default)

    def clear(self):
        self.modified = True
        self.accessed = True
        super().clear()

    def update(self, *args, **kwargs):
        self.modified = True
        self.accessed = True
        super().update(*args, **kwargs)
    
    def __str__(self):
        return str(dict(self))

    def as_cookie_value(self):
        return quote(json.dumps(dict(self), separators=(",", ":")))

# Current session context var (set in route_to_thread)
_current_session = contextvars.ContextVar("current_session")

# Proxy to retrieve current session
class PawprintProxy:
    def _get(self):
        return _current_session.get()

    def __getitem__(self, key):
        return self._get()[key]

    def __setitem__(self, key, value):
        self._get()[key] = value

    def get(self, key, default=None):
        return self._get().get(key, default)