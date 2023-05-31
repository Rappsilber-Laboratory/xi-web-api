from flask import Blueprint

bp = Blueprint('pdbdev', __name__)

from xi_web_api.pdbdev import routes
