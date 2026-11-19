"""In-memory Tasks resources for selected-write/reconciliation behavior tests."""
from copy import deepcopy
from types import SimpleNamespace


class HttpFailure(Exception):
    def __init__(self, status):
        self.resp = SimpleNamespace(status=status)
        super().__init__("provider-canary-private-response")


class Request:
    def __init__(self, action):
        self.action = action

    def execute(self, num_retries=0):
        if num_retries:
            raise AssertionError("Non-idempotent client retries are not permitted")
        return self.action()


class FakeTasksService:
    def __init__(self):
        self.remote = []
        self.insert_attempts = 0
        self.failures = {}
        self.timeout_after_create = set()
        self.choices = [{"id": "other-list", "title": "Other"}, {"id": "chosen-list", "title": "Chosen"}]
        self.list_reads = 0

    def tasklists(self):
        outer = self
        class Lists:
            def list(self, **kwargs):
                offset = int(kwargs.get("pageToken", "0"))
                page = {"items": deepcopy(outer.choices[offset:offset + 1])}
                if offset + 1 < len(outer.choices):
                    page["nextPageToken"] = str(offset + 1)
                return Request(lambda: page)
        return Lists()

    def tasks(self):
        outer = self
        class Tasks:
            def insert(self, *, tasklist, body, **kwargs):
                def create():
                    outer.insert_attempts += 1
                    attempt = outer.insert_attempts
                    if attempt in outer.failures:
                        raise outer.failures[attempt]
                    task = {**deepcopy(body), "id": f"real-fake-{len(outer.remote) + 1}", "tasklist": tasklist}
                    outer.remote.append(task)
                    if attempt in outer.timeout_after_create:
                        raise TimeoutError("provider-canary-private-response")
                    return deepcopy(task)
                return Request(create)

            def list(self, *, tasklist, **kwargs):
                def read():
                    outer.list_reads += 1
                    items = [deepcopy(item) for item in outer.remote if item["tasklist"] == tasklist and (not item.get("hidden") or kwargs.get("showHidden")) and (item.get("status") != "completed" or kwargs.get("showCompleted"))]
                    offset = int(kwargs.get("pageToken", "0"))
                    page = {"items": items[offset:offset + 1]}
                    if offset + 1 < len(items):
                        page["nextPageToken"] = str(offset + 1)
                    return page
                return Request(read)
        return Tasks()
