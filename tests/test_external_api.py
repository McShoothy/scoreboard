"""
Tests for the external API endpoints.
"""
import pytest
import json


class TestAPIHealthAndScopes:
    """Test unauthenticated endpoints."""
    
    def test_health_check(self, client):
        """Test health endpoint returns OK."""
        response = client.get('/ext/v1/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'version' in data
    
    def test_list_scopes(self, client):
        """Test scopes endpoint returns available scopes."""
        response = client.get('/ext/v1/scopes')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'scopes' in data
        assert 'score:write' in data['scopes']


class TestAPIAuthentication:
    """Test API token authentication."""
    
    def test_missing_auth_header(self, client, test_tournament):
        """Test request without auth header fails."""
        response = client.get(f'/ext/v1/tournament/{test_tournament}')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_invalid_token(self, client, test_tournament):
        """Test request with invalid token fails."""
        response = client.get(
            f'/ext/v1/tournament/{test_tournament}',
            headers={'Authorization': 'Bearer invalid-token'}
        )
        assert response.status_code == 401
    
    def test_valid_token_works(self, client, api_token, test_tournament):
        """Test request with valid token succeeds."""
        response = client.get(
            f'/ext/v1/tournament/{test_tournament}',
            headers={'Authorization': f'Bearer {api_token}'}
        )
        assert response.status_code == 200


class TestMatchEndpoints:
    """Test match API endpoints."""
    
    def test_get_match(self, client, api_token, test_match):
        """Test getting match details."""
        response = client.get(
            f'/ext/v1/match/{test_match}',
            headers={'Authorization': f'Bearer {api_token}'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'match' in data
        assert data['match']['id'] == test_match
    
    def test_add_point_team1(self, client, api_token, test_match):
        """Test adding point to team 1."""
        response = client.post(
            f'/ext/v1/match/{test_match}/add-point',
            headers={'Authorization': f'Bearer {api_token}'},
            json={'team': 1}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['team1_score'] == 1
        assert data['team2_score'] == 0
    
    def test_add_point_team2(self, client, api_token, test_match):
        """Test adding point to team 2."""
        response = client.post(
            f'/ext/v1/match/{test_match}/add-point',
            headers={'Authorization': f'Bearer {api_token}'},
            json={'team': 2}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['team2_score'] == 1
    
    def test_update_score(self, client, api_token, test_match):
        """Test updating match score."""
        response = client.post(
            f'/ext/v1/match/{test_match}/score',
            headers={'Authorization': f'Bearer {api_token}'},
            json={'team1_score': 5, 'team2_score': 3}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['match']['team1_score'] == 5
        assert data['match']['team2_score'] == 3
    
    def test_set_winner_auto(self, client, api_token, test_match, app):
        """Test auto-determining winner."""
        # First set scores
        client.post(
            f'/ext/v1/match/{test_match}/score',
            headers={'Authorization': f'Bearer {api_token}'},
            json={'team1_score': 5, 'team2_score': 3}
        )
        
        # Then set winner
        response = client.post(
            f'/ext/v1/match/{test_match}/set-winner',
            headers={'Authorization': f'Bearer {api_token}'},
            json={}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'winner_id' in data
    
    def test_match_not_found(self, client, api_token):
        """Test 404 for non-existent match."""
        response = client.get(
            '/ext/v1/match/99999',
            headers={'Authorization': f'Bearer {api_token}'}
        )
        assert response.status_code == 404


class TestTournamentEndpoints:
    """Test tournament API endpoints."""
    
    def test_get_tournament(self, client, api_token, test_tournament):
        """Test getting tournament details."""
        response = client.get(
            f'/ext/v1/tournament/{test_tournament}',
            headers={'Authorization': f'Bearer {api_token}'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tournament' in data
        assert data['tournament']['name'] == 'Test Tournament'
    
    def test_get_current_match(self, client, api_token, test_tournament, test_match):
        """Test getting current match."""
        response = client.get(
            f'/ext/v1/tournament/{test_tournament}/current',
            headers={'Authorization': f'Bearer {api_token}'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['current_match']['id'] == test_match
    
    def test_tournament_not_found(self, client, api_token):
        """Test 404 for non-existent tournament."""
        response = client.get(
            '/ext/v1/tournament/99999',
            headers={'Authorization': f'Bearer {api_token}'}
        )
        assert response.status_code == 404
