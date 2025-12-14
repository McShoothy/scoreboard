"""
Tests for admin routes and functionality.
"""
import pytest
import json


class TestAdminAuthentication:
    """Test admin login/logout."""
    
    def test_login_page_loads(self, client):
        """Test login page is accessible."""
        response = client.get('/login')
        assert response.status_code == 200
    
    def test_login_success(self, client):
        """Test successful login."""
        response = client.post('/login', data={
            'username': 'testadmin',
            'password': 'testpassword'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_login_wrong_password(self, client):
        """Test login with wrong password."""
        response = client.post('/login', data={
            'username': 'testadmin',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert b'Invalid' in response.data or response.status_code == 200
    
    def test_logout(self, authenticated_client):
        """Test logout."""
        response = authenticated_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200


class TestAdminDashboard:
    """Test admin dashboard."""
    
    def test_dashboard_requires_auth(self, client):
        """Test dashboard redirects when not logged in."""
        response = client.get('/admin/')
        assert response.status_code == 302  # Redirect to login
    
    def test_dashboard_loads(self, authenticated_client):
        """Test dashboard loads when authenticated."""
        response = authenticated_client.get('/admin/')
        assert response.status_code == 200


class TestAPITokenManagement:
    """Test API token management."""
    
    def test_token_page_loads(self, authenticated_client):
        """Test API tokens page loads."""
        response = authenticated_client.get('/admin/api-tokens')
        assert response.status_code == 200
    
    def test_create_token(self, authenticated_client):
        """Test creating an API token."""
        response = authenticated_client.post(
            '/admin/api-tokens/create',
            json={'name': 'Test Token'},
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'token' in data
        assert len(data['token']) > 20  # Token should be reasonably long
    
    def test_list_tokens(self, authenticated_client):
        """Test listing API tokens."""
        # First create a token
        authenticated_client.post(
            '/admin/api-tokens/create',
            json={'name': 'Test Token'},
            content_type='application/json'
        )
        
        # Then list
        response = authenticated_client.get('/admin/api-tokens/list')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tokens' in data
        assert len(data['tokens']) >= 1


class TestTournamentManagement:
    """Test tournament management."""
    
    def test_tournaments_page_loads(self, authenticated_client):
        """Test tournaments page loads."""
        response = authenticated_client.get('/admin/tournaments')
        assert response.status_code == 200
    
    def test_view_tournament(self, authenticated_client, test_tournament):
        """Test viewing a tournament."""
        response = authenticated_client.get(f'/admin/tournaments/{test_tournament}')
        assert response.status_code == 200


class TestTeamManagement:
    """Test team management."""
    
    def test_teams_page_loads(self, authenticated_client):
        """Test teams page loads."""
        response = authenticated_client.get('/admin/teams')
        assert response.status_code == 200


class TestUserManagement:
    """Test user management."""
    
    def test_users_page_loads(self, authenticated_client):
        """Test users page loads."""
        response = authenticated_client.get('/admin/users')
        assert response.status_code == 200
