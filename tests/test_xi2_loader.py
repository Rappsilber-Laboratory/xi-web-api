from xiview_server import create_app
import pytest
from flask import url_for
import os


@pytest.fixture
def app():
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    config = os.path.join(fixtures_dir, 'test_db.ini')
    os.environ["DB_CONFIG"] = config
    app = create_app()
    return app


# ToDo: write actual tests. Need to create a test database with some data to test against.
# def test_index(client, config):
#     url = url_for('index')
#     assert client.get(url)._status_code == 200
#
#
# def test_dataset(client, config):
#     url = url_for('dataset', pxid='PXD000001')
#     assert client.get(url)._status_code == 200
#
#
# def test_get_data(client, config):
#     url = url_for('get_data', id=1)
#     # GET allowed
#     assert client.get(url)._status_code == 200
#     # check cors headers
#     assert config['CORS_HEADERS'] == 'Content-Type'
#
#
# def test_get_peaklist(client, config):
#     url = url_for('get_peaklist', id=1)
#     assert client.get(url)._status_code == 200
