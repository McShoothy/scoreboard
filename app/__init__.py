from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from config import Config

db = SQLAlchemy()
socketio = SocketIO()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    from app.routes import main, admin, input_bp, display, auth
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(input_bp, url_prefix='/input')
    app.register_blueprint(display, url_prefix='/display')

    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        from app.models import Admin
        if not Admin.query.first():
            default_admin = Admin(username='admin')
            default_admin.set_password('robotuprising')
            db.session.add(default_admin)
            db.session.commit()

    return app
