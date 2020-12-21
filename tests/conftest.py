import pytest
import urllib3
import urllib
import urllib.request
import socket

# https://realpython.com/pytest-python-testing/
@pytest.fixture(autouse=True)
def disable_network_calls(monkeypatch):
    def stunted_get(*args, **kwargs):
        raise RuntimeError('Network access not allowed during testing!')
    monkeypatch.setattr(urllib.request, 'Request', stunted_get)
    monkeypatch.setattr(urllib3.PoolManager, 'request', stunted_get)
    monkeypatch.setattr(socket, 'socket', stunted_get)
