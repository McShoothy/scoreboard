"""
Tests for UI routes accessibility.
"""
import pytest


class TestPublicPages:
    """Test publicly accessible pages."""
    
    def test_index_loads(self, client):
        """Test index page loads."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_login_loads(self, client):
        """Test login page loads."""
        response = client.get('/login')
        assert response.status_code == 200
    
    def test_register_index_loads(self, client):
        """Test registration index loads."""
        response = client.get('/register/')
        assert response.status_code == 200


class TestDisplayPages:
    """Test TV display pages."""
    
    def test_display_index_loads(self, client):
        """Test display index with QR code loads."""
        response = client.get('/display/')
        assert response.status_code == 200
    
    def test_display_tournament(self, client, test_tournament):
        """Test tournament display page."""
        response = client.get(f'/display/tournament/{test_tournament}')
        assert response.status_code == 200
    
    def test_display_bracket(self, client, test_tournament):
        """Test bracket display page."""
        response = client.get(f'/display/bracket/{test_tournament}')
        assert response.status_code == 200


class TestInputPages:
    """Test iPad input controller pages."""
    
    def test_input_index_requires_auth(self, client):
        """Test input index requires authentication."""
        response = client.get('/input/')
        assert response.status_code == 302  # Redirect to login
    
    def test_input_index_loads_authenticated(self, authenticated_client):
        """Test input index loads when authenticated."""
        response = authenticated_client.get('/input/')
        assert response.status_code == 200


class TestAdminPages:
    """Test admin panel pages require auth."""
    
    def test_admin_index_requires_auth(self, client):
        """Test admin index requires auth."""
        response = client.get('/admin/')
        assert response.status_code == 302
    
    def test_admin_teams_requires_auth(self, client):
        """Test admin teams requires auth."""
        response = client.get('/admin/teams')
        assert response.status_code == 302
    
    def test_admin_tournaments_requires_auth(self, client):
        """Test admin tournaments requires auth."""
        response = client.get('/admin/tournaments')
        assert response.status_code == 302
    
    def test_admin_users_requires_auth(self, client):
        """Test admin users requires auth."""
        response = client.get('/admin/users')
        assert response.status_code == 302
    
    def test_admin_api_tokens_requires_auth(self, client):
        """Test API tokens page requires auth."""
        response = client.get('/admin/api-tokens')
        assert response.status_code == 302
