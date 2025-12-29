# RobotUprising Tournament Scoreboard

A real-time tournament management system for competitive events. Supports multiple tournament formats, live TV displays, iPad score input, and team registration.

## Features

### Tournament Formats
- Single Elimination
- Double Elimination  
- Round Robin
- Round Robin with Playoffs
- Swiss System

### Real-Time Display
- TV-optimized display modes (scoreboard, bracket, countdown)
- WebSocket-powered live updates
- Multiple theme options (dark, hacker, neon, princess)
- QR code pairing for controllers

### Score Input
- iPad-optimized touch interface
- Multi-TV control from single device
- Timer countdown with customizable duration

### Team Registration
- Public registration with tournament codes
- QR code scanning support
- Admin confirmation workflow
- Check-in tracking

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone repository
git clone https://github.com/McShoothy/scoreboard.git
cd scoreboard

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
flask run
```

Open `http://localhost:5000` in your browser.

### Default Login
- Username: `admin`
- Password: `password`

---

## Project Structure

```
scoreboard/
├── app/
│   ├── blueprints/       # Flask blueprints (modular routes)
│   │   ├── admin.py      # Admin panel routes
│   │   ├── api.py        # Internal REST API
│   │   ├── auth.py       # Authentication
│   │   ├── display.py    # TV display routes
│   │   ├── external_api.py  # External API (token auth)
│   │   ├── input.py      # iPad score input
│   │   └── register.py   # Public registration
│   ├── templates/        # Jinja2 templates
│   ├── static/           # CSS, JS, images
│   ├── models.py         # Database models
│   └── utils.py          # Helper functions
├── docs/
│   └── API.md            # External API documentation
├── tests/                # pytest test suite
├── config.py             # Configuration
├── requirements.txt      # Python dependencies
├── Procfile              # Heroku deployment
└── run.py                # Application entry point
```

---

## Admin Panel

Access at `/admin` after logging in.

### Tournament Management
- Create tournaments with different formats
- Configure registration settings (codes, deadlines, team limits)
- Start tournaments and generate brackets
- View live standings and match progress

### Team Management
- Confirm or reject registrations
- Check-in teams on event day
- Add teams manually

### User Management
- Create admin accounts
- Change passwords
- Manage API tokens

### Match Control
- Edit match scores
- Force complete matches
- Reset match state
- Swap teams

---

## for admins:

### Team Registration Workflow

1. **Create Tournament**
   - Go to `Manage Tournaments`
   - Select format (e.g., Single Elimination, Round Robin)
   - Enable `Open Registration` mode (default)
   - Set limits: Max Teams, Min Teams
   - (Optional) Require admin confirmation for new teams

2. **Open Registration**
   - Once created, click the green `Registrations` button
   - Ensure the status shows "Registration Open"
   - If not, click "Open Registration"

3. **Share Registration Info**
   - **QR Code**: Click the QR icon to show a large code on screen for teams to scan
   - **Code**: Share the 6-character code (e.g., `ABC123`) for teams to enter manually
   - **URL**: Copy the direct link for sharing via chat/email

4. **Manage Incoming Teams**
   - As teams register, they appear in the list
   - **Confirm**: If confirmation is required, click the checkmark ✅ to approve
   - **Check-in**: On event day, toggle the person icon 👤 to mark teams as physically present
   - **Manual Add**: Use the form on the left to add teams who cannot self-register

5. **Start Tournament**
   - When ready (and min teams reached), click "Start Tournament"
   - This will lock registrations and generate the bracket automatically

---

## Display Modes

Access at `/display` on TV screens.

| Mode | Description |
|------|-------------|
| Scoreboard | Live match scores with team names |
| Bracket | Tournament bracket visualization |
| Countdown | Match timer with visual countdown |
| Waiting | Idle screen between matches |
| Winner | Match winner announcement |

TVs can be controlled via:
- iPad input interface (`/input`)
- Admin panel
- External API

---

## External API

Full documentation: [docs/API.md](docs/API.md)

### Authentication
Generate tokens in Admin Panel under API Tokens.

```bash
curl -X GET http://localhost:5000/ext/v1/tournament/1/current \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ext/v1/tournament/{id}` | GET | Tournament details |
| `/ext/v1/tournament/{id}/current` | GET | Current match |
| `/ext/v1/match/{id}/add-point` | POST | Increment score |
| `/ext/v1/match/{id}/set-winner` | POST | Complete match |
| `/ext/v1/display/mode` | POST | Change TV display |
| `/ext/v1/countdown/start` | POST | Start timer |

### Permission Scopes
- `tournament:read` - Read tournament info
- `match:read` / `match:write` - Match operations
- `score:read` / `score:write` - Score operations
- `display:write` - Control displays
- `timer:write` - Timer control

---

## Deployment

### Heroku

```bash
# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Set environment variables
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Deploy
git push heroku main
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | Yes |
| `DATABASE_URL` | Database connection string | No (defaults to SQLite) |
| `FLASK_DEBUG` | Enable debug mode | No |

---

## Development

### Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=app
```

### Code Structure

The application uses Flask Blueprints for modularity:

- **auth** - Login, logout, decorators
- **admin** - Tournament and user management
- **api** - Internal API for frontend
- **external_api** - Token-authenticated external API
- **display** - TV display rendering
- **input** - iPad score input
- **register** - Public team registration

---

## Security

- Password hashing with scrypt
- CSRF protection on all forms
- Session-based authentication for admin
- Token-based authentication for API
- Input sanitization

---

## License

MIT License. See [LICENSE](LICENSE) for details.
