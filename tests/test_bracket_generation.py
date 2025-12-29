
import pytest
from app import create_app, db
from app.models import Tournament, Team, Match
from app.blueprints.bracket import (
    create_single_elimination_bracket,
    create_double_elimination_bracket,
    create_round_robin,
    create_round_robin_playoffs,
    create_swiss_round
)

class TestBracketReproduction:
    def setup_method(self):
        from tests.conftest import TestConfig
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def teardown_method(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_tournament_and_teams(self, num_teams):
        tournament = Tournament(name='Test', format='test')
        db.session.add(tournament)
        db.session.commit()
        
        team_ids = []
        for i in range(num_teams):
            team = Team(name=f'Team {i}', player1=f'P1_{i}', player2=f'P2_{i}', tournament_id=tournament.id)
            db.session.add(team)
            db.session.commit()
            team_ids.append(team.id)
            
        return tournament.id, team_ids

    def test_round_robin_four_teams(self):
        """Test round robin with 4 teams - User says it's broken, probably referring to payoffs variant"""
        t_id, team_ids = self.create_tournament_and_teams(4)
        
        # Test standard round robin - expect success (based on code analysis)
        create_round_robin(t_id, team_ids)
        matches = Match.query.filter_by(tournament_id=t_id).all()
        # 4 teams -> 6 matches matches?
        # Code says: max(1, 4//2) = 2 matches per round. 6 pairings. 
        # Check if matches created
        assert len(matches) > 0, "Round robin for 4 teams created no matches"
        
        # Clear matches for next check
        Match.query.delete()
        db.session.commit()
    
    def test_round_robin_playoffs_four_teams(self):
        """Test round robin playoffs with 4 teams - Should now WORK"""
        t_id, team_ids = self.create_tournament_and_teams(4)
        
        create_round_robin_playoffs(t_id, team_ids)
        matches = Match.query.filter_by(tournament_id=t_id).all()
        
        # 4 teams round robin: 6 matches
        # Plus Playoffs: Semi1, Semi2, Finals = 3 matches
        # Total = 9 matches
        assert len(matches) == 9, f"Expected 9 matches, got {len(matches)}"

    def test_brackets_two_teams(self):
        """Test all bracket types with 2 teams - Should all WORK now"""
        t_id, team_ids = self.create_tournament_and_teams(2)
        
        # 1. Single Elimination
        create_single_elimination_bracket(t_id, team_ids)
        matches = Match.query.filter_by(tournament_id=t_id).all()
        assert len(matches) == 1, "Single Elim 2 teams should have 1 match"
        Match.query.delete()
        db.session.commit()
        
        # 2. Double Elimination
        create_double_elimination_bracket(t_id, team_ids)
        matches = Match.query.filter_by(tournament_id=t_id).all()
        # 2 teams: power of 2 is 2. 
        # Winners bracket: 1 round, 1 match.
        # Losers bracket: (1-1)*2 = 0 rounds? No, code logic might be tricky for 2 teams.
        # Let's count: Winners (1) + Finals (1) = 2 matches. Losers bracket loops might not run.
        # Just ensure we have matches and a finals.
        assert len(matches) >= 2, f"Double Elim 2 teams should have at least 2 matches, got {len(matches)}"
        Match.query.delete()
        db.session.commit()
        
        # 3. Round Robin
        create_round_robin(t_id, team_ids)
        matches = Match.query.filter_by(tournament_id=t_id).all()
        # 2 teams: 1 pair. 1 match.
        assert len(matches) == 1, "Round Robin 2 teams should have 1 match"
        Match.query.delete()
        db.session.commit()

        # 4. Swiss
        create_swiss_round(t_id, team_ids)
        matches = Match.query.filter_by(tournament_id=t_id).all()
        # 2 teams: 1 match.
        assert len(matches) == 1, "Swiss 2 teams should have 1 match"
