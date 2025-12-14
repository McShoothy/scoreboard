from app import db
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string


def utc_now():
    """Get current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


class Admin(db.Model):
    """Admin users who can control the tournament"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # Werkzeug hash (longer)
    created_at = db.Column(db.DateTime, default=utc_now)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        """Hash and store password using werkzeug's secure hashing"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against stored hash"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TVSession(db.Model):
    """TV display sessions that can be paired with admin controllers"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)  # 6-char pairing code
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)
    socket_id = db.Column(db.String(100), nullable=True)  # Socket.IO session ID
    created_at = db.Column(db.DateTime, default=utc_now)
    last_seen = db.Column(db.DateTime, default=utc_now)
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
    """Teams registered for tournaments"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)  # Team name (unique per tournament)
    player1 = db.Column(db.String(30), nullable=False)  # Player 1 name
    player2 = db.Column(db.String(30), nullable=False)  # Player 2 name
    
    # Tournament association
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)
    
    # Registration metadata
    email = db.Column(db.String(100), nullable=True)  # Contact email (for future notifications)
    phone = db.Column(db.String(20), nullable=True)  # Contact phone (optional)
    registered_at = db.Column(db.DateTime, default=utc_now)
    registration_ip = db.Column(db.String(45), nullable=True)  # For abuse prevention
    
    # Status
    is_confirmed = db.Column(db.Boolean, default=True)  # Admin can require confirmation
    is_checked_in = db.Column(db.Boolean, default=False)  # For day-of check-in
    seed = db.Column(db.Integer, nullable=True)  # Seeding for brackets
    
    # For legacy/global teams (nullable tournament_id)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    tournament = db.relationship('Tournament', backref='registered_teams', foreign_keys=[tournament_id])
    
    # Unique constraint: team name must be unique within a tournament
    __table_args__ = (
        db.UniqueConstraint('name', 'tournament_id', name='unique_team_per_tournament'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'player1': self.player1,
            'player2': self.player2,
            'tournament_id': self.tournament_id,
            'is_confirmed': self.is_confirmed,
            'is_checked_in': self.is_checked_in,
            'seed': self.seed,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None
        }


class Tournament(db.Model):
    """Tournament configuration and settings"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)  # Tournament description
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Owner (admin who created this tournament)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)
    owner = db.relationship('Admin', foreign_keys=[owner_id])
    
    # Registration settings
    registration_code = db.Column(db.String(20), nullable=True)  # 6-char code or custom password
    registration_open = db.Column(db.Boolean, default=True)  # Is registration currently open
    registration_deadline = db.Column(db.DateTime, nullable=True)  # Auto-close registration
    max_teams = db.Column(db.Integer, default=16, nullable=True)  # Maximum number of teams (optional)
    min_teams = db.Column(db.Integer, default=4, nullable=True)  # Minimum to start (optional)
    require_confirmation = db.Column(db.Boolean, default=False)  # Admin must confirm teams
    require_email = db.Column(db.Boolean, default=False)  # Email required for registration
    require_player_names = db.Column(db.Boolean, default=False)  # Player names required (default: just team name)
    
    # Tournament settings
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='registration')  # registration, ready, in_progress, completed, cancelled
    timer_duration = db.Column(db.Integer, default=150)  # Default 2:30 (150 seconds)
    format = db.Column(db.String(50), default='single_elimination')
    current_phase = db.Column(db.String(50), default='registration')
    
    # Event details (for future features)
    event_date = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    
    # Matches relationship
    matches = db.relationship('Match', backref='tournament', lazy=True)
    
    @staticmethod
    def generate_registration_code():
        """Generate a unique 6-character registration code"""
        chars = string.ascii_uppercase + string.digits
        chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(6))
            if not Tournament.query.filter_by(registration_code=code).first():
                return code
    
    def get_registered_team_count(self):
        """Get count of registered teams"""
        return Team.query.filter_by(tournament_id=self.id).count()
    
    def get_confirmed_team_count(self):
        """Get count of confirmed teams"""
        return Team.query.filter_by(tournament_id=self.id, is_confirmed=True).count()
    
    def can_register(self):
        """Check if registration is still possible"""
        if not self.registration_open:
            return False, "Registration is closed"
        if self.status != 'registration':
            return False, "Tournament has already started"
        if self.registration_deadline and utc_now() > self.registration_deadline:
            return False, "Registration deadline has passed"
        if self.get_registered_team_count() >= self.max_teams:
            return False, "Tournament is full"
        return True, "OK"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'status': self.status,
            'timer_duration': self.timer_duration,
            'format': self.format,
            'current_phase': self.current_phase,
            'registration_open': self.registration_open,
            'max_teams': self.max_teams,
            'min_teams': self.min_teams,
            'registered_teams': self.get_registered_team_count(),
            'confirmed_teams': self.get_confirmed_team_count(),
            'require_confirmation': self.require_confirmation,
            'require_email': self.require_email,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'location': self.location,
            'created_at': self.created_at.isoformat()
        }
    
    def to_public_dict(self):
        """Public info (no sensitive data like registration code)"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'format': self.format,
            'registration_open': self.registration_open,
            'max_teams': self.max_teams,
            'registered_teams': self.get_registered_team_count(),
            'spots_remaining': max(0, self.max_teams - self.get_registered_team_count()),
            'require_email': self.require_email,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'location': self.location
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


class DisplayState(db.Model):
    """Global display state for TV displays (legacy, use TVSession instead)"""
    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(50), default='waiting')  # waiting, scoreboard, bracket, winner, message
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=True)
    custom_message = db.Column(db.String(500), nullable=True)
    show_players = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    tournament = db.relationship('Tournament', foreign_keys=[tournament_id])
    match = db.relationship('Match', foreign_keys=[match_id])
    
    def to_dict(self):
        return {
            'mode': self.mode,
            'tournament_id': self.tournament_id,
            'match_id': self.match_id,
            'custom_message': self.custom_message,
            'show_players': self.show_players
        }


class APIToken(db.Model):
    """API tokens for external system integration"""
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(128), unique=True, nullable=False)  # SHA256 hash
    token_prefix = db.Column(db.String(8), nullable=False)  # First 8 chars for identification
    name = db.Column(db.String(80), nullable=False)  # "Robot Controller", "Scoring System"
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)  # Optional scope
    permissions = db.Column(db.String(500), default='[]')  # JSON array of permissions
    is_active = db.Column(db.Boolean, default=True)
    last_used = db.Column(db.DateTime, nullable=True)
    request_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    admin = db.relationship('Admin', backref=db.backref('api_tokens', lazy='dynamic'))
    tournament = db.relationship('Tournament', foreign_keys=[tournament_id])
    
    # Available permission scopes
    SCOPES = [
        'tournament:read',   # Read tournament info
        'match:read',        # Read match info
        'match:write',       # Complete matches, set winners
        'score:read',        # Read scores
        'score:write',       # Update scores
        'display:write',     # Control TV displays
        'timer:write',       # Start/stop timers
        'team:read',         # Read team info
    ]
    
    @staticmethod
    def generate_token():
        """Generate a secure random token (shown only once to user)"""
        return secrets.token_urlsafe(32)  # 256 bits of entropy
    
    @staticmethod
    def hash_token(token):
        """Hash a token for secure storage"""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()
    
    @classmethod
    def create_token(cls, name, admin_id, permissions=None, tournament_id=None, expires_at=None):
        """Create a new API token and return (token_object, raw_token)"""
        raw_token = cls.generate_token()
        
        token = cls(
            token_hash=cls.hash_token(raw_token),
            token_prefix=raw_token[:8],
            name=name,
            admin_id=admin_id,
            tournament_id=tournament_id,
            permissions=str(permissions or cls.SCOPES),  # Default: all permissions
            expires_at=expires_at
        )
        
        return token, raw_token
    
    @classmethod
    def validate_token(cls, raw_token):
        """Validate a token and return the token object if valid"""
        token_hash = cls.hash_token(raw_token)
        token = cls.query.filter_by(token_hash=token_hash, is_active=True).first()
        
        if not token:
            return None
        
        # Check expiration
        if token.expires_at and token.expires_at < datetime.now(timezone.utc):
            return None
        
        # Update usage stats
        token.last_used = utc_now()
        token.request_count += 1
        db.session.commit()
        
        return token
    
    def has_permission(self, scope):
        """Check if token has a specific permission"""
        import json
        try:
            perms = json.loads(self.permissions.replace("'", '"'))
        except (json.JSONDecodeError, AttributeError):
            perms = []
        return scope in perms
    
    def get_permissions(self):
        """Get list of permissions"""
        import json
        try:
            return json.loads(self.permissions.replace("'", '"'))
        except (json.JSONDecodeError, AttributeError):
            return []
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'token_prefix': self.token_prefix,
            'admin_id': self.admin_id,
            'admin_username': self.admin.username if self.admin else None,
            'tournament_id': self.tournament_id,
            'tournament_name': self.tournament.name if self.tournament else None,
            'permissions': self.get_permissions(),
            'is_active': self.is_active,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'request_count': self.request_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }