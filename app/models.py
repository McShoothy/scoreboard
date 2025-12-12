from app import db
from datetime import datetime
import hashlib
import secrets
import string


class Admin(db.Model):
    """Admin users who can control the tournament"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)  # Not used, hardcoded below
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Hardcoded admin password hash (SHA512)
    ADMIN_PASSWORD_HASH = 'd3b1e3325fdac83dafcb6041991303cfb7dc5fa2cd9cb6d19f1409f2a35fe180a240cf2ad7f0a834c63989bc748210e2eeb1efe2974979f68e2f773d5260bdae'
    
    def set_password(self, password):
        # Password is hardcoded, this is a no-op
        pass
    
    def check_password(self, password):
        return hashlib.sha512(password.encode()).hexdigest() == self.ADMIN_PASSWORD_HASH
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }


class TVSession(db.Model):
    """TV display sessions that can be paired with admin controllers"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)  # 6-char pairing code
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)
    socket_id = db.Column(db.String(100), nullable=True)  # Socket.IO session ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Display state for this specific TV
    mode = db.Column(db.String(50), default='waiting')  # scoreboard, bracket, winner, message, waiting
    custom_message = db.Column(db.String(500), nullable=True)
    winner_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    show_players = db.Column(db.Boolean, default=True)
    
    tournament = db.relationship('Tournament', foreign_keys=[tournament_id])
    winner_team = db.relationship('Team', foreign_keys=[winner_team_id])
    
    @staticmethod
    def generate_code():
        """Generate a unique 6-character alphanumeric code"""
        chars = string.ascii_uppercase + string.digits
        # Remove confusing characters
        chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(6))
            if not TVSession.query.filter_by(code=code, is_active=True).first():
                return code
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'tournament_id': self.tournament_id,
            'tournament_name': self.tournament.name if self.tournament else None,
            'mode': self.mode,
            'is_active': self.is_active,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(8), unique=True, nullable=False)  # Max 8 chars, must be unique
    player1 = db.Column(db.String(10), nullable=False)  # Max 10 chars
    player2 = db.Column(db.String(10), nullable=False)  # Max 10 chars
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'player1': self.player1,
            'player2': self.player2
        }


class DisplayState(db.Model):
    """Stores the current TV display state"""
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)
    mode = db.Column(db.String(50), default='scoreboard')  # scoreboard, bracket, winner, message, waiting
    custom_message = db.Column(db.String(500), nullable=True)
    winner_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    show_players = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(50), default='dark-orange')  # Theme identifier
    
    tournament = db.relationship('Tournament', foreign_keys=[tournament_id])
    winner_team = db.relationship('Team', foreign_keys=[winner_team_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'tournament_id': self.tournament_id,
            'mode': self.mode,
            'custom_message': self.custom_message,
            'winner_team_id': self.winner_team_id,
            'show_players': self.show_players,
            'theme': self.theme or 'dark-orange'
        }


class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    timer_duration = db.Column(db.Integer, default=150)  # Default 2:30 (150 seconds)
    format = db.Column(db.String(50), default='single_elimination')  # single_elimination, double_elimination, round_robin, round_robin_playoffs, swiss
    current_phase = db.Column(db.String(50), default='group')  # group, playoffs, finals
    matches = db.relationship('Match', backref='tournament', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active,
            'timer_duration': self.timer_duration,
            'format': self.format,
            'current_phase': self.current_phase,
            'created_at': self.created_at.isoformat()
        }


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    match_number = db.Column(db.Integer, nullable=False)
    team1_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    team2_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    team1_score = db.Column(db.Integer, default=0)
    team2_score = db.Column(db.Integer, default=0)
    winner_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    is_current = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    next_match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=True)
    match_type = db.Column(db.String(50), default='bracket')  # bracket, group, losers_bracket, finals
    group_name = db.Column(db.String(50), nullable=True)  # For round robin: 'Group A', etc.
    
    team1 = db.relationship('Team', foreign_keys=[team1_id])
    team2 = db.relationship('Team', foreign_keys=[team2_id])
    winner = db.relationship('Team', foreign_keys=[winner_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'round_number': self.round_number,
            'match_number': self.match_number,
            'team1': self.team1.to_dict() if self.team1 else None,
            'team2': self.team2.to_dict() if self.team2 else None,
            'team1_score': self.team1_score,
            'team2_score': self.team2_score,
            'winner': self.winner.to_dict() if self.winner else None,
            'is_current': self.is_current,
            'is_completed': self.is_completed
        }
