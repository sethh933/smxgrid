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
from fastapi import Depends, Query, BackgroundTasks
from typing import Optional
from fastapi.responses import JSONResponse
import smtplib
from email.message import EmailMessage


# Load .env.local from the same folder as main.py
env_path = Path(__file__).resolve().parent / ".env.local"
load_dotenv(dotenv_path=env_path)

# print("DEBUG - DB_SERVER:", os.getenv("DB_SERVER"))



class LoginRequest(BaseModel):
    email_or_username: str
    password: str
    remember_me: bool = False
    guest_id: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    identifier: str  # email or username

class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str

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

def send_reset_email(to_email: str, reset_link: str):
    msg = EmailMessage()
    msg["Subject"] = "Reset your smxmuse password"
    msg["From"] = os.getenv("SMTP_FROM_EMAIL")
    msg["To"] = to_email
    msg.set_content(f"Click the link below to reset your password:\n\n{reset_link}")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_user = os.getenv("SMTP_FROM_EMAIL")
    smtp_pass = os.getenv("SMTP_FROM_PASSWORD")

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


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
    guest_id = str(payload.guest_id)
    email = payload.email.lower()
    username = payload.username.strip()
    password = payload.password
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    hashed_pw = hash_password(password)

    if profanity.contains_profanity(username):
        raise HTTPException(status_code=400, detail="Inappropriate username")

    if not is_valid_password(password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters and contain a letter and a number")

    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()

        # ✅ Ensure this GuestID exists
        cursor.execute("SELECT UserID FROM Users WHERE GuestID = ?", (guest_id,))
        guest_row = cursor.fetchone()

        if not guest_row:
        # ✅ Create a new row for this guest_id
            cursor.execute("INSERT INTO Users (GuestID, CreatedAt) VALUES (?, GETDATE())", (guest_id,))
            conn.commit()
            cursor.execute("SELECT UserID FROM Users WHERE GuestID = ?", (guest_id,))
            guest_row = cursor.fetchone()

        if not guest_row:
            raise HTTPException(status_code=500, detail="Failed to create guest user for registration")


        # ✅ Block duplicate email across any guest
        cursor.execute("SELECT 1 FROM Users WHERE Email = ? AND GuestID != ?", (email, guest_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already in use")

        # ✅ Block duplicate username across any guest
        cursor.execute("SELECT 1 FROM Users WHERE Username = ? AND GuestID != ?", (username, guest_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already taken")

        # ✅ Check if this GuestID already has a completed registration
        cursor.execute("SELECT Username FROM Users WHERE GuestID = ?", (guest_id,))
        existing_username = cursor.fetchone()
        if existing_username and existing_username[0] is not None:
            raise HTTPException(status_code=400, detail="This guest ID already has a registered account")

        # ✅ Update the existing guest row with full account info
        cursor.execute("""
            UPDATE Users
            SET Email = ?, Username = ?, HashedPassword = ?, CreatedAt = GETDATE(),
                FirstName = ?, LastName = ?
            WHERE GuestID = ?
        """, (email, username, hashed_pw, first_name, last_name, guest_id))
        conn.commit()

        cursor.execute("SELECT UserID FROM Users WHERE GuestID = ?", (guest_id,))
        user_id = cursor.fetchone()[0]

    token = create_access_token(data={"sub": str(user_id), "username": username})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/login")
def login_user(payload: LoginRequest):
    identifier = payload.email_or_username.strip().lower()
    password = payload.password
    guest_id = payload.guest_id if hasattr(payload, "guest_id") else None

    if guest_id:
        try:
            guest_id = UUID(str(guest_id).strip())
        except ValueError:
            guest_id = None

    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()

        # Fetch user by email or username
        if "@" in identifier:
            cursor.execute("SELECT UserID, HashedPassword, Username FROM Users WHERE LOWER(Email) = ?", (identifier,))
        else:
            cursor.execute("SELECT UserID, HashedPassword, Username FROM Users WHERE LOWER(Username) = ?", (identifier,))

        row = cursor.fetchone()
        if not row or not verify_password(password, row[1]):
            raise HTTPException(status_code=401, detail="Invalid login credentials")

        user_id = row[0]
        username = row[2]

        # 🔁 Merge blank guest account from this device
        if guest_id:
            cursor.execute("SELECT UserID, Username FROM Users WHERE GuestID = ?", (str(guest_id),))
            guest_row = cursor.fetchone()

            if guest_row:
                guest_userid, guest_username = guest_row

                # If it’s a blank guest row, assign the username
                if guest_username is None:
                    cursor.execute("""
                        UPDATE Users
                        SET Username = ?, Email = NULL, HashedPassword = NULL,
                            FirstName = NULL, LastName = NULL, CreatedAt = NULL
                        WHERE GuestID = ?
                    """, (username, str(guest_id)))
                    conn.commit()

            else:
        # ✅ Insert new row for this guest_id and assign username
                cursor.execute("""
                    INSERT INTO Users (GuestID, Username, CreatedAt)
                    VALUES (?, ?, GETDATE())
                """, (str(guest_id), username))
                conn.commit()


    minutes = 43200 if payload.remember_me else 120
    token = create_access_token(data={"sub": str(user_id), "username": username}, minutes=minutes)

    return {"access_token": token, "token_type": "bearer", "username":username}

@app.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    identifier = payload.identifier.strip().lower()

    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()

        if "@" in identifier:
            cursor.execute("SELECT UserID, Email FROM Users WHERE LOWER(Email) = ?", (identifier,))
        else:
            cursor.execute("SELECT UserID, Email FROM Users WHERE LOWER(Username) = ?", (identifier,))

        row = cursor.fetchone()
        if not row or not row[1]:
            raise HTTPException(status_code=404, detail="No account found with that email or username.")

        user_id, email = row
        token = create_access_token(data={"sub": str(user_id)}, minutes=30)
        reset_link = f"https://smxmuse.com/reset-password-confirm?token={token}"
        send_reset_email(email, reset_link)

        # 📨 Replace with email sending logic
        print(f"DEBUG: Send this reset link to user: {reset_link}")

        return {"message": "Reset link sent if account exists."}

@app.post("/reset-password-confirm")
def reset_password_confirm(payload: ResetPasswordConfirmRequest):
    try:
        data = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(data.get("sub"))

        if not is_valid_password(payload.new_password):
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters and include a letter and number."
            )

        hashed_pw = hash_password(payload.new_password)

        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Users SET HashedPassword = ? WHERE UserID = ?",
                hashed_pw, user_id
            )
            conn.commit()

        return {"message": "Password reset successful"}

    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

@app.get("/user-profile")
def get_user_profile(username: str):
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

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
            SUM(gs.GuessPercentage) + (100 * (9 - COUNT(DISTINCT CONCAT(ug.RowCriterion, '-', ug.ColumnCriterion))
))
            AS RarityScore
        FROM UserGuesses ug
        JOIN (
            SELECT GridID, RowCriterion, ColumnCriterion, FullName,
                   COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(PARTITION BY GridID, RowCriterion, ColumnCriterion), 0) AS GuessPercentage
            FROM UserGuesses
            WHERE IsCorrect = 1
            GROUP BY GridID, RowCriterion, ColumnCriterion, FullName
        ) gs
          ON ug.GridID = gs.GridID
         AND ug.RowCriterion = gs.RowCriterion
         AND ug.ColumnCriterion = gs.ColumnCriterion
         AND ug.FullName = gs.FullName
        WHERE ug.GameID = g.GameID AND ug.IsCorrect = 1
    ) AS ProfileRarity
    WHERE g.Completed = 1 AND (
        g.UserID IN ({user_placeholders}) OR g.GuestID IN ({guest_placeholders})
    )
            """, all_params)

            stats = cursor.fetchone() or (0, 0.0, 0.0, 0.0)


            # ✅ Current streak
            cursor.execute(f"""
                WITH OrderedGames AS (
                    SELECT 
                        PlayedAt,
                        Completed,
                        ROW_NUMBER() OVER (ORDER BY PlayedAt DESC) AS rn,
                        ROW_NUMBER() OVER (PARTITION BY Completed ORDER BY PlayedAt DESC) AS group_rn
                    FROM Games
                    WHERE UserID IN ({user_placeholders}) OR GuestID IN ({guest_placeholders})
                )
                SELECT COUNT(*) AS CurrentStreak
                FROM OrderedGames
                WHERE rn = group_rn AND rn <= (
                    SELECT MIN(rn)
                    FROM OrderedGames
                    WHERE Completed = 0
                )
            """, all_params)
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
        print("❌ PROFILE ERROR:", str(e))  # ✅ Add this line
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {str(e)}")


@app.post("/start-game")
def start_game(guest_id: Optional[str] = None, grid_id: Optional[int] = None):
    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()

        # ✅ Use active grid if none provided
        if not grid_id:
            cursor.execute("SELECT TOP 1 GridID FROM dbo.DailyGrids WHERE Status = 'Active' ORDER BY GridDate DESC")
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="No active grid found")
            grid_id = result[0]

        # ✅ Fetch row/column headers from DailyGrids
        cursor.execute("""
            SELECT Row1, Row2, Row3, Column1, Column2, Column3
            FROM dbo.DailyGrids
            WHERE GridID = ?
        """, (grid_id,))
        grid_data = cursor.fetchone()
        if not grid_data:
            raise HTTPException(status_code=404, detail="Grid not found")

        rows = [grid_data[0], grid_data[1], grid_data[2]]
        columns = [grid_data[3], grid_data[4], grid_data[5]]

        return {
            "grid_id": grid_id,
            "rows": rows,
            "columns": columns
        }



@app.get("/game-progress")
def game_progress(grid_id: int, guest_id: Optional[str] = None, username: Optional[str] = None):
    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()

        user_ids = []
        guest_ids = []

        if username:
            cursor.execute("SELECT UserID, GuestID FROM dbo.Users WHERE Username = ?", username)
            user_rows = cursor.fetchall()
            if not user_rows:
                return {"status": "new"}  # ✅ If username exists but has no history
            user_ids = [row[0] for row in user_rows if row[0] is not None]
            guest_ids = [str(row[1]) for row in user_rows if row[1] is not None]
        elif guest_id:
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
            "remaining_attempts": max(0, 9 - guesses_made)
        }


@app.get("/grid")
def get_grid():
    """Fetch today's active grid from DailyGrids and generate valid answers dynamically."""
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
            rows = [grid[1], grid[2], grid[3]]
            cols = [grid[4], grid[5], grid[6]]

            # Dynamically compute valid answers for each cell
            grid_data = {
                (row, col): fetch_riders_for_criterion(row, conn) & fetch_riders_for_criterion(col, conn)
                for row in rows for col in cols
            }

            return {
                "grid_id": grid_id,
                "rows": rows,
                "columns": cols,
                "grid_data": {f"{row},{col}": list(riders) for (row, col), riders in grid_data.items()}
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
@app.get("/grid/{grid_id}")
def get_specific_grid(grid_id: int):
    """Load a specific grid by GridID (archived or active)."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
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
def submit_guess(guess: GuessRequest, guest_id: UUID = Query(None), username: str = Query(None)):
    try:
        grid_id = guess.grid_id
        row = guess.row
        column = guess.column
        rider = guess.rider

        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Ensure GuestID exists in Users table
            if guest_id:
                cursor.execute("SELECT 1 FROM dbo.Users WHERE GuestID = ?", str(guest_id))
                exists = cursor.fetchone()
                if not exists:
                    cursor.execute("INSERT INTO dbo.Users (GuestID, CreatedAt) VALUES (?, GETDATE())", str(guest_id))
                    conn.commit()

            # ✅ 1. Resolve UserID(s) and GuestID(s)
            user_ids, guest_ids = [], []

            if username:
                cursor.execute("SELECT UserID, GuestID FROM dbo.Users WHERE Username = ?", username)
                ids = cursor.fetchall()
                user_ids = [row[0] for row in ids if row[0] is not None]
                guest_ids = [str(row[1]) for row in ids if row[1] is not None]
            elif guest_id:
                user_ids, guest_ids = resolve_all_user_ids(guest_id, conn)
            else:
                raise HTTPException(status_code=400, detail="Missing guest_id or username")

            # ✅ 2. Look for existing GameID
            cursor.execute(f"""
                SELECT TOP 1 GameID, Completed FROM dbo.Games
                WHERE GridID = ? AND (
                    {" OR ".join(["UserID = ?" for _ in user_ids] + ["GuestID = ?" for _ in guest_ids])}
                )
                ORDER BY PlayedAt DESC
            """, (grid_id, *user_ids, *guest_ids))
            game_row = cursor.fetchone()

            if game_row:
                game_id, completed = game_row
                if completed:
                    raise HTTPException(status_code=400, detail="This game is already completed.")
            else:
                # ✅ 3. Create new game
                cursor.execute("""
                    INSERT INTO dbo.Games (GridID, UserID, GuestID, GuessesMade, GuessesCorrect, Completed, PlayedAt)
                    OUTPUT INSERTED.GameID
                    VALUES (?, ?, ?, 0, 0, 0, GETDATE());
                """, grid_id, user_ids[0] if user_ids else None, guest_ids[0] if guest_ids else None)

                game_id_row = cursor.fetchone()
                if not game_id_row:
                    raise HTTPException(status_code=500, detail="Failed to retrieve newly created GameID")
                game_id = game_id_row[0]

            # ✅ 4. Check for duplicate correct guesses or already-filled cell
            cursor.execute("""
    SELECT RowCriterion, ColumnCriterion, FullName, IsCorrect FROM dbo.UserGuesses
    WHERE GameID = ?;
""", game_id)
            previous_guesses = cursor.fetchall()

            used_correct_riders = set(row[2].lower() for row in previous_guesses if row[2] and row[3] == 1)
            correct_cells = {(row[0], row[1]) for row in previous_guesses if row[3] == 1}

# ✅ Block if this rider was already used correctly in another cell
            if rider.lower() in used_correct_riders:
                return JSONResponse(status_code=200, content={
        "message": f"{rider} already used correctly in another cell",
        "is_correct": False,
        "duplicate": True,
        "game_id": game_id,
        "remaining_attempts": None
    })

# ✅ Block only if this cell has already been guessed CORRECTLY
            if (row, column) in correct_cells:
                return JSONResponse(status_code=200, content={
        "message": f"Cell ({row}, {column}) already answered correctly, try another",
        "is_correct": False,
        "duplicate": True,
        "game_id": game_id,
        "remaining_attempts": None
    })



            # ✅ 5. Validate if guess is correct using criteria logic
            valid_riders_row = fetch_riders_for_criterion(row, conn)
            valid_riders_col = fetch_riders_for_criterion(column, conn)
            valid_riders = valid_riders_row & valid_riders_col

            is_correct = rider.strip().lower() in {r.strip().lower() for r in valid_riders}

            # ✅ 6. Fetch image URL (optional fallback)
            cursor.execute("SELECT ImageURL FROM dbo.Rider_List WHERE FullName = ?", rider)
            rider_image = cursor.fetchone()
            image_url = rider_image[0] if rider_image else ""

            # ✅ 7. Insert guess
            cursor.execute("""
                INSERT INTO dbo.UserGuesses (GridID, RowCriterion, ColumnCriterion, FullName, IsCorrect, GuessedAt, UserID, GuestID, GameID, ImageURL)
                VALUES (?, ?, ?, ?, ?, GETDATE(), ?, ?, ?, ?)
            """, (
                grid_id,
                row,
                column,
                rider,
                int(is_correct),
                user_ids[0] if user_ids else None,
                guest_ids[0] if guest_ids else None,
                game_id,
                image_url
            ))

            # ✅ 8. Update stats in Games table
            cursor.execute("""
                UPDATE dbo.Games
                SET GuessesMade = GuessesMade + 1,
                    GuessesCorrect = GuessesCorrect + ?
                WHERE GameID = ?
            """, int(is_correct), game_id)

            # ✅ 9. Count remaining attempts
            cursor.execute("SELECT COUNT(*) FROM dbo.UserGuesses WHERE GameID = ?", game_id)
            total_guesses = cursor.fetchone()[0]
            remaining_attempts = max(0, 9 - total_guesses)

            # ✅ 10. Optionally mark completed
            if remaining_attempts == 0:
                cursor.execute("UPDATE dbo.Games SET Completed = 1 WHERE GameID = ?", game_id)
            # ✅ 11. Fetch guess percentage
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

            percentage_result = cursor.fetchone()
            guess_percentage = round(percentage_result[0], 2) if percentage_result else 0.0
    
            conn.commit()

            if not is_correct:
                conn.commit()
                return {
                    "is_correct": False,
                    "rider": None,
                    "row": row,
                    "column": column,
                    "image_url": None,
                    "guess_percentage": 0,
                    "remaining_attempts": remaining_attempts,
                    "game_id": game_id
                }

# ✅ Else return correct guess info
            return {
                "is_correct": True,
                "rider": rider,
                "row": row,
                "column": column,
                "image_url": image_url,
                "guess_percentage": guess_percentage,
                "remaining_attempts": remaining_attempts,
                "game_id": game_id
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/current-guess-percentage")
def current_guess_percentage(grid_id: int, row: str, column: str, rider: str):
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # Calculate how often this rider was guessed correctly for the specified cell
            cursor.execute("""
                WITH CorrectGuesses AS (
                    SELECT GridID, RowCriterion, ColumnCriterion, FullName, COUNT(*) AS GuessCount
                    FROM dbo.UserGuesses
                    WHERE GridID = ? AND RowCriterion = ? AND ColumnCriterion = ? AND IsCorrect = 1
                    GROUP BY GridID, RowCriterion, ColumnCriterion, FullName
                )
                SELECT 
                    cg.FullName,
                    (cg.GuessCount * 100.0 / NULLIF(total.TotalGuesses, 0)) AS GuessPercentage
                FROM CorrectGuesses cg
                JOIN (
                    SELECT GridID, RowCriterion, ColumnCriterion, SUM(GuessCount) AS TotalGuesses
                    FROM CorrectGuesses
                    GROUP BY GridID, RowCriterion, ColumnCriterion
                ) total ON cg.GridID = total.GridID
                         AND cg.RowCriterion = total.RowCriterion
                         AND cg.ColumnCriterion = total.ColumnCriterion
                WHERE cg.FullName = ?
            """, (grid_id, row, column, rider))

            result = cursor.fetchone()
            percentage = round(result[1], 2) if result else 0.0

            return {"guess_percentage": percentage}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch guess percentage: {str(e)}")



@app.post("/give-up")
def give_up(grid_id: int, guest_id: Optional[str] = None, username: Optional[str] = None):
    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()

        user_ids = []
        guest_ids = []

        if username:
            cursor.execute("SELECT UserID, GuestID FROM dbo.Users WHERE Username = ?", username)
            user_rows = cursor.fetchall()
            if not user_rows:
                raise HTTPException(status_code=404, detail="No user records found for username")
            user_ids = [row[0] for row in user_rows if row[0] is not None]
            guest_ids = [str(row[1]) for row in user_rows if row[1] is not None]
        elif guest_id:
            user_ids, guest_ids = resolve_all_user_ids(guest_id, conn)
        else:
            raise HTTPException(status_code=400, detail="guest_id or username is required")

        if not user_ids and not guest_ids:
            raise HTTPException(status_code=404, detail="User not found")

        conditions = []
        params = [grid_id]

        if user_ids:
            conditions.append(f"UserID IN ({','.join(['?'] * len(user_ids))})")
            params.extend(user_ids)

        if guest_ids:
            conditions.append(f"GuestID IN ({','.join(['?'] * len(guest_ids))})")
            params.extend(guest_ids)

        where_clause = " OR ".join(conditions)

        # ✅ Find latest GameID
        cursor.execute(f"""
            SELECT TOP 1 GameID, Completed FROM dbo.Games
            WHERE GridID = ? AND ({where_clause})
            ORDER BY PlayedAt DESC
        """, tuple(params))

        game = cursor.fetchone()

        if not game:
            raise HTTPException(status_code=404, detail="No game found for user on this grid")

        game_id, completed = game
        if completed:
            return {"message": "Game already marked as completed."}

        # ✅ Update it to mark as completed
        cursor.execute("UPDATE dbo.Games SET Completed = 1 WHERE GameID = ?", game_id)
        conn.commit()

        return {"message": "Game marked as completed", "game_id": game_id}


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

# ✅ Extract grid_id from query param if provided
            grid_id = request.query_params.get("grid_id")
            if grid_id:
                grid_id = int(grid_id)  # ensure it's an int
            else:
    # Fallback to active grid if none specified
                cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = ?", ('Active',))
                grid_id_result = cursor.fetchone()
                if not grid_id_result:
                    raise HTTPException(status_code=404, detail="No active grid found.")
                grid_id = grid_id_result[0]


            # ✅ Fetch Game ID for the specific guest
            user_ids, guest_ids = resolve_all_user_ids(UUID(guest_id), conn)
            cursor.execute(f"""
                SELECT TOP 1 GameID FROM dbo.Games
                WHERE GridID = ? AND (
                    UserID IN ({','.join(['?']*len(user_ids))}) OR GuestID IN ({','.join(['?']*len(guest_ids))})
                )
                ORDER BY PlayedAt DESC
            """, (grid_id, *user_ids, *guest_ids))


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
                        COUNT(DISTINCT CONCAT(ug.RowCriterion, '-', ug.ColumnCriterion)) AS AnsweredCells,
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

@app.get("/daily-leaderboard")
def get_daily_leaderboard():
    """Returns the top 20 lowest rarity scores for the active grid, deduplicated by Username or GuestID."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

            # ✅ Get active grid ID
            cursor.execute("SELECT GridID FROM dbo.DailyGrids WHERE Status = 'Active'")
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="No active grid found.")
            grid_id = result[0]

            # ✅ Run rarity score query deduplicated per Username/GuestID
            cursor.execute("""
                WITH GameSessions AS (
                    SELECT 
                        g.GameID,
                        g.GridID,
                        g.PlayedAt,
                        u.Username,
                        g.GuestID,
                        COALESCE(u.Username, CAST(g.GuestID AS VARCHAR(100))) AS PlayerKey
                    FROM dbo.Games g
                    LEFT JOIN dbo.Users u ON g.GuestID = u.GuestID
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
                CorrectGuesses AS (
                    SELECT GridID, RowCriterion, ColumnCriterion, FullName, COUNT(*) AS RiderGuessCount
                    FROM dbo.UserGuesses
                    WHERE IsCorrect = 1
                    GROUP BY GridID, RowCriterion, ColumnCriterion, FullName
                ),
                TotalGuessesPerCell AS (
                    SELECT GridID, RowCriterion, ColumnCriterion, SUM(RiderGuessCount) AS TotalCellGuesses
                    FROM CorrectGuesses
                    GROUP BY GridID, RowCriterion, ColumnCriterion
                ),
                GuessStats AS (
                    SELECT cg.GridID, cg.RowCriterion, cg.ColumnCriterion, cg.FullName,
                           (cg.RiderGuessCount * 100.0 / NULLIF(tg.TotalCellGuesses, 0)) AS GuessPercentage
                    FROM CorrectGuesses cg
                    JOIN TotalGuessesPerCell tg
                      ON cg.GridID = tg.GridID
                     AND cg.RowCriterion = tg.RowCriterion
                     AND cg.ColumnCriterion = tg.ColumnCriterion
                ),
                UserCorrectGuesses AS (
                    SELECT ug.GameID, ug.RowCriterion, ug.ColumnCriterion, ug.FullName,
                           gs.GuessPercentage
                    FROM dbo.UserGuesses ug
                    JOIN GuessStats gs
                      ON ug.GridID = gs.GridID
                     AND ug.RowCriterion = gs.RowCriterion
                     AND ug.ColumnCriterion = gs.ColumnCriterion
                     AND ug.FullName = gs.FullName
                    WHERE ug.IsCorrect = 1
                ),
                RarityScoreRaw AS (
                    SELECT GameID,
                           COUNT(DISTINCT RowCriterion + '|' + ColumnCriterion) AS AnsweredCells,
                           SUM(GuessPercentage) AS TotalGuessPercentage
                    FROM UserCorrectGuesses
                    GROUP BY GameID
                )
                SELECT TOP 20 
                    COALESCE(s.Username, 'Guest') AS Username,
                    ROUND(r.TotalGuessPercentage + (100 * (9 - r.AnsweredCells)), 2) AS RarityScore
                FROM RarityScoreRaw r
                JOIN LatestGamePerPlayer l ON r.GameID = l.GameID
                JOIN GameSessions s ON r.GameID = s.GameID
                ORDER BY RarityScore ASC
            """, (grid_id,))

            rows = cursor.fetchall()
            leaderboard = [
                {"username": row[0], "rarity_score": float(row[1])}
                for row in rows
            ]

            return leaderboard

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating leaderboard: {str(e)}")

    
@app.get("/grid-archive")
def get_grid_archive(guest_id: Optional[UUID] = Query(None), username: Optional[str] = Query(None)):
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()

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
                user_ids, guest_ids = resolve_all_user_ids(guest_id, conn)

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

            cursor.execute(f"""
                SELECT 
                    d.GridID, d.GridDate, 
                    game.Completed, game.GuessesCorrect, 
                    (
                        SELECT 
                            ROUND(
                                COALESCE(SUM(gs.GuessPercentage), 0) 
                                + (100 * (9 - COUNT(DISTINCT CONCAT(ug.RowCriterion, '-', ug.ColumnCriterion)))), 2)
                        FROM UserGuesses ug
                        JOIN (
                            SELECT GridID, RowCriterion, ColumnCriterion, FullName, 
                                   COUNT(*) * 100.0 / 
                                   NULLIF(SUM(COUNT(*)) OVER(PARTITION BY GridID, RowCriterion, ColumnCriterion), 0) AS GuessPercentage
                            FROM UserGuesses
                            WHERE IsCorrect = 1
                            GROUP BY GridID, RowCriterion, ColumnCriterion, FullName
                        ) gs ON ug.GridID = gs.GridID AND ug.RowCriterion = gs.RowCriterion 
                             AND ug.ColumnCriterion = gs.ColumnCriterion AND ug.FullName = gs.FullName
                        WHERE ug.GameID = game.GameID AND ug.IsCorrect = 1
                    ) AS RarityScore
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




@app.post("/populate-grid-pool")
def populate_grid_pool(max_to_generate: int = 1000):
    """Precompute and store valid grids into the GridPool table."""
    from itertools import combinations
    inserted_count = 0

    with pyodbc.connect(CONN_STR) as conn:
        cursor = conn.cursor()
        # ✅ Only use criteria that have SQL queries defined
        valid_criteria = [c for c in criteria_pool if c in criteria_queries]
        all_combinations = list(combinations(valid_criteria, 6))

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