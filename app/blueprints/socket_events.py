"""
Socket.IO event handlers.
"""
from datetime import datetime
import logging

from flask_socketio import emit, join_room, leave_room

from app import db, socketio
from app.models import Match, TVSession
from app.blueprints.auth import socket_login_required

logger = logging.getLogger(__name__)


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')


@socketio.on('join_tv')
def handle_join_tv(data):
    """TV joins its own room for targeted updates."""
    code = data.get('code', '').upper()
    if code:
        join_room(f'tv_{code}')
        print(f'TV {code} joined room')
        tv_session = TVSession.query.filter_by(code=code, is_active=True).first()
        if tv_session:
            tv_session.last_seen = datetime.utcnow()
            db.session.commit()


@socketio.on('leave_tv')
def handle_leave_tv(data):
    """TV leaves its room."""
    code = data.get('code', '').upper()
    if code:
        leave_room(f'tv_{code}')
        logger.info(f'TV {code} left room')


@socketio.on('join_tournament')
def handle_join_tournament(data):
    """Join a tournament room."""
    room = f"tournament_{data['tournament_id']}"
    join_room(room)
    emit('joined', {'room': room})


@socketio.on('start_countdown')
@socket_login_required
def handle_start_countdown(data):
    """Broadcast countdown start to all connected displays."""
    socketio.emit('start_countdown', data)


@socketio.on('update_score')
@socket_login_required
def handle_score_update(data):
    """Handle score update from iPad."""
    match_id = data['match_id']
    match = db.session.get(Match, match_id)
    if match:
        if 'team1_score' in data:
            match.team1_score = data['team1_score']
        if 'team2_score' in data:
            match.team2_score = data['team2_score']
        db.session.commit()
        
        socketio.emit('score_update', {
            'match_id': match_id,
            'team1_score': match.team1_score,
            'team2_score': match.team2_score
        })


@socketio.on('winner_pending')
@socket_login_required
def handle_winner_pending(data):
    """Handle when match time ends and there's a pending winner to confirm."""
    socketio.emit('winner_pending', {
        'match_id': data['match_id'],
        'team1_score': data['team1_score'],
        'team2_score': data['team2_score'],
        'winner_id': data['winner_id'],
        'winner_name': data['winner_name'],
        'is_overtime': data.get('is_overtime', False)
    })


@socketio.on('tv_command')
@socket_login_required
def handle_tv_command(data):
    """Send a command to a specific TV by code."""
    tv_code = data.get('tv_code', '').upper()
    command = data.get('command', {})
    if tv_code:
        emit('display_update', command, to=f'tv_{tv_code}')
        logger.info(f'Sent command to TV {tv_code}: {command}')


@socketio.on('refresh_tv')
@socket_login_required
def handle_refresh_tv(data):
    """Send refresh command to a specific TV."""
    tv_code = data.get('tv_code', '').upper()
    if tv_code:
        emit('refresh_display', {}, to=f'tv_{tv_code}')
        logger.info(f'Refresh sent to TV {tv_code}')
