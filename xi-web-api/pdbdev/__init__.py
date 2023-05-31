from flask import Blueprint

bp = Blueprint('pdbdev', __name__)

from xi2_xiview_loader.pdbdev import routes
