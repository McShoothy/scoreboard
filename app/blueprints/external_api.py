"""
External API blueprint - Token-authenticated API for external systems.
"""
from flask import Blueprint, request, jsonify
from functools import wraps
import logging

from app import db, socketio
from app.models import APIToken, Match, Tournament, Team, DisplayState

logger = logging.getLogger(__name__)

external_api = Blueprint('external_api', __name__)


# ==================== Authentication ====================

def require_token(scope=None):
    """Decorator to require a valid API token with optional scope check."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization', '')
            
            if not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Missing or invalid Authorization header',
                    'hint': 'Use: Authorization: Bearer <token>'
                }), 401
            
            raw_token = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Validate token
            token = APIToken.validate_token(raw_token)
            if not token:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # Check permission scope
            if scope and not token.has_permission(scope):
                return jsonify({
                    'error': f'Token lacks required permission: {scope}',
                    'your_permissions': token.get_permissions()
                }), 403
            
            # Add token to request context
            request.api_token = token
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_or_create_display_state():
    """Get or create the singleton display state."""
    state = DisplayState.query.first()
    if not state:
        state = DisplayState(mode='waiting')
        db.session.add(state)
        db.session.commit()
    return state


# ==================== Tournament Endpoints ====================

@external_api.route('/tournament/<int:tournament_id>', methods=['GET'])
@require_token('tournament:read')
def get_tournament(tournament_id):
    """Get tournament information."""
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    return jsonify({
        'tournament': tournament.to_dict(),
        'team_count': tournament.get_registered_team_count() if hasattr(tournament, 'get_registered_team_count') else 0
    })


@external_api.route('/tournament/<int:tournament_id>/current', methods=['GET'])
@require_token('match:read')
def get_current_match(tournament_id):
    """Get the current active match for a tournament."""
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    
    if not current_match:
        return jsonify({
            'current_match': None,
            'message': 'No active match'
        })
    
    return jsonify({
        'current_match': current_match.to_dict(),
        'team1': current_match.team1.to_dict() if current_match.team1 else None,
        'team2': current_match.team2.to_dict() if current_match.team2 else None
    })


@external_api.route('/tournament/<int:tournament_id>/teams', methods=['GET'])
@require_token('team:read')
def get_tournament_teams(tournament_id):
    """Get all teams in a tournament."""
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    
    return jsonify({
        'tournament_id': tournament_id,
        'teams': [t.to_dict() for t in teams]
    })


# ==================== Match Endpoints ====================

@external_api.route('/match/<int:match_id>', methods=['GET'])
@require_token('match:read')
def get_match(match_id):
    """Get match details."""
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    return jsonify({
        'match': match.to_dict(),
        'team1': match.team1.to_dict() if match.team1 else None,
        'team2': match.team2.to_dict() if match.team2 else None
    })


@external_api.route('/match/<int:match_id>/score', methods=['POST'])
@require_token('score:write')
def update_match_score(match_id):
    """
    Update match score.
    
    Body: {"team1_score": 5, "team2_score": 3}
    """
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    if match.is_completed:
        return jsonify({'error': 'Match is already completed'}), 400
    
    data = request.get_json() or {}
    
    if 'team1_score' in data:
        match.team1_score = int(data['team1_score'])
    if 'team2_score' in data:
        match.team2_score = int(data['team2_score'])
    
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('score_update', {
        'match_id': match_id,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score,
        'source': 'external_api'
    })
    
    logger.info(f"External API score update: match={match_id}, score={match.team1_score}-{match.team2_score}")
    
    return jsonify({
        'success': True,
        'match': match.to_dict()
    })


@external_api.route('/match/<int:match_id>/add-point', methods=['POST'])
@require_token('score:write')
def add_point(match_id):
    """
    Add a point to a team's score.
    
    Body: {"team": 1} or {"team": 2}
    """
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    if match.is_completed:
        return jsonify({'error': 'Match is already completed'}), 400
    
    data = request.get_json() or {}
    team = data.get('team')
    
    if team not in [1, 2]:
        return jsonify({'error': 'Invalid team, must be 1 or 2'}), 400
    
    if team == 1:
        match.team1_score += 1
    else:
        match.team2_score += 1
    
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('score_update', {
        'match_id': match_id,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score,
        'source': 'external_api'
    })
    
    logger.info(f"External API add-point: match={match_id}, team={team}, score={match.team1_score}-{match.team2_score}")
    
    return jsonify({
        'success': True,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score
    })


@external_api.route('/match/<int:match_id>/set-winner', methods=['POST'])
@require_token('match:write')
def set_winner_auto(match_id):
    """
    Automatically determine and set the winner based on current scores.
    
    Body: {} (empty) or {"force_team": 1} to force a specific winner
    """
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    if match.is_completed:
        return jsonify({'error': 'Match is already completed'}), 400
    
    data = request.get_json() or {}
    force_team = data.get('force_team')
    
    # Determine winner
    if force_team == 1:
        winner_id = match.team1_id
    elif force_team == 2:
        winner_id = match.team2_id
    elif match.team1_score > match.team2_score:
        winner_id = match.team1_id
    elif match.team2_score > match.team1_score:
        winner_id = match.team2_id
    else:
        return jsonify({
            'error': 'Scores are tied, cannot auto-determine winner',
            'hint': 'Use force_team to pick a winner'
        }), 400
    
    # Complete the match
    match.winner_id = winner_id
    match.is_completed = True
    match.is_current = False
    
    # Advance winner to next match
    if match.next_match_id:
        next_match = Match.query.with_for_update().get(match.next_match_id)
        if next_match:
            if next_match.team1_id is None:
                next_match.team1_id = winner_id
            else:
                next_match.team2_id = winner_id
    
    # Set next match as current
    next_current = Match.query.filter_by(
        tournament_id=match.tournament_id,
        is_completed=False
    ).filter(Match.team1_id.isnot(None), Match.team2_id.isnot(None)).first()
    
    if next_current:
        next_current.is_current = True
    
    db.session.commit()
    
    # Emit real-time update
    winner_team = Team.query.get(winner_id)
    socketio.emit('match_complete', {
        'match_id': match_id,
        'winner_id': winner_id,
        'winner': winner_team.to_dict() if winner_team else None,
        'source': 'external_api'
    })
    
    logger.info(f"External API set-winner: match={match_id}, winner={winner_id}")
    
    return jsonify({
        'success': True,
        'winner_id': winner_id,
        'winner_name': winner_team.name if winner_team else None,
        'match': match.to_dict()
    })


@external_api.route('/match/<int:match_id>/complete', methods=['POST'])
@require_token('match:write')
def complete_match(match_id):
    """
    Complete a match with a specific winner.
    
    Body: {"winner_id": 5}
    """
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    if match.is_completed:
        return jsonify({'error': 'Match is already completed'}), 400
    
    data = request.get_json() or {}
    winner_id = data.get('winner_id')
    
    if not winner_id:
        return jsonify({'error': 'winner_id is required'}), 400
    
    if winner_id not in [match.team1_id, match.team2_id]:
        return jsonify({'error': 'winner_id must be one of the teams in this match'}), 400
    
    # Complete the match
    match.winner_id = winner_id
    match.is_completed = True
    match.is_current = False
    
    # Advance winner
    if match.next_match_id:
        next_match = Match.query.with_for_update().get(match.next_match_id)
        if next_match:
            if next_match.team1_id is None:
                next_match.team1_id = winner_id
            else:
                next_match.team2_id = winner_id
    
    # Set next match as current
    next_current = Match.query.filter_by(
        tournament_id=match.tournament_id,
        is_completed=False
    ).filter(Match.team1_id.isnot(None), Match.team2_id.isnot(None)).first()
    
    if next_current:
        next_current.is_current = True
    
    db.session.commit()
    
    # Emit real-time update
    winner_team = Team.query.get(winner_id)
    socketio.emit('match_complete', {
        'match_id': match_id,
        'winner_id': winner_id,
        'winner': winner_team.to_dict() if winner_team else None,
        'source': 'external_api'
    })
    
    logger.info(f"External API complete: match={match_id}, winner={winner_id}")
    
    return jsonify({
        'success': True,
        'match': match.to_dict()
    })


# ==================== Display Control ====================

@external_api.route('/display/mode', methods=['POST'])
@require_token('display:write')
def set_display_mode(match_id=None):
    """
    Set TV display mode.
    
    Body: {"mode": "scoreboard", "tournament_id": 1}
    Modes: waiting, scoreboard, bracket, winner, message
    """
    data = request.get_json() or {}
    state = get_or_create_display_state()
    
    if 'mode' in data:
        state.mode = data['mode']
    if 'tournament_id' in data:
        state.tournament_id = data['tournament_id']
    if 'custom_message' in data:
        state.custom_message = data['custom_message']
    if 'winner_team_id' in data:
        state.winner_team_id = data['winner_team_id']
    
    db.session.commit()
    
    # Emit to all displays
    socketio.emit('display_update', state.to_dict())
    
    return jsonify({
        'success': True,
        'display_state': state.to_dict()
    })


# ==================== Timer Control ====================

@external_api.route('/countdown/start', methods=['POST'])
@require_token('timer:write')
def start_countdown():
    """
    Start the match countdown timer.
    
    Body: {"tournament_id": 1, "duration": 150} (duration in seconds)
    """
    data = request.get_json() or {}
    tournament_id = data.get('tournament_id')
    duration = data.get('duration')
    
    if not tournament_id:
        return jsonify({'error': 'tournament_id is required'}), 400
    
    # Get tournament for default duration
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    if not duration:
        duration = tournament.timer_duration
    
    # Emit countdown start
    socketio.emit('start_countdown', {
        'tournament_id': tournament_id,
        'timer_duration': duration,
        'source': 'external_api'
    })
    
    logger.info(f"External API countdown start: tournament={tournament_id}, duration={duration}")
    
    return jsonify({
        'success': True,
        'duration': duration
    })


# ==================== Health & Info ====================

@external_api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint (no auth required)."""
    return jsonify({
        'status': 'ok',
        'version': '1.0',
        'api': 'RobotUprising Scoreboard External API'
    })


@external_api.route('/scopes', methods=['GET'])
def list_scopes():
    """List available permission scopes (no auth required)."""
    return jsonify({
        'scopes': APIToken.SCOPES,
        'description': {
            'tournament:read': 'Read tournament information',
            'match:read': 'Read match information and scores',
            'match:write': 'Complete matches and set winners',
            'score:read': 'Read scores',
            'score:write': 'Update scores and add points',
            'display:write': 'Control TV display modes',
            'timer:write': 'Start and stop match timers',
            'team:read': 'Read team information'
        }
    })
