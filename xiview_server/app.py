from flask import Flask
from flask_cors import CORS
# from flask_compress import Compress
from flask import send_from_directory
# import logging.config

# logging.config.fileConfig('logging.ini')
# logger = logging.getLogger(__name__)

def create_app():
    """
    Create the flask app.

    :return: flask app
    """
    app = Flask(__name__, static_url_path="",
                static_folder='../static', template_folder='../templates')

    CORS(app)
    # Compress(app)

    from xi2annotator import bp as xi2_bp
    app.register_blueprint(xi2_bp)

    @app.route('/network.html', methods=['GET'])
    def network():
        """
        Serve the network.html file.

        :return: file
        """
        return app.send_static_file('network.html')

    @app.route('/docs/<path:filename>')
    def send_file(filename):
        # todo? - https://tedboy.github.io/flask/generated/flask.send_from_directory.html -
        # It is strongly recommended to activate either X - Sendfile support in your webserver or (if no authentication
        # happens) to tell the webserver to serve files for the given path on its own without calling into the web
        # application for improved performance.
        return send_from_directory('../static/xidocs/', filename)

    return app
