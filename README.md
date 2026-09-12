# FTC EPA Predictor

**Real-time analytics, match prediction, and alliance strategy for FIRST Tech Challenge robotics teams.**

FTC EPA Predictor turns raw FIRST Tech Challenge event data into actionable competitive intelligence: it tracks every team's performance across seasons, predicts match outcomes before they happen, and recommends the best alliance partner at any event — all in a fast, modern web app built for scouts, drive teams, and event organizers.

---

## What it does

- **Team Intelligence** — Look up any FTC team and see its historical EPA (Expected Points Added), match history, and performance trends across seasons.
- **Event Predictions** — For any live or upcoming event, get win-probability predictions for every scheduled match, computed from real EPA data.
- **Alliance Matchmaker** — Given a team, automatically surface the best available alliance partner at an event, scored on complementary auto/teleop/endgame strengths and combined EPA — individually or in batch across an entire alliance selection.
- **Admin Tools** — Authenticated dashboard for managing match data and running matchmaking at scale during live events.

## Why it's interesting

Most scouting tools stop at "here are the stats." FTC EPA Predictor goes further:

- **A real rating system, not a guess.** Match, season, and multi-season historical EPA are computed with recency weighting and opponent-strength adjustment, then converted to win probabilities with an Elo-style logistic model — the same family of math used by chess and FRC-scale scouting systems.
- **Built to run at event speed.** EPA and predictions for an entire event (every team, every match) are computed in parallel (up to 50 concurrent workers), returning full-event predictions in seconds.
- **Engineered like a production system, not a hackathon script.** The app ships with two interchangeable backends: a lightweight FastAPI server for local development, and a complete serverless architecture (AWS Lambda + API Gateway + DynamoDB + EventBridge) for production, with CloudFormation-defined infrastructure and scheduled data sync every 6 hours.
- **Cost-aware by design.** The production data-sync layer uses HTTP conditional requests (`ETag`, `Last-Modified`) against the official FIRST API, achieving a 70–80% cache-hit rate and 60–80% bandwidth savings after warm-up, and only recomputes EPA when underlying match data actually changes.
- **Alliance Matchmaker** is a genuinely novel feature: it doesn't just rank teams by EPA, it recommends *pairings* based on complementary skill profiles — the kind of strategic tool real FTC alliance captains want at Worlds-level events.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, React Router, Material UI, Framer Motion, Recharts |
| Backend (local dev) | FastAPI (Python), served with Uvicorn |
| Backend (production) | AWS Lambda, API Gateway, DynamoDB, EventBridge (CloudFormation-managed) |
| Data source | Official FIRST Tech Challenge Events API |
| Auth / cloud SDK | AWS Amplify |

## Architecture

```
                 ┌────────────────────┐
                 │   React Frontend    │
                 └──────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
     Local Dev Mode               Production Mode
              │                           │
   ┌──────────▼─────────┐     ┌───────────▼────────────┐
   │  FastAPI Server     │     │  API Gateway            │
   │  (server/main.py)   │     │  → Lambda Functions     │
   │  EPA + matchmaking  │     │  → DynamoDB             │
   │  computed on-demand │     │  → EventBridge (6h sync)│
   └──────────┬──────────┘     └───────────┬────────────┘
              │                            │
              └────────────┬───────────────┘
                            ▼
              FIRST Tech Challenge Events API
```

## The EPA Model

For each match, a team's contribution to its alliance's score is weighted by:

1. **Opponent strength** — a stronger opposing alliance boosts the credit given for the same score.
2. **Match importance** — playoff matches are weighted 1.3× versus qualification matches.
3. **Recency** — within a season, later matches count for up to 20% more than early ones.
4. **Multi-season blending** — historical EPA combines seasons with fixed decay weights (e.g. current season 1.0, prior season 0.7, two seasons back 0.5).

Win probability between two alliances is then computed with a logistic (Elo-style) formula:

```
P(red wins) = 1 / (1 + 10^(-(EPA_red - EPA_blue) / 400))
```

## Project Structure

```
FTC_EPA_PREDICTOR/
├── src/                     # React frontend
│   ├── pages/               # Home, Teams, Events, EventDetails, TeamDetails, Admin
│   ├── components/          # Navbar, AllianceMatchmaker, EventMatches, etc.
│   └── services/            # API clients (local + AWS)
├── server/                  # FastAPI backend (local dev)
│   ├── main.py               # REST API
│   ├── epa_calculator.py     # EPA + win probability math
│   ├── epa_parallel.py       # Parallelized event-wide EPA computation
│   └── alliance_matchmaker.py
├── aws/                     # Serverless production backend
│   ├── lambda/               # teams-api, events-api, epa-api, alliance-matchmaker, sync jobs
│   ├── infrastructure/       # CloudFormation templates
│   └── docs/                 # Caching + deployment docs
├── local-dev/               # Docker Compose (Postgres mirror) for offline dev
└── models/                  # Shared data models
```

## API Overview

| Endpoint | Description |
|---|---|
| `GET /api/teams/{season}` | List/search teams for a season |
| `GET /api/teams/{teamNumber}/historical-epa` | Blended multi-season EPA for a team |
| `GET /api/events/{season}` | List events in a season |
| `GET /api/events/{season}/{eventCode}/rankings` | Event rankings |
| `GET /api/matches/{season}/{eventCode}` | All matches at an event |
| `POST /api/event-predictions-epa` | Win-probability predictions for every match at an event |
| `POST /api/match-prediction` | Win probability for an arbitrary matchup |
| `POST /api/teams/batch-historical-epa` | Batch EPA lookup for many teams |
| `POST /api/alliance-matchmaker` | Recommend the best alliance partner for a team |
| `POST /api/alliance-matchmaker/batch` | Batch alliance recommendations across an event |

## Getting Started

### Prerequisites
- Node.js 16+
- Python 3.9+
- A [FIRST Tech Challenge Events API](https://ftc-events.firstinspires.org/api-docs/) username and key

### 1. Frontend
```bash
npm install
npm start
```
Runs at `http://localhost:3000`.

### 2. Backend (local dev)
```bash
cd server
pip install -r requirements.txt
```
Create a `.env` file in `server/`:
```
FTC_API_USERNAME=your_username
FTC_API_KEY=your_api_key
```
Then run:
```bash
uvicorn main:app --reload
```

### 3. (Optional) Deploy the production AWS backend
```bash
cd aws
./deploy.sh dev us-east-1
```
This provisions DynamoDB tables, Lambda functions, API Gateway, and the scheduled sync job via CloudFormation. See [`aws/README.md`](aws/README.md) for the full migration guide.

## Roadmap

- Authentication-gated team scouting notes
- Live match ticker during events
- Mobile app (early exploration in progress)

---

Built for FTC teams who want to walk into an event knowing exactly who to pick, who to beat, and why.
