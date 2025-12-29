"""
Input blueprint - iPad controller routes.
"""
from flask import Blueprint, render_template, session

from app.models import Tournament, Match, Team, TVSession
from app.blueprints.auth import login_required

input_bp = Blueprint('input', __name__)


@input_bp.route('/')
@login_required
def input_index():
    """Input controller landing page."""
    tournaments = Tournament.query.filter_by(is_active=True).all()
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
    """Input controller for a specific tournament."""
    tournament = db.get_or_404(Tournament, tournament_id)
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    matches = Match.query.filter_by(tournament_id=tournament_id, is_completed=False).all()
    return render_template('input/tournament.html', tournament=tournament, current_match=current_match, matches=matches)


@input_bp.route('/tournament/<int:tournament_id>/remote')
@login_required
def input_remote(tournament_id):
    """Remote control for a tournament."""
    tournament = db.get_or_404(Tournament, tournament_id)
    teams = Team.query.all()
    return render_template('input/remote.html', tournament=tournament, teams=teams)


@input_bp.route('/tournament/<int:tournament_id>/ipad')
@login_required
def input_ipad(tournament_id):
    """Combined iPad control - scores + TV remote in one interface."""
    tournament = db.get_or_404(Tournament, tournament_id)
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    teams = Team.query.all()
    tv_code = session.get('tv_code')
    return render_template('input/ipad.html', tournament=tournament, current_match=current_match, matches=matches, teams=teams, tv_code=tv_code)


@input_bp.route('/match/<int:match_id>')
@login_required
def input_match(match_id):
    """Input for a specific match."""
    match = db.get_or_404(Match, match_id)
    return render_template('input/match.html', match=match)
