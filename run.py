import os
from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    socketio.run(app, debug=debug_mode, host='0.0.0.0', port=5000, 
                 allow_unsafe_werkzeug=debug_mode)

