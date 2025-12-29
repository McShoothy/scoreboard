"""
Register blueprint - public team registration routes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import db, socketio
from app.models import Tournament, Team

register = Blueprint('register', __name__)


@register.route('/')
def register_index():
    """Registration landing page - enter tournament code."""
    return render_template('register/index.html')


@register.route('/tournament/<code>', methods=['GET'])
def register_tournament(code):
    """Registration page for a specific tournament."""
    tournament = Tournament.query.filter_by(registration_code=code.upper()).first()
    if not tournament:
        flash('Invalid tournament code', 'error')
        return redirect(url_for('register.register_index'))
    
    can_register, message = tournament.can_register()
    teams = Team.query.filter_by(tournament_id=tournament.id, is_confirmed=True).order_by(Team.registered_at).all()
    
    return render_template('register/tournament.html', 
                           tournament=tournament, 
                           teams=teams,
                           can_register=can_register,
                           register_message=message)


@register.route('/join', methods=['POST'])
def register_join():
    """Handle tournament code submission."""
    code = request.form.get('code', '').strip().upper()
    if not code:
        flash('Please enter a tournament code', 'error')
        return redirect(url_for('register.register_index'))
    
    tournament = Tournament.query.filter_by(registration_code=code).first()
    if not tournament:
        flash('Invalid tournament code', 'error')
        return redirect(url_for('register.register_index'))
    
    return redirect(url_for('register.register_tournament', code=code))


@register.route('/team', methods=['POST'])
def register_team():
    """Register a team for a tournament."""
    code = request.form.get('tournament_code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()
    player1 = request.form.get('player1', '').strip()
    player2 = request.form.get('player2', '').strip()
    email = request.form.get('email', '').strip() or None
    phone = request.form.get('phone', '').strip() or None
    
    tournament = Tournament.query.filter_by(registration_code=code).first()
    if not tournament:
        flash('Invalid tournament code', 'error')
        return redirect(url_for('register.register_index'))
    
    can_register, message = tournament.can_register()
    if not can_register:
        flash(message, 'error')
        return redirect(url_for('register.register_tournament', code=code))
    
    if not team_name or len(team_name) > 20:
        flash('Team name is required (max 20 characters)', 'error')
        return redirect(url_for('register.register_tournament', code=code))
    
    if tournament.require_player_names:
        if not player1 or len(player1) > 30:
            flash('Player 1 name is required (max 30 characters)', 'error')
            return redirect(url_for('register.register_tournament', code=code))
        
        if not player2 or len(player2) > 30:
            flash('Player 2 name is required (max 30 characters)', 'error')
            return redirect(url_for('register.register_tournament', code=code))
    
    if tournament.require_email and not email:
        flash('Email is required for this tournament', 'error')
        return redirect(url_for('register.register_tournament', code=code))
    
    existing = Team.query.filter_by(tournament_id=tournament.id, name=team_name).first()
    if existing:
        flash('A team with this name is already registered', 'error')
        return redirect(url_for('register.register_tournament', code=code))
    
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
    
    if tournament.require_confirmation:
        flash(f'Team "{team_name}" registered! Awaiting admin confirmation.', 'success')
    else:
        flash(f'Team "{team_name}" successfully registered!', 'success')
    
    return redirect(url_for('register.register_success', code=code, team_id=team.id))


@register.route('/success/<code>/<int:team_id>')
def register_success(code, team_id):
    """Registration success page."""
    tournament = Tournament.query.filter_by(registration_code=code.upper()).first()
    team = db.session.get(Team, team_id)
    
    if not tournament or not team:
        return redirect(url_for('register.register_index'))
    
    teams = Team.query.filter_by(tournament_id=tournament.id, is_confirmed=True).order_by(Team.registered_at).all()
    
    return render_template('register/success.html', 
                           tournament=tournament, 
                           team=team,
                           teams=teams)
