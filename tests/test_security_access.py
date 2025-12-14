
import pytest
from app.models import TVSession

class TestSecurityAccess:
    """Test security restrictions on API endpoints."""

    def test_public_access_denied(self, client, test_tournament):
        """Test that public users are denied access to sensitive data."""
        endpoints = [
            f'/api/match/1',
            f'/api/tournament/{test_tournament}/bracket',
            f'/api/tournament/{test_tournament}/next-match',
            f'/api/tournament/{test_tournament}/stats',
            f'/api/tournament/{test_tournament}/teams'
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should be 401 Unauthorized or 403 Forbidden
            assert response.status_code == 401, f"Endpoint {endpoint} should be protected"

    def test_admin_access_allowed(self, authenticated_client, test_tournament, test_match):
        """Test that admins can access sensitive data."""
        # Match endpoint
        response = authenticated_client.get(f'/api/match/{test_match}')
        assert response.status_code == 200

        # Bracket endpoint
        response = authenticated_client.get(f'/api/tournament/{test_tournament}/bracket')
        assert response.status_code == 200

        # Stats endpoint
        response = authenticated_client.get(f'/api/tournament/{test_tournament}/stats')
        assert response.status_code == 200

    def test_tv_session_access_allowed(self, client, app, test_tournament, test_match):
        """Test that valid TV sessions can access sensitive data."""
        # Create a TV session
        with app.app_context():
            tv_session = TVSession(code='TESTTV')
            from app import db
            db.session.add(tv_session)
            db.session.commit()
            tv_id = tv_session.id
        
        # Simulate TV session login
        with client.session_transaction() as sess:
            sess['tv_session_id'] = tv_id

        # Match endpoint
        response = client.get(f'/api/match/{test_match}')
        assert response.status_code == 200

        # Bracket endpoint
        response = client.get(f'/api/tournament/{test_tournament}/bracket')
        assert response.status_code == 200
