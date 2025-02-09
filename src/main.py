from fastapi import FastAPI, HTTPException
from pydantic import BaseModel  # Import Pydantic model
import pyodbc
import random
import time
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# ✅ Define Pydantic model for request validation
class GuessRequest(BaseModel):
    rider: str
    row: str
    column: str

# Initialize FastAPI app
app = FastAPI()
# CORS Configuration: Allow both React development ports (5173 and 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Allow multiple origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Azure SQL Connection Details
CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=tcp:smxmuse.database.windows.net;"
    "DATABASE=smxmuse;"
    "UID=smxmuseadmin;"
    "PWD=Anaheim12025!;"
    "Encrypt=yes;TrustServerCertificate=no;"
)

# Store game state globally
game_state = {
    "grid_data": {},
    "used_riders": set(),
    "unanswered_cells": set(),
    "remaining_attempts": 9,
    "rows": [],
    "cols": [],
}

# Define valid row/column criteria
criteria_pool = [
    "450 SX Win", "250 SX Win", "1+ 450 SX Championships", "1+ 250 SX Championships",
    "10+ 450 SX Podiums", "10+ 250 SX Podiums",
    "450 SX Race Winner in 3+ Different Years", "SX Multi-Class Winner", "Non-US SX Winner",
    "450 MX Win", "250 MX Win", "1+ 450 MX Championships", "1+ 250 MX Championships", "10+ 450 MX Podiums",
    "KTM", "HUS", "YAM", "HON", "SUZ", "KAW", "GAS", "10+ 450 SX Wins", "10+ 250 MX Podiums", "2+ 450 SX Championships",
    "2+ 250 SX Championships", "2+ 450 MX Championships", "2+ 250 MX Championships", "Raced in the 1970s", "Raced in the 1980s",
    "Raced in the 1990s", "Raced in the 2000s", "Raced in the 2010s", "Raced in the 2020s", "France SX Winner",
    "Australia SX Winner", "Australia", "France", "United States", "20+ 450 SX Wins", "Anaheim 1 450 SX Winner", "Daytona 450 SX Winner", "Red Bud 450 MX Winner"
]

# Define invalid row-column pairings (redundant or conflicting)
invalid_pairings = {
    "450 SX Win": ["Daytona 450 SX Winner"],
    "Daytona 450 SX Winner": ["450 SX Win"],
    "1+ 450 SX Championships": ["450 SX Win"],
    "450 SX Win": ["1+ 450 SX Championships"],
    "1+ 250 SX Championships": ["250 SX Win"],
    "250 SX Win": ["1+ 250 SX Championships"],
    "1+ 450 MX Championships": ["450 MX Win"],
    "450 MX Win": ["1+ 450 MX Championships"],
    "1+ 250 MX Championships": ["250 MX Win"],
    "250 MX Win": ["1+ 250 MX Championships"],
    "450 SX Win": ["Anaheim 1 450 SX Winner"],
    "Anaheim 1 450 SX Winner": ["450 SX Win"],
    "Raced in the 1990s": ["Raced in the 2020s"],
    "Raced in the 2020s": ["Raced in the 1990s"],    
}

def is_strongly_playable(grid_data: Dict[Tuple[str, str], Set[str]]) -> bool:
    """Validates if a grid is playable based on unique rider distribution."""
    all_riders = set()
    rider_usage = defaultdict(set)

    for cell, riders in grid_data.items():
        all_riders.update(riders)
        for rider in riders:
            rider_usage[rider].add(cell)

    if len(all_riders) < 9:
        return False

    bottleneck_cells = {cell for cell, riders in grid_data.items() if len(riders) <= 8}
    overused_riders = {rider for rider, cells in rider_usage.items() if len(cells) >= 2}

    for cell in bottleneck_cells:
        riders_in_cell = grid_data[cell]
        if all(rider in overused_riders for rider in riders_in_cell):
            return False

    return True

def fetch_riders_for_criterion(criterion: str, conn) -> Set[str]:
    """Fetch riders from Azure SQL that match a given criterion."""
    query = ""

    if criterion == "450 SX Win":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 AND m.Result = 1"
    elif criterion == "250 SX Win":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 2 AND m.Result = 1"
    elif criterion == "10+ 450 SX Wins":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 GROUP BY r.FullName HAVING COUNT(CASE WHEN m.Result = 1 THEN 1 END) >= 10"
    elif criterion == "20+ 450 SX Wins":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 GROUP BY r.FullName HAVING COUNT(CASE WHEN m.Result = 1 THEN 1 END) >= 20"
    elif criterion == "450 MX Win":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN MX_OVERALLS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 AND m.Result = 1"
    elif criterion == "250 MX Win":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN MX_OVERALLS m ON r.RiderID = m.RiderID WHERE m.ClassID = 2 AND m.Result = 1"
    elif criterion == "1+ 450 SX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 1 AND c.ClassID = 1"
    elif criterion == "1+ 250 SX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 1 AND c.ClassID = 2"
    elif criterion == "1+ 450 MX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 2 AND c.ClassID = 1"
    elif criterion == "1+ 250 MX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 2 AND c.ClassID = 2"
    elif criterion == "2+ 450 SX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 1 AND c.ClassID = 1 GROUP BY r.FullName HAVING COUNT(c.Year) >= 2"
    elif criterion == "2+ 250 SX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 1 AND c.ClassID = 2 GROUP BY r.FullName HAVING COUNT(c.Year) >= 2"
    elif criterion == "2+ 450 MX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 2 AND c.ClassID = 1 GROUP BY r.FullName HAVING COUNT(c.Year) >= 2"
    elif criterion == "2+ 250 MX Championships":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN Champions c ON r.RiderID = c.RiderID WHERE c.SportID = 2 AND c.ClassID = 2 GROUP BY r.FullName HAVING COUNT(c.Year) >= 2"
    elif criterion == "10+ 450 SX Podiums":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 GROUP BY r.FullName HAVING COUNT(CASE WHEN m.Result <= 3 THEN 1 END) >= 10"
    elif criterion == "10+ 250 SX Podiums":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 2 GROUP BY r.FullName HAVING COUNT(CASE WHEN m.Result <= 3 THEN 1 END) >= 10"
    elif criterion == "10+ 450 MX Podiums":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN MX_OVERALLS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 GROUP BY r.FullName HAVING COUNT(CASE WHEN m.Result <= 3 THEN 1 END) >= 10"
    elif criterion == "10+ 250 MX Podiums":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN MX_OVERALLS m ON r.RiderID = m.RiderID WHERE m.ClassID = 2 GROUP BY r.FullName HAVING COUNT(CASE WHEN m.Result <= 3 THEN 1 END) >= 10"
    elif criterion == "France SX Winner":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.Result = 1 AND r.Country = 'France'"
    elif criterion == "Australia SX Winner":
        query = "SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.Result = 1 AND r.Country = 'Australia'"
    elif criterion == "SX Multi-Class Winner":
        query = "SELECT FullName FROM (SELECT r.FullName, COUNT(DISTINCT m.ClassID) AS class_wins FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.Result = 1 GROUP BY r.FullName) AS subquery WHERE class_wins > 1"
    elif criterion in ["KTM", "HUS", "YAM", "HON", "SUZ", "KAW", "GAS"]:
        query = f"SELECT DISTINCT r.FullName FROM Rider_List r JOIN RiderBrandList rb ON r.RiderID = rb.RiderID WHERE rb.Brand = '{criterion}'"
    elif criterion in ["Australia", "France", "United States"]:
        query = f"SELECT DISTINCT r.FullName FROM Rider_List r WHERE r.Country = '{criterion}'"
    elif criterion in ["Raced in the 1970s", "Raced in the 1980s", "Raced in the 1990s", "Raced in the 2000s", "Raced in the 2010s", "Raced in the 2020s"]:
        decade_start = int(criterion.split()[-1][:4])
        decade_end = decade_start + 9
    
        query = f"""
        SELECT DISTINCT r.FullName
        FROM Rider_List r
        JOIN SX_MAINS sm ON r.RiderID = sm.RiderID
        JOIN Race_Table rt ON sm.RaceID = rt.RaceID
        WHERE rt.Year BETWEEN {decade_start} AND {decade_end}
        
        UNION
        
        SELECT DISTINCT r.FullName
        FROM Rider_List r
        JOIN MX_OVERALLS mx ON r.RiderID = mx.RiderID
        JOIN Race_Table rt ON mx.RaceID = rt.RaceID
        WHERE rt.Year BETWEEN {decade_start} AND {decade_end}
    """
    elif criterion == "Anaheim 1 450 SX Winner":
        query = f"SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID JOIN Race_Table rt ON m.RaceID = rt.RaceID WHERE m.TrackID = 96 AND rt.Round = 1 AND m.ClassID = 1 AND m.Result = 1"
    elif criterion == "Daytona 450 SX Winner":
        query = f"SELECT DISTINCT r.FullName FROM Rider_List r JOIN SX_MAINS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 AND m.Result = 1 AND m.TrackID = 88"
    elif criterion == "Red Bud 450 MX Winner":
        query = f"SELECT DISTINCT r.FullName FROM Rider_List r JOIN MX_OVERALLS m ON r.RiderID = m.RiderID WHERE m.ClassID = 1 AND m.Result = 1 AND m.TrackID = 3"
        
    if query:
        cursor = conn.cursor()
        cursor.execute(query)
        riders = {row[0] for row in cursor.fetchall()}
        return riders

    return set()


def generate_valid_grid():
    """Attempts to generate a valid grid using real data."""
    with pyodbc.connect(CONN_STR) as conn:
        start_time = time.time()
        print("Starting grid generation...")  # Debugging
        for attempt in range(50):  # Try up to 50 times
            elapsed_time = time.time() - start_time
            if elapsed_time > 60:
                print("Grid generation timed out!")  # Debugging
                raise HTTPException(status_code=500, detail="Grid generation timeout")

            chosen_criteria = random.sample(criteria_pool, 6)
            rows, cols = chosen_criteria[:3], chosen_criteria[3:]
            print(f"Attempt {attempt+1}: Selected Rows: {rows}, Columns: {cols}")  # Debugging

            # Ensure valid row-column pairs
            if any(row in invalid_pairings and col in invalid_pairings[row] for row in rows for col in cols):
                continue  # Skip invalid combinations

            # Fetch riders for the grid
            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }
            print(f"Attempt {attempt+1}: Grid Data Generated")  # Debugging

            if is_strongly_playable(grid_data):
                print("Valid grid found!")  # Debugging
                return rows, cols, grid_data

        raise HTTPException(status_code=500, detail="Failed to generate a playable grid")

@app.get("/")
async def root():
        return {"message":"Hello World"}

@app.get("/api/data")
async def get_data():
        return {"data":"this is your data"}


@app.post("/generate-grid")
def generate_grid():
    """API endpoint to generate a new grid."""
    global game_state
    rows, cols, grid_data = generate_valid_grid()

    game_state.update({
        "grid_data": grid_data,
        "used_riders": set(),
        "unanswered_cells": set(grid_data.keys()),
        "remaining_attempts": 9,
        "rows": rows,
        "cols": cols,
    })

    return {"message": "Grid generated successfully", "rows": rows, "columns": cols}

@app.get("/grid")
def get_grid():
    """API endpoint to retrieve the current grid state."""
    return {
        "rows": game_state["rows"],
        "columns": game_state["cols"],
        "grid_data": {str(k): list(v) for k, v in game_state["grid_data"].items()},
        "remaining_attempts": game_state["remaining_attempts"],
        "used_riders": list(game_state["used_riders"]),
    }

@app.get("/autocomplete")
def autocomplete_riders(query: str):
    """Return a list of rider names matching the query."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT FullName FROM Rider_List WHERE LOWER(FullName) LIKE ?",
                f"%{query.lower()}%",
            )
            riders = [row[0] for row in cursor.fetchall()]
        return {"riders": riders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching autocomplete: {str(e)}")

@app.post("/guess")
def submit_guess(guess: GuessRequest):
    """API endpoint to submit a guess for a grid cell and return rider image."""
    global game_state
    selected_cell = (guess.row, guess.column)

    if selected_cell not in game_state["unanswered_cells"]:
        raise HTTPException(status_code=400, detail="Invalid grid cell selection")

    if guess.rider in game_state["used_riders"]:
        game_state["remaining_attempts"] -= 1
        return {
            "message": f"❌ '{guess.rider}' already used. Try again!",
            "remaining_attempts": game_state["remaining_attempts"]
        }

    if guess.rider not in game_state["grid_data"][selected_cell]:
        game_state["remaining_attempts"] -= 1
        return {
            "message": f"❌ '{guess.rider}' is not a valid answer for {guess.row} | {guess.column}. Try again!",
            "remaining_attempts": game_state["remaining_attempts"]
        }

    # Fetch the rider's image URL from the Rider_Images table
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT image_url FROM Rider_Images WHERE fullname = ?",
                (guess.rider,)
            )
            result = cursor.fetchone()
            image_url = result[0] if result else None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching rider image: {str(e)}")

    # Update game state
    game_state["used_riders"].add(guess.rider)
    game_state["unanswered_cells"].remove(selected_cell)
    game_state["remaining_attempts"] -= 1

    return {
        "message": f"✅ '{guess.rider}' placed in {guess.row} | {guess.column}!",
        "remaining_attempts": game_state["remaining_attempts"],
        "rider": guess.rider,
        "image_url": image_url  # ✅ Returning the image URL
    }

@app.post("/give-up")
def give_up():
    """API endpoint to end the game immediately."""
    global game_state
    game_state["remaining_attempts"] = 0  # Set guesses left to zero

    return {
        "message": "Game ended! You have used all attempts.",
        "remaining_attempts": game_state["remaining_attempts"]
    }

@app.post("/reset")
def reset_game():
    """API endpoint to reset the game."""
    global game_state
    game_state.update({
        "grid_data": {},
        "used_riders": set(),
        "unanswered_cells": set(),
        "remaining_attempts": 9,
        "rows": [],
        "cols": [],
    })
    return {"message": "Game reset successfully"}