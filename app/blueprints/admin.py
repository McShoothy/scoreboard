"""
Admin blueprint - handles tournament, team, user, and API token management.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timezone
import logging
import json

from app import db, socketio
from app.models import Team, Tournament, Match, Admin, APIToken
from app.utils import sanitize_team_name, sanitize_player_name, sanitize_text
from app.blueprints.auth import login_required

logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__)


# ==================== Dashboard ====================

@admin.route('/')
@login_required
def admin_index():
    """Admin dashboard."""
    teams = Team.query.all()
    tournaments = Tournament.query.all()
    return render_template('admin/index.html', teams=teams, tournaments=tournaments)


# ==================== Team Management ====================

@admin.route('/teams', methods=['GET', 'POST'])
@login_required
def manage_teams():
    """Manage global teams."""
    if request.method == 'POST':
        name = sanitize_team_name(request.form.get('name'))
        player1 = sanitize_player_name(request.form.get('player1'))
        player2 = sanitize_player_name(request.form.get('player2'))
        
        if not name or not player1 or not player2:
            flash('All fields are required', 'error')
            return redirect(url_for('admin.manage_teams'))
        
        existing_team = Team.query.filter(
            db.func.lower(Team.name) == name.lower(),
            Team.tournament_id == None
        ).first()
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
    """Delete a team."""
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    return redirect(url_for('admin.manage_teams'))


# ==================== Tournament Management ====================

@admin.route('/tournaments', methods=['GET', 'POST'])
@login_required
def manage_tournaments():
    """Create and manage tournaments."""
    from app.blueprints.bracket import (
        create_single_elimination_bracket, create_double_elimination_bracket,
        create_round_robin, create_round_robin_playoffs, create_swiss_round
    )
    
    if request.method == 'POST':
        name = sanitize_text(request.form.get('name'), max_length=100)
        if not name:
            flash('Tournament name is required', 'error')
            return redirect(url_for('admin.manage_tournaments'))
            
        timer_minutes = int(request.form.get('timer_minutes', 2))
        timer_seconds = int(request.form.get('timer_seconds', 30))
        timer_duration = timer_minutes * 60 + timer_seconds
        format_type = request.form.get('format', 'single_elimination')
        registration_mode = request.form.get('registration_mode', 'open')
        
        tournament = Tournament(
            name=name, 
            timer_duration=timer_duration, 
            format=format_type,
            owner_id=session.get('admin_id')
        )
        
        if registration_mode == 'open':
            custom_code = request.form.get('registration_code', '').strip()
            if custom_code:
                tournament.registration_code = custom_code.upper()
            else:
                tournament.registration_code = Tournament.generate_registration_code()
            
            tournament.registration_open = True
            tournament.status = 'registration'
            
            max_teams_str = request.form.get('max_teams', '').strip()
            min_teams_str = request.form.get('min_teams', '').strip()
            tournament.max_teams = int(max_teams_str) if max_teams_str else 16
            tournament.min_teams = int(min_teams_str) if min_teams_str else 4
            
            tournament.require_confirmation = 'require_confirmation' in request.form
            tournament.require_email = 'require_email' in request.form
            tournament.require_player_names = 'require_player_names' in request.form
            
            db.session.add(tournament)
            db.session.commit()
            
            return redirect(url_for('admin.admin_tournament_registrations', tournament_id=tournament.id))
        else:
            tournament.registration_open = False
            tournament.status = 'ready'
            
            db.session.add(tournament)
            db.session.commit()
            
            team_ids = request.form.getlist('teams')
            
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
    
    current_admin_id = session.get('admin_id')
    tournaments = Tournament.query.filter(
        (Tournament.owner_id == current_admin_id) | (Tournament.owner_id == None)
    ).all()
    
    teams = Team.query.filter_by(tournament_id=None).all()
    return render_template('admin/tournaments.html', teams=teams, tournaments=tournaments)


@admin.route('/tournaments/<int:tournament_id>')
@login_required
def view_tournament(tournament_id):
    """View tournament details."""
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    
    standings = []
    if tournament.format in ['round_robin', 'round_robin_playoffs', 'swiss']:
        standings = calculate_standings(tournament_id)
    
    all_teams = Team.query.filter_by(tournament_id=tournament_id).order_by(Team.name).all()
    
    return render_template('admin/tournament_view.html', tournament=tournament, matches=matches, standings=standings, all_teams=all_teams)


def calculate_standings(tournament_id):
    """Calculate team standings based on completed matches."""
    matches = Match.query.filter_by(tournament_id=tournament_id, is_completed=True).all()
    
    team_stats = {}
    
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
    
    standings = []
    for team_id, stats in team_stats.items():
        stats['team_id'] = team_id
        stats['point_diff'] = stats['points_for'] - stats['points_against']
        standings.append(stats)
    
    standings.sort(key=lambda x: (x['wins'], x['point_diff'], x['points_for']), reverse=True)
    
    for i, entry in enumerate(standings):
        entry['rank'] = i + 1
    
    return standings


@admin.route('/tournaments/<int:tournament_id>/delete', methods=['POST'])
@login_required
def delete_tournament(tournament_id):
    """Delete a tournament."""
    tournament = Tournament.query.get_or_404(tournament_id)
    Match.query.filter_by(tournament_id=tournament_id).delete()
    db.session.delete(tournament)
    db.session.commit()
    return redirect(url_for('admin.manage_tournaments'))


@admin.route('/tournaments/<int:tournament_id>/advance-to-playoffs', methods=['POST'])
@login_required
def advance_to_playoffs(tournament_id):
    """Advance top 4 teams from group stage to playoffs."""
    tournament = Tournament.query.get_or_404(tournament_id)
    
    if tournament.format != 'round_robin_playoffs':
        return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))
    
    standings = calculate_standings(tournament_id)
    
    if len(standings) < 4:
        return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))
    
    semifinals = Match.query.filter_by(tournament_id=tournament_id, round_number=100).order_by(Match.match_number).all()
    
    if len(semifinals) >= 2:
        semifinals[0].team1_id = standings[0]['team_id']
        semifinals[0].team2_id = standings[3]['team_id']
        
        semifinals[1].team1_id = standings[1]['team_id']
        semifinals[1].team2_id = standings[2]['team_id']
        
        tournament.current_phase = 'playoffs'
        semifinals[0].is_current = True
        
        db.session.commit()
    
    return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))


    return redirect(url_for('admin.view_tournament', tournament_id=tournament_id))


@admin.route('/match/<int:match_id>/edit', methods=['POST'])
@login_required
def edit_match(match_id):
    """Manually edit match details (teams, scores, state)."""
    match = Match.query.get_or_404(match_id)
    
    # 1. Update Teams
    team1_id = request.form.get('team1_id')
    team2_id = request.form.get('team2_id')
    
    # Allow setting to None if empty string passed, otherwise int
    match.team1_id = int(team1_id) if team1_id and team1_id.strip() else None
    match.team2_id = int(team2_id) if team2_id and team2_id.strip() else None
    
    # 2. Update Scores
    try:
        match.team1_score = int(request.form.get('team1_score', 0))
        match.team2_score = int(request.form.get('team2_score', 0))
    except ValueError:
        pass # Ignore invalid numbers
        
    # 3. Update State (e.g. force complete or reset)
    action = request.form.get('action')
    if action == 'mark_complete':
        match.is_completed = True
        match.is_current = False
        winner_id = request.form.get('winner_id')
        match.winner_id = int(winner_id) if winner_id and winner_id.strip() else None
        
        # Trigger basic progression logic if needed? 
        # For manual edit, we might trust the admin set everything correctly, 
        # but if they want auto-progression they should use the normal flow.
        # Here we just save the state.
        
    elif action == 'reset':
        match.is_completed = False
        match.winner_id = None
        match.team1_score = 0
        match.team2_score = 0
        
    elif action == 'set_current':
        # Reset other current matches in tournament
        Match.query.filter_by(tournament_id=match.tournament_id, is_current=True).update({'is_current': False})
        match.is_current = True
        match.is_completed = False
        
    db.session.commit()
    
    # Emit update for displays
    socketio.emit('score_update', {
        'match_id': match.id,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score
    })
    
    flash(f"Match {match.match_number} updated successfully", "success")
    return redirect(url_for('admin.view_tournament', tournament_id=match.tournament_id))


# ==================== User Management ====================

@admin.route('/users')
@login_required
def manage_users():
    """Manage admin users."""
    admins = Admin.query.all()
    return render_template('admin/users.html', admins=admins)


@admin.route('/users/add', methods=['POST'])
@login_required
def add_user():
    """Add an admin user."""
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
    """Delete an admin user."""
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
    """Change an admin user's password."""
    admin_user = Admin.query.get_or_404(user_id)
    new_password = request.form.get('password')
    admin_user.set_password(new_password)
    db.session.commit()
    flash(f'Password changed for {admin_user.username}', 'success')
    return redirect(url_for('admin.manage_users'))


# ==================== Registration Management ====================

@admin.route('/tournament/<int:tournament_id>/registrations')
@login_required
def admin_tournament_registrations(tournament_id):
    """View and manage tournament registrations."""
    tournament = Tournament.query.get_or_404(tournament_id)
    teams = Team.query.filter_by(tournament_id=tournament_id).order_by(Team.registered_at).all()
    
    return render_template('admin/registrations.html', tournament=tournament, teams=teams)


@admin.route('/tournament/<int:tournament_id>/team/<int:team_id>/confirm', methods=['POST'])
@login_required
def admin_confirm_team(tournament_id, team_id):
    """Confirm a team registration."""
    team = Team.query.get_or_404(team_id)
    if team.tournament_id != tournament_id:
        return jsonify({'success': False, 'error': 'Team not in this tournament'}), 400
    
    team.is_confirmed = True
    db.session.commit()
    
    socketio.emit('team_confirmed', {
        'tournament_id': tournament_id,
        'team': team.to_dict()
    })
    
    return jsonify({'success': True, 'team': team.to_dict()})


@admin.route('/tournament/<int:tournament_id>/team/add', methods=['POST'])
@login_required
def admin_add_team_to_tournament(tournament_id):
    """Manually add a team to a tournament."""
    tournament = Tournament.query.get_or_404(tournament_id)
    data = request.get_json()
    
    name = sanitize_team_name(data.get('name', ''))
    player1 = sanitize_player_name(data.get('player1', ''))
    player2 = sanitize_player_name(data.get('player2', ''))
    
    if not name or not player1 or not player2:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    
    existing = Team.query.filter(
        db.func.lower(Team.name) == name.lower(),
        Team.tournament_id == tournament_id
    ).first()
    if existing:
        return jsonify({'success': False, 'error': f'Team name "{name}" already exists in this tournament'}), 400
    
    if tournament.get_registered_team_count() >= tournament.max_teams:
        return jsonify({'success': False, 'error': 'Tournament is full'}), 400
    
    team = Team(
        name=name,
        player1=player1,
        player2=player2,
        tournament_id=tournament_id,
        is_confirmed=True
    )
    db.session.add(team)
    db.session.commit()
    
    socketio.emit('team_registered', {
        'tournament_id': tournament_id,
        'team': team.to_dict()
    })
    
    return jsonify({'success': True, 'team': team.to_dict()})


@admin.route('/tournament/<int:tournament_id>/team/<int:team_id>/reject', methods=['POST'])
@login_required
def admin_reject_team(tournament_id, team_id):
    """Reject/remove a team registration."""
    team = Team.query.get_or_404(team_id)
    if team.tournament_id != tournament_id:
        return jsonify({'success': False, 'error': 'Team not in this tournament'}), 400
    
    team_name = team.name
    db.session.delete(team)
    db.session.commit()
    
    socketio.emit('team_removed', {
        'tournament_id': tournament_id,
        'team_id': team_id,
        'team_name': team_name
    })
    
    return jsonify({'success': True})


@admin.route('/tournament/<int:tournament_id>/team/<int:team_id>/checkin', methods=['POST'])
@login_required
def admin_checkin_team(tournament_id, team_id):
    """Check in a team on event day."""
    team = Team.query.get_or_404(team_id)
    if team.tournament_id != tournament_id:
        return jsonify({'success': False, 'error': 'Team not in this tournament'}), 400
    
    team.is_checked_in = not team.is_checked_in
    db.session.commit()
    
    return jsonify({'success': True, 'checked_in': team.is_checked_in})


@admin.route('/tournament/<int:tournament_id>/registration/toggle', methods=['POST'])
@login_required
def admin_toggle_registration(tournament_id):
    """Toggle registration open/closed."""
    tournament = Tournament.query.get_or_404(tournament_id)
    tournament.registration_open = not tournament.registration_open
    db.session.commit()
    
    socketio.emit('registration_status_changed', {
        'tournament_id': tournament_id,
        'registration_open': tournament.registration_open
    })
    
    return jsonify({
        'success': True, 
        'registration_open': tournament.registration_open
    })


@admin.route('/tournament/<int:tournament_id>/start', methods=['POST'])
@login_required
def admin_start_tournament(tournament_id):
    """Start the tournament (close registration, generate bracket)."""
    from app.blueprints.bracket import (
        create_single_elimination_bracket, create_double_elimination_bracket,
        create_round_robin, create_round_robin_playoffs, create_swiss_round
    )
    
    tournament = Tournament.query.get_or_404(tournament_id)
    
    teams = Team.query.filter_by(tournament_id=tournament_id, is_confirmed=True).all()
    team_ids = [t.id for t in teams]
    
    if len(teams) < (tournament.min_teams or 2):
        return jsonify({
            'success': False, 
            'error': f'Need at least {tournament.min_teams or 2} confirmed teams to start'
        }), 400
    
    tournament.registration_open = False
    tournament.status = 'in_progress'
    tournament.current_phase = 'bracket'
    db.session.commit()
    
    format_type = tournament.format or 'single_elimination'
    
    if format_type == 'single_elimination':
        create_single_elimination_bracket(tournament_id, team_ids)
    elif format_type == 'double_elimination':
        create_double_elimination_bracket(tournament_id, team_ids)
    elif format_type == 'round_robin':
        create_round_robin(tournament_id, team_ids)
    elif format_type == 'round_robin_playoffs':
        create_round_robin_playoffs(tournament_id, team_ids)
    elif format_type == 'swiss':
        create_swiss_round(tournament_id, team_ids, round_num=1)
    else:
        create_single_elimination_bracket(tournament_id, team_ids)
    
    socketio.emit('tournament_started', {
        'tournament_id': tournament_id,
        'team_count': len(teams)
    })
    
    return jsonify({
        'success': True,
        'team_count': len(teams),
        'message': f'Tournament started with {len(teams)} teams! Bracket generated.'
    })


@admin.route('/tournament/<int:tournament_id>/regenerate-code', methods=['POST'])
@login_required
def admin_regenerate_code(tournament_id):
    """Generate a new registration code."""
    tournament = Tournament.query.get_or_404(tournament_id)
    tournament.registration_code = Tournament.generate_registration_code()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'code': tournament.registration_code
    })


# ==================== API Token Management ====================

@admin.route('/api-tokens')
@login_required
def manage_api_tokens():
    """Manage API tokens for external integrations."""
    admin_id = session.get('admin_id')
    tokens = APIToken.query.filter_by(admin_id=admin_id).order_by(APIToken.created_at.desc()).all()
    tournaments = Tournament.query.all()
    scopes = APIToken.SCOPES
    
    return render_template('admin/api_tokens.html', 
                          tokens=tokens, 
                          tournaments=tournaments,
                          scopes=scopes)


@admin.route('/api-tokens/create', methods=['POST'])
@login_required
def create_api_token():
    """Create a new API token."""
    admin_id = session.get('admin_id')
    data = request.get_json() or request.form.to_dict()
    
    name = data.get('name', 'Unnamed Token').strip()
    if not name:
        name = 'Unnamed Token'
    
    # Get tournament scope (optional)
    tournament_id = data.get('tournament_id')
    if tournament_id:
        tournament_id = int(tournament_id) if tournament_id != '' else None
    else:
        tournament_id = None
    
    # Get permissions
    permissions = data.get('permissions')
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except json.JSONDecodeError:
            permissions = APIToken.SCOPES
    elif not permissions:
        permissions = APIToken.SCOPES
    
    # Get expiration
    expires_at = None
    expires_days = data.get('expires_days')
    if expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=int(expires_days))
    
    # Create token
    token, raw_token = APIToken.create_token(
        name=name,
        admin_id=admin_id,
        permissions=permissions,
        tournament_id=tournament_id,
        expires_at=expires_at
    )
    
    db.session.add(token)
    db.session.commit()
    
    # Return raw token (shown only once!)
    return jsonify({
        'success': True,
        'token': raw_token,
        'token_info': token.to_dict(),
        'message': 'Token created. Copy it now - it will not be shown again!'
    })


@admin.route('/api-tokens/<int:token_id>/revoke', methods=['POST'])
@login_required
def revoke_api_token(token_id):
    """Revoke an API token."""
    admin_id = session.get('admin_id')
    token = APIToken.query.filter_by(id=token_id, admin_id=admin_id).first()
    
    if not token:
        return jsonify({'success': False, 'error': 'Token not found'}), 404
    
    token.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Token revoked'})


@admin.route('/api-tokens/<int:token_id>/delete', methods=['POST'])
@login_required
def delete_api_token(token_id):
    """Delete an API token."""
    admin_id = session.get('admin_id')
    token = APIToken.query.filter_by(id=token_id, admin_id=admin_id).first()
    
    if not token:
        return jsonify({'success': False, 'error': 'Token not found'}), 404
    
    db.session.delete(token)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Token deleted'})


@admin.route('/api-tokens/list', methods=['GET'])
@login_required
def list_api_tokens():
    """List all API tokens for current admin (JSON)."""
    admin_id = session.get('admin_id')
    tokens = APIToken.query.filter_by(admin_id=admin_id).all()
    
    return jsonify({
        'tokens': [t.to_dict() for t in tokens]
    })

