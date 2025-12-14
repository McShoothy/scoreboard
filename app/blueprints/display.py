"""
Display blueprint - TV display routes.
"""
from flask import Blueprint, render_template, request, session, url_for
import qrcode
import io
import base64

from app import db
from app.models import Tournament, Match, Team, TVSession

display = Blueprint('display', __name__)


@display.route('/')
def display_index():
    """TV display landing page - shows QR code for pairing."""
    
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
    
    # Generate QR code
    pair_url = request.url_root.rstrip('/') + url_for('auth.pair_tv', code=tv_session.code)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(pair_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#ff6b00", back_color="#14141f")
    
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('display/index.html', 
                          tv_session=tv_session,
                          qr_code=qr_base64,
                          pair_url=pair_url)


@display.route('/tournament/<int:tournament_id>')
def display_tournament(tournament_id):
    """Display a tournament."""
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    return render_template('display/tournament.html', tournament=tournament, matches=matches, current_match=current_match)


@display.route('/bracket/<int:tournament_id>')
def display_bracket(tournament_id):
    """Dedicated bracket display - optimized for TV screens."""
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.round_number, Match.match_number).all()
    teams = Team.query.join(Match, (Match.team1_id == Team.id) | (Match.team2_id == Team.id)).filter(Match.tournament_id == tournament_id).distinct().all()
    return render_template('display/bracket.html', tournament=tournament, matches=matches, teams=teams)


@display.route('/scoreboard/<int:tournament_id>')
def display_scoreboard(tournament_id):
    """Display the scoreboard."""
    tournament = Tournament.query.get_or_404(tournament_id)
    current_match = Match.query.filter_by(tournament_id=tournament_id, is_current=True).first()
    return render_template('display/scoreboard.html', tournament=tournament, current_match=current_match)


@display.route('/live/<int:tournament_id>')
def display_live(tournament_id):
    """Dynamic TV display controlled by iPad remote."""
    tournament = Tournament.query.get_or_404(tournament_id)
    
    # Create or get TV session
    tv_session_id = session.get('tv_session_id')
    tv_session = None
    
    if tv_session_id:
        tv_session = TVSession.query.filter_by(id=tv_session_id, is_active=True).first()
    
    if not tv_session:
        tv_session = TVSession(
            code=TVSession.generate_code(),
            tournament_id=tournament_id,
            mode='waiting'
        )
        db.session.add(tv_session)
        db.session.commit()
        session['tv_session_id'] = tv_session.id
    else:
        if tv_session.tournament_id != tournament_id:
            tv_session.tournament_id = tournament_id
            db.session.commit()
    
    # Generate QR code
    pair_url = url_for('auth.pair_tv', code=tv_session.code, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(pair_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#ff6b00", back_color="#14141f")
    
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('display/live.html', 
                         tournament=tournament, 
                         tv_session=tv_session,
                         qr_code=qr_base64,
                         pair_url=pair_url)
