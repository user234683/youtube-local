from youtube import util
import settings
import pytest # overview: https://realpython.com/pytest-python-testing/
import urllib3
import io
import os
import stem


def load_test_page(name):
    with open(os.path.join('./tests/test_responses', name), 'rb') as f:
        return f.read()


html429 = load_test_page('429.html')


class MockResponse(urllib3.response.HTTPResponse):
    def __init__(self, body='success', headers=None, status=200, reason=''):
        print(body[0:10])
        headers = headers or {}
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.body_io = io.BytesIO(body)
        self.read = self.body_io.read
        urllib3.response.HTTPResponse.__init__(
            self, body=body, headers=headers, status=status,
            preload_content=False, decode_content=False, reason=reason
        )


class NewIdentityState():
    MAX_TRIES = util.TorManager.MAX_TRIES
    def __init__(self, new_identities_till_success):
        self.new_identities_till_success = new_identities_till_success

    def new_identity(self, *args, **kwargs):
        print('newidentity')
        self.new_identities_till_success -= 1

    def fetch_url_response(self, *args, **kwargs):
        cleanup_func = (lambda r: None)
        if self.new_identities_till_success == 0:
            return MockResponse(), cleanup_func
        return MockResponse(body=html429, status=429), cleanup_func


class MockController():
    def authenticate(self, *args, **kwargs):
        pass
    @classmethod
    def from_port(cls, *args, **kwargs):
        return cls()
    def __enter__(self, *args, **kwargs):
        return self
    def __exit__(self, *args, **kwargs):
        pass


@pytest.mark.parametrize('new_identities_till_success',
                          [i for i in range(0, NewIdentityState.MAX_TRIES+2)])
def test_exit_node_retry(monkeypatch, new_identities_till_success):
    new_identity_state = NewIdentityState(new_identities_till_success)
    # https://docs.pytest.org/en/stable/monkeypatch.html
    monkeypatch.setattr(settings, 'route_tor', 1)
    monkeypatch.setattr(util, 'tor_manager', util.TorManager()) # fresh one
    MockController.signal = new_identity_state.new_identity
    monkeypatch.setattr(stem.control, 'Controller', MockController)
    monkeypatch.setattr(util, 'fetch_url_response',
                        new_identity_state.fetch_url_response)
    if new_identities_till_success <= NewIdentityState.MAX_TRIES:
        assert util.fetch_url('url') == b'success'
    else:
        with pytest.raises(util.FetchError) as excinfo:
            util.fetch_url('url')
        assert int(excinfo.value.code) == 429
