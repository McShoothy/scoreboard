"""
Blueprints package - register all Flask blueprints.
"""
from app.blueprints.main import main
from app.blueprints.auth import auth
from app.blueprints.admin import admin
from app.blueprints.api import api
from app.blueprints.display import display
from app.blueprints.input import input_bp
from app.blueprints.register import register
from app.blueprints.external_api import external_api


def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    # Main routes (index)
    app.register_blueprint(main)
    
    # Authentication (login, logout, TV pairing)
    app.register_blueprint(auth)
    
    # Admin panel
    app.register_blueprint(admin, url_prefix='/admin')
    
    # Internal API endpoints
    app.register_blueprint(api, url_prefix='/api')
    
    # External API (token-authenticated)
    app.register_blueprint(external_api, url_prefix='/ext/v1')
    
    # TV display
    app.register_blueprint(display, url_prefix='/display')
    
    # iPad input controller
    app.register_blueprint(input_bp, url_prefix='/input')
    
    # Team registration
    app.register_blueprint(register, url_prefix='/register')


def register_socket_events():
    """Import socket events to register handlers."""
    from app.blueprints import socket_events  # noqa: F401

