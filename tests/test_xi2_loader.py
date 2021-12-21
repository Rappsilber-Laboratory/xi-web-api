from xi2_xiview_loader import create_app
import pytest
from flask import url_for


@pytest.fixture
def app():
    app = create_app()
    return app


def test_general(client, config):
    url = url_for('get_data')
    # GET allowed
    assert client.get(url)._status_code == 200
    # check cors headers
    assert config['CORS_HEADERS'] == 'Content-Type'
