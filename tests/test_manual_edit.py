
import pytest
from app import db
from app.models import Admin, Tournament, Team, Match

@pytest.fixture
def admin_user(client):
    admin = Admin(username='edit_test')
    admin.set_password('password')
    db.session.add(admin)
    db.session.commit()
    return admin

def test_manual_match_edit(client, admin_user):
    """Test that admin can manually edit a match"""
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_user.id
        
    # Setup tournament
    t = Tournament(name="Edit Test", owner_id=admin_user.id)
    db.session.add(t)
    db.session.commit()
    
    # Create teams
    team1 = Team(name="Team A", player1="P1", player2="P2", tournament_id=t.id)
    team2 = Team(name="Team B", player1="P3", player2="P4", tournament_id=t.id)
    team3 = Team(name="Team C", player1="P5", player2="P6", tournament_id=t.id)
    db.session.add_all([team1, team2, team3])
    db.session.commit()
    
    # Create match
    m = Match(tournament_id=t.id, round_number=1, match_number=1, team1_id=team1.id, team2_id=team2.id)
    db.session.add(m)
    db.session.commit()
    
    # 1. Edit teams (Swap T2 for T3)
    resp = client.post(f'/admin/match/{m.id}/edit', data={
        'team1_id': team1.id,
        'team2_id': team3.id,
        'team1_score': 0,
        'team2_score': 0
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    
    updated_match = Match.query.get(m.id)
    assert updated_match.team2_id == team3.id
    
    # 2. Edit scores
    client.post(f'/admin/match/{m.id}/edit', data={
        'team1_id': team1.id,
        'team2_id': team3.id,
        'team1_score': 10,
        'team2_score': 5
    })
    
    updated_match = Match.query.get(m.id)
    assert updated_match.team1_score == 10
    assert updated_match.team2_score == 5
    
    # 3. Force Complete
    client.post(f'/admin/match/{m.id}/edit', data={
        'action': 'mark_complete',
        'winner_id': team1.id,
        'team1_id': team1.id,
        'team2_id': team3.id
    })
    
    updated_match = Match.query.get(m.id)
    assert updated_match.is_completed == True
    assert updated_match.winner_id == team1.id
