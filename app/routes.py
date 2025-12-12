from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from flask_socketio import emit, join_room, leave_room
from functools import wraps
from app import db, socketio
from app.models import Team, Tournament, Match, DisplayState, Admin, TVSession
from app.utils import (
    sanitize_team_name, sanitize_player_name, sanitize_message,
    sanitize_text, get_theme, get_all_themes, generate_theme_css, THEMES
)
from datetime import datetime
import math
import qrcode
import io
import base64

main = Blueprint('main', __name__)
auth = Blueprint('auth', __name__)
admin = Blueprint('admin', __name__)
input_bp = Blueprint('input', __name__)
display = Blueprint('display', __name__)


# ==================== Authentication ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_current_admin():
    if 'admin_id' in session:
        return Admin.query.get(session['admin_id'])
    return None


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = Admin.query.filter_by(username=username, is_active=True).first()
        if admin_user and admin_user.check_password(password):
            session['admin_id'] = admin_user.id
            session['admin_username'] = admin_user.username
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('admin.admin_index'))
        flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')


@auth.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('tv_code', None)
    return redirect(url_for('main.index'))


@auth.route('/pair/<code>')
@login_required
def pair_tv(code):
    """Pair with a TV using its code"""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    print(f"Pairing attempt for code: {code.upper()}, found session: {tv_session}")
    if tv_session:
        session['tv_code'] = tv_session.code
        
        # Notify the TV that a controller has connected
        print(f"Emitting controller_connected to room: tv_{tv_session.code}")
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


# ==================== Main Routes ====================
@main.route('/')
def index():
    return render_template('index.html')


# ==================== Admin Routes ====================
@admin.route('/')
@login_required
def admin_index():
    teams = Team.query.all()
    tournaments = Tournament.query.all()
    return render_template('admin/index.html', teams=teams, tournaments=tournaments)


@admin.route('/teams', methods=['GET', 'POST'])
@login_required
def manage_teams():
    if request.method == 'POST':
        # Sanitize all input to prevent XSS
        name = sanitize_team_name(request.form.get('name'))
        player1 = sanitize_player_name(request.form.get('player1'))
        player2 = sanitize_player_name(request.form.get('player2'))
        
        if not name or not player1 or not player2:
            flash('All fields are required', 'error')
            return redirect(url_for('admin.manage_teams'))
        
        # Check for unique team name (case-insensitive)
        existing_team = Team.query.filter(db.func.lower(Team.name) == name.lower()).first()
        if existing_team:
            flash(f'Team name "{name}" already exists. Please choose a unique name.', 'error')
            return redirect(url_for('admin.manage_teams'))
        
        team = Team(name=name, player1=player1, player2=player2)
        db.session.add(team)
        db.session.commit()
        return redirect(url_for('admin.manage_teams'))
    
    teams = Team.query.all()
    return render_template('admin/teams.html', teams=teams)


@admin.route('/teams/<int:team_id>/delete', methods=['POST'])
@login_required
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    return redirect(url_for('admin.manage_teams'))


@admin.route('/tournaments', methods=['GET', 'POST'])
@login_required
def manage_tournaments():
    if request.method == 'POST':
        # Sanitize tournament name
        name = sanitize_text(request.form.get('name'), max_length=100)
        if not name:
            flash('Tournament name is required', 'error')
            return redirect(url_for('admin.manage_tournaments'))
            
        team_ids = request.form.getlist('teams')
        timer_minutes = int(request.form.get('timer_minutes', 2))
        timer_seconds = int(request.form.get('timer_seconds', 30))
        timer_duration = timer_minutes * 60 + timer_seconds
        format_type = request.form.get('format', 'single_elimination')
        
        tournament = Tournament(name=name, timer_duration=timer_duration, format=format_type)
        db.session.add(tournament)
        db.session.commit()
        
        # Create bracket based on format
        if format_type == 'single_elimination':
            create_single_elimination_bracket(tournament.id, team_ids)
        elif format_type == 'double_elimination':
            create_double_elimination_bracket(tournament.id, team_ids)
        elif format_type == 'round_robin':
            create_round_robin(tournament.id, team_ids)
        elif format_type == 'round_robin_playoffs':
            create_round_robin_playoffs(tournament.id, team_ids)
        elif format_type == 'swiss':
            create_swiss_round(tournament.id, team_ids, round_num=1)
        else:
            create_single_elimination_bracket(tournament.id, team_ids)
        
        return redirect(url_for('admin.view_tournament', tournament_id=tournament.id))
    
    teams = Team.query.all()
    tournaments = Tournament.query.all()
    return render_template('admin/tournaments.html', teams=teams, tournaments=tournaments)


@admin.route('/tournaments/<int:tournament_id>')
@login_required
def view_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    
    # Calculate standings for round robin formats
    standings = []
    if tournament.format in ['round_robin', 'round_robin_playoffs', 'swiss']:
        standings = calculate_standings(tournament_id)
    
    return render_template('admin/tournament_view.html', tournament=tournament, matches=matches, standings=standings)


def calculate_standings(tournament_id):
    """Calculate team standings based on completed matches"""
    matches = Match.query.filter_by(tournament_id=tournament_id, is_completed=True).all()
    
    team_stats = {}  # team_id -> {wins, losses, points_for, points_against, matches_played}
    
    for match in matches:
        if match.team1_id:
            if match.team1_id not in team_stats:
                team_stats[match.team1_id] = {'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0, 'matches_played': 0, 'team': match.team1}
            team_stats[match.team1_id]['points_for'] += match.team1_score
            team_stats[match.team1_id]['points_against'] += match.team2_score if match.team2_id else 0
            team_stats[match.team1_id]['matches_played'] += 1
            if match.winner_id == match.team1_id:
                team_stats[match.team1_id]['wins'] += 1
            elif match.winner_id:
                team_stats[match.team1_id]['losses'] += 1
        
        if match.team2_id:
            if match.team2_id not in team_stats:
                team_stats[match.team2_id] = {'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0, 'matches_played': 0, 'team': match.team2}
            team_stats[match.team2_id]['points_for'] += match.team2_score
            team_stats[match.team2_id]['points_against'] += match.team1_score
            team_stats[match.team2_id]['matches_played'] += 1
            if match.winner_id == match.team2_id:
                team_stats[match.team2_id]['wins'] += 1
            elif match.winner_id:
                team_stats[match.team2_id]['losses'] += 1
    
    # Convert to list and sort by wins, then point differential
    standings = []
    for team_id, stats in team_stats.items():
        stats['team_id'] = team_id
        stats['point_diff'] = stats['points_for'] - stats['points_against']
        standings.append(stats)
    
    standings.sort(key=lambda x: (x['wins'], x['point_diff'], x['points_for']), reverse=True)
    
    # Add ranking
    for i, entry in enumerate(standings):
        entry['rank'] = i + 1
    
    return standings


@admin.route('/tournaments/<int:tournament_id>/delete', methods=['POST'])
@login_required
def delete_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    Match.query.filter_by(tournament_id=tournament_id).delete()
    db.session.delete(tournament)
    db.session.commit()
    return redirect(url_for('admin.manage_tournaments'))


@admin.route('/tournaments/<int:tournament_id>/advance-to-playoffs', methods=['POST'])
@login_required
def advance_to_playoffs(tournament_id):
    """Advance top 4 teams from group stage to playoffs"""
    tournament = Tournament.query.get_or_404(tournament_id)
    
    if tournament.format != 'round_robin_playoffs':
        return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))
    
    standings = calculate_standings(tournament_id)
    
    if len(standings) < 4:
        return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))
    
    # Get playoff matches (semifinals)
    semifinals = Match.query.filter_by(tournament_id=tournament_id, round_number=100).order_by(Match.match_number).all()
    
    if len(semifinals) >= 2:
        # Semi 1: 1st vs 4th
        semifinals[0].team1_id = standings[0]['team_id']
        semifinals[0].team2_id = standings[3]['team_id']
        
        # Semi 2: 2nd vs 3rd
        semifinals[1].team1_id = standings[1]['team_id']
        semifinals[1].team2_id = standings[2]['team_id']
        
        # Update tournament phase
        tournament.current_phase = 'playoffs'
        
        # Set first semifinal as current
        semifinals[0].is_current = True
        
        db.session.commit()
    
    return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))


# ==================== Admin User Management ====================
@admin.route('/users')
@login_required
def manage_users():
    admins = Admin.query.all()
    return render_template('admin/users.html', admins=admins)


@admin.route('/users/add', methods=['POST'])
@login_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if Admin.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
        return redirect(url_for('admin.manage_users'))
    
    new_admin = Admin(username=username)
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    flash(f'Admin {username} created', 'success')
    return redirect(url_for('admin.manage_users'))


@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == session.get('admin_id'):
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('admin.manage_users'))
    
    admin_user = Admin.query.get_or_404(user_id)
    db.session.delete(admin_user)
    db.session.commit()
    flash(f'Admin {admin_user.username} deleted', 'success')
    return redirect(url_for('admin.manage_users'))


@admin.route('/users/<int:user_id>/change-password', methods=['POST'])
@login_required
def change_user_password(user_id):
    admin_user = Admin.query.get_or_404(user_id)
    new_password = request.form.get('password')
    admin_user.set_password(new_password)
    db.session.commit()
    flash(f'Password changed for {admin_user.username}', 'success')
    return redirect(url_for('admin.manage_users'))


# ==================== TV Session API ====================
@main.route('/api/tv/pair', methods=['POST'])
@login_required
def pair_tv_api():
    """Pair with a TV using its code"""
    data = request.get_json()
    code = data.get('code', '').upper()
    
    tv_session = TVSession.query.filter_by(code=code, is_active=True).first()
    if tv_session:
        # Store as list of TV codes
        tv_codes = session.get('tv_codes', [])
        if code not in tv_codes:
            tv_codes.append(code)
        session['tv_codes'] = tv_codes
        session['tv_code'] = code  # Keep for backward compatibility
        
        # Notify the TV that a controller has connected
        socketio.emit('controller_connected', {
            'code': tv_session.code,
            'admin': session.get('admin_username', 'Unknown')
        }, room=f'tv_{tv_session.code}')
        
        return jsonify({'success': True, 'tv_session': tv_session.to_dict()})
    return jsonify({'success': False, 'error': 'Invalid code'}), 404


@main.route('/api/tv/pair-all', methods=['POST'])
@login_required
def pair_all_tvs_api():
    """Pair with ALL active TV sessions"""
    tv_sessions = TVSession.query.filter_by(is_active=True).all()
    
    if not tv_sessions:
        return jsonify({'success': False, 'error': 'No active TVs found'}), 404
    
    paired_codes = []
    for tv_session in tv_sessions:
        paired_codes.append(tv_session.code)
        
        # Notify each TV that a controller has connected
        socketio.emit('controller_connected', {
            'code': tv_session.code,
            'admin': session.get('admin_username', 'Unknown'),
            'control_all': True
        }, room=f'tv_{tv_session.code}')
    
    # Store all codes in session
    session['tv_codes'] = paired_codes
    session['tv_code'] = paired_codes[0] if paired_codes else None  # Backward compat
    session['control_all_tvs'] = True
    
    return jsonify({
        'success': True, 
        'count': len(paired_codes),
        'codes': paired_codes
    })


@main.route('/api/tv/unpair', methods=['POST'])
@login_required
def unpair_tv_api():
    """Unpair from current TV(s)"""
    old_codes = session.pop('tv_codes', [])
    old_code = session.pop('tv_code', None)
    session.pop('control_all_tvs', None)
    
    # Add single code if not in list
    if old_code and old_code not in old_codes:
        old_codes.append(old_code)
    
    # Notify all TVs that controller disconnected
    for code in old_codes:
        socketio.emit('controller_disconnected', {
            'code': code
        }, room=f'tv_{code}')
    
    return jsonify({'success': True})


@main.route('/api/tv/validate', methods=['POST'])
@login_required
def validate_tv_codes():
    """Validate multiple TV codes and return which are still active"""
    data = request.get_json()
    codes = data.get('codes', [])
    
    if not codes:
        return jsonify({'active': [], 'inactive': []})
    
    # Check each code - consider a TV stale if not seen in last 2 minutes
    from datetime import timedelta
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


@main.route('/api/tv/sessions')
@login_required
def get_tv_sessions():
    """Get all active TV sessions"""
    sessions = TVSession.query.filter_by(is_active=True).all()
    return jsonify([s.to_dict() for s in sessions])


@main.route('/api/tv/<code>/state', methods=['GET'])
def get_tv_state(code):
    """Get current state of a TV session"""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    if tv_session:
        tv_session.last_seen = datetime.utcnow()
        db.session.commit()
        return jsonify(tv_session.to_dict())
    return jsonify({'error': 'Not found'}), 404


@main.route('/api/tv/<code>/heartbeat', methods=['POST'])
def tv_heartbeat(code):
    """Update TV session last_seen timestamp - keeps TV marked as active"""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    if tv_session:
        tv_session.last_seen = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'last_seen': tv_session.last_seen.isoformat()})
    return jsonify({'error': 'TV not found'}), 404


@main.route('/api/tv/<code>/control', methods=['POST'])
@login_required
def control_tv(code):
    """Send control commands to a TV"""
    tv_session = TVSession.query.filter_by(code=code.upper(), is_active=True).first()
    if not tv_session:
        return jsonify({'error': 'TV not found'}), 404
    
    data = request.get_json()
    
    # Update TV session state with sanitization
    if 'mode' in data:
        tv_session.mode = sanitize_text(data['mode'], max_length=50)
    if 'custom_message' in data:
        tv_session.custom_message = sanitize_message(data['custom_message'])
    if 'winner_team_id' in data:
        tv_session.winner_team_id = data['winner_team_id']
    if 'tournament_id' in data:
        tv_session.tournament_id = data['tournament_id']
    
    db.session.commit()
    
    # If redirect_to_live is set, tell the TV to go to the live display
    if data.get('redirect_to_live') and tv_session.tournament_id:
        live_url = url_for('display.display_live', tournament_id=tv_session.tournament_id)
        socketio.emit('redirect_to_live', {
            'code': tv_session.code,
            'url': live_url,
            'tournament_id': tv_session.tournament_id
        }, room=f'tv_{tv_session.code}')
    
    # Emit to the specific TV
    socketio.emit('tv_control', {
        'code': tv_session.code,
        'mode': tv_session.mode,
        'custom_message': tv_session.custom_message,
        'winner_team_id': tv_session.winner_team_id,
        'tournament_id': tv_session.tournament_id
    }, room=f'tv_{tv_session.code}')
    
    return jsonify({'success': True, 'tv_session': tv_session.to_dict()})


def create_single_elimination_bracket(tournament_id, team_ids):
    """Create elimination bracket for the tournament with bye support for uneven teams"""
    import random
    
    num_teams = len(team_ids)
    if num_teams < 2:
        return
    
    # Shuffle teams for random seeding
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Calculate number of rounds needed
    num_rounds = math.ceil(math.log2(num_teams))
    total_slots = 2 ** num_rounds
    
    # Calculate byes needed (teams that get a free pass to round 2)
    num_byes = total_slots - num_teams
    
    # Create all matches
    matches = []
    
    for round_num in range(1, num_rounds + 1):
        matches_in_round = total_slots // (2 ** round_num)
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                tournament_id=tournament_id,
                round_number=round_num,
                match_number=match_num
            )
            db.session.add(match)
            matches.append(match)
    
    db.session.commit()
    
    # Link matches to next round first
    for round_num in range(1, num_rounds):
        current_round = [m for m in matches if m.round_number == round_num]
        next_round = [m for m in matches if m.round_number == round_num + 1]
        
        for i, match in enumerate(current_round):
            next_match_idx = i // 2
            if next_match_idx < len(next_round):
                match.next_match_id = next_round[next_match_idx].id
    
    db.session.commit()
    
    # Get first and second round matches
    first_round_matches = [m for m in matches if m.round_number == 1]
    second_round_matches = [m for m in matches if m.round_number == 2] if num_rounds > 1 else []
    
    # Assign teams with byes going directly to round 2
    team_index = 0
    bye_teams = []  # Teams that get byes
    playing_teams = []  # Teams that play in round 1
    
    # First, determine which teams get byes (first num_byes teams after shuffle)
    for i in range(num_teams):
        if i < num_byes:
            bye_teams.append(team_ids[i])
        else:
            playing_teams.append(team_ids[i])
    
    # Assign playing teams to first round matches
    for i, team_id in enumerate(playing_teams):
        match_idx = i // 2
        if match_idx < len(first_round_matches):
            if i % 2 == 0:
                first_round_matches[match_idx].team1_id = int(team_id)
            else:
                first_round_matches[match_idx].team2_id = int(team_id)
    
    # Assign bye teams directly to second round
    # They go into the second round slots that correspond to "empty" first round matches
    if num_rounds > 1:
        # Calculate which second round slots should receive bye teams
        # Bye teams fill in where there would be missing first round matches
        bye_slot_index = 0
        for i, match in enumerate(second_round_matches):
            # Check the two first round matches that feed into this second round match
            feeding_match_1_idx = i * 2
            feeding_match_2_idx = i * 2 + 1
            
            # If a feeding match has no team2 (incomplete), the bye team goes here
            if feeding_match_1_idx < len(first_round_matches):
                fm1 = first_round_matches[feeding_match_1_idx]
                if fm1.team1_id and not fm1.team2_id:
                    # This first round match only has 1 team - they get a bye
                    # Auto-advance them and mark match complete
                    fm1.winner_id = fm1.team1_id
                    fm1.is_completed = True
                    if match.team1_id is None:
                        match.team1_id = fm1.team1_id
                    else:
                        match.team2_id = fm1.team1_id
                elif not fm1.team1_id and not fm1.team2_id:
                    # Empty match - assign bye team directly to second round
                    if bye_slot_index < len(bye_teams):
                        if match.team1_id is None:
                            match.team1_id = int(bye_teams[bye_slot_index])
                        else:
                            match.team2_id = int(bye_teams[bye_slot_index])
                        bye_slot_index += 1
                        fm1.is_completed = True
            
            if feeding_match_2_idx < len(first_round_matches):
                fm2 = first_round_matches[feeding_match_2_idx]
                if fm2.team1_id and not fm2.team2_id:
                    fm2.winner_id = fm2.team1_id
                    fm2.is_completed = True
                    if match.team1_id is None:
                        match.team1_id = fm2.team1_id
                    else:
                        match.team2_id = fm2.team1_id
                elif not fm2.team1_id and not fm2.team2_id:
                    if bye_slot_index < len(bye_teams):
                        if match.team1_id is None:
                            match.team1_id = int(bye_teams[bye_slot_index])
                        else:
                            match.team2_id = int(bye_teams[bye_slot_index])
                        bye_slot_index += 1
                        fm2.is_completed = True
    
    # Set first incomplete match with both teams as current
    for match in matches:
        if not match.is_completed and match.team1_id and match.team2_id:
            match.is_current = True
            break
    
    db.session.commit()


def create_double_elimination_bracket(tournament_id, team_ids):
    """Create double elimination bracket - winners and losers brackets"""
    import random
    
    num_teams = len(team_ids)
    if num_teams < 3:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Calculate rounds for winners bracket
    num_rounds = math.ceil(math.log2(num_teams))
    total_slots = 2 ** num_rounds
    num_byes = total_slots - num_teams
    
    # Create winners bracket matches
    matches = []
    for round_num in range(1, num_rounds + 1):
        matches_in_round = total_slots // (2 ** round_num)
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                tournament_id=tournament_id,
                round_number=round_num,
                match_number=match_num,
                match_type='bracket'
            )
            db.session.add(match)
            matches.append(match)
    
    # Create losers bracket matches (roughly same number)
    losers_rounds = (num_rounds - 1) * 2  # Double elimination needs more losers rounds
    losers_match_num = 1
    for round_num in range(1, losers_rounds + 1):
        # Losers bracket has variable matches per round
        if round_num % 2 == 1:
            matches_in_round = max(1, total_slots // (2 ** ((round_num + 1) // 2 + 1)))
        else:
            matches_in_round = max(1, total_slots // (2 ** (round_num // 2 + 1)))
        
        for match_num in range(1, matches_in_round + 1):
            match = Match(
                tournament_id=tournament_id,
                round_number=100 + round_num,  # 100+ for losers bracket
                match_number=losers_match_num,
                match_type='losers_bracket'
            )
            db.session.add(match)
            matches.append(match)
            losers_match_num += 1
    
    # Grand finals (winner of winners vs winner of losers)
    grand_finals = Match(
        tournament_id=tournament_id,
        round_number=200,
        match_number=1,
        match_type='finals'
    )
    db.session.add(grand_finals)
    matches.append(grand_finals)
    
    db.session.commit()
    
    # Assign teams to first round (same logic as single elimination)
    first_round = [m for m in matches if m.round_number == 1]
    bye_teams = team_ids[:num_byes]
    playing_teams = team_ids[num_byes:]
    
    for i, team_id in enumerate(playing_teams):
        match_idx = i // 2
        if match_idx < len(first_round):
            if i % 2 == 0:
                first_round[match_idx].team1_id = int(team_id)
            else:
                first_round[match_idx].team2_id = int(team_id)
    
    # Handle byes
    second_round = [m for m in matches if m.round_number == 2 and m.match_type == 'bracket']
    for i, team_id in enumerate(bye_teams):
        if i < len(second_round):
            if second_round[i].team1_id is None:
                second_round[i].team1_id = int(team_id)
            else:
                second_round[i].team2_id = int(team_id)
    
    # Set first match as current
    for match in first_round:
        if match.team1_id and match.team2_id:
            match.is_current = True
            break
    
    db.session.commit()


def create_round_robin(tournament_id, team_ids):
    """Create round robin - every team plays every other team"""
    import random
    from itertools import combinations
    
    num_teams = len(team_ids)
    if num_teams < 3:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Generate all possible pairings
    all_pairings = list(combinations(team_ids, 2))
    random.shuffle(all_pairings)
    
    # Create matches - group into "rounds" for organization
    matches_per_round = num_teams // 2
    round_num = 1
    match_num = 1
    
    for i, (team1_id, team2_id) in enumerate(all_pairings):
        match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team1_id),
            team2_id=int(team2_id),
            match_type='group',
            group_name='Round Robin'
        )
        db.session.add(match)
        
        match_num += 1
        if match_num > matches_per_round:
            match_num = 1
            round_num += 1
    
    db.session.commit()
    
    # Set first match as current
    first_match = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).first()
    if first_match:
        first_match.is_current = True
        db.session.commit()


def create_round_robin_playoffs(tournament_id, team_ids):
    """Create round robin group stage followed by top 4 playoffs"""
    import random
    from itertools import combinations
    
    num_teams = len(team_ids)
    if num_teams < 5:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # Create round robin group stage matches
    all_pairings = list(combinations(team_ids, 2))
    random.shuffle(all_pairings)
    
    matches_per_round = max(1, num_teams // 2)
    round_num = 1
    match_num = 1
    
    for i, (team1_id, team2_id) in enumerate(all_pairings):
        match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team1_id),
            team2_id=int(team2_id),
            match_type='group',
            group_name='Group Stage'
        )
        db.session.add(match)
        
        match_num += 1
        if match_num > matches_per_round:
            match_num = 1
            round_num += 1
    
    # Create playoff bracket (4 teams - semifinals and finals)
    # Teams will be assigned after group stage completes
    playoff_round = 100  # Playoffs start at round 100
    
    # Semi-final 1
    semi1 = Match(
        tournament_id=tournament_id,
        round_number=playoff_round,
        match_number=1,
        match_type='bracket',
        group_name='Semifinal 1'
    )
    db.session.add(semi1)
    
    # Semi-final 2
    semi2 = Match(
        tournament_id=tournament_id,
        round_number=playoff_round,
        match_number=2,
        match_type='bracket',
        group_name='Semifinal 2'
    )
    db.session.add(semi2)
    
    db.session.commit()
    
    # Finals
    finals = Match(
        tournament_id=tournament_id,
        round_number=playoff_round + 1,
        match_number=1,
        match_type='finals',
        group_name='Finals'
    )
    db.session.add(finals)
    
    # Link semifinals to finals
    semi1.next_match_id = finals.id
    semi2.next_match_id = finals.id
    
    db.session.commit()
    
    # Set first group match as current
    first_match = Match.query.filter_by(tournament_id=tournament_id, match_type='group').order_by(Match.round_number, Match.match_number).first()
    if first_match:
        first_match.is_current = True
        db.session.commit()


def create_swiss_round(tournament_id, team_ids, round_num=1):
    """Create a Swiss system round - pair teams with similar records"""
    import random
    
    num_teams = len(team_ids)
    if num_teams < 4:
        return
    
    team_ids = list(team_ids)
    random.shuffle(team_ids)
    
    # For first round, just pair randomly
    # For subsequent rounds, we'd need to pair by score (handled separately)
    match_num = 1
    for i in range(0, len(team_ids) - 1, 2):
        match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team_ids[i]),
            team2_id=int(team_ids[i + 1]) if i + 1 < len(team_ids) else None,
            match_type='group',
            group_name=f'Swiss Round {round_num}'
        )
        db.session.add(match)
        match_num += 1
    
    # If odd number of teams, last team gets a bye
    if num_teams % 2 == 1:
        # The last team gets a bye - create a "completed" match with a win
        bye_match = Match(
            tournament_id=tournament_id,
            round_number=round_num,
            match_number=match_num,
            team1_id=int(team_ids[-1]),
            team2_id=None,
            match_type='group',
            group_name=f'Swiss Round {round_num} (Bye)',
            is_completed=True,
            winner_id=int(team_ids[-1])
        )
        db.session.add(bye_match)
    
    db.session.commit()
    
    # Set first match as current
    first_match = Match.query.filter_by(tournament_id=tournament_id, round_number=round_num).order_by(Match.match_number).first()
    if first_match and first_match.team1_id and first_match.team2_id:
        first_match.is_current = True
        db.session.commit()


# ==================== Input Routes (iPad) ====================
@input_bp.route('/')
@login_required
def input_index():
    tournaments = Tournament.query.filter_by(is_active=True).all()
    # Get active TV sessions for this admin to choose from
    tv_sessions = TVSession.query.filter_by(is_active=True).all()
    current_tv_code = session.get('tv_code')
    tv_codes = session.get('tv_codes', [])
    control_all = session.get('control_all_tvs', False)
    return render_template('input/index.html', 
                          tournaments=tournaments, 
                          tv_sessions=tv_sessions, 
                          current_tv_code=current_tv_code,
                          tv_codes=tv_codes,
                          control_all=control_all)


@input_bp.route('/tournament/<int:tournament_id>')
@login_required
def input_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    matches = Match.query.filter_by(tournament_id=tournament_id, is_completed=False).all()
    return render_template('input/tournament.html', tournament=tournament, current_match=current_match, matches=matches)


@input_bp.route('/tournament/<int:tournament_id>/remote')
@login_required
def input_remote(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    teams = Team.query.all()
    return render_template('input/remote.html', tournament=tournament, teams=teams)


@input_bp.route('/tournament/<int:tournament_id>/ipad')
@login_required
def input_ipad(tournament_id):
    """Combined iPad control - scores + TV remote in one interface"""
    tournament = Tournament.query.get_or_404(tournament_id)
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    teams = Team.query.all()
    tv_code = session.get('tv_code')
    return render_template('input/ipad.html', tournament=tournament, current_match=current_match, matches=matches, teams=teams, tv_code=tv_code)


@input_bp.route('/match/<int:match_id>')
@login_required
def input_match(match_id):
    match = Match.query.get_or_404(match_id)
    return render_template('input/match.html', match=match)


# ==================== Display Routes (TV) ====================
@display.route('/')
def display_index():
    """TV display landing page - shows QR code for pairing"""
    tournaments = Tournament.query.filter_by(is_active=True).all()
    
    # Create or get TV session for this display
    tv_session_id = session.get('tv_session_id')
    tv_session = None
    
    if tv_session_id:
        tv_session = TVSession.query.get(tv_session_id)
        if tv_session and not tv_session.is_active:
            tv_session = None
    
    if not tv_session:
        # Create new TV session
        tv_session = TVSession(code=TVSession.generate_code())
        db.session.add(tv_session)
        db.session.commit()
        session['tv_session_id'] = tv_session.id
    
    # Generate QR code that links to admin panel with TV code for pairing
    # Build the full URL to the pairing endpoint
    pair_url = request.url_root.rstrip('/') + url_for('auth.pair_tv', code=tv_session.code)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(pair_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#ff6b00", back_color="#14141f")
    
    # Convert to base64
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('display/index.html', 
                          tournaments=tournaments, 
                          tv_session=tv_session,
                          qr_code=qr_base64,
                          pair_url=pair_url)


@display.route('/tournament/<int:tournament_id>')
def display_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    return render_template('display/tournament.html', tournament=tournament, matches=matches, current_match=current_match)


@display.route('/bracket/<int:tournament_id>')
def display_bracket(tournament_id):
    """Dedicated bracket display - optimized for TV screens"""
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    teams = Team.query.join(Match, (Match.team1_id == Team.id) | (Match.team2_id == Team.id)).filter(Match.tournament_id == tournament_id).distinct().all()
    return render_template('display/bracket.html', tournament=tournament, matches=matches, teams=teams)


@display.route('/scoreboard/<int:tournament_id>')
def display_scoreboard(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    return render_template('display/scoreboard.html', tournament=tournament, current_match=current_match)


@display.route('/live/<int:tournament_id>')
def display_live(tournament_id):
    """Dynamic TV display controlled by iPad remote"""
    tournament = Tournament.query.get_or_404(tournament_id)
    
    # Create or get TV session for this display
    # Check if there's an existing session in the browser cookie
    tv_session_id = session.get('tv_session_id')
    tv_session = None
    
    if tv_session_id:
        tv_session = TVSession.query.filter_by(id=tv_session_id, is_active=True).first()
    
    if not tv_session:
        # Create new TV session with unique code
        tv_session = TVSession(
            code=TVSession.generate_code(),
            tournament_id=tournament_id,
            mode='waiting'
        )
        db.session.add(tv_session)
        db.session.commit()
        session['tv_session_id'] = tv_session.id
    else:
        # Update tournament if changed
        if tv_session.tournament_id != tournament_id:
            tv_session.tournament_id = tournament_id
            db.session.commit()
    
    # Generate QR code for pairing URL
    pair_url = url_for('auth.pair_tv', code=tv_session.code, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(pair_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#ff6b00", back_color="#14141f")
    
    # Convert to base64 for embedding
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('display/live.html', 
                         tournament=tournament, 
                         tv_session=tv_session,
                         qr_code=qr_base64,
                         pair_url=pair_url)


# ==================== API Routes ====================
@main.route('/api/match/<int:match_id>', methods=['GET'])
def get_match(match_id):
    match = Match.query.get_or_404(match_id)
    return jsonify(match.to_dict())


@main.route('/api/match/<int:match_id>/score', methods=['POST'])
def update_score(match_id):
    match = Match.query.get_or_404(match_id)
    data = request.get_json()
    
    if 'team1_score' in data:
        match.team1_score = data['team1_score']
    if 'team2_score' in data:
        match.team2_score = data['team2_score']
    
    db.session.commit()
    
    # Emit score update via Socket.IO
    socketio.emit('score_update', {
        'match_id': match_id,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score
    })
    
    return jsonify(match.to_dict())


@main.route('/api/match/<int:match_id>/complete', methods=['POST'])
def complete_match(match_id):
    match = Match.query.get_or_404(match_id)
    data = request.get_json()
    
    winner_id = data.get('winner_id')
    match.winner_id = winner_id
    match.is_completed = True
    match.is_current = False
    
    # Advance winner to next match
    if match.next_match_id:
        next_match = Match.query.get(match.next_match_id)
        if next_match:
            # Determine which slot (team1 or team2) to fill
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
    
    # Set display mode to waiting and emit next match info
    state = get_or_create_display_state()
    state.mode = 'waiting'
    db.session.commit()
    
    # Prepare next match data for the waiting screen
    next_match_data = None
    if next_current:
        team1 = Team.query.get(next_current.team1_id) if next_current.team1_id else None
        team2 = Team.query.get(next_current.team2_id) if next_current.team2_id else None
        next_match_data = {
            'match_id': next_current.id,
            'round': next_current.round_number,
            'team1': team1.to_dict() if team1 else None,
            'team2': team2.to_dict() if team2 else None
        }
    
    # Get winner team info
    winner_team = Team.query.get(winner_id) if winner_id else None
    winner_data = winner_team.to_dict() if winner_team else None
    
    # Emit match completion via Socket.IO with winner and next match info
    socketio.emit('match_complete', {
        'match_id': match_id,
        'winner_id': winner_id,
        'winner': winner_data,
        'next_match_id': match.next_match_id,
        'next_match': next_match_data
    })
    
    return jsonify(match.to_dict())


@main.route('/api/match/<int:match_id>/set-current', methods=['POST'])
def set_current_match(match_id):
    match = Match.query.get_or_404(match_id)
    
    # Clear current flag from all matches in tournament
    Match.query.filter_by(tournament_id=match.tournament_id, is_current=True).update({'is_current': False})
    
    match.is_current = True
    db.session.commit()
    
    socketio.emit('current_match_changed', {'match_id': match_id})
    
    return jsonify(match.to_dict())


@main.route('/api/tournament/<int:tournament_id>/bracket')
def get_bracket(tournament_id):
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    return jsonify([m.to_dict() for m in matches])


# ==================== TV Display Control API ====================
def get_or_create_display_state():
    """Get or create the singleton display state"""
    state = DisplayState.query.first()
    if not state:
        state = DisplayState(mode='waiting')
        db.session.add(state)
        db.session.commit()
    return state


@main.route('/api/display/state', methods=['GET'])
def get_display_state():
    state = get_or_create_display_state()
    result = state.to_dict()
    
    # Add additional context
    if state.tournament_id:
        tournament = Tournament.query.get(state.tournament_id)
        if tournament:
            result['tournament'] = tournament.to_dict()
            current_match = Match.query.filter_by(tournament_id=state.tournament_id, is_current=True).first()
            if current_match:
                result['current_match'] = current_match.to_dict()
                
                # Also include next match info for waiting mode
                if state.mode == 'waiting':
                    team1 = Team.query.get(current_match.team1_id) if current_match.team1_id else None
                    team2 = Team.query.get(current_match.team2_id) if current_match.team2_id else None
                    result['next_match'] = {
                        'match_id': current_match.id,
                        'round': current_match.round_number,
                        'team1': team1.to_dict() if team1 else None,
                        'team2': team2.to_dict() if team2 else None
                    }
                
                # Include next match info for scoreboard mode ("Playing Next" indicator)
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
    
    if state.winner_team_id:
        winner = Team.query.get(state.winner_team_id)
        if winner:
            result['winner_team'] = winner.to_dict()
    
    # Include theme CSS
    result['theme_css'] = generate_theme_css(result.get('theme', 'dark-orange'))
    
    return jsonify(result)


@main.route('/api/themes', methods=['GET'])
def get_themes():
    """Get all available themes"""
    themes_list = []
    for theme_id, theme_data in THEMES.items():
        themes_list.append({
            'id': theme_id,
            'name': theme_data['name'],
            'type': theme_data['type'],
            'primary': theme_data['primary']
        })
    return jsonify(themes_list)


@main.route('/api/display/theme', methods=['POST'])
@login_required
def set_display_theme():
    """Set the display theme (admin only)"""
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
    
    # Broadcast theme change to all displays
    socketio.emit('theme_change', {
        'theme': theme_id,
        'theme_css': generate_theme_css(theme_id)
    })
    
    return jsonify({'success': True, 'theme': theme_id})


@main.route('/api/tournament/<int:tournament_id>/timer', methods=['POST'])
def update_tournament_timer(tournament_id):
    """Update the timer duration for a tournament"""
    tournament = Tournament.query.get_or_404(tournament_id)
    data = request.get_json()
    
    if 'timer_duration' in data:
        tournament.timer_duration = data['timer_duration']
        db.session.commit()
    
    return jsonify({'success': True, 'timer_duration': tournament.timer_duration})


@main.route('/api/display/mode', methods=['POST'])
def set_display_mode():
    data = request.get_json()
    state = get_or_create_display_state()
    
    # Sanitize all text inputs to prevent XSS
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
        # Validate theme exists
        theme_id = data['theme']
        if theme_id in THEMES:
            state.theme = theme_id
    
    db.session.commit()
    
    # Broadcast the change to all TV displays
    socketio.emit('display_update', state.to_dict())
    
    return jsonify(state.to_dict())


@main.route('/api/tournament/<int:tournament_id>/next-match', methods=['GET'])
def get_next_match(tournament_id):
    """Get the next upcoming match (first incomplete match with both teams assigned)"""
    tournament = Tournament.query.get_or_404(tournament_id)
    
    # Find the first incomplete match with both teams
    next_match = Match.query.filter(
        Match.tournament_id == tournament_id,
        Match.is_completed == False,
        Match.is_current == False,
        Match.team1_id.isnot(None),
        Match.team2_id.isnot(None)
    ).order_by(Match.round_number, Match.match_number).first()
    
    if next_match:
        return jsonify({
            'next_match': {
                'id': next_match.id,
                'round_number': next_match.round_number,
                'match_number': next_match.match_number,
                'team1': {
                    'id': next_match.team1.id,
                    'name': next_match.team1.name,
                    'player1': next_match.team1.player1,
                    'player2': next_match.team1.player2
                } if next_match.team1 else None,
                'team2': {
                    'id': next_match.team2.id,
                    'name': next_match.team2.name,
                    'player1': next_match.team2.player1,
                    'player2': next_match.team2.player2
                } if next_match.team2 else None
            }
        })
    
    return jsonify({'next_match': None})


@main.route('/api/tournament/<int:tournament_id>/stats', methods=['GET'])
def get_tournament_stats(tournament_id):
    """Get tournament statistics"""
    tournament = Tournament.query.get_or_404(tournament_id)
    
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


# ==================== Socket.IO Events ====================
@socketio.on('connect')
def handle_connect():
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('join_tv')
def handle_join_tv(data):
    """TV joins its own room for targeted updates"""
    code = data.get('code', '').upper()
    if code:
        join_room(f'tv_{code}')
        print(f'TV {code} joined room')
        # Update last seen
        tv_session = TVSession.query.filter_by(code=code, is_active=True).first()
        if tv_session:
            tv_session.last_seen = datetime.utcnow()
            db.session.commit()


@socketio.on('leave_tv')
def handle_leave_tv(data):
    """TV leaves its room"""
    code = data.get('code', '').upper()
    if code:
        leave_room(f'tv_{code}')
        print(f'TV {code} left room')


@socketio.on('join_tournament')
def handle_join_tournament(data):
    room = f"tournament_{data['tournament_id']}"
    join_room(room)
    emit('joined', {'room': room})


@socketio.on('start_countdown')
def handle_start_countdown(data):
    """Broadcast countdown start to all connected displays"""
    emit('start_countdown', data, broadcast=True)


@socketio.on('update_score')
def handle_score_update(data):
    match_id = data['match_id']
    match = Match.query.get(match_id)
    if match:
        if 'team1_score' in data:
            match.team1_score = data['team1_score']
        if 'team2_score' in data:
            match.team2_score = data['team2_score']
        db.session.commit()
        
        emit('score_update', {
            'match_id': match_id,
            'team1_score': match.team1_score,
            'team2_score': match.team2_score
        }, broadcast=True)


@socketio.on('winner_pending')
def handle_winner_pending(data):
    """Handle when match time ends and there's a pending winner to confirm"""
    # Simply broadcast to all connected clients (especially iPad remotes)
    emit('winner_pending', {
        'match_id': data['match_id'],
        'team1_score': data['team1_score'],
        'team2_score': data['team2_score'],
        'winner_id': data['winner_id'],
        'winner_name': data['winner_name'],
        'is_overtime': data.get('is_overtime', False)
    }, broadcast=True)


@socketio.on('tv_command')
def handle_tv_command(data):
    """Send a command to a specific TV by code"""
    tv_code = data.get('tv_code', '').upper()
    command = data.get('command', {})
    if tv_code:
        # Send to the specific TV's room
        emit('display_update', command, to=f'tv_{tv_code}')
        print(f'Sent command to TV {tv_code}: {command}')


@socketio.on('refresh_tv')
def handle_refresh_tv(data):
    """Send refresh command to a specific TV"""
    tv_code = data.get('tv_code', '').upper()
    if tv_code:
        emit('refresh_display', {}, to=f'tv_{tv_code}')
        print(f'Refresh sent to TV {tv_code}')
