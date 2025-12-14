# RobotUprising Scoreboard - External API Documentation

## Base URL
```
http://your-server/ext/v1/
```

## Authentication

All endpoints (except `/health` and `/scopes`) require a Bearer token:

```
Authorization: Bearer <your-token>
```

Create tokens in the Admin Panel: **Admin → API Tokens**

---

## Permission Scopes

| Scope | Description |
|-------|-------------|
| `tournament:read` | Read tournament info |
| `match:read` | Read match details |
| `match:write` | Complete matches, set winners |
| `score:read` | Read scores |
| `score:write` | Update scores, add points |
| `display:write` | Control TV displays |
| `timer:write` | Start/stop timers |
| `team:read` | Read team info |

---

## Endpoints

### Health Check
```http
GET /ext/v1/health
```
No auth required. Returns API status.

---

### Tournament

#### Get Tournament
```http
GET /ext/v1/tournament/{id}
```
**Scope**: `tournament:read`

#### Get Current Match
```http
GET /ext/v1/tournament/{id}/current
```
**Scope**: `match:read`

Returns the currently active match.

#### Get Teams
```http
GET /ext/v1/tournament/{id}/teams
```
**Scope**: `team:read`

---

### Match

#### Get Match Details
```http
GET /ext/v1/match/{id}
```
**Scope**: `match:read`

#### Update Score
```http
POST /ext/v1/match/{id}/score
Content-Type: application/json

{"team1_score": 5, "team2_score": 3}
```
**Scope**: `score:write`

#### Add Point
```http
POST /ext/v1/match/{id}/add-point
Content-Type: application/json

{"team": 1}
```
**Scope**: `score:write`

Increments the score for team 1 or 2 by 1.

#### Auto-Determine Winner
```http
POST /ext/v1/match/{id}/set-winner
Content-Type: application/json

{}
```
**Scope**: `match:write`

Automatically sets winner based on current scores. Use `{"force_team": 1}` to force a specific winner if tied.

#### Complete Match
```http
POST /ext/v1/match/{id}/complete
Content-Type: application/json

{"winner_id": 5}
```
**Scope**: `match:write`

---

### Display Control

#### Set Display Mode
```http
POST /ext/v1/display/mode
Content-Type: application/json

{
  "mode": "scoreboard",
  "tournament_id": 1
}
```
**Scope**: `display:write`

Modes: `waiting`, `scoreboard`, `bracket`, `winner`, `message`

---

### Timer Control

#### Start Countdown
```http
POST /ext/v1/countdown/start
Content-Type: application/json

{
  "tournament_id": 1,
  "duration": 150
}
```
**Scope**: `timer:write`

Duration in seconds. Omit to use tournament default.

---

## Example Usage

### curl
```bash
# Add a point to team 1
curl -X POST http://localhost:5000/ext/v1/match/1/add-point \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"team": 1}'
```

### Python
```python
import requests

TOKEN = "your-token-here"
BASE = "http://localhost:5000/ext/v1"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Get current match
r = requests.get(f"{BASE}/tournament/1/current", headers=HEADERS)
print(r.json())

# Add point
r = requests.post(f"{BASE}/match/1/add-point", 
                  headers=HEADERS, 
                  json={"team": 1})
print(r.json())
```

---

## Error Responses

```json
{"error": "Invalid or expired token"}  // 401
{"error": "Token lacks required permission: score:write"}  // 403
{"error": "Match not found"}  // 404
{"error": "Match is already completed"}  // 400
```

---

## Rate Limits

Currently no rate limits. Be reasonable with request frequency.

---

## Real-Time Updates

Score updates and match completions emit Socket.IO events to all connected displays. Your changes will appear on TV screens instantly.
