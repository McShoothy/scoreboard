# RobotUprising 2v2 Tournament Scoreboard

## Project Overview
A Flask web application for managing a 2v2 tournament scoreboard and match fixer for the RobotUprising event.

## Features
- **iPad Input Interface**: Touch-friendly interface for entering match results and managing brackets
- **TV Display View**: Large, readable scoreboard display for spectators
- **Real-time Updates**: Live score updates using Socket.IO
- **Tournament Bracket Management**: Create and manage elimination brackets
- **Team Registration**: Add and manage competing teams

## Tech Stack
- Python 3.11+
- Flask (web framework)
- Flask-SocketIO (real-time updates)
- SQLite (database)
- Bootstrap 5 (responsive UI)

## Project Structure
```
scoreboard/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
│       ├── base.html
│       ├── admin/
│       ├── display/
│       └── input/
├── config.py
├── requirements.txt
├── run.py
└── README.md
```

## Running the Application
```bash
pip install -r requirements.txt
python run.py
```

## Endpoints
- `/` - Home page
- `/input` - iPad input interface
- `/display` - TV scoreboard display
- `/admin` - Tournament management
