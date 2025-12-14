"""
Pytest configuration and fixtures for the scoreboard application.
"""
import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Admin, Tournament, Team, Match, APIToken


class TestConfig:
    """Test configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    WTF_CSRF_CHECK_DEFAULT = False


@pytest.fixture
def app():
    """Create and configure a test application instance."""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create test admin
        admin = Admin(username='testadmin')
        admin.set_password('testpassword')
        db.session.add(admin)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(app, client):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['admin_id'] = 1
        sess['admin_username'] = 'testadmin'
    return client


@pytest.fixture
def test_tournament(app):
    """Create a test tournament."""
    with app.app_context():
        tournament = Tournament(
            name='Test Tournament',
            format='single_elimination',
            timer_duration=150,
            registration_code='TEST01',
            owner_id=1
        )
        db.session.add(tournament)
        db.session.commit()
        return tournament.id


@pytest.fixture
def test_teams(app, test_tournament):
    """Create test teams."""
    with app.app_context():
        teams = []
        for i in range(4):
            team = Team(
                name=f'Team {i+1}',
                player1=f'Player {i*2+1}',
                player2=f'Player {i*2+2}',
                tournament_id=test_tournament,
                is_confirmed=True
            )
            db.session.add(team)
            teams.append(team)
        db.session.commit()
        return [t.id for t in teams]


@pytest.fixture
def test_match(app, test_tournament, test_teams):
    """Create a test match."""
    with app.app_context():
        match = Match(
            tournament_id=test_tournament,
            round_number=1,
            match_number=1,
            team1_id=test_teams[0],
            team2_id=test_teams[1],
            is_current=True
        )
        db.session.add(match)
        db.session.commit()
        return match.id


@pytest.fixture
def api_token(app):
    """Create an API token for testing."""
    with app.app_context():
        token, raw_token = APIToken.create_token(
            name='Test Token',
            admin_id=1,
            permissions=['score:write', 'match:read', 'match:write', 'tournament:read']
        )
        db.session.add(token)
        db.session.commit()
        return raw_token
