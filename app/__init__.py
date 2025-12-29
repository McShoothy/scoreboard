from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
socketio = SocketIO()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # CSRF protection
    app.config['WTF_CSRF_CHECK_DEFAULT'] = True
    
    db.init_app(app)
    
    # Determine async mode
    import sys
    async_mode = 'gevent' # Default for Production (Gunicorn + Gevent)
    
    # Fallback to threading (or eventlet if preferred) for local Flask run
    # 'werkzeug' in sys.modules check helps detect if we are running under dev server
    if 'werkzeug.serving' in sys.modules:
        async_mode = 'threading'

    socketio.init_app(app, cors_allowed_origins="*", async_mode=async_mode)
    csrf.init_app(app)

    # Register blueprints from the new modular structure
    from app.blueprints import register_blueprints, register_socket_events
    register_blueprints(app)
    register_socket_events()
    
    # Exempt API blueprints from CSRF protection
    from app.blueprints.api import api
    from app.blueprints.external_api import external_api
    from app.blueprints.input import input_bp
    
    csrf.exempt(api)
    csrf.exempt(external_api)
    csrf.exempt(input_bp)  # iPad input often uses AJAX/fetch without CSRF token
    
    # Error handlers
    from flask import render_template
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404


    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        # Password hash is pre-computed using werkzeug.security.generate_password_hash
        # NEVER store plaintext passwords in code
        from app.models import Admin
        if not Admin.query.first():
            default_admin = Admin(username='admin')
            # Pre-computed hash - password is NOT stored in plaintext
            default_admin.password_hash = 'scrypt:32768:8:1$D0zJEmIs28mRYCkq$26009d8dff433e1d903b8ee16f17e19429a3e8ce9eb1a7c6ecc77c4a854e0ea0b6bc4ea85b7b7420f22d23876b8781f21aeec8df7bad52562edf9f1296f8e9d4'
            db.session.add(default_admin)
            db.session.commit()

    return app


