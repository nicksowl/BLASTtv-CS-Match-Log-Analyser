# BLASTtv CS Match Log Analyser

## Overview

This project takes **CS match server log `.txt` files** as input, extracts and analyses key match events with a **Python/FastAPI backend**, exports structured **JSON**, and displays everything in a **React (Vite + TypeScript + MUI) SPA**.

---

## Run App in Docker (Demo)

1.	Make sure Docker is installed and running
2.	Make entrypoint executable
    ```bash
    chmod +x docker/entrypoint.sh
3.	Build container
    ```bash
    docker build -t blast-cs-match-log-analyser .
4. Run container (mount local data/ into the container)
    ```bash
    docker run --rm -p 8000:8000 \
    -v "$(pwd)/data:/app/data" \
    blast-cs-match-log-analyser
5.	Access app at http://0.0.0.0:8000

---

## Process Notes

	•	Starting point is a CS match server logs .txt file.
	•	Backend (Python): Data extraction, manipulation, analysis, JSON export, and FastAPI serving.
	•	    Uses regex for parsing.
	•	    Extraction flow:
	•	        Extract key events marked as "FACEIT" (used as reference for further extraction).
	•	        Extract match + round events and sort by round.
	•	        Extract team roster and accolade events.
	•	        Extend/expand round events, focusing on kills and some round statistics (includes analysis).
	•	        Serve JSON for frontend.
	•	    Initially started with pandas/Streamlit, but not implemented.
	•	Frontend (Vite + TS + React + MUI): SPA app that loads and parses JSON.
	•	    Uses loadJson and parseMatch to provide data to the React app.

---

## Run Production (Local)

### Backend

1. Create a Python virtual environment
   ```bash
   python -m venv .venv
2.	Activate the environment
    ```bash
    source .venv/bin/activate  # macOS/Linux
    # .venv\Scripts\activate   # Windows
3.	Install dependencies
    ```bash
    pip install -r requirements.txt
4. Create match JSON files for the frontend
    ```bash
    python src/blastlog/parse_faceit.py && \
    python src/blastlog/parse_match_start_end_roster_accolade.py && \
    python src/blastlog/parse_round_events.py && \
    python src/blastlog/extend_round_events.py
5. Serve backend (FastAPI)
    ```bash
    uvicorn src.fastapi.app.main:app --reload --port 8000

### Frontend

1.	Go to the frontend directory
    ```bash
    cd frontend/
2.	Install node packages
    ```bash
    npm install
3.	Run the app
    ```bash
    npm run dev

---

## Tech Stack

Backend:
	•	Python
	•	FastAPI
	•	Uvicorn

Frontend:
	•	Vite
	•	TypeScript
	•	React
	•	Material UI (MUI)