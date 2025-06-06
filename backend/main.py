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
from uuid import UUID, uuid4
from fastapi import HTTPException
from fastapi import Request
from dotenv import load_dotenv
import os
from pathlib import Path
import logging

# Load .env.local from the same folder as main.py
env_path = Path(__file__).resolve().parent / ".env.local"
load_dotenv(dotenv_path=env_path)

# print("DEBUG - DB_SERVER:", os.getenv("DB_SERVER"))






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
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://smxmusegrid.azurewebsites.net", "https://purple-plant-009b2850f.6.azurestaticapps.net", "https://smxmuse.com" ],  # Allow multiple origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Azure SQL Connection Details
CONN_STR = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER=tcp:{os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')};"
    "Encrypt=yes;TrustServerCertificate=no;"
    "MARS_Connection=yes;"
)

with open("criteria.json") as f:
    config = json.load(f)
    criteria_pool = config["criteria_pool"]
    invalid_pairings = config["invalid_pairings"]

with open("criteria_queries.json") as f:
    criteria_queries = json.load(f)



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
    query = criteria_queries.get(criterion)
    if not query:
        return set()

    cursor = conn.cursor()
    cursor.execute(query)
    return {row[0] for row in cursor.fetchall()}



def generate_valid_grid(excluded_criteria=None):
    """Attempts to generate a valid grid using real data, excluding certain criteria."""
    with pyodbc.connect(CONN_STR) as conn:
        start_time = time.time()
        # print("Starting grid generation...")  # Debugging
        
        available_criteria = [c for c in criteria_pool if c not in (excluded_criteria or [])]

        for attempt in range(100):  # Try up to 50 times
            elapsed_time = time.time() - start_time
            if elapsed_time > 120:
                print("Grid generation timed out!")  # Debugging
                raise HTTPException(status_code=500, detail="Grid generation timeout")

            chosen_criteria = random.sample(available_criteria, 6)
            rows, cols = chosen_criteria[:3], chosen_criteria[3:]
            # print(f"Attempt {attempt+1}: Selected Rows: {rows}, Columns: {cols}")  # Debugging

            # ✅ Ensure valid row-column pairs
            invalid_found = any(
                (row in invalid_pairings and col in invalid_pairings[row]) or
                (col in invalid_pairings and row in invalid_pairings[col])
                for row in rows for col in cols
            )

            
            if invalid_found:
                print("⚠️ Invalid row-column pairing detected. Retrying...")
                continue

            # ✅ Fetch riders for the grid
            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }
            # print(f"Attempt {attempt+1}: Grid Data Generated")  # Debugging

            if is_strongly_playable(grid_data):
                # print("✅ Valid grid found!")  # Debugging
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

# ✅ New endpoint to generate first, then archive and switch
@app.api_route("/generate-and-archive-switch", methods=["GET", "POST"])
def generate_and_archive_switch():
    today = date.today()

    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # Fetch previously used layout combos
            cursor.execute("""
                SELECT Row1, Row2, Row3, Column1, Column2, Column3 
                FROM dbo.DailyGrids
            """)
            used_position_combos = {
                (row[0], row[1], row[2], row[3], row[4], row[5])
                for row in cursor.fetchall()
            }

            # Fetch active grid
            cursor.execute("""
                SELECT Row1, Row2, Row3, Column1, Column2, Column3 
                FROM dbo.DailyGrids 
                WHERE Status = 'Active'
            """)
            active_grid = cursor.fetchone()
            active_criteria_set = set(active_grid) if active_grid else set()

            # Fetch manually selected override GridPoolID
            cursor.execute("SELECT SettingValue FROM dbo.GridPoolSettings WHERE SettingKey = 'NextGridPoolID'")
            override_row = cursor.fetchone()
            override_id = override_row[0] if override_row else None

            selected = None
            grid_id = None

            # Function to validate grid
            def validate_and_select_grid(grid):
                grid_position_tuple = (grid.Row1, grid.Row2, grid.Row3, grid.Column1, grid.Column2, grid.Column3)
                grid_criteria = {grid.Row1, grid.Row2, grid.Row3, grid.Column1, grid.Column2, grid.Column3}

                if grid_position_tuple in used_position_combos:
                    return False
                if not active_criteria_set.isdisjoint(grid_criteria):
                    return False

                # Build grid data for playability check
                rows = [grid.Row1, grid.Row2, grid.Row3]
                cols = [grid.Column1, grid.Column2, grid.Column3]
                grid_data = {
                    (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                    for row in rows for col in cols
                }

                if is_strongly_playable(grid_data):
                    return (rows, cols)
                else:
                    cursor.execute("UPDATE dbo.GridPool SET Invalid = 1 WHERE GridPoolID = ?", grid.GridPoolID)
                    return False

            # ✅ Try manual override first
            if override_id:
                cursor.execute("""
                    SELECT GridPoolID, Row1, Row2, Row3, Column1, Column2, Column3 
                    FROM dbo.GridPool 
                    WHERE GridPoolID = ? AND IsUsed = 0 AND Invalid = 0
                """, override_id)
                override_grid = cursor.fetchone()

                if override_grid:
                    result = validate_and_select_grid(override_grid)
                    if result:
                        selected = override_grid
                        rows, cols = result
                        grid_id = override_grid.GridPoolID

            # ✅ Fallback to random if override failed or not set
            if not selected:
                cursor.execute("""
                    SELECT TOP 1000 GridPoolID, Row1, Row2, Row3, Column1, Column2, Column3
                    FROM dbo.GridPool
                    WHERE IsUsed = 0 AND Invalid = 0
                    ORDER BY NEWID()
                """)
                for grid in cursor.fetchall():
                    result = validate_and_select_grid(grid)
                    if result:
                        selected = grid
                        rows, cols = result
                        grid_id = grid.GridPoolID
                        break

            if not selected:
                raise HTTPException(status_code=500, detail="No valid, playable grid found.")

            # ✅ Archive old active grid
            cursor.execute("UPDATE dbo.DailyGrids SET Status = 'Archived' WHERE Status = 'Active'")

            # ✅ Insert new active grid
            cursor.execute("""
                INSERT INTO dbo.DailyGrids (GridDate, Row1, Row2, Row3, Column1, Column2, Column3, Status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
            """, today, rows[0], rows[1], rows[2], cols[0], cols[1], cols[2])

            # ✅ Mark as used
            cursor.execute("UPDATE dbo.GridPool SET IsUsed = 1 WHERE GridPoolID = ?", grid_id)

            # ✅ Reset manual override
            cursor.execute("""
                UPDATE dbo.GridPoolSettings 
                SET SettingValue = NULL 
                WHERE SettingKey = 'NextGridPoolID'
            """)


            conn.commit()

        return {
            "message": f"✅ New grid (GridPoolID {grid_id}) generated and old grid archived.",
            "new_rows": rows,
            "new_columns": cols
        }

    except Exception as e:
        try:
            cursor.execute("ROLLBACK TRANSACTION")
        except:
            pass
        logging.error(f"Grid generation or archive failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Grid generation failed: {str(e)}")





from datetime import date

@app.post("/start-game")
def start_game(guest_id: UUID):
    """Ensure each guest can play only once per day with the active grid and reset state when needed."""
    global game_state

    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Check if the guest exists in dbo.Users
            cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
            existing_user = cursor.fetchone()

            # ✅ Insert a new guest if not found
            if not existing_user:
                cursor.execute("""
                    INSERT INTO dbo.Users (GuestID, CreatedAt) VALUES (?, GETDATE())
                """, str(guest_id))
                conn.commit()

                # Retrieve the UserID of the newly created guest
                cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
                existing_user = cursor.fetchone()

            user_id = existing_user[0]

            # ✅ Get today's active GridID
            cursor.execute("""
                SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active';
            """)
            grid_id_result = cursor.fetchone()

            if not grid_id_result:
                raise HTTPException(status_code=500, detail="No active grid found for today.")

            grid_id = grid_id_result[0]

            # ✅ Check if the guest has already played today
            cursor.execute("""
                SELECT GameID FROM dbo.Games WHERE GuestID = ? AND GridID = ?;
            """, (str(guest_id), grid_id))
            existing_game = cursor.fetchone()

            if existing_game:
                # ✅ If a game already exists, ensure the game state is consistent
                if user_id not in game_state or game_state[user_id].get("grid_id") != grid_id:
                   # print(f"🔄 Restoring existing game state for GridID {grid_id}")
                    game_state[user_id] = {
                        "grid_id": grid_id,
                        "remaining_attempts": 9,  # Adjust if needed based on the database
                        "used_riders": set(),  # This should ideally be fetched from UserGuesses
                        "unanswered_cells": set(game_state["grid_data"].keys()),
                    }

                return {
                    "message": "Game already exists",
                    "grid_id": grid_id,
                    "guest_id": str(guest_id),
                    "game_id": existing_game[0],
                }

            # ✅ No existing game → Reset and create fresh game state
            # print(f"🆕 New Grid Detected! Resetting game state for GridID {grid_id}")
            game_state[user_id] = {
                "grid_id": grid_id,
                "remaining_attempts": 9,
                "used_riders": set(),
                "unanswered_cells": set(game_state["grid_data"].keys()),
            }

            return {
                "message": "No game exists yet, will be created on first guess.",
                "grid_id": grid_id,
                "guest_id": str(guest_id),
                "game_id": None  # ✅ No GameID until a guess is made
            }

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

            # print(f"DEBUG: Active Grid ID = {grid_id}")
            # print(f"DEBUG: Rows: {rows}, Columns: {cols}")

            # ✅ Generate answers dynamically instead of using GridAnswers table
            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }

            # print(f"DEBUG: Generated Grid Data: {grid_data}")

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
def submit_guess(guess: GuessRequest, guest_id: UUID):
    global game_state

    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Retrieve UserID associated with the guest
            cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
            user_id_result = cursor.fetchone()
            if not user_id_result:
                raise HTTPException(status_code=404, detail="Guest user not found.")
            user_id = user_id_result[0]

            # ✅ Retrieve active GridID
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active';")
            grid_id_result = cursor.fetchone()
            if not grid_id_result:
                raise HTTPException(status_code=500, detail="No active grid found for today.")
            grid_id = grid_id_result[0]

            # ✅ Retrieve existing GameID for this user and grid
            cursor.execute("SELECT GameID, GuessesMade FROM dbo.Games WHERE UserID = ? AND GridID = ?", (user_id, grid_id))
            game_id_result = cursor.fetchone()

            if not game_id_result:
                # ✅ No game found → Create GameID BEFORE logging the first guess
                cursor.execute("""
                    INSERT INTO dbo.Games (UserID, GuestID, GridID, GuessesMade, Completed, PlayedAt)
                    OUTPUT INSERTED.GameID
                    VALUES (?, ?, ?, 0, 0, GETDATE());
                """, (user_id, str(guest_id), grid_id))
                game_id_result = cursor.fetchone()

                if not game_id_result:
                    raise HTTPException(status_code=500, detail="Failed to create a new game session.")

                game_id = game_id_result[0]
                guesses_made = 0  # ✅ New game starts with 0 guesses
                # print(f"DEBUG: Created new GameID {game_id} for UserID {user_id} and GridID {grid_id}")
            else:
                game_id = game_id_result[0]
                guesses_made = game_id_result[1]  # ✅ Retrieve current guesses made
                print(f"DEBUG: Found existing GameID {game_id} for UserID {user_id} and GridID {grid_id}")

            # ✅ Ensure user has a game session in memory
            if user_id not in game_state:
                game_state[user_id] = {
                    "remaining_attempts": 9,
                    "used_riders": set(),
                    "unanswered_cells": set(game_state["grid_data"].keys()),  # Initialize based on grid
                }

            selected_cell = (guess.row, guess.column)

            print(f"DEBUG: User guessed {guess.rider} for cell ({guess.row}, {guess.column})")

            # ✅ Check if the cell has already been answered
            if selected_cell not in game_state[user_id]["unanswered_cells"]:
                return {
                    "message": f"⚠️ '{guess.rider}' has already been guessed for {guess.row} | {guess.column}!",
                    "remaining_attempts": game_state[user_id]["remaining_attempts"]
                }

            # ✅ Check if the rider has already been used in another cell
            if guess.rider in game_state[user_id]["used_riders"]:
                return {
                    "message": f"❌ '{guess.rider}' has already been used in another cell. Try a different rider!",
                    "remaining_attempts": game_state[user_id]["remaining_attempts"]
                }

            # ✅ Retrieve expected riders for this cell
            if selected_cell in game_state["grid_data"]:
                expected_riders = game_state["grid_data"][selected_cell]
                print(f"DEBUG: Expected correct riders for {selected_cell}: {expected_riders}")
            else:
                return {"error": f"Cell {selected_cell} has no valid riders."}

            # ✅ Normalize input for case-insensitive comparison
            guessed_rider = guess.rider.strip().lower()
            expected_riders_normalized = {rider.strip().lower() for rider in expected_riders}

            is_correct = guessed_rider in expected_riders_normalized
            print(f"DEBUG: is_correct = {is_correct}")

            # ✅ Deduct an attempt for each unique guess (correct or incorrect)
            game_state[user_id]["remaining_attempts"] -= 1
            guesses_made += 1  # ✅ Increment guess count

            # ✅ Insert the guess into `UserGuesses`
            cursor.execute("""
                INSERT INTO UserGuesses (GridID, UserID, GameID, GuestID, RowCriterion, ColumnCriterion, FullName, IsCorrect, GuessedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE());
            """, (grid_id, user_id, game_id, str(guest_id), guess.row, guess.column, guess.rider, int(is_correct)))
            conn.commit()

            # ✅ Step 11: Update GuessesMade and GuessesCorrect in `Games`
            cursor.execute("""
                UPDATE dbo.Games
                SET GuessesMade = GuessesMade + 1,
                    GuessesCorrect = GuessesCorrect + ?
                WHERE GameID = ?;
            """, (1 if is_correct else 0, game_id))
            conn.commit()

            # ✅ Check if game is now completed
            if game_state[user_id]["remaining_attempts"] == 0:
                cursor.execute("UPDATE dbo.Games SET Completed = 1 WHERE GameID = ?", (game_id,))
                conn.commit()
                print(f"DEBUG: Game {game_id} marked as Completed.")

            # ✅ If incorrect, return immediately
            if not is_correct:
                return {
                    "message": f"❌ '{guess.rider}' is incorrect for {guess.row} | {guess.column}!",
                    "remaining_attempts": game_state[user_id]["remaining_attempts"],
                    "rider": None,
                    "image_url": None,
                    "guess_percentage": None
                }

            # ✅ Fetch guess percentage for correct guesses
            cursor.execute("""
                WITH CorrectGuesses AS (
                    SELECT g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName, 
                           COUNT(*) AS GuessCount
                    FROM dbo.UserGuesses g
                    WHERE g.GridID = ? AND g.RowCriterion = ? AND g.ColumnCriterion = ? AND g.IsCorrect = 1
                    GROUP BY g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName
                )
                SELECT (cg.GuessCount * 100.0 / NULLIF(total.TotalGuesses, 0)) AS GuessPercentage
                FROM CorrectGuesses cg
                JOIN (
                    SELECT GridID, RowCriterion, ColumnCriterion, SUM(GuessCount) AS TotalGuesses
                    FROM CorrectGuesses
                    GROUP BY GridID, RowCriterion, ColumnCriterion
                ) total
                ON cg.GridID = total.GridID 
                AND cg.RowCriterion = total.RowCriterion 
                AND cg.ColumnCriterion = total.ColumnCriterion
                WHERE cg.FullName = ?
            """, (grid_id, guess.row, guess.column, guess.rider))

            guess_percentage_result = cursor.fetchall()
            guess_percentage = round(guess_percentage_result[0][0], 2) if guess_percentage_result else 0.0

            # ✅ Fetch rider image for correct guess
            cursor.execute("SELECT ImageURL FROM Rider_List WHERE FullName = ?", (guess.rider,))
            result = cursor.fetchone()
            image_url = result[0] if result else None

            # ✅ Update game state for correct guesses
            game_state[user_id]["used_riders"].add(guess.rider)
            game_state[user_id]["unanswered_cells"].discard(selected_cell)

            print(f"DEBUG: Correct guess! '{guess.rider}' placed in {selected_cell}. Rider now locked.")

            return {
                "message": f"✅ '{guess.rider}' placed in {guess.row} | {guess.column}!",
                "remaining_attempts": game_state[user_id]["remaining_attempts"],
                "rider": guess.rider,
                "image_url": image_url,
                "guess_percentage": guess_percentage
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing guess: {str(e)}")


@app.get("/current-guess-percentage")
def get_current_guess_percentage(grid_id: int, row: str, column: str, rider: str):
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                WITH CorrectGuesses AS (
                    SELECT g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName, 
                           COUNT(*) AS GuessCount
                    FROM dbo.UserGuesses g
                    WHERE g.GridID = ? AND g.RowCriterion = ? AND g.ColumnCriterion = ? AND g.IsCorrect = 1
                    GROUP BY g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName
                )
                SELECT (cg.GuessCount * 100.0 / NULLIF(total.TotalGuesses, 0)) AS GuessPercentage
                FROM CorrectGuesses cg
                JOIN (
                    SELECT GridID, RowCriterion, ColumnCriterion, SUM(GuessCount) AS TotalGuesses
                    FROM CorrectGuesses
                    GROUP BY GridID, RowCriterion, ColumnCriterion
                ) total
                ON cg.GridID = total.GridID 
                AND cg.RowCriterion = total.RowCriterion 
                AND cg.ColumnCriterion = total.ColumnCriterion
                WHERE cg.FullName = ?
            """, (grid_id, row, column, rider))
            result = cursor.fetchone()
            guess_percentage = round(result[0], 2) if result else 0.0
            return {"guess_percentage": guess_percentage}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching guess percentage: {str(e)}")



    

@app.post("/give-up")
def give_up(guest_id: UUID):
    """Ends the game immediately. Ensures a GameID is assigned before finalizing the game."""
    global game_state

    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Retrieve UserID for guest
            cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
            user_id_result = cursor.fetchone()
            if not user_id_result:
                raise HTTPException(status_code=404, detail="Guest user not found.")
            user_id = user_id_result[0]

            # ✅ Retrieve active GridID
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active';")
            grid_id_result = cursor.fetchone()
            if not grid_id_result:
                raise HTTPException(status_code=500, detail="No active grid found for today.")
            grid_id = grid_id_result[0]

            # ✅ Check if a GameID exists
            cursor.execute("""
                SELECT TOP 1 GameID FROM dbo.Games 
                WHERE UserID = ? AND GridID = ? 
                ORDER BY PlayedAt DESC;
            """, (user_id, grid_id))
            game_id_result = cursor.fetchone()

            if not game_id_result:
                # ✅ Create a game if it doesn't exist yet
                cursor.execute("""
                    INSERT INTO dbo.Games (UserID, GuestID, GridID, GuessesMade, Completed, PlayedAt)
                    OUTPUT INSERTED.GameID
                    VALUES (?, ?, ?, 0, 1, GETDATE());
                """, (user_id, str(guest_id), grid_id))
                game_id_result = cursor.fetchone()

                if not game_id_result:
                    raise HTTPException(status_code=500, detail="Failed to create a new game for Give Up.")

                game_id = game_id_result[0]
                print(f"DEBUG: Created new GameID {game_id} for guest {guest_id} on Give Up")
            else:
                game_id = game_id_result[0]
                print(f"DEBUG: Found existing GameID {game_id} for guest {guest_id} on Give Up")

            # ✅ Mark the game as completed in the database
            cursor.execute("""
                UPDATE dbo.Games
                SET Completed = 1
                WHERE GameID = ?;
            """, (game_id,))
            conn.commit()

            # ✅ Ensure the game state reflects game over
            game_state["remaining_attempts"] = 0  

            return {
                "message": "Game ended! You have used all attempts.",
                "remaining_attempts": 0
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing give-up: {str(e)}")


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
def get_game_summary(request: Request):
    """Returns the summary for today's game including stats, popular guesses, and rarity score."""
    try:
        # ✅ Extract guest_id from request parameters
        guest_id = request.query_params.get("guest_id")
        if not guest_id:
            raise HTTPException(status_code=400, detail="Guest ID is required.")

        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Fetch Active Grid ID
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = ?", ('Active',))
            grid_id_result = cursor.fetchone()
            if not grid_id_result:
                raise HTTPException(status_code=404, detail="No active grid found.")
            grid_id = grid_id_result[0]

            # ✅ Fetch Game ID for the specific guest
            cursor.execute("""
                SELECT GameID FROM dbo.Games
                WHERE GridID = ? AND GuestID = ?
            """, (grid_id, guest_id))

            game_id_result = cursor.fetchone()
            if not game_id_result:
                raise HTTPException(status_code=404, detail=f"No GameID found for GridID {grid_id} and GuestID {guest_id}.")
            game_id = game_id_result[0]

            # ✅ Debugging logs
            print(f"DEBUG: Using GridID={grid_id}, GameID={game_id}, GuestID={guest_id}")


            # ✅ Fetch Total Games Played & Average Correct Answers Per Game
            cursor.execute("""
                SELECT COUNT(*) AS TotalGamesPlayed, 
                       CAST(AVG(CAST(GuessesCorrect AS FLOAT)) AS DECIMAL(10,2)) AS AverageScore
                FROM dbo.Games
                WHERE GridID = ? AND Completed = 1;  -- ✅ Count only completed games
            """, (grid_id,))

            
            stats = cursor.fetchone()
            total_games = stats[0] if stats[0] else 0
            average_score = "{:.2f}".format(float(stats[1])) if stats[1] else "0.00"

            # ✅ Fetch Most Guessed Rider Per Cell (Correct Only)
            cursor.execute("""
                WITH CorrectGuesses AS (
                    SELECT 
                        g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName, 
                        COUNT(*) AS GuessCount,
                        RANK() OVER (PARTITION BY g.GridID, g.RowCriterion, g.ColumnCriterion ORDER BY COUNT(*) DESC) AS Rank
                    FROM dbo.UserGuesses g
                    WHERE g.GridID = ? AND g.IsCorrect = 1
                    GROUP BY g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName
                )
                SELECT cg.RowCriterion, cg.ColumnCriterion, cg.FullName, cg.GuessCount, rl.imageurl,
                       (cg.GuessCount * 100.0 / NULLIF(total.TotalGuesses, 0)) AS GuessPercentage
                FROM CorrectGuesses cg
                LEFT JOIN Rider_List rl ON cg.FullName = rl.FullName
                JOIN (
                    SELECT GridID, RowCriterion, ColumnCriterion, SUM(GuessCount) AS TotalGuesses
                    FROM CorrectGuesses
                    GROUP BY GridID, RowCriterion, ColumnCriterion
                ) total
                ON cg.GridID = total.GridID 
                AND cg.RowCriterion = total.RowCriterion 
                AND cg.ColumnCriterion = total.ColumnCriterion
                WHERE cg.Rank = 1;
            """, (grid_id,))

            most_guessed = cursor.fetchall()
            most_guessed_riders = [
                {
                    "row": row[0],
                    "col": row[1],
                    "rider": row[2],
                    "guess_percentage": round(row[5] if row[5] else 0, 2),
                    "image": row[4]
                }
                for row in most_guessed if row[2] and row[2] != ""
            ]

            # ✅ Fetch Percentage of Correct Guesses Per Cell
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

            # ✅ Debugging Game & Grid IDs
            print(f"DEBUG: Using GridID={grid_id}")
            print(f"DEBUG: Using GameID={game_id}")

            # ✅ Fetch Rarity Score
            print(f"DEBUG: Running rarity score query for GridID={grid_id}, GameID={game_id}")

            cursor.execute("""
                WITH CorrectGuesses AS (
                    SELECT 
                        ug.GridID, 
                        ug.RowCriterion, 
                        ug.ColumnCriterion, 
                        ug.FullName, 
                        COUNT(*) AS RiderGuessCount
                    FROM dbo.UserGuesses ug
                    WHERE ug.GridID = ?
                    AND ug.IsCorrect = 1
                    GROUP BY ug.GridID, ug.RowCriterion, ug.ColumnCriterion, ug.FullName
                ),
                TotalGuessesPerCell AS (
                    SELECT 
                        cg.GridID, 
                        cg.RowCriterion, 
                        cg.ColumnCriterion, 
                        SUM(cg.RiderGuessCount) AS TotalCellGuesses
                    FROM CorrectGuesses cg
                    GROUP BY cg.GridID, cg.RowCriterion, cg.ColumnCriterion
                ),
                GuessStats AS (
                    SELECT 
                        cg.RowCriterion,
                        cg.ColumnCriterion,
                        cg.FullName AS GuessedRider,
                        (cg.RiderGuessCount * 100.0 / NULLIF(tgc.TotalCellGuesses, 0)) AS GuessPercentage
                    FROM CorrectGuesses cg
                    JOIN TotalGuessesPerCell tgc
                        ON cg.GridID = tgc.GridID 
                        AND cg.RowCriterion = tgc.RowCriterion 
                        AND cg.ColumnCriterion = tgc.ColumnCriterion
                ),
                UserAnsweredCells AS (
                    SELECT 
                        COUNT(DISTINCT ug.RowCriterion + '-' + ug.ColumnCriterion) AS AnsweredCells,
                        COALESCE(SUM(gs.GuessPercentage), 0) AS TotalGuessedPercentage
                    FROM dbo.UserGuesses ug
                    JOIN GuessStats gs
                        ON ug.RowCriterion = gs.RowCriterion 
                        AND ug.ColumnCriterion = gs.ColumnCriterion 
                        AND ug.FullName = gs.GuessedRider
                    WHERE ug.GameID = ?
                    AND ug.IsCorrect = 1
                )
                SELECT 
                    TotalGuessedPercentage + (100 * (9 - AnsweredCells)) AS GameRarityScore
                FROM UserAnsweredCells;
            """, (grid_id, game_id))

            rarity_score_result = cursor.fetchone()
            rarity_score = round(rarity_score_result[0], 2) if rarity_score_result else 0.0

            print(f"DEBUG: Fetched rarity score = {rarity_score}")

            # ✅ Return Final Summary Data
            return {
                "total_games_played": total_games,
                "average_score": average_score,
                "rarity_score": rarity_score,
                "most_guessed_riders": most_guessed_riders,
                "cell_completion_rates": cell_completion_rates,
            }
            

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")  # ✅ Log the actual error message
        raise HTTPException(status_code=500, detail=f"Error fetching game summary: {str(e)}")
    
@app.post("/populate-grid-pool")
def populate_grid_pool(max_to_generate: int = 1000):
    """Precompute and store valid grids into the GridPool table."""
    from itertools import combinations
    inserted_count = 0

    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()
        all_combinations = list(combinations(criteria_pool, 6))
        random.shuffle(all_combinations)

        for combo in all_combinations:
            rows, cols = combo[:3], combo[3:]

            # Skip invalid combinations
            if any(
                (row in invalid_pairings and col in invalid_pairings[row]) or
                (col in invalid_pairings and row in invalid_pairings[col])
                for row in rows for col in cols
            ):
                continue


            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }

            if is_strongly_playable(grid_data):
                cursor.execute("""
                    INSERT INTO dbo.GridPool (Row1, Row2, Row3, Column1, Column2, Column3)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, rows[0], rows[1], rows[2], cols[0], cols[1], cols[2])
                inserted_count += 1
                conn.commit()

                if inserted_count >= max_to_generate:
                    break

    return {"message": f"✅ Inserted {inserted_count} valid grids into GridPool."}

@app.post("/reload-config")
def reload_config():
    global criteria_pool, invalid_pairings, criteria_queries

    try:
        with open("criteria.json") as f:
            config = json.load(f)
            criteria_pool = config["criteria_pool"]
            invalid_pairings = config["invalid_pairings"]

        with open("criteria_queries.json") as f:
            criteria_queries = json.load(f)

        return {"message": "✅ Config reloaded successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")