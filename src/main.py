from fastapi import FastAPI, HTTPException
from pydantic import BaseModel  # Import Pydantic model
import pyodbc
import random
import time
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import json
from datetime import date
from datetime import datetime


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

# ✅ Store game state globally
game_state = {
    "grid_id": None,
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
    "Red Bud 450 MX Winner": ["450 MX Win"],
    "450 MX Win": ["Red Bud 450 MX Winner"],
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

            # ✅ Ensure valid row-column pairs (Fix Here)
            invalid_found = any(
                row in invalid_pairings and col in invalid_pairings[row] for row in rows for col in cols
            )
            
            if invalid_found:
                print("⚠️ Invalid row-column pairing detected. Retrying...")
                continue  # Skip and regenerate grid

            # ✅ Fetch riders for the grid
            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }
            print(f"Attempt {attempt+1}: Grid Data Generated")  # Debugging

            if is_strongly_playable(grid_data):
                print("✅ Valid grid found!")  # Debugging
                return rows, cols, grid_data

        raise HTTPException(status_code=500, detail="Failed to generate a playable grid")


@app.get("/")
async def root():
        return {"message":"Hello World"}

@app.get("/api/data")
async def get_data():
        return {"data":"this is your data"}


from datetime import date
import json
import pyodbc
from fastapi import FastAPI, HTTPException

@app.post("/generate-grid")
def generate_grid():
    """API endpoint to generate a new grid for today and store it in the database."""
    global game_state

    today = date.today()

    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            
            # Check if a grid for today already exists
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE GridDate = ?", today)
            existing_grid = cursor.fetchone()

            if existing_grid:
                raise HTTPException(status_code=400, detail="A grid for today already exists.")

            # Generate the grid data
            rows, cols, grid_data = generate_valid_grid()

            # Serialize grid_data
            serialized_grid = {f"{row}|{col}": list(riders) for (row, col), riders in grid_data.items()}
            serialized_grid_json = json.dumps(serialized_grid)

            # Insert the new grid into the DailyGrids table
            insert_query = """
            INSERT INTO dbo.DailyGrids (GridDate, Row1, Row2, Row3, Column1, Column2, Column3, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Active');
            """
            cursor.execute(insert_query, today, rows[0], rows[1], rows[2], cols[0], cols[1], cols[2])
            conn.commit()

            # Retrieve the new GridID
            cursor.execute("SELECT TOP 1 GridID FROM dbo.DailyGrids WHERE GridDate = ? ORDER BY GridID DESC;", today)
            grid_id = cursor.fetchone()

            if not grid_id:
                raise HTTPException(status_code=500, detail="Error retrieving GridID after insert.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving grid: {str(e)}")

    # Update the game state
    game_state.update({
        "grid_id": grid_id[0],
        "grid_data": grid_data,
        "used_riders": set(),
        "unanswered_cells": set(grid_data.keys()),
        "remaining_attempts": 9,
        "rows": rows,
        "cols": cols,
    })

    return {"message": "Grid generated successfully", "rows": rows, "columns": cols, "grid_id": grid_id[0]}

from datetime import date

@app.post("/start-game")
def start_game(user_id: int):
    user_id = int(user_id)  # Ensure it's an integer
    """Ensures each user can play only once per day with the active grid."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            
            # ✅ Get today's active GridID from DailyGrids
            cursor.execute("""
    SELECT GridID, Row1, Row2, Row3, Column1, Column2, Column3
    FROM dbo.DailyGrids
    WHERE Status = 'Active';
""")

            
            grid = cursor.fetchone()
            if not grid:
                raise HTTPException(status_code=500, detail="No active grid found for today.")
            
            grid_id = grid[0]
            rows = [grid[1], grid[2], grid[3]]
            cols = [grid[4], grid[5], grid[6]]

            # ✅ Check if user has already played today
            cursor.execute("""
                SELECT COUNT(*) FROM dbo.Games 
                WHERE UserID = ? AND GridID = ?;
            """, user_id, grid_id)
            
            already_played = cursor.fetchone()[0] > 0
            if already_played:
                raise HTTPException(status_code=400, detail="You have already played today!")

            # ✅ Create a new game session for the user
            cursor.execute("""
                INSERT INTO dbo.Games (UserID, GridID, GuessesMade, Completed, Score, PlayedAt)
                VALUES (?, ?, 0, 0, 0, GETDATE());
            """, user_id, grid_id)
            conn.commit()

            # ✅ Ensure unanswered cells are set
            unanswered_cells = {(row, col) for row in rows for col in cols}

            # ✅ Store active GridID in game_state
            game_state["grid_id"] = grid_id

            # ✅ Initialize game state for this user
            game_state[user_id] = {
                "remaining_attempts": 9,  
                "used_riders": set(),
                "unanswered_cells": unanswered_cells,
            }

            print(f"DEBUG: Unanswered cells initialized: {unanswered_cells}")

            return {"message": "Game started successfully!", "grid_id": grid_id, "unanswered_cells": list(unanswered_cells)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting game: {str(e)}")




@app.get("/grid")
def get_grid():
    """Fetch today's active grid from DailyGrids and generate valid answers dynamically."""
    global game_state  # Ensure game_state is accessible

    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # Fetch today's active grid
            cursor.execute("""
                SELECT GridID, Row1, Row2, Row3, Column1, Column2, Column3
                FROM dbo.DailyGrids
                WHERE Status = 'Active';
            """)
            grid = cursor.fetchone()

            if not grid:
                raise HTTPException(status_code=404, detail="No active grid found for today.")

            grid_id = grid[0]
            rows, cols = [grid[1], grid[2], grid[3]], [grid[4], grid[5], grid[6]]

            print(f"DEBUG: Active Grid ID = {grid_id}")
            print(f"DEBUG: Rows: {rows}, Columns: {cols}")

            # ✅ Generate answers dynamically instead of using GridAnswers table
            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }

            print(f"DEBUG: Generated Grid Data: {grid_data}")

            game_state.update({
                "grid_id": grid_id,
                "rows": rows,
                "cols": cols,
                "grid_data": grid_data,  # ✅ Use dynamically generated answers
                "unanswered_cells": set(grid_data.keys()),
                "remaining_attempts": 9,
                "used_riders": set(),
            })

            return {
                "grid_id": grid_id,
                "rows": rows,
                "columns": cols,
                "grid_data": {str(k): list(v) for k, v in grid_data.items()},
                "remaining_attempts": game_state["remaining_attempts"],
                "used_riders": list(game_state["used_riders"]),
            }

    except Exception as e:
        return {"error": str(e)}


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
def submit_guess(guess: GuessRequest, user_id: int):
    """Submit a guess and update stats."""
    global game_state  # Ensure game_state is global

    # ✅ Ensure user has a game session
    if user_id not in game_state:
        return {"detail": "Game session not found. Start a new game first."}

    selected_cell = (guess.row, guess.column)

    print(f"DEBUG: User guessed {guess.rider} for cell ({guess.row}, {guess.column})")

    # ✅ Check if the cell has already been answered correctly
    if selected_cell not in game_state[user_id]["unanswered_cells"]:
        return {
            "message": f"⚠️ '{guess.rider}' has already been guessed for {guess.row} | {guess.column}!",
            "remaining_attempts": game_state[user_id]["remaining_attempts"]
        }

    # ✅ Check if the rider has already been used elsewhere in the game
    if guess.rider in game_state[user_id]["used_riders"]:
        return {
            "message": f"❌ '{guess.rider}' has already been used in another cell. Try a different rider!",
            "remaining_attempts": game_state[user_id]["remaining_attempts"]
        }

    # ✅ Debugging: Print out expected riders for this cell
    if selected_cell in game_state["grid_data"]:
        expected_riders = game_state["grid_data"][selected_cell]
        print(f"DEBUG: Expected correct riders for {selected_cell}: {expected_riders}")
    else:
        print(f"ERROR: No riders found for {selected_cell}. This should not happen!")
        return {"error": f"Cell {selected_cell} has no valid riders."}

    # ✅ Normalize input to avoid casing/whitespace mismatches
    guessed_rider = guess.rider.strip().lower()
    expected_riders_normalized = {rider.strip().lower() for rider in expected_riders}

    print(f"DEBUG: Normalized guessed rider: {guessed_rider}")
    print(f"DEBUG: Normalized expected riders: {expected_riders_normalized}")

    # ✅ Check if the guessed rider is correct
    is_correct = guessed_rider in expected_riders_normalized
    print(f"DEBUG: is_correct = {is_correct}")

    # ✅ Deduct an attempt for each unique guess (correct or incorrect)
    game_state[user_id]["remaining_attempts"] -= 1

    # ✅ Always Insert Guess into `UserGuesses`
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Fetch GridID
            cursor.execute("""
                SELECT GridID FROM dbo.DailyGrids 
                WHERE Status = 'Active';
            """)
            grid_id_result = cursor.fetchone()

            if not grid_id_result:
                print("ERROR: No active grid found!")
                raise HTTPException(status_code=500, detail="No active grid found for today.")

            grid_id = grid_id_result[0]

            cursor.execute("""
                INSERT INTO UserGuesses (GridID, UserID, RowCriterion, ColumnCriterion, FullName, IsCorrect)
                VALUES (?, ?, ?, ?, ?, ?)
            """, grid_id, user_id, guess.row, guess.column, guess.rider, int(is_correct))

            conn.commit()
    except Exception as e:
        print(f"ERROR: Database error while inserting guess: {e}")
        return {"error": f"Database error: {str(e)}"}

    # ✅ If incorrect, return immediately
    if not is_correct:
        print(f"DEBUG: Incorrect guess for {selected_cell}. Returning error response.")
        return {
            "message": f"❌ '{guess.rider}' is incorrect for {guess.row} | {guess.column}!",
            "remaining_attempts": game_state[user_id]["remaining_attempts"],
            "rider": None,
            "image_url": None,
            "guess_percentage": None
        }

    # ✅ Fetch rider image for correct guess
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT image_url FROM Rider_Images WHERE fullname = ?", (guess.rider,))
            result = cursor.fetchone()
            image_url = result[0] if result else None
    except Exception as e:
        print(f"ERROR: Database error while fetching rider image: {e}")
        image_url = None

    # ✅ Update game state (mark cell as answered & rider as used)
    game_state[user_id]["used_riders"].add(guess.rider)  # 🚨 Rider is now locked out
    game_state[user_id]["unanswered_cells"].discard(selected_cell)  # 🚨 Cell is now locked out

    print(f"DEBUG: Correct guess! '{guess.rider}' placed in {selected_cell}. Rider now locked.")

    return {
        "message": f"✅ '{guess.rider}' placed in {guess.row} | {guess.column}!",
        "remaining_attempts": game_state[user_id]["remaining_attempts"],
        "rider": guess.rider,
        "image_url": image_url
    }



@app.post("/give-up")
def give_up():
    """End the game immediately."""
    global game_state  # Declare game_state as global
    game_state["remaining_attempts"] = 0  # Set remaining attempts to zero

    return {
        "message": "Game ended! You have used all attempts.",
        "remaining_attempts": game_state["remaining_attempts"]
    }

@app.post("/reset")
def reset_game():
    """Reset the game state."""
    global game_state  # Declare game_state as global

    game_state.update({
        "grid_id": None,
        "grid_data": {},
        "used_riders": set(),
        "unanswered_cells": set(),
        "remaining_attempts": 9,
        "rows": [],
        "cols": [],
    })
    return {"message": "Game reset successfully"}


@app.get("/game-summary")
def get_game_summary():
    """Returns the summary for today's game including stats, popular guesses, and rarity score."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Fetch Active Grid ID
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = ?", ('Active',))
            grid_id_result = cursor.fetchone()
            if not grid_id_result:
                raise HTTPException(status_code=404, detail="No active grid found.")
            grid_id = grid_id_result[0]

            # ✅ Most Guessed Rider Per Cell
            cursor.execute("""
                WITH RankedGuesses AS (
                    SELECT 
                        g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName, 
                        COUNT(*) AS GuessCount,
                        RANK() OVER (PARTITION BY g.GridID, g.RowCriterion, g.ColumnCriterion ORDER BY COUNT(*) DESC) AS Rank
                    FROM dbo.UserGuesses g
                    WHERE g.GridID = ?
                    GROUP BY g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName
                )
                SELECT rg.RowCriterion, rg.ColumnCriterion, rg.FullName, rg.GuessCount,
                       (rg.GuessCount * 100.0 / NULLIF(total.TotalGuesses, 0)) AS GuessPercentage
                FROM RankedGuesses rg
                JOIN (
                    SELECT GridID, RowCriterion, ColumnCriterion, SUM(GuessCount) AS TotalGuesses
                    FROM RankedGuesses
                    GROUP BY GridID, RowCriterion, ColumnCriterion
                ) total 
                ON rg.GridID = total.GridID 
                AND rg.RowCriterion = total.RowCriterion 
                AND rg.ColumnCriterion = total.ColumnCriterion
                WHERE rg.Rank = 1;
            """, (grid_id,))
            most_guessed = cursor.fetchall()
            most_guessed_riders = [
                {"row": row[0], "col": row[1], "rider": row[2], "guess_percentage": round(row[4] if row[4] else 0, 2)}
                for row in most_guessed
            ]

            # ✅ Percentage of Correct Guesses Per Cell
            cursor.execute("""
                SELECT g.RowCriterion, g.ColumnCriterion, 
                       COUNT(CASE WHEN g.IsCorrect = 1 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS CorrectPercentage
                FROM dbo.UserGuesses g
                WHERE g.GridID = ?
                GROUP BY g.RowCriterion, g.ColumnCriterion;
            """, (grid_id,))
            correct_percents = cursor.fetchall()
            cell_completion_rates = [
                {"row": row[0], "col": row[1], "completion_percentage": round(row[2] if row[2] else 0, 2)}
                for row in correct_percents
            ]

            # ✅ Total Games Played & Average Correct Answers Per Game
            query = f"""
                SELECT COUNT(DISTINCT g.UserID) AS TotalGamesPlayed, 
                       AVG(GameScores.CorrectGuesses) AS AverageScore
                FROM (
                    SELECT ug.UserID, COUNT(*) AS CorrectGuesses
                    FROM dbo.UserGuesses ug
                    WHERE ug.GridID = {grid_id}
                    AND ug.IsCorrect = 1
                    GROUP BY ug.UserID
                ) AS GameScores
                JOIN dbo.Games g ON g.UserID = GameScores.UserID
                WHERE g.GridID = {grid_id};
            """
            print("DEBUG: Running SQL Query:\n", query)  # ✅ See actual query being run
            cursor.execute(query)  # ✅ Execute as formatted string
            stats = cursor.fetchone()
            total_games = stats[0] if stats[0] else 0
            average_score = round(stats[1], 2) if stats[1] else 0

            # ✅ Rarity Score Calculation (Sum of Correct Guess Percentages Per Player)
            cursor.execute("""
                WITH CellGuessCounts AS (
                    SELECT 
                        ug.GridID, ug.RowCriterion, ug.ColumnCriterion, ug.FullName, ug.UserID,
                        COUNT(*) AS RiderGuessCount
                    FROM dbo.UserGuesses ug
                    WHERE ug.GridID = ?
                    AND ug.IsCorrect = 1
                    GROUP BY ug.GridID, ug.RowCriterion, ug.ColumnCriterion, ug.FullName, ug.UserID
                ),
                TotalCorrectGuesses AS (
                    SELECT 
                        cgc.GridID, cgc.RowCriterion, cgc.ColumnCriterion, 
                        SUM(cgc.RiderGuessCount) AS TotalCellGuesses
                    FROM CellGuessCounts cgc
                    GROUP BY cgc.GridID, cgc.RowCriterion, cgc.ColumnCriterion
                ),
                GuessStats AS (
                    SELECT 
                        cgc.UserID,
                        cgc.RowCriterion,
                        cgc.ColumnCriterion,
                        cgc.FullName AS GuessedRider,
                        (cgc.RiderGuessCount * 100.0 / NULLIF(tcg.TotalCellGuesses, 0)) AS GuessPercentage
                    FROM CellGuessCounts cgc
                    JOIN TotalCorrectGuesses tcg
                        ON cgc.GridID = tcg.GridID 
                        AND cgc.RowCriterion = tcg.RowCriterion 
                        AND cgc.ColumnCriterion = tcg.ColumnCriterion
                )
                SELECT gs.UserID, SUM(gs.GuessPercentage) AS RarityScore
                FROM GuessStats gs
                GROUP BY gs.UserID;
            """, (grid_id,))
            rarity_scores = cursor.fetchall()
            rarity_scores_dict = {row[0]: round(row[1] if row[1] else 0, 2) for row in rarity_scores}

            return {
                "most_guessed_riders": most_guessed_riders,
                "cell_completion_rates": cell_completion_rates,
                "total_games_played": total_games,
                "average_score": average_score,
                "rarity_scores": rarity_scores_dict
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching game summary: {str(e)}")




