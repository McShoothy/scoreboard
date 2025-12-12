# Robot Uprising 2v2 Tournament Scoreboard

A Flask web application for managing a 2v2 tournament scoreboard with real-time TV displays, iPad controls, and multi-admin support for the RobotUprising event.

## ⚠️ Security Disclaimer

**This project is NOT secure in any way, shape, or form.** It is designed for local network use only and should never be exposed to the internet. The authentication system uses hardcoded password hashes and there are no security measures in place. Running this on a public server or exposing it to the internet will likely result in your system being compromised.

**I am in no way responsible if you get hacked, lose data, or experience any security incidents.** Use at your own risk.

Python 3.11+
Flask 3.0
License: MIT

## Features

- iPad control interface for entering match results
- TV display system with real-time updates
- QR code TV pairing to associate iPads with TVs
- Real-time updates using Socket.IO across connected devices
- Tournament bracket generation and progression
- Multiple display themes (Dark Orange, Neon Blue, Cyber Green, Purple Haze, Blood Red, Arctic)
- Multi-admin support for multiple iPads
- Match timer with configurable countdown and visual indicators
- Winner announcements with animations

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/scoreboard.git
   cd scoreboard
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python run.py
   ```

5. Open in browser: http://localhost:5000

## Usage Guide

### Endpoints

| URL | Purpose |
|-----|---------|
| `/` | Home page with navigation |
| `/admin` | Tournament and team management |
| `/input` | iPad control interface |
| `/display` | TV display (shows QR code for pairing) |

### Step-by-Step Setup

#### 1. Create Teams (Admin Panel)
- Navigate to `/admin/teams`
- Add your 2v2 teams with team name, player 1, and player 2

#### 2. Create a Tournament
- Go to `/admin/tournaments`
- Create a new tournament and select participating teams
- The bracket is generated automatically

#### 3. Set Up TV Displays
- Open `/display` on each TV browser (Chrome recommended)
- A QR code will appear on the screen

#### 4. Control from iPad
- Open `/input` on your iPad
- Tap "Scan TV" to scan a TV's QR code
- The iPad is now paired with that TV
- Control the display mode, update scores, manage matches

#### 5. Run the Tournament
- Select the current match from iPad
- Use +/- buttons to update scores in real-time
- Complete matches to progress the bracket
- The winning team is displayed with celebrations!

## Network Setup

### Local Network (Recommended for Events)

The server binds to `0.0.0.0:5000` by default, making it accessible on your local network.

1. **Find your computer's IP address:**
   ```bash
   # macOS/Linux
   ifconfig | grep "inet " | grep -v 127.0.0.1
   
   # Windows
   ipconfig
   ```

2. **Connect devices:**
   - iPad: `http://<your-ip>:5000/input`
   - TV: `http://<your-ip>:5000/display`

### Remote Access with ngrok

For remote access or when a local network is not available:

1. **Install ngrok:** https://ngrok.com/download

2. **Start the Flask server:**
   ```bash
   python run.py
   ```

3. **In another terminal, start ngrok:**
   ```bash
   ngrok http 5000
   ```

4. Use the ngrok URL (for example, `https://abc123.ngrok.io`) on all devices.

Note: Free ngrok accounts have connection limits. For production events, consider a paid plan or a local network setup.

## Project Structure

```
scoreboard/
├── app/
│   ├── __init__.py           # Flask app factory with Socket.IO
│   ├── models.py             # Database models (Team, Tournament, Match, etc.)
│   ├── routes.py             # Routes, API endpoints, Socket.IO events
│   ├── utils.py              # Utility functions
│   ├── static/
│   │   └── img/              # Images and logos
│   └── templates/
│       ├── base.html         # Base template
│       ├── index.html        # Home page
│       ├── admin/            # Admin panel templates
│       ├── auth/             # Login templates
│       ├── input/            # iPad control templates
│       └── display/          # TV display templates
├── config.py                 # Configuration (auto-generates secret key)
├── requirements.txt          # Python dependencies
├── run.py                    # Application entry point
└── README.md
```

## API Reference

### Match Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/match/<id>` | GET | Get match details |
| `POST /api/match/<id>/score` | POST | Update match score |
| `POST /api/match/<id>/complete` | POST | Complete match with winner |
| `POST /api/match/<id>/set-current` | POST | Set as current match |

### Display Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/display/state` | GET | Get current display state |
| `POST /api/tv/<code>/control` | POST | Control a specific TV |
| `POST /api/display/theme` | POST | Change display theme |

### Tournament

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/tournament/<id>/bracket` | GET | Get tournament bracket |
| `GET /api/tournament/<id>/next-match` | GET | Get next upcoming match |

## Display Themes

The application includes 6 built-in themes:

| Theme | Description |
|-------|-------------|
| Dark Orange | Default RobotUprising theme |
| Neon Blue | Cyberpunk blue aesthetic |
| Cyber Green | Matrix-style green |
| Purple Haze | Deep purple vibes |
| Blood Red | Intense red theme |
| Arctic | Cool white/blue theme |

Change themes from the iPad control interface.

## Configuration

### Environment Variables (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | Auto-generated |
| `DATABASE_URL` | Database connection string | `sqlite:///tournament.db` |

### config.py

The app auto-generates a secure secret key and stores it in `.secret_key` (gitignored).

## Development

### Running in Debug Mode

```bash
python run.py
```

Debug mode is enabled by default for development.

## Deploying to Heroku

This project can be deployed to Heroku for remote access. The application is configured to use `gunicorn` with the `eventlet` worker to support Socket.IO over WebSockets.

Steps:

1. **Install the Heroku CLI:** https://devcenter.heroku.com/articles/heroku-cli

2. **Login and create an app:**
```bash
heroku login
heroku create your-app-name
```

3. **Add a Heroku Postgres addon (optional):**
```bash
heroku addons:create heroku-postgresql:hobby-dev
```

4. **Set environment variables (recommended):**
```bash
heroku config:set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(16))')"
# If using PostgreSQL, set DATABASE_URL will be provided by the addon automatically
```

5. **Push to Heroku:**
```bash
git push heroku main
heroku ps:scale web=1
```

6. **View logs / open app:**
```bash
heroku logs --tail
heroku open
```

Notes:
- The repository includes a `Procfile` configured as: `web: gunicorn -k eventlet -w 1 run:app`.
- Use the Heroku Postgres `DATABASE_URL` environment variable for production databases. If not set, the application will default to a local SQLite database.
- WebSocket support is enabled through `eventlet` workers (installed via `requirements.txt`).

### Database

SQLite database (`tournament.db`) is created automatically on first run. To reset:

```bash
rm tournament.db
python run.py
```

## Troubleshooting

### TVs showing as offline
- TVs send heartbeats every 30 seconds
- Stale TVs (>2 minutes without heartbeat) are auto-removed
- Refresh the iPad to update TV status

### QR Code not scanning
- Ensure good lighting and camera focus
- Try moving closer/further from the screen
- Manual pairing code entry is available as backup

### Real-time updates not working
- Check that all devices are on the same network
- Verify WebSocket connections in browser console
- Try refreshing the page

### Fullscreen not working on TV
- Chrome may require user interaction before fullscreen
- Click anywhere on the TV page, then refresh

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
