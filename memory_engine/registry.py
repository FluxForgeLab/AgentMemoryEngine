class AdapterRegistry:
    def __init__(self):
        self._items = {}

    def register(self, name, adapter, *, replace=False):
        if name in self._items and not replace:
            raise KeyError(f"adapter already registered: {name}")
        self._items[name] = adapter

    def get(self, name):
        if name not in self._items:
            raise KeyError(f"adapter not found: {name}")
        return self._items[name]
