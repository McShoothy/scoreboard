"""
Authentication blueprint - handles login, logout, TV pairing, and auth decorators.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from urllib.parse import urlparse
import logging

from app import db, socketio
from app.models import Admin, TVSession

logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)


# ==================== Auth Decorators ====================

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_current_admin():
    """Get the currently logged-in admin user."""
    if 'admin_id' in session:
        return Admin.query.get(session['admin_id'])
    return None


def api_login_required(f):
    """Decorator for API endpoints that return JSON error instead of redirect."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def socket_login_required(f):
    """Decorator for Socket.IO events that require authentication."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'admin_id' not in session:
            logger.warning(f"Unauthorized Socket.IO event attempt: {f.__name__}")
            return  # Silently ignore unauthorized socket events
        return f(*args, **kwargs)
    return wrapped


def admin_or_tv_required(f):
    """Decorator to require either Admin login OR a valid TV session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_admin = 'admin_id' in session
        
        # Check for valid TV session
        tv_session_id = session.get('tv_session_id')
        is_tv = False
        if tv_session_id:
            from app.models import TVSession
            tv = TVSession.query.get(tv_session_id)
            if tv and tv.is_active:
                is_tv = True
        
        if not is_admin and not is_tv:
            return jsonify({'error': 'Unauthorized: Admin or TV Session required'}), 401
            
        return f(*args, **kwargs)
    return decorated_function


# ==================== Auth Routes ====================

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = Admin.query.filter_by(username=username, is_active=True).first()
        if admin_user and admin_user.check_password(password):
            session['admin_id'] = admin_user.id
            session['admin_username'] = admin_user.username
            next_page = request.args.get('next')
            if next_page:
                # Validate redirect URL to prevent open redirect attacks
                parsed = urlparse(next_page)
                # Only allow relative URLs or same-host URLs
                if not parsed.netloc or parsed.netloc == urlparse(request.url).netloc:
                    return redirect(next_page)
            return redirect(url_for('admin.admin_index'))
        flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')


@auth.route('/logout')
def logout():
    """Handle user logout."""
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('tv_code', None)
    return redirect(url_for('main.index'))


@auth.route('/pair/<code>')
@login_required
def pair_tv(code):
    """Pair with a TV using its code."""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    logger.info(f"Pairing attempt for code: {code.upper()}, found session: {tv_session}")
    if tv_session:
        session['tv_code'] = tv_session.code
        
        # Notify the TV that a controller has connected
        logger.info(f"Emitting controller_connected to room: tv_{tv_session.code}")
        socketio.emit('controller_connected', {
            'code': tv_session.code,
            'admin': session.get('admin_username', 'Unknown')
        }, room=f'tv_{tv_session.code}')
        
        # Redirect to iPad control for this TV's tournament
        if tv_session.tournament_id:
            return redirect(url_for('input.input_ipad', tournament_id=tv_session.tournament_id))
        return redirect(url_for('input.input_index'))
    flash('Invalid TV code', 'error')
    return redirect(url_for('input.input_index'))
