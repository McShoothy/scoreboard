
import pytest
import json
from app import create_app, db
from app.models import Admin

class TestBracketAPI:
    def setup_method(self):
        from tests.conftest import TestConfig
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create admin for auth
        admin = Admin(username='testadmin')
        admin.set_password('testpassword')
        db.session.add(admin)
        db.session.commit()
        
        # Login
        with self.client.session_transaction() as sess:
            sess['admin_id'] = admin.id
            sess['admin_username'] = admin.username

    def teardown_method(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_generate_brackets_endpoint(self):
        response = self.client.post('/api/test/generate-brackets')
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Verify structure
        formats = ['single_elimination', 'double_elimination', 'round_robin', 'round_robin_playoffs', 'swiss']
        counts = ['2', '3', '4', '64'] # JSON keys are strings
        
        print("\n=== Bracket Generation Test Results ===")
        for fmt in formats:
            assert fmt in data, f"Missing format: {fmt}"
            print(f"\nFormat: {fmt}")
            for count in counts:
                assert count in data[fmt], f"Missing count {count} in {fmt}"
                result = data[fmt][count]
                
                if 'error' in result:
                    print(f"  Teams: {count} -> ERROR: {result['error']}")
                    # Fail if error, unless it's expected for some reason (but we fixed limits, so should be fine)
                    pytest.fail(f"Error generating {fmt} for {count} teams: {result['error']}")
                else:
                    match_count = result['match_count']
                    print(f"  Teams: {count} -> {match_count} matches generated")
                    assert match_count > 0, f"No matches generated for {fmt} with {count} teams"

        # Output full JSON for user inspection (creating a file artifact)
        with open('bracket_test_output.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("\nFull output saved to bracket_test_output.json")
