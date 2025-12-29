
import pytest
from app import create_app, db
from app.models import Tournament, Team, Match

class TestTeamSwap:
    def setup_method(self):
        from tests.conftest import TestConfig
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create auth session
        with self.client.session_transaction() as sess:
            sess['admin_id'] = 1
            sess['admin_username'] = 'testadmin'

    def teardown_method(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_swap_teams(self):
        # Create tournament and teams
        t = Tournament(name='Test T', owner_id=1)
        db.session.add(t)
        db.session.commit()
        
        team1 = Team(name='Team 1', player1='P1', player2='P2', tournament_id=t.id)
        team2 = Team(name='Team 2', player1='P3', player2='P4', tournament_id=t.id)
        db.session.add(team1)
        db.session.add(team2)
        db.session.commit()
        
        # Create match
        m = Match(
            tournament_id=t.id, 
            round_number=1, 
            match_number=1, 
            team1_id=team1.id, 
            team2_id=team2.id,
            team1_score=10,
            team2_score=5
        )
        db.session.add(m)
        db.session.commit()
        
        # Verify initial state
        assert m.team1_id == team1.id
        assert m.team2_id == team2.id
        assert m.team1_score == 10
        assert m.team2_score == 5
        
        # Call swap endpoint
        resp = self.client.post(f'/api/match/{m.id}/swap-teams')
        assert resp.status_code == 200
        
        # Reload match
        db.session.refresh(m)
        
        # Verify swapped state
        assert m.team1_id == team2.id
        assert m.team2_id == team1.id
        # Scores should also swap
        assert m.team1_score == 5
        assert m.team2_score == 10
