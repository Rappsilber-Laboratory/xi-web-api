from xi2_xiview_loader import create_app
import pytest
from flask import url_for
import os


@pytest.fixture
def app():
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    config = os.path.join(fixtures_dir, 'test_db.ini')
    app = create_app(config)
    return app


def test_no_uuid(client, config):
    """Test that the API returns a 400 if no uuid is provided"""
    url = url_for('get_data')
    assert client.get(url)._status_code == 400
    # check cors headers
    assert config['CORS_HEADERS'] == 'Content-Type'
