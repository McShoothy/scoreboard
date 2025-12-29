"""
API blueprint - REST API routes for matches, display, TV, and registration.
"""
from flask import Blueprint, request, jsonify, session, url_for
from datetime import datetime, timezone, timedelta
import logging

from app import db, socketio
from app.models import Match, Tournament, Team, DisplayState, TVSession
from app.utils import sanitize_text, generate_theme_css, THEMES
from app.utils import sanitize_text, generate_theme_css, THEMES
from app.blueprints.auth import login_required, api_login_required, admin_or_tv_required

logger = logging.getLogger(__name__)

api = Blueprint('api', __name__)


def get_or_create_display_state():
    """Get or create the singleton display state."""
    state = DisplayState.query.first()
    if not state:
        state = DisplayState(mode='waiting')
        db.session.add(state)
        db.session.commit()
    return state


# ==================== Match API ====================

@api.route('/match/<int:match_id>', methods=['GET'])
@admin_or_tv_required
def get_match(match_id):
    """Get match details."""
    match = db.get_or_404(Match, match_id)
    return jsonify(match.to_dict())


@api.route('/match/<int:match_id>/score', methods=['POST'])
@api_login_required
def update_score(match_id):
    """Update match score."""
    match = db.get_or_404(Match, match_id)
    data = request.get_json()
    
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
    
    return jsonify(match.to_dict())


@api.route('/match/<int:match_id>/swap-teams', methods=['POST'])
@api_login_required
def swap_teams(match_id):
    """Swap team 1 and team 2 (ids and scores)."""
    match = db.get_or_404(Match, match_id)
    
    # Swap IDs
    temp_id = match.team1_id
    match.team1_id = match.team2_id
    match.team2_id = temp_id
    
    # Swap scores
    temp_score = match.team1_score
    match.team1_score = match.team2_score
    match.team2_score = temp_score
    
    db.session.commit()
    
    # Emit update using the standard score_update event (or full match update)
    # Using 'match_swap' as a specific event might be clearer for clients
    socketio.emit('score_update', {
        'match_id': match_id,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score,
        'swap': True
    })
    
    return jsonify(match.to_dict())


@api.route('/match/<int:match_id>/complete', methods=['POST'])
@api_login_required
def complete_match(match_id):
    """Complete a match with a winner."""
    match = db.get_or_404(Match, match_id)
    data = request.get_json()
    
    winner_id = data.get('winner_id')
    match.winner_id = winner_id
    match.is_completed = True
    match.is_current = False
    
    # Advance winner to next match
    if match.next_match_id:
        next_match = db.session.get(Match, match.next_match_id, with_for_update=True)
        if next_match:
            if next_match.team1_id is None:
                next_match.team1_id = winner_id
            else:
                next_match.team2_id = winner_id
    
    # Set next incomplete match as current
    next_current = Match.query.filter_by(
        tournament_id=match.tournament_id,
        is_completed=False
    ).filter(Match.team1_id.isnot(None), Match.team2_id.isnot(None)).first()
    
    if next_current:
        next_current.is_current = True
    
    db.session.commit()
    
    # Update display state
    state = get_or_create_display_state()
    state.mode = 'waiting'
    db.session.commit()
    
    # Prepare response data
    next_match_data = None
    if next_current:
        team1 = db.session.get(Team, next_current.team1_id) if next_current.team1_id else None
        team2 = db.session.get(Team, next_current.team2_id) if next_current.team2_id else None
        next_match_data = {
            'match_id': next_current.id,
            'round': next_current.round_number,
            'team1': team1.to_dict() if team1 else None,
            'team2': team2.to_dict() if team2 else None
        }
    
    winner_team = db.session.get(Team, winner_id) if winner_id else None
    winner_data = winner_team.to_dict() if winner_team else None
    
    socketio.emit('match_complete', {
        'match_id': match_id,
        'winner_id': winner_id,
        'winner': winner_data,
        'next_match_id': match.next_match_id,
        'next_match': next_match_data
    })
    
    return jsonify(match.to_dict())


@api.route('/match/<int:match_id>/set-current', methods=['POST'])
@api_login_required
def set_current_match(match_id):
    """Set a match as the current match."""
    match = db.get_or_404(Match, match_id)
    
    Match.query.filter_by(tournament_id=match.tournament_id, is_current=True).update({'is_current': False})
    match.is_current = True
    db.session.commit()
    
    socketio.emit('current_match_changed', {'match_id': match_id})
    
    return jsonify(match.to_dict())


@api.route('/tournament/<int:tournament_id>/bracket')
@admin_or_tv_required
def get_bracket(tournament_id):
    """Get tournament bracket."""
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    return jsonify([m.to_dict() for m in matches])


@api.route('/tournament/<int:tournament_id>/next-match', methods=['GET'])
@admin_or_tv_required
def get_next_match(tournament_id):
    """Get the next upcoming match, prioritizing team continuity."""
    db.get_or_404(Tournament, tournament_id)
    
    # 1. Find all playable matches
    playable_matches = Match.query.filter(
        Match.tournament_id == tournament_id,
        Match.is_completed == False,
        Match.is_current == False,
        Match.team1_id.isnot(None),
        Match.team2_id.isnot(None)
    ).order_by(Match.round_number, Match.match_number).all()
    
    if not playable_matches:
        return jsonify({'next_match': None})
        
    # 2. Identify teams currently "on the field" (from last completed match)
    last_completed = Match.query.filter_by(
        tournament_id=tournament_id, 
        is_completed=True
    ).order_by(Match.id.desc()).first()
    
    teams_on_field = set()
    if last_completed:
        if last_completed.team1_id: teams_on_field.add(last_completed.team1_id)
        if last_completed.team2_id: teams_on_field.add(last_completed.team2_id)
    
    # 3. Sort matches: Priority to those containing a team on the field
    # We use python's sort which is stable. 
    # Primary key: 0 if has team on field, 1 if not (so continuity comes first)
    # Secondary key: round number (already sorted by query)
    # Tertiary key: match number (already sorted by query)
    
    def priority_sort_key(match):
        has_continuity = (match.team1_id in teams_on_field) or (match.team2_id in teams_on_field)
        return 0 if has_continuity else 1
        
    playable_matches.sort(key=priority_sort_key)
    
    next_match = playable_matches[0]
    
    return jsonify({
        'next_match': {
            'id': next_match.id,
            'round_number': next_match.round_number,
            'match_number': next_match.match_number,
            'team1': next_match.team1.to_dict() if next_match.team1 else None,
            'team2': next_match.team2.to_dict() if next_match.team2 else None,
            'is_continuity': (priority_sort_key(next_match) == 0)
        }
    })


@api.route('/tournament/<int:tournament_id>/stats', methods=['GET'])
@admin_or_tv_required
def get_tournament_stats(tournament_id):
    """Get tournament statistics."""
    db.get_or_404(Tournament, tournament_id)
    
    total_matches = Match.query.filter_by(tournament_id=tournament_id).count()
    completed_matches = Match.query.filter_by(tournament_id=tournament_id, is_completed=True).count()
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    
    return jsonify({
        'total': total_matches,
        'completed': completed_matches,
        'remaining': total_matches - completed_matches,
        'has_current_match': current_match is not None,
        'current_round': current_match.round_number if current_match else None
    })


@api.route('/tournament/<int:tournament_id>/timer', methods=['POST'])
def update_tournament_timer(tournament_id):
    """Update tournament timer duration."""
    tournament = db.get_or_404(Tournament, tournament_id)
    data = request.get_json()
    
    if 'timer_duration' in data:
        tournament.timer_duration = data['timer_duration']
        db.session.commit()
    
    return jsonify({'success': True, 'timer_duration': tournament.timer_duration})


@api.route('/tournament/<int:tournament_id>/teams', methods=['GET'])
@admin_or_tv_required
def api_get_tournament_teams(tournament_id):
    """Get all teams in a tournament."""
    tournament = db.get_or_404(Tournament, tournament_id)
    teams = Team.query.filter_by(tournament_id=tournament_id).order_by(Team.registered_at).all()
    
    return jsonify({
        'tournament': tournament.to_public_dict(),
        'teams': [t.to_dict() for t in teams]
    })


# ==================== Display API ====================

@api.route('/display/state', methods=['GET'])
def get_display_state():
    """Get current display state."""
    state = get_or_create_display_state()
    result = state.to_dict()
    
    if state.tournament_id:
        tournament = db.session.get(Tournament, state.tournament_id)
        if tournament:
            result['tournament'] = tournament.to_dict()
            current_match = Match.query.filter_by(tournament_id=state.tournament_id, is_current=True).first()
            if current_match:
                result['current_match'] = current_match.to_dict()
                
                if state.mode == 'waiting':
                    team1 = db.session.get(Team, current_match.team1_id) if current_match.team1_id else None
                    team2 = db.session.get(Team, current_match.team2_id) if current_match.team2_id else None
                    result['next_match'] = {
                        'match_id': current_match.id,
                        'round': current_match.round_number,
                        'team1': team1.to_dict() if team1 else None,
                        'team2': team2.to_dict() if team2 else None
                    }
                
                if state.mode == 'scoreboard':
                    next_upcoming = Match.query.filter(
                        Match.tournament_id == state.tournament_id,
                        Match.is_completed == False,
                        Match.is_current == False,
                        Match.team1_id.isnot(None),
                        Match.team2_id.isnot(None)
                    ).order_by(Match.round_number, Match.match_number).first()
                    
                    if next_upcoming:
                        result['next_match'] = {
                            'match_id': next_upcoming.id,
                            'round': next_upcoming.round_number,
                            'team1': next_upcoming.team1.to_dict() if next_upcoming.team1 else None,
                            'team2': next_upcoming.team2.to_dict() if next_upcoming.team2 else None,
                            'is_finals': next_upcoming.next_match_id is None
                        }
    
    if hasattr(state, 'winner_team_id') and state.winner_team_id:
        winner = db.session.get(Team, state.winner_team_id)
        if winner:
            result['winner_team'] = winner.to_dict()
    
    result['theme_css'] = generate_theme_css(result.get('theme', 'dark-orange'))
    
    return jsonify(result)


@api.route('/display/mode', methods=['POST'])
def set_display_mode():
    """Set display mode."""
    data = request.get_json()
    state = get_or_create_display_state()
    
    if 'mode' in data:
        state.mode = sanitize_text(data['mode'], max_length=50)
    if 'tournament_id' in data:
        state.tournament_id = data['tournament_id']
    if 'custom_message' in data:
        state.custom_message = sanitize_message(data['custom_message'])
    if 'winner_team_id' in data:
        state.winner_team_id = data['winner_team_id']
    if 'show_players' in data:
        state.show_players = data['show_players']
    if 'theme' in data:
        theme_id = data['theme']
        if theme_id in THEMES:
            state.theme = theme_id
    
    db.session.commit()
    
    socketio.emit('display_update', state.to_dict())
    
    return jsonify(state.to_dict())


@api.route('/display/theme', methods=['POST'])
@login_required
def set_display_theme():
    """Set display theme."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data received'}), 400
    
    theme_id = data.get('theme')
    
    if not theme_id:
        return jsonify({'error': 'No theme specified'}), 400
    
    if theme_id not in THEMES:
        return jsonify({'error': f'Invalid theme: {theme_id}', 'valid_themes': list(THEMES.keys())}), 400
    
    state = get_or_create_display_state()
    state.theme = theme_id
    db.session.commit()
    
    socketio.emit('theme_change', {
        'theme': theme_id,
        'theme_css': generate_theme_css(theme_id)
    })
    
    return jsonify({'success': True, 'theme': theme_id})


@api.route('/themes', methods=['GET'])
def get_themes():
    """Get all available themes."""
    themes_list = []
    for theme_id, theme_data in THEMES.items():
        themes_list.append({
            'id': theme_id,
            'name': theme_data['name'],
            'type': theme_data['type'],
            'primary': theme_data['primary']
        })
    return jsonify(themes_list)


# ==================== TV Session API ====================

@api.route('/tv/pair', methods=['POST'])
@login_required
def pair_tv_api():
    """Pair with a TV using its code."""
    data = request.get_json()
    code = data.get('code', '').upper()
    
    tv_session = TVSession.query.filter_by(code=code, is_active=True).first()
    if tv_session:
        tv_codes = session.get('tv_codes', [])
        if code not in tv_codes:
            tv_codes.append(code)
        session['tv_codes'] = tv_codes
        session['tv_code'] = code
        
        socketio.emit('controller_connected', {
            'code': tv_session.code,
            'admin': session.get('admin_username', 'Unknown')
        }, room=f'tv_{tv_session.code}')
        
        return jsonify({'success': True, 'tv_session': tv_session.to_dict()})
    return jsonify({'success': False, 'error': 'Invalid code'}), 404


@api.route('/tv/pair-all', methods=['POST'])
@login_required
def pair_all_tvs_api():
    """Pair with all active TVs."""
    tv_sessions = TVSession.query.filter_by(is_active=True).all()
    
    if not tv_sessions:
        return jsonify({'success': False, 'error': 'No active TVs found'}), 404
    
    paired_codes = []
    for tv_session in tv_sessions:
        paired_codes.append(tv_session.code)
        
        socketio.emit('controller_connected', {
            'code': tv_session.code,
            'admin': session.get('admin_username', 'Unknown'),
            'control_all': True
        }, room=f'tv_{tv_session.code}')
    
    session['tv_codes'] = paired_codes
    session['tv_code'] = paired_codes[0] if paired_codes else None
    session['control_all_tvs'] = True
    
    return jsonify({
        'success': True, 
        'count': len(paired_codes),
        'codes': paired_codes
    })


@api.route('/tv/unpair', methods=['POST'])
@login_required
def unpair_tv_api():
    """Unpair from all TVs."""
    old_codes = session.pop('tv_codes', [])
    old_code = session.pop('tv_code', None)
    session.pop('control_all_tvs', None)
    
    if old_code and old_code not in old_codes:
        old_codes.append(old_code)
    
    for code in old_codes:
        socketio.emit('controller_disconnected', {
            'code': code
        }, room=f'tv_{code}')
    
    return jsonify({'success': True})


@api.route('/tv/validate', methods=['POST'])
@login_required
def validate_tv_codes():
    """Validate TV codes."""
    data = request.get_json()
    codes = data.get('codes', [])
    
    if not codes:
        return jsonify({'active': [], 'inactive': []})
    
    stale_threshold = datetime.utcnow() - timedelta(minutes=2)
    
    active = []
    inactive = []
    
    for code in codes:
        tv = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
        if tv and tv.last_seen and tv.last_seen > stale_threshold:
            active.append(code)
        else:
            inactive.append(code)
    
    return jsonify({'active': active, 'inactive': inactive})


@api.route('/tv/sessions')
@login_required
def get_tv_sessions():
    """Get all active TV sessions."""
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    sessions = TVSession.query.filter(
        TVSession.is_active == True,
        TVSession.last_seen >= cutoff_time
    ).all()
    return jsonify([s.to_dict() for s in sessions])


@api.route('/tv/<code>/state', methods=['GET'])
def get_tv_state(code):
    """Get TV state."""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    if tv_session:
        tv_session.last_seen = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify(tv_session.to_dict())
    return jsonify({'error': 'Not found'}), 404


@api.route('/tv/<code>/heartbeat', methods=['POST'])
def tv_heartbeat(code):
    """TV heartbeat to stay active."""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    if tv_session:
        tv_session.last_seen = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'last_seen': tv_session.last_seen.isoformat()})
    return jsonify({'error': 'TV not found'}), 404


@api.route('/tv/<code>/control', methods=['POST'])
@login_required
def control_tv(code):
    """Send control commands to a TV."""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    if not tv_session:
        return jsonify({'error': 'TV not found'}), 404
    
    data = request.get_json()
    
    if 'mode' in data:
        tv_session.mode = sanitize_text(data['mode'], max_length=50)
    if 'custom_message' in data:
        tv_session.custom_message = sanitize_message(data['custom_message'])
    if 'winner_team_id' in data:
        tv_session.winner_team_id = data['winner_team_id']
    if 'tournament_id' in data:
        tv_session.tournament_id = data['tournament_id']
    
    db.session.commit()
    
    if data.get('redirect_to_live') and tv_session.tournament_id:
        live_url = url_for('display.display_live', tournament_id=tv_session.tournament_id)
        socketio.emit('redirect_to_live', {
            'code': tv_session.code,
            'url': live_url,
            'tournament_id': tv_session.tournament_id
        }, room=f'tv_{tv_session.code}')
    
    socketio.emit('tv_control', {
        'code': tv_session.code,
        'mode': tv_session.mode,
        'custom_message': tv_session.custom_message,
        'winner_team_id': tv_session.winner_team_id,
        'tournament_id': tv_session.tournament_id
    }, room=f'tv_{tv_session.code}')
    
    return jsonify({'success': True, 'tv_session': tv_session.to_dict()})


# ==================== Registration API ====================

@api.route('/register/validate-code', methods=['POST'])
def api_validate_code():
    """Validate a tournament registration code."""
    data = request.get_json()
    code = data.get('code', '').strip().upper()
    
    tournament = Tournament.query.filter_by(registration_code=code).first()
    if not tournament:
        return jsonify({'valid': False, 'error': 'Invalid tournament code'})
    
    can_register, message = tournament.can_register()
    
    return jsonify({
        'valid': True,
        'can_register': can_register,
        'message': message,
        'tournament': tournament.to_public_dict()
    })


@api.route('/register/team', methods=['POST'])
def api_register_team():
    """API endpoint to register a team."""
    data = request.get_json()
    
    code = data.get('code', '').strip().upper()
    team_name = data.get('team_name', '').strip()
    player1 = data.get('player1', '').strip()
    player2 = data.get('player2', '').strip()
    email = data.get('email', '').strip() or None
    phone = data.get('phone', '').strip() or None
    
    tournament = Tournament.query.filter_by(registration_code=code).first()
    if not tournament:
        return jsonify({'success': False, 'error': 'Invalid tournament code'}), 400
    
    can_register, message = tournament.can_register()
    if not can_register:
        return jsonify({'success': False, 'error': message}), 400
    
    if not team_name or len(team_name) > 20:
        return jsonify({'success': False, 'error': 'Team name is required (max 20 characters)'}), 400
    
    if not player1 or len(player1) > 30:
        return jsonify({'success': False, 'error': 'Player 1 name is required (max 30 characters)'}), 400
    
    if not player2 or len(player2) > 30:
        return jsonify({'success': False, 'error': 'Player 2 name is required (max 30 characters)'}), 400
    
    if tournament.require_email and not email:
        return jsonify({'success': False, 'error': 'Email is required for this tournament'}), 400
    
    existing = Team.query.filter_by(tournament_id=tournament.id, name=team_name).first()
    if existing:
        return jsonify({'success': False, 'error': 'A team with this name is already registered'}), 400
    
    team = Team(
        name=team_name,
        player1=player1,
        player2=player2,
        tournament_id=tournament.id,
        email=email,
        phone=phone,
        registration_ip=request.remote_addr,
        is_confirmed=not tournament.require_confirmation
    )
    
    db.session.add(team)
    db.session.commit()
    
    socketio.emit('team_registered', {
        'tournament_id': tournament.id,
        'team': team.to_dict()
    })
    
    return jsonify({
        'success': True,
        'team': team.to_dict(),
        'confirmed': team.is_confirmed,
        'message': 'Awaiting admin confirmation' if not team.is_confirmed else 'Successfully registered'
    })


# ==================== Test API ====================

@api.route('/test/generate-brackets', methods=['POST'])
@api_login_required
def test_generate_brackets():
    """Test bracket generation for all formats and team counts."""
    from app.blueprints.bracket import (
        create_single_elimination_bracket,
        create_double_elimination_bracket,
        create_round_robin,
        create_round_robin_playoffs,
        create_swiss_round
    )
    
    formats = {
        'single_elimination': create_single_elimination_bracket,
        'double_elimination': create_double_elimination_bracket,
        'round_robin': create_round_robin,
        'round_robin_playoffs': create_round_robin_playoffs,
        'swiss': create_swiss_round
    }
    
    team_counts = [2, 3, 4, 64]
    results = {}
    
    for fmt_name, fmt_func in formats.items():
        results[fmt_name] = {}
        
        for count in team_counts:
            # Create temp tournament
            t = Tournament(
                name=f'Test {fmt_name} {count}',
                format=fmt_name,
                owner_id=session.get('admin_id', 1)
            )
            db.session.add(t)
            db.session.commit()
            
            try:
                # Create teams
                team_ids = []
                for i in range(count):
                    team = Team(
                        name=f'T{i+1}', 
                        player1=f'P{i+1}a', 
                        player2=f'P{i+1}b', 
                        tournament_id=t.id
                    )
                    db.session.add(team)
                    db.session.commit()
                    team_ids.append(team.id)
                
                # Generate bracket
                fmt_func(t.id, team_ids)
                
                # Collect results
                matches = Match.query.filter_by(tournament_id=t.id).order_by(Match.round_number, Match.match_number).all()
                
                match_data = []
                for m in matches:
                    match_data.append({
                        'round': m.round_number,
                        'match_num': m.match_number,
                        'type': m.match_type,
                        'team1': m.team1.name if m.team1 else 'BYE/TBD',
                        'team2': m.team2.name if m.team2 else 'BYE/TBD',
                        'next_match_id': m.next_match_id
                    })
                
                results[fmt_name][count] = {
                    'match_count': len(matches),
                    'matches': match_data
                }
                
            except Exception as e:
                results[fmt_name][count] = {
                    'error': str(e)
                }
            finally:
                # Cleanup
                Match.query.filter_by(tournament_id=t.id).delete()
                Team.query.filter_by(tournament_id=t.id).delete()
                db.session.delete(t)
                db.session.commit()
                
    return jsonify(results)
