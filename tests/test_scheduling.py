
import pytest
from app import create_app, db
from app.models import Admin, Tournament, Team, Match, TVSession

@pytest.fixture
def tournament_with_matches(client):
    """Setup tournament with 4 teams and bracket generated"""
    # Create admin
    admin = Admin(username='schedule_test')
    admin.set_password('password')
    db.session.add(admin)
    db.session.commit()
    
    # Create tournament
    tournament = Tournament(name="Scheduling Test", owner_id=admin.id)
    db.session.add(tournament)
    db.session.commit()
    
    # Add 4 teams
    teams = []
    for i in range(4):
        t = Team(name=f"Team {i+1}", player1=f"P{i*2+1}", player2=f"P{i*2+2}", tournament_id=tournament.id, is_confirmed=True)
        db.session.add(t)
        teams.append(t)
    db.session.commit()
    
    # Start tournament to generate bracket (Manual setup for precise control or use generic start)
    # Using generic start
    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
        
    client.post(f'/admin/tournament/{tournament.id}/start')
    
    return tournament

def test_smart_scheduling_continuity(client, tournament_with_matches):
    """Test that get_next_match prioritizes matches with teams already on field (or just finished)"""
    t_id = tournament_with_matches.id
    
    # Login as admin
    admin = Admin.query.filter_by(username='schedule_test').first()
    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
    
    # Get all matches
    matches = Match.query.filter_by(tournament_id=t_id).order_by(Match.match_number).all()
    # Match 1: Team 1 vs Team 2
    # Match 2: Team 3 vs Team 4
    # Match 3: Winner 1 vs Winner 2
    
    match1 = matches[0]
    match2 = matches[1]
    
    # Complete Match 1
    # Team 1 wins
    resp = client.post(f'/api/match/{match1.id}/complete', json={'winner_id': match1.team1_id})
    assert resp.status_code == 200
    
    # Now, normally Match 2 would be next by sequence.
    # But if Match 3 is ready (it's not, because match 2 needs to finish first for Match 3 to have 2 teams).
    # Wait, in single elimination:
    # Match 1 (1v2) -> Winner to Match 3
    # Match 2 (3v4) -> Winner to Match 3
    # Match 3 is NOT ready yet.
    
    # Smart scheduling only works if there ARE multiple playable matches.
    # Let's create a bigger tournament (8 teams) so we have:
    # M1, M2, M3, M4 (Round 1)
    # M5, M6 (Round 2)
    # If M1 finishes, M2, M3, M4 are candidates.
    # None of them have Team 1 (winner of M1).
    # Team 1 goes to M5. M5 needs winner of M2.
    # So M5 is NOT playable yet.
    
    # Actually, smart scheduling helps when say:
    # Round Robin or Group stage, where a team might play back-to-back.
    # OR Double Elimination.
    
    # Let's try simulate a situation where it WOULD help.
    # Manual setup: 
    # Match A: T1 vs T2
    # Match B: T3 vs T4
    # Match C: T1 vs T5 (Playable!)
    
    # Create custom matches
    m_a = Match(tournament_id=t_id, round_number=1, match_number=10, team1_id=matches[0].team1_id, team2_id=matches[0].team2_id)
    m_b = Match(tournament_id=t_id, round_number=1, match_number=11, team1_id=matches[1].team1_id, team2_id=matches[1].team2_id)
    m_c = Match(tournament_id=t_id, round_number=1, match_number=12, team1_id=matches[0].team1_id, team2_id=matches[1].team1_id) # T1 vs T3
    
    # Mark standard generated matches as completed or ignore them
    Match.query.filter_by(tournament_id=t_id).delete()
    db.session.add_all([m_a, m_b, m_c])
    db.session.commit()
    
    # Start: All incomplete.
    # Complete m_a (Winner T1)
    m_a.winner_id = m_a.team1_id
    m_a.is_completed = True
    db.session.commit()
    
    # Now playable: m_b and m_c.
    # m_b is earlier number (11 vs 12).
    # BUT m_c has T1 (who just finished m_a).
    # Expect get_next_match to pick m_c.
    
    resp = client.get(f'/api/tournament/{t_id}/next-match')
    data = resp.get_json()
    
    assert data['next_match']['id'] == m_c.id
    assert data['next_match']['is_continuity'] == True
    
