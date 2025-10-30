from fastapi import FastAPI, HTTPException
from pydantic import BaseModel  # Import Pydantic model
import pyodbc
import random
import time
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import json
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4
from fastapi import HTTPException
from fastapi import Request
from dotenv import load_dotenv
import os
from pathlib import Path
import logging
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import EmailStr, BaseModel
from better_profanity import profanity
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, Query
from typing import Optional

# ✅ Load criteria_queries
with open("criteria_queries.json", "r", encoding="utf-8") as f:
    criteria_queries = json.load(f)


pyodbc.pooling = True

rider_cache = {}

# Load .env.local from the same folder as main.py
env_path = Path(__file__).resolve().parent / ".env.local"
load_dotenv(dotenv_path=env_path)

# print("DEBUG - DB_SERVER:", os.getenv("DB_SERVER"))



class LoginRequest(BaseModel):
    email_or_username: str
    password: str
    remember_me: bool = False
    guest_id: Optional[str] = None


# ✅ Define Pydantic model for request validation
class GuessRequest(BaseModel):
    rider: str
    row: str
    column: str
    grid_id: int = None  # ✅ Add this

# Initialize FastAPI app
app = FastAPI()
# CORS Configuration: Allow both React development ports (5173 and 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000", "https://smxmusegrid.azurewebsites.net", "https://purple-plant-009b2850f.6.azurestaticapps.net", "https://smxmuse.com" ],  # Allow multiple origins
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

profanity.load_censor_words()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 30 days default

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def resolve_all_user_ids(guest_id: UUID, conn) -> Tuple[List[int], List[str]]:
    cursor = conn.cursor()
    cursor.execute("SELECT Username FROM dbo.Users WHERE GuestID = ?", str(guest_id))
    result = cursor.fetchone()
    if not result or result[0] is None:
        cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
        row = cursor.fetchone()
        return ([row[0]] if row else [], [str(guest_id)])
    
    username = result[0]
    cursor.execute("SELECT UserID, GuestID FROM dbo.Users WHERE Username = ?", (username,))
    rows = cursor.fetchall()
    user_ids = [r[0] for r in rows]
    guest_ids = [str(r[1]) for r in rows]
    return user_ids, guest_ids


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

def fetch_riders_for_criterion(criterion: str, conn) -> set:
    """Return a set of FullNames for a given criterion using rider cache if available."""
    if criterion in rider_cache:
        return rider_cache[criterion]

    # Run query
    query = criteria_queries.get(criterion)
    if not query:
        return set()

    cursor = conn.cursor()
    cursor.execute(query)
    result = {row[0] for row in cursor.fetchall()}
    rider_cache[criterion] = result  # ✅ Cache result
    return result




def generate_valid_grid(excluded_criteria=None):
    """Attempts to generate a valid grid using real data, excluding certain criteria."""
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    try:
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

    finally:
        cursor.close()
        conn.close()

@app.get("/")
async def root():
        return {"message":"Hello World"}

@app.get("/api/data")
async def get_data():
        return {"data":"this is your data"}


# ✅ New endpoint to generate first, then archive and switch
@app.api_route("/generate-and-archive-switch", methods=["GET", "POST"])
def generate_and_archive_switch():
    today = date.today()
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
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

    finally:
        cursor.close()
        conn.close()

class RegisterRequest(BaseModel):
    guest_id: UUID
    email: EmailStr
    username: str
    password: str
    first_name: str
    last_name: str

def is_valid_password(password: str):
    return len(password) >= 8 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)

def resolve_all_user_ids(guest_id: UUID, conn) -> Tuple[List[int], List[str]]:
    cursor = conn.cursor()
    cursor.execute("SELECT Username FROM dbo.Users WHERE GuestID = ?", str(guest_id))
    result = cursor.fetchone()
    if not result or result[0] is None:
        cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
        row = cursor.fetchone()
        return ([row[0]] if row else [], [str(guest_id)])
    
    username = result[0]
    cursor.execute("SELECT UserID, GuestID FROM dbo.Users WHERE Username = ?", (username,))
    rows = cursor.fetchall()
    user_ids = [r[0] for r in rows]
    guest_ids = [str(r[1]) for r in rows]
    return user_ids, guest_ids


@app.post("/register")
def register_user(payload: RegisterRequest):
    trace = str(uuid4())
    guest_id = str(payload.guest_id).strip()
    email = (payload.email or "").strip().lower()
    username = (payload.username or "").strip().lower()
    password = payload.password or ""
    first_name = (payload.first_name or "").strip()
    last_name = (payload.last_name or "").strip()

    if profanity.contains_profanity(username):
        raise HTTPException(status_code=400, detail={"code": "SIGNUP_BAD_USERNAME", "message": "Inappropriate username", "trace": trace})

    if not is_valid_password(password):
        raise HTTPException(status_code=400, detail={"code": "SIGNUP_WEAK_PASSWORD", "message": "Password must be at least 8 characters and contain a letter and a number", "trace": trace})

    hashed_pw = hash_password(password)

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        # --- 1) Ensure a shell row exists for this guest
        cursor.execute("SELECT UserID, Username, HashedPassword FROM dbo.Users WHERE GuestID = ?", (guest_id,))
        guest_row = cursor.fetchone()

        if not guest_row:
            cursor.execute("INSERT INTO dbo.Users (GuestID, CreatedAt) VALUES (?, GETDATE())", (guest_id,))
            conn.commit()
            cursor.execute("SELECT UserID, Username, HashedPassword FROM dbo.Users WHERE GuestID = ?", (guest_id,))
            guest_row = cursor.fetchone()

        if not guest_row:
            raise HTTPException(status_code=500, detail={"code": "SIGNUP_NO_SHELL", "message": "Failed to create guest user for registration", "trace": trace})

        # If this guest already has a completed registration (real account row),
        # treat it as "already registered" (defensive: check password presence too).
        if guest_row[1] is not None and guest_row[2] is not None:
            raise HTTPException(status_code=400, detail={"code": "SIGNUP_ALREADY_REGISTERED", "message": "This guest ID already has a registered account", "trace": trace})

        # --- 2) Enforce uniqueness only among REAL accounts
        cursor.execute("""
            SELECT 1 FROM dbo.Users
            WHERE LOWER(Email) = ? AND HashedPassword IS NOT NULL
        """, (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail={"code": "SIGNUP_EMAIL_TAKEN", "message": "Email already in use", "trace": trace})

        cursor.execute("""
            SELECT 1 FROM dbo.Users
            WHERE LOWER(Username) = ? AND HashedPassword IS NOT NULL
        """, (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail={"code": "SIGNUP_USERNAME_TAKEN", "message": "Username already taken", "trace": trace})

        # (Optional) Log presence of shells with same identifiers, but allow proceed
        # You can flip this to a hard error if desired.
        cursor.execute("SELECT COUNT(*) FROM dbo.Users WHERE LOWER(Email) = ? AND HashedPassword IS NULL", (email,))
        shell_emails = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM dbo.Users WHERE LOWER(Username) = ? AND HashedPassword IS NULL", (username,))
        shell_usernames = cursor.fetchone()[0] or 0
        # If you want to surface in logs, you can print/log here.

        # --- 3) Promote this guest shell to a real account (update-in-place)
        cursor.execute("""
            UPDATE dbo.Users
            SET Email = ?, Username = ?, HashedPassword = ?, CreatedAt = GETDATE(),
                FirstName = ?, LastName = ?
            WHERE GuestID = ?
        """, (email, username, hashed_pw, first_name, last_name, guest_id))
        conn.commit()

        cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", (guest_id,))
        user_id = cursor.fetchone()[0]

        token = create_access_token(data={"sub": str(user_id), "username": username})
        return {"access_token": token, "token_type": "bearer", "trace": trace}

    except pyodbc.Error:
        raise HTTPException(status_code=500, detail={"code": "SIGNUP_DB_ERROR", "message": "Database error", "trace": trace})
    finally:
        cursor.close()
        conn.close()



from uuid import UUID, uuid4
from fastapi import HTTPException
import pyodbc

@app.post("/login")
def login_user(payload: LoginRequest):
    trace = str(uuid4())  # for log correlation
    identifier = (payload.email_or_username or "").strip().lower()
    password = payload.password or ""
    guest_id = getattr(payload, "guest_id", None)

    if guest_id:
        try:
            guest_id = UUID(str(guest_id).strip())
        except ValueError:
            guest_id = None  # ignore bad guest ids

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        # --- 1) Count real vs shell rows for diagnostics
        if "@" in identifier:
            cursor.execute("""
                SELECT
                  SUM(CASE WHEN HashedPassword IS NOT NULL THEN 1 ELSE 0 END) AS RealCnt,
                  SUM(CASE WHEN HashedPassword IS NULL THEN 1 ELSE 0 END)     AS ShellCnt
                FROM dbo.Users WHERE LOWER(Email) = ?
            """, (identifier,))
        else:
            cursor.execute("""
                SELECT
                  SUM(CASE WHEN HashedPassword IS NOT NULL THEN 1 ELSE 0 END) AS RealCnt,
                  SUM(CASE WHEN HashedPassword IS NULL THEN 1 ELSE 0 END)     AS ShellCnt
                FROM dbo.Users WHERE LOWER(Username) = ?
            """, (identifier,))
        counts = cursor.fetchone()
        real_cnt = (counts[0] or 0) if counts else 0
        shell_cnt = (counts[1] or 0) if counts else 0

        # --- 2) Fetch a real account row only (avoid shells)
        if "@" in identifier:
            cursor.execute("""
                SELECT TOP 1 UserID, HashedPassword, Username
                FROM dbo.Users
                WHERE LOWER(Email) = ? AND HashedPassword IS NOT NULL
                ORDER BY UserID DESC
            """, (identifier,))
        else:
            cursor.execute("""
                SELECT TOP 1 UserID, HashedPassword, Username
                FROM dbo.Users
                WHERE LOWER(Username) = ? AND HashedPassword IS NOT NULL
                ORDER BY UserID DESC
            """, (identifier,))

        row = cursor.fetchone()

        if not row:
            # Precise failure reasons for observability
            if real_cnt == 0 and shell_cnt > 0:
                raise HTTPException(
                    status_code=401,
                    detail={"code": "AUTH_SHELL_COLLISION", "message": "Invalid login credentials", "trace": trace}
                )
            raise HTTPException(
                status_code=401,
                detail={"code": "AUTH_NO_USER", "message": "Invalid login credentials", "trace": trace}
            )

        user_id, hashed_pw, username = row[0], row[1], row[2]
        if not verify_password(password, hashed_pw):
            raise HTTPException(
                status_code=401,
                detail={"code": "AUTH_BAD_PASSWORD", "message": "Invalid login credentials", "trace": trace}
            )

        # --- 3) Ensure a shell exists for this device, but DON'T stamp username/email on shells
        if guest_id:
            cursor.execute("SELECT 1 FROM dbo.Users WHERE GuestID = ?", (str(guest_id),))
            exists = cursor.fetchone()
            if not exists:
                cursor.execute("INSERT INTO dbo.Users (GuestID, CreatedAt) VALUES (?, GETDATE())", (str(guest_id),))
                conn.commit()

        minutes = 43200 if getattr(payload, "remember_me", False) else 120
        token = create_access_token(data={"sub": str(user_id), "username": username}, minutes=minutes)

        return {"access_token": token, "token_type": "bearer", "username": username, "trace": trace}

    except pyodbc.Error:
        # DB-level failure
        raise HTTPException(status_code=500, detail={"code": "AUTH_DB_ERROR", "message": "Database error", "trace": trace})
    finally:
        cursor.close()
        conn.close()



@app.get("/user-profile")
def get_user_profile(username: str):
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        # ✅ Look up all UserIDs and GuestIDs tied to this username
        cursor.execute("""
            SELECT UserID, GuestID
            FROM dbo.Users
            WHERE Username = ?
        """, username)
        user_rows = cursor.fetchall()

        if not user_rows:
            raise HTTPException(status_code=404, detail="User not found")

        user_ids = [row[0] for row in user_rows]
        guest_ids = [row[1] for row in user_rows]

        if not user_ids and not guest_ids:
            raise HTTPException(status_code=404, detail="No associated IDs found.")

        user_placeholders = ','.join(['?'] * len(user_ids))
        guest_placeholders = ','.join(['?'] * len(guest_ids))
        all_params = (*user_ids, *guest_ids)

        # ✅ Profile stats (fixed SQL)
        cursor.execute(f"""
            SELECT 
                COUNT(*) AS GridsCompleted,
                ROUND(AVG(CAST(GuessesCorrect AS FLOAT)), 2) AS AvgScore,
                ROUND(AVG(ISNULL(ProfileRarity.RarityScore, 0)), 2) AS AvgRarity,
                ROUND(MIN(ISNULL(ProfileRarity.RarityScore, 0)), 2) AS LowestRarity
            FROM Games g
            OUTER APPLY (
    SELECT 
        SUM(rs.GuessPercentage) + (100 * (9 - COUNT(DISTINCT ug.RowCriterion + '-' + ug.ColumnCriterion))) AS RarityScore
    FROM UserGuesses ug
    JOIN RarityGuessStats rs
      ON ug.GridID = rs.GridID
     AND ug.RowCriterion = rs.RowCriterion
     AND ug.ColumnCriterion = rs.ColumnCriterion
     AND ug.FullName = rs.FullName
    WHERE ug.GameID = g.GameID AND ug.IsCorrect = 1
) AS ProfileRarity
            WHERE g.Completed = 1 AND (
                g.UserID IN ({user_placeholders}) OR g.GuestID IN ({guest_placeholders})
            )
        """, all_params)

        stats = cursor.fetchone() or (0, 0.0, 0.0, 0.0)

        # ✅ Current streak
        # ✅ Accurate daily streak calculation
        cursor.execute(f"""
    WITH UserIDs AS (
        SELECT UserID, GuestID
        FROM dbo.Users
        WHERE Username = ?
    ),
    AllGrids AS (
        SELECT GridID, GridDate
        FROM dbo.DailyGrids
        WHERE Status IN ('Archived', 'Active')
    ),
    UserGames AS (
        SELECT g.GridID, g.Completed,
               ROW_NUMBER() OVER (PARTITION BY g.GridID ORDER BY g.PlayedAt DESC) AS rn
        FROM dbo.Games g
        JOIN UserIDs u ON g.UserID = u.UserID OR g.GuestID = u.GuestID
    ),
    LatestUserGames AS (
        SELECT GridID, Completed
        FROM UserGames
        WHERE rn = 1
    ),
    GridsWithCompletion AS (
        SELECT ag.GridID, ag.GridDate, 
               ISNULL(lg.Completed, 0) AS IsCompleted
        FROM AllGrids ag
        LEFT JOIN LatestUserGames lg ON ag.GridID = lg.GridID
    ),
    StreakCalc AS (
        SELECT *, 
               ROW_NUMBER() OVER (ORDER BY GridDate DESC) AS rn_desc
        FROM GridsWithCompletion
    ),
    FirstMiss AS (
        SELECT MIN(rn_desc) AS FirstUncompleted
        FROM StreakCalc
        WHERE IsCompleted = 0
    )
    SELECT COUNT(*) AS CurrentStreak
    FROM (
        SELECT rn_desc
        FROM StreakCalc
        CROSS JOIN FirstMiss f
        WHERE rn_desc < f.FirstUncompleted OR f.FirstUncompleted IS NULL
    ) x;
""", (username,))
        streak = cursor.fetchone()
        current_streak = streak[0] if streak else 0


        # ✅ Top riders
        cursor.execute(f"""
            SELECT TOP 9 
                g.FullName,
                COUNT(*) AS CorrectGuesses,
                MAX(r.ImageURL) AS ImageURL
            FROM UserGuesses g
            JOIN Rider_List r ON g.FullName = r.FullName
            WHERE g.IsCorrect = 1
              AND (g.UserID IN ({user_placeholders}) OR g.GuestID IN ({guest_placeholders}))
            GROUP BY g.FullName
            ORDER BY COUNT(*) DESC;
        """, all_params)
        rider_rows = cursor.fetchall()

        top_riders = [
            {
                "name": row[0],
                "correct_guesses": row[1],
                "image_url": row[2] or ""
            }
            for row in rider_rows
        ]

        return {
            "grids_completed": stats[0] or 0,
            "avg_score": float(stats[1] or 0),
            "avg_rarity": float(stats[2] or 0),
            "lowest_rarity": float(stats[3] or 0),
            "current_streak": current_streak,
            "top_riders": top_riders
        }

    except Exception as e:
        print("❌ PROFILE ERROR:", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {str(e)}")

    finally:
        cursor.close()
        conn.close()


@app.post("/start-game")
def start_game(request: Request):
    try:
        guest_id = request.query_params.get("guest_id")
        grid_id = request.query_params.get("grid_id")

        if not guest_id:
            raise HTTPException(status_code=400, detail="Guest ID is required.")

        guest_id = UUID(guest_id)
        try:
            grid_id = int(grid_id)
        except (TypeError, ValueError):
            grid_id = None

        global game_state

        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        try:
            # ✅ Ensure the User exists
            cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO dbo.Users (GuestID, CreatedAt) VALUES (?, GETDATE())", str(guest_id))
                conn.commit()
                cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
                row = cursor.fetchone()
            user_id = row[0]

            # ✅ Use active grid if none provided
            if grid_id is None:
                cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active'")
                grid_id = cursor.fetchone()[0]

            # ✅ Fetch grid layout
            cursor.execute("SELECT Row1, Row2, Row3, Column1, Column2, Column3 FROM dbo.DailyGrids WHERE GridID = ?", (grid_id,))
            grid_info = cursor.fetchone()
            if not grid_info:
                raise HTTPException(status_code=404, detail="Grid not found.")

            rows = list(grid_info[:3])
            cols = list(grid_info[3:])
            grid_data = {
                (r, c): fetch_riders_for_criterion(r, conn) & fetch_riders_for_criterion(c, conn)
                for r in rows for c in cols
            }

            if user_id not in game_state:
                game_state[user_id] = {}

            game_state[user_id][grid_id] = {
                "remaining_attempts": 9,
                "used_riders": set(),
                "unanswered_cells": set(grid_data.keys()),
                "grid_data": grid_data
            }

            # ✅ Check for existing game across all merged accounts
            user_ids, guest_ids = resolve_all_user_ids(guest_id, conn)

            if user_ids and guest_ids:
                placeholders = ','.join(['?'] * len(user_ids))
                placeholders2 = ','.join(['?'] * len(guest_ids))
                query = f"""
                    SELECT TOP 1 GameID, Completed 
                    FROM dbo.Games 
                    WHERE GridID = ? AND (
                        UserID IN ({placeholders}) OR GuestID IN ({placeholders2})
                    )
                    ORDER BY PlayedAt DESC
                """
                params = [grid_id] + user_ids + guest_ids
                cursor.execute(query, params)
                existing_game = cursor.fetchone()
            else:
                existing_game = None

            if existing_game:
                return {
                    "message": "Game already exists",
                    "grid_id": grid_id,
                    "guest_id": str(guest_id),
                    "game_id": existing_game[0],
                    "completed": bool(existing_game[1])
                }

            # ✅ Insert new game
            cursor.execute("""
                INSERT INTO dbo.Games (UserID, GuestID, GridID, GuessesMade, Completed, PlayedAt)
                OUTPUT INSERTED.GameID
                VALUES (?, ?, ?, 0, 0, GETDATE());
            """, (user_id, str(guest_id), grid_id))
            game_id = cursor.fetchone()[0]

            conn.commit()

            return {
                "message": "New game created",
                "grid_id": grid_id,
                "guest_id": str(guest_id),
                "game_id": game_id,
                "completed": False
            }

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting game: {str(e)}")



@app.get("/game-progress")
def game_progress(grid_id: int, guest_id: Optional[str] = None, username: Optional[str] = None):
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        if username:
            cursor.execute("SELECT UserID, GuestID FROM dbo.Users WHERE Username = ?", username)
            user_rows = cursor.fetchall()
            if not user_rows:
                raise HTTPException(status_code=404, detail="No user records found for username")
            user_ids = [row[0] for row in user_rows]
            guest_ids = [row[1] for row in user_rows]
        elif guest_id:
            if not username:
                user_ids, guest_ids = resolve_all_user_ids(UUID(guest_id), conn)
        else:
            raise HTTPException(status_code=400, detail="guest_id or username is required")

        if not user_ids and not guest_ids:
            return {"status": "new"}

        conditions = []
        params = [grid_id]

        if user_ids:
            conditions.append(f"UserID IN ({','.join(['?'] * len(user_ids))})")
            params.extend(user_ids)

        if guest_ids:
            conditions.append(f"GuestID IN ({','.join(['?'] * len(guest_ids))})")
            params.extend(guest_ids)

        where_clause = " OR ".join(conditions)

        cursor.execute(f"""
            SELECT TOP 1 GameID, GuessesMade, Completed 
            FROM dbo.Games 
            WHERE GridID = ? AND ({where_clause})
            ORDER BY PlayedAt DESC
        """, tuple(params))

        game_row = cursor.fetchone()

        if not game_row:
            return {"status": "new"}

        game_id, guesses_made, completed = game_row

        cursor.execute("""
            SELECT RowCriterion, ColumnCriterion, FullName, IsCorrect, ImageURL
            FROM dbo.UserGuesses
            WHERE GameID = ?
        """, (game_id,))
        guesses = cursor.fetchall()

        formatted_guesses = [{
            "row": row,
            "column": col,
            "rider": rider,
            "is_correct": bool(correct),
            "image_url": image
        } for row, col, rider, correct, image in guesses]

        return {
            "status": "completed" if completed else "in_progress",
            "game_id": game_id,
            "guesses": formatted_guesses,
            "remaining_attempts": 9 - guesses_made
        }

    finally:
        cursor.close()
        conn.close()


@app.get("/grid")
def get_grid():
    """Fetch today's active grid from DailyGrids and generate valid answers dynamically."""
    global game_state

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
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

        # ✅ Generate valid riders dynamically
        grid_data = {
            (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
            for row in rows for col in cols
        }

        game_state.update({
            "grid_id": grid_id,
            "rows": rows,
            "cols": cols,
            "grid_data": grid_data,
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

    finally:
        cursor.close()
        conn.close()

    
@app.get("/grid/{grid_id}")
def get_specific_grid(grid_id: int, guest_id: Optional[UUID] = Query(None)):
    """Load a specific grid by GridID (archived or active)."""
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT GridID, Row1, Row2, Row3, Column1, Column2, Column3
            FROM dbo.DailyGrids
            WHERE GridID = ?
        """, (grid_id,))
        grid = cursor.fetchone()

        if not grid:
            raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found.")

        rows, cols = [grid[1], grid[2], grid[3]], [grid[4], grid[5], grid[6]]

        grid_data = {
            (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
            for row in rows for col in cols
        }

        return {
            "grid_id": grid_id,
            "rows": rows,
            "columns": cols,
            "grid_data": {str(k): list(v) for k, v in grid_data.items()}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading grid: {str(e)}")

    finally:
        cursor.close()
        conn.close()

@app.get("/autocomplete")
def autocomplete_riders(query: str):
    """Return a list of rider names matching the query."""
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT FullName FROM Rider_List WHERE LOWER(FullName) LIKE ?",
            f"%{query.lower()}%",
        )
        riders = [row[0] for row in cursor.fetchall()]
        return {"riders": riders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching autocomplete: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@app.post("/guess")
def submit_guess(guess: GuessRequest, guest_id: UUID):
    global game_state
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        # ✅ Get UserID from GuestID
        cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
        user_id_result = cursor.fetchone()
        if not user_id_result:
            raise HTTPException(status_code=404, detail="Guest user not found.")
        user_id = user_id_result[0]

        user_ids, guest_ids = resolve_all_user_ids(guest_id, conn)
        if not user_ids and not guest_ids:
            return {"status": "new"}

        # ✅ Get GridID (either passed or active)
        grid_id = guess.grid_id
        if grid_id is None:
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active'")
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=500, detail="No active grid found.")
            grid_id = result[0]

        # ✅ Restore game_state from DB if missing
        if user_id not in game_state:
            game_state[user_id] = {}

        if grid_id not in game_state[user_id]:
            cursor.execute("SELECT Row1, Row2, Row3, Column1, Column2, Column3 FROM dbo.DailyGrids WHERE GridID = ?", (grid_id,))
            grid_info = cursor.fetchone()
            if not grid_info:
                raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found.")
            rows = list(grid_info[:3])
            cols = list(grid_info[3:])
            grid_data = {(r, c): fetch_riders_for_criterion(r, conn) & fetch_riders_for_criterion(c, conn) for r in rows for c in cols}

            # ✅ Get GameID
            cursor.execute(f"""
                SELECT TOP 1 GameID FROM dbo.Games
                WHERE GridID = ? AND (
                    UserID IN ({','.join(['?'] * len(user_ids))}) OR
                    GuestID IN ({','.join(['?'] * len(guest_ids))})
                )
                ORDER BY PlayedAt DESC
            """, (grid_id, *user_ids, *guest_ids))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Game not found.")
            game_id = row[0]

            # ✅ Get previous guesses
            cursor.execute("SELECT RowCriterion, ColumnCriterion, FullName, IsCorrect FROM dbo.UserGuesses WHERE GameID = ?", (game_id,))
            guess_rows = cursor.fetchall()

            used_riders = set()
            correct_cells = set()
            for row in guess_rows:
                r_crit, c_crit, full_name, is_correct = row
                if is_correct:
                    used_riders.add(full_name)
                    correct_cells.add((r_crit, c_crit))

            game_state[user_id][grid_id] = {
                "remaining_attempts": max(0, 9 - len(guess_rows)),
                "used_riders": used_riders,
                "unanswered_cells": set(grid_data.keys()) - correct_cells,
                "grid_data": grid_data
            }

        state = game_state[user_id][grid_id]

        # ✅ Retrieve GameID and GuessesMade
        cursor.execute(f"""
            SELECT TOP 1 GameID, GuessesMade FROM dbo.Games
            WHERE GridID = ? AND (
                UserID IN ({','.join(['?'] * len(user_ids))}) OR
                GuestID IN ({','.join(['?'] * len(guest_ids))})
            )
            ORDER BY PlayedAt DESC
        """, (grid_id, *user_ids, *guest_ids))
        game_id_result = cursor.fetchone()

        if not game_id_result:
            cursor.execute("""
                INSERT INTO dbo.Games (UserID, GuestID, GridID, GuessesMade, Completed, PlayedAt)
                OUTPUT INSERTED.GameID
                VALUES (?, ?, ?, 0, 0, GETDATE());
            """, (user_id, str(guest_id), grid_id))
            game_id_result = cursor.fetchone()
            if not game_id_result:
                raise HTTPException(status_code=500, detail="Failed to create a new game session.")
            game_id = game_id_result[0]
            guesses_made = 0
        else:
            game_id, guesses_made = game_id_result
            state["remaining_attempts"] = max(0, 9 - guesses_made)

            # ✅ Prevent guessing if game is completed
            cursor.execute("SELECT Completed FROM dbo.Games WHERE GameID = ?", (game_id,))
            completed_row = cursor.fetchone()
            if completed_row and completed_row[0]:
                raise HTTPException(status_code=400, detail="Game already completed.")

        selected_cell = (guess.row, guess.column)
        if selected_cell not in state["unanswered_cells"]:
            return {
                "message": f"⚠️ '{guess.rider}' has already been guessed for {guess.row} | {guess.column}!",
                "remaining_attempts": state["remaining_attempts"]
            }

        if guess.rider in state["used_riders"]:
            return {
                "message": f"❌ '{guess.rider}' has already been used in another cell. Try a different rider!",
                "remaining_attempts": state["remaining_attempts"]
            }

        expected_riders = state["grid_data"].get(selected_cell)
        if expected_riders is None:
            return {"error": f"Cell {selected_cell} has no valid riders."}

        guessed_rider = guess.rider.strip().lower()
        expected_riders_normalized = {r.strip().lower() for r in expected_riders}
        is_correct = guessed_rider in expected_riders_normalized

        state["remaining_attempts"] -= 1
        guesses_made += 1

        image_url = None
        if is_correct:
            cursor.execute("SELECT ImageURL FROM Rider_List WHERE FullName = ?", (guess.rider,))
            result = cursor.fetchone()
            image_url = result[0] if result else None

        cursor.execute("""
            INSERT INTO UserGuesses (GridID, UserID, GameID, GuestID, RowCriterion, ColumnCriterion, FullName, IsCorrect, GuessedAt, ImageURL)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), ?);
        """, (grid_id, user_id, game_id, str(guest_id), guess.row, guess.column, guess.rider, int(is_correct), image_url))
        cursor.execute("""
            UPDATE dbo.Games
            SET GuessesMade = GuessesMade + 1,
                GuessesCorrect = GuessesCorrect + ?
            WHERE GameID = ?;
        """, (1 if is_correct else 0, game_id))

        if state["remaining_attempts"] == 0:
            cursor.execute("UPDATE dbo.Games SET Completed = 1 WHERE GameID = ?", (game_id,))

        conn.commit()

        update_rarity_stats(grid_id, guess.row, guess.column, conn)

        if not is_correct:
            return {
                "message": f"❌ '{guess.rider}' is incorrect for {guess.row} | {guess.column}!",
                "remaining_attempts": state["remaining_attempts"],
                "rider": None,
                "image_url": None,
                "guess_percentage": None
            }

        cursor.execute("""
            WITH CorrectGuesses AS (
                SELECT g.GridID, g.RowCriterion, g.ColumnCriterion, g.FullName, COUNT(*) AS GuessCount
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
            ) total ON cg.GridID = total.GridID
            AND cg.RowCriterion = total.RowCriterion
            AND cg.ColumnCriterion = total.ColumnCriterion
            WHERE cg.FullName = ?
        """, (grid_id, guess.row, guess.column, guess.rider))
        guess_percentage_result = cursor.fetchone()
        guess_percentage = round(guess_percentage_result[0], 2) if guess_percentage_result else 0.0

        state["used_riders"].add(guess.rider)
        state["unanswered_cells"].discard(selected_cell)

        return {
            "message": f"✅ '{guess.rider}' placed in {guess.row} | {guess.column}!",
            "remaining_attempts": state["remaining_attempts"],
            "rider": guess.rider,
            "image_url": image_url,
            "guess_percentage": guess_percentage
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing guess: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/current-guess-percentage")
def get_current_guess_percentage(grid_id: int, row: str, column: str, rider: str):
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
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

    finally:
        cursor.close()
        conn.close()


@app.post("/give-up")
def give_up(guest_id: UUID, grid_id: int = Query(None)):
    """Ends the game immediately. Ensures a GameID is assigned before finalizing the game."""
    global game_state

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        # ✅ Retrieve UserID for guest
        cursor.execute("SELECT UserID FROM dbo.Users WHERE GuestID = ?", str(guest_id))
        user_id_result = cursor.fetchone()
        if not user_id_result:
            raise HTTPException(status_code=404, detail="Guest user not found.")
        user_id = user_id_result[0]

        user_ids, guest_ids = resolve_all_user_ids(guest_id, conn)
        if not user_ids and not guest_ids:
            return { "status": "new" }

        # ✅ Determine GridID
        if grid_id is not None:
            actual_grid_id = grid_id
        else:
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active'")
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="No active grid found.")
            actual_grid_id = result[0]

        grid_id = actual_grid_id  # for consistency

        # ✅ Check for existing GameID
        cursor.execute(f"""
            SELECT TOP 1 GameID FROM dbo.Games
            WHERE GridID = ? AND (
                UserID IN ({','.join(['?'] * len(user_ids))}) OR
                GuestID IN ({','.join(['?'] * len(guest_ids))})
            )
            ORDER BY PlayedAt DESC
        """, (grid_id, *user_ids, *guest_ids))

        game_id_result = cursor.fetchone()

        if not game_id_result:
            # ✅ Create new game marked as completed
            cursor.execute("""
                INSERT INTO dbo.Games (UserID, GuestID, GridID, GuessesMade, Completed, PlayedAt)
                OUTPUT INSERTED.GameID
                VALUES (?, ?, ?, 0, 1, GETDATE());
            """, (user_id, str(guest_id), grid_id))
            game_id_result = cursor.fetchone()

            if not game_id_result:
                raise HTTPException(status_code=500, detail="Failed to create a new game for Give Up.")

            game_id = game_id_result[0]
        else:
            game_id = game_id_result[0]

        # ✅ Mark as completed
        cursor.execute("UPDATE dbo.Games SET Completed = 1 WHERE GameID = ?", (game_id,))
        conn.commit()

        # ✅ Set game state to reflect zero remaining attempts
        if user_id in game_state and grid_id in game_state[user_id]:
            game_state[user_id][grid_id]["remaining_attempts"] = 0

        return {
            "message": "Game ended! You have used all attempts.",
            "remaining_attempts": 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing give-up: {str(e)}")

    finally:
        cursor.close()
        conn.close()

@app.get("/game-summary")
def get_game_summary(request: Request):
    """Returns the summary for today's game including stats, popular guesses, and rarity score."""
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        guest_id = request.query_params.get("guest_id")
        if not guest_id:
            raise HTTPException(status_code=400, detail="Guest ID is required.")

        grid_id = request.query_params.get("grid_id")
        if grid_id:
            grid_id = int(grid_id)
        else:
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = ?", ('Active',))
            grid_id_result = cursor.fetchone()
            if not grid_id_result:
                raise HTTPException(status_code=404, detail="No active grid found.")
            grid_id = grid_id_result[0]

        user_ids, guest_ids = resolve_all_user_ids(UUID(guest_id), conn)
        cursor.execute(f"""
            SELECT TOP 1 GameID FROM dbo.Games
            WHERE GridID = ? AND (
                UserID IN ({','.join(['?'] * len(user_ids))}) OR GuestID IN ({','.join(['?'] * len(guest_ids))})
            )
            ORDER BY PlayedAt DESC
        """, (grid_id, *user_ids, *guest_ids))

        game_id_result = cursor.fetchone()
        if not game_id_result:
            raise HTTPException(status_code=404, detail=f"No GameID found for GridID {grid_id} and GuestID {guest_id}.")
        game_id = game_id_result[0]

        # ✅ Fetch game stats
        cursor.execute("""
            SELECT COUNT(*) AS TotalGamesPlayed, 
                   CAST(AVG(CAST(GuessesCorrect AS FLOAT)) AS DECIMAL(10,2)) AS AverageScore
            FROM dbo.Games
            WHERE GridID = ? AND Completed = 1;
        """, (grid_id,))
        stats = cursor.fetchone()
        total_games = stats[0] if stats[0] else 0
        average_score = "{:.2f}".format(float(stats[1])) if stats[1] else "0.00"

        # ✅ Most guessed riders
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

        # ✅ Correct guess percentage per cell
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

        # ✅ Rarity score
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

        return {
            "total_games_played": total_games,
            "average_score": average_score,
            "rarity_score": rarity_score,
            "most_guessed_riders": most_guessed_riders,
            "cell_completion_rates": cell_completion_rates,
        }

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching game summary: {str(e)}")

    finally:
        cursor.close()
        conn.close()


@app.get("/daily-leaderboard")
def get_daily_leaderboard():
    """Returns the top 20 lowest rarity scores for the active grid, showing 'Guest' for players without a username."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Get active grid ID
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active'")
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="No active grid found.")
            grid_id = result[0]

            # ✅ Execute deduplicated rarity score query
            # ✅ Execute deduplicated rarity score query using precomputed rarity
            cursor.execute("""
    WITH GameSessions AS (
        SELECT 
            g.GameID,
            g.GridID,
            g.PlayedAt,
            u.Username,
            g.GuestID,
            COALESCE(u.Username, CAST(g.GuestID AS VARCHAR(100))) AS PlayerKey,
            CASE WHEN u.Username IS NOT NULL THEN u.Username ELSE 'Guest' END AS DisplayName
        FROM dbo.Games g
        LEFT JOIN dbo.Users u ON g.UserID = u.UserID
        WHERE g.Completed = 1 AND g.GridID = ?
    ),
    LatestGamePerPlayer AS (
        SELECT GameID, PlayerKey
        FROM (
            SELECT GameID, PlayerKey,
                   ROW_NUMBER() OVER (PARTITION BY PlayerKey ORDER BY PlayedAt DESC) AS rn
            FROM GameSessions
        ) x
        WHERE rn = 1
    ),
    RarityScoreRaw AS (
        SELECT 
            ug.GameID,
            SUM(rs.GuessPercentage) + (100 * (9 - COUNT(DISTINCT ug.RowCriterion + '-' + ug.ColumnCriterion))) AS RarityScore
        FROM dbo.UserGuesses ug
        JOIN dbo.RarityGuessStats rs
          ON ug.GridID = rs.GridID
         AND ug.RowCriterion = rs.RowCriterion
         AND ug.ColumnCriterion = rs.ColumnCriterion
         AND ug.FullName = rs.FullName
        WHERE ug.GridID = ? AND ug.IsCorrect = 1
        GROUP BY ug.GameID
    )
    SELECT TOP 20 
        gs.DisplayName AS Username,
        ROUND(r.RarityScore, 2) AS RarityScore
    FROM RarityScoreRaw r
    JOIN LatestGamePerPlayer lg ON r.GameID = lg.GameID
    JOIN GameSessions gs ON r.GameID = gs.GameID
    ORDER BY RarityScore ASC
""", (grid_id, grid_id))

            rows = cursor.fetchall()
            leaderboard = [
                {"username": row[0], "rarity_score": float(row[1])}
                for row in rows
            ]

            return leaderboard

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating leaderboard: {str(e)}")


    
@app.get("/grid-archive")
def get_grid_archive(
    guest_id: Optional[UUID] = Query(None),
    username: Optional[str] = Query(None),
    show_all: bool = Query(False)
):
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
        user_ids, guest_ids = [], []

        if username:
            cursor.execute("""
                SELECT UserID, GuestID
                FROM dbo.Users
                WHERE Username = ?
            """, (username,))
            rows = cursor.fetchall()
            user_ids = [r[0] for r in rows]
            guest_ids = [r[1] for r in rows]
        elif guest_id:
            cursor.execute("SELECT UserID FROM Users WHERE GuestID = ?", (str(guest_id),))
            row = cursor.fetchone()
            if row:
                user_ids = [row[0]]
                guest_ids = [str(guest_id)]
            else:
                guest_ids = [str(guest_id)]

        user_filter = " OR ".join([
            f"g.UserID IN ({','.join(['?']*len(user_ids))})" if user_ids else "",
            f"g.GuestID IN ({','.join(['?']*len(guest_ids))})" if guest_ids else ""
        ]).strip(" OR ")

        join_clause = f"""
            OUTER APPLY (
                SELECT TOP 1 g.Completed, g.GuessesCorrect, g.GameID
                FROM Games g
                WHERE g.GridID = d.GridID
                {f"AND ({user_filter})" if user_filter else ""}
                ORDER BY g.PlayedAt DESC
            ) game
        """
        # ✅ Add TOP 20 if show_all is False
        top_clause = "" if show_all else "TOP 20"

        cursor.execute(f"""
            SELECT {top_clause}
                d.GridID, d.GridDate, 
                game.Completed, game.GuessesCorrect,
                CASE 
                    WHEN game.GameID IS NOT NULL THEN (
                        SELECT 
                            ROUND(
                                COALESCE(SUM(rs.GuessPercentage), 0) 
                                + (100 * (9 - COUNT(DISTINCT ug.RowCriterion + '-' + ug.ColumnCriterion))), 2)
                        FROM UserGuesses ug
                        JOIN RarityGuessStats rs
                          ON ug.GridID = rs.GridID
                         AND ug.RowCriterion = rs.RowCriterion
                         AND ug.ColumnCriterion = rs.ColumnCriterion
                         AND ug.FullName = rs.FullName
                        WHERE ug.GameID = game.GameID AND ug.IsCorrect = 1
                    )
                    ELSE NULL
                END AS RarityScore
            FROM DailyGrids d
            {join_clause}
            WHERE d.Status = 'Archived'
            ORDER BY d.GridDate DESC
        """, tuple(user_ids + guest_ids))

        archive = []
        for row in cursor.fetchall():
            grid_id, date, completed, score, rarity = row
            archive.append({
                "grid_id": grid_id,
                "date": date.strftime("%Y-%m-%d") if date else "—",
                "completed": completed,
                "score": score,
                "rarity_score": rarity
            })

        return archive

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching archive: {str(e)}")

    finally:
        cursor.close()
        conn.close()

def update_rarity_stats(grid_id: int, row: str, col: str, conn):
    cursor = conn.cursor()
    cursor.execute("""
        WITH CorrectGuesses AS (
            SELECT FullName, COUNT(*) AS GuessCount
            FROM UserGuesses
            WHERE IsCorrect = 1
              AND GridID = ? AND RowCriterion = ? AND ColumnCriterion = ?
            GROUP BY FullName
        ),
        TotalGuesses AS (
            SELECT SUM(GuessCount) AS Total
            FROM CorrectGuesses
        )
        MERGE RarityGuessStats AS target
        USING (
            SELECT 
                ?, ?, ?, cg.FullName,
                (cg.GuessCount * 100.0 / NULLIF(t.Total, 0)) AS GuessPercentage
            FROM CorrectGuesses cg
            CROSS JOIN TotalGuesses t
        ) AS source (GridID, RowCriterion, ColumnCriterion, FullName, GuessPercentage)
        ON target.GridID = source.GridID
           AND target.RowCriterion = source.RowCriterion
           AND target.ColumnCriterion = source.ColumnCriterion
           AND target.FullName = source.FullName
        WHEN MATCHED THEN
            UPDATE SET GuessPercentage = source.GuessPercentage, LastUpdated = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (GridID, RowCriterion, ColumnCriterion, FullName, GuessPercentage)
            VALUES (source.GridID, source.RowCriterion, source.ColumnCriterion, source.FullName, source.GuessPercentage);
    """, (grid_id, row, col, grid_id, row, col))
    conn.commit()


@app.post("/populate-grid-pool")
def populate_grid_pool(max_to_generate: int = 1000):
    """Precompute and store valid grids into the GridPool table."""
    from itertools import combinations
    inserted_count = 0
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    try:
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error populating grid pool: {str(e)}")

    finally:
        cursor.close()
        conn.close()


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
    
@app.post("/refresh-cache")
def refresh_cache():
    try:
        print("🔄 Step 1: Starting refresh")
        global rider_cache
        rider_cache.clear()
        print("🧹 Step 2: Cleared rider_cache")

        with pyodbc.connect(CONN_STR) as conn:
            print("🔌 Step 3: DB connection opened")
            cursor = conn.cursor()
            cursor.execute("SELECT FullName FROM Rider_List")
            rows = cursor.fetchall()
            print(f"📝 Step 4: Retrieved {len(rows)} riders")

            rider_cache.update({row[0]: True for row in rows})

        print("✅ Step 5: Cache refresh complete")
        return {"message": "✅ Rider cache refreshed successfully."}

    except Exception as e:
        import traceback
        print("❌ ERROR in /refresh-cache:", str(e))
        print(traceback.format_exc())  # 🔍 full traceback to Azure logs
        raise HTTPException(status_code=500, detail=f"Internal cache refresh failure: {str(e)}")





