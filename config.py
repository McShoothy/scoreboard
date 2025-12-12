import os
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))


def get_secret_key():
    """Get or generate a secure secret key"""
    # First check environment variable
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    
    # Check for a key file
    key_file = os.path.join(basedir, '.secret_key')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            return f.read().strip()
    
    # Generate a new key and save it
    key = secrets.token_hex(32)
    with open(key_file, 'w') as f:
        f.write(key)
    return key


class Config:
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'tournament.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
