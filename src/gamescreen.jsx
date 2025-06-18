import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";
import SummaryModal from "./SummaryModal.jsx";
import { v4 as uuidv4 } from 'uuid';
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faInstagram, faXTwitter } from "@fortawesome/free-brands-svg-icons";
import { faQuestionCircle } from "@fortawesome/free-solid-svg-icons";
import HowToPlayModal from "./HowToPlayModal";
import debounce from "lodash/debounce";
import LeaderboardModal from './dailyleaderboard.jsx';
import { Link } from "react-router-dom";
import { useParams } from "react-router-dom";
import UpdateModal from "./updatemodal";



const API_BASE_URL = import.meta.env.VITE_API_URL;

function Game() {
  const [grid, setGrid] = useState(Array(3).fill(Array(3).fill("")));
  const [rows, setRows] = useState([]);
  const [columns, setColumns] = useState([]);
  const [guessesLeft, setGuessesLeft] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [riderName, setRiderName] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [incorrectGuesses, setIncorrectGuesses] = useState({});
  const [gameSummary, setGameSummary] = useState(null);
  const [gameOver, setGameOver] = useState(false);
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);
  const [guestId, setGuestId] = useState(null);
  const { grid_id } = useParams();
  const [gridId, setGridId] = useState(() =>grid_id && !isNaN(parseInt(grid_id)) ? parseInt(grid_id) : null);
  const [correctGuesses, setCorrectGuesses] = useState(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [isHowToPlayOpen, setIsHowToPlayOpen] = useState(false);
  const [submittingGuess, setSubmittingGuess] = useState(false);
  const [isLeaderboardOpen, setLeaderboardOpen] = useState(false);
  const [leaderboardData, setLeaderboardData] = useState([]);
  const [hydrated, setHydrated] = useState(false); // 🔄 Track whether backend/local restore is complete
  const [hasOpenedSummary, setHasOpenedSummary] = useState(false);
  const [readyForSummaryPopup, setReadyForSummaryPopup] = useState(false);
  const [showUpdateModal, setShowUpdateModal] = useState(false); // 👈 ADD THIS



  const categoryFlags = {
    "United States": "https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg",
    "France": "https://upload.wikimedia.org/wikipedia/en/c/c3/Flag_of_France.svg",
    "Australia": "https://upload.wikimedia.org/wikipedia/en/b/b9/Flag_of_Australia.svg",
    "United Kingdom": "https://upload.wikimedia.org/wikipedia/en/a/ae/Flag_of_the_United_Kingdom.svg",
    "Japan": "https://upload.wikimedia.org/wikipedia/en/9/9e/Flag_of_Japan.svg",
    "Spain": "https://upload.wikimedia.org/wikipedia/en/9/9a/Flag_of_Spain.svg",
    "Canada": "https://upload.wikimedia.org/wikipedia/commons/c/cf/Flag_of_Canada.svg",
    "South Africa": "https://upload.wikimedia.org/wikipedia/commons/a/af/Flag_of_South_Africa.svg",
    "Brazil": "https://upload.wikimedia.org/wikipedia/en/0/05/Flag_of_Brazil.svg"
  };

  const categoryLogos = {
    "KTM": "https://assets.liveracemedia.com/manufacturers/primary/ktm.png",
    "HON": "https://assets.liveracemedia.com/manufacturers/primary/honda.png",
    "HUS": "https://assets.liveracemedia.com/manufacturers/primary/husqvarna.png",
    "YAM": "https://assets.liveracemedia.com/manufacturers/primary/yamaha.png",
    "KAW": "https://assets.liveracemedia.com/manufacturers/primary/kawasaki.png",
    "GAS": "https://assets.liveracemedia.com/manufacturers/primary/gasgas.png",
    "SUZ": "https://assets.liveracemedia.com/manufacturers/primary/suzuki.png"
  };
  
  const categoryDisplayNames = {
    // 🌍 Countries
    "United States": "United States nationality",
    "France": "France nationality",
    "Australia": "Australia nationality",
    "United Kingdom": "United Kingdom nationality",
    "Japan": "Japan nationality",
    "Spain": "Spain nationality",
    "Canada": "Canada nationality",
    "South Africa": "South Africa nationality",
    "Brazil": "Brazil nationality",
  
    // 🏍 Brands
    "KTM": "KTM",
    "HON": "Honda",
    "HUS": "Husqvarna",
    "YAM": "Yamaha",
    "KAW": "Kawasaki",
    "GAS": "GasGas",
    "SUZ": "Suzuki"
  };
  
  

  // ✅ Close the input container when clicking anywhere else
useEffect(() => {
  const handleClickOutside = (event) => {
    if (selectedCell && !event.target.closest(".input-container") && !event.target.closest(".grid-cell")) {
      setSelectedCell(null);
    }
  };

  document.addEventListener("click", handleClickOutside);
  return () => document.removeEventListener("click", handleClickOutside);
}, [selectedCell]);

useEffect(() => {
  if (isSummaryOpen || isHowToPlayOpen) {
    document.body.classList.add("modal-open");
  } else {
    document.body.classList.remove("modal-open");
  }
}, [isSummaryOpen, isHowToPlayOpen]);


// ✅ Generate or Retrieve UUID from LocalStorage
useEffect(() => {
  let storedGuestId = localStorage.getItem('guest_id');
  if (!storedGuestId) {
    storedGuestId = uuidv4(); // Generate a new UUID
    localStorage.setItem('guest_id', storedGuestId);
  }
  setGuestId(storedGuestId);
}, []);


// ✅ Fetch grid data from backend only after guestId is set
useEffect(() => {
  if (!guestId) return;

  const initializeGrid = async () => {
    try {
      const endpoint = grid_id && !isNaN(parseInt(grid_id)) ? `/grid/${grid_id}` : `/grid`;
      const response = await axios.get(`${API_BASE_URL}${endpoint}?guest_id=${guestId}`);
      setRows(response.data.rows);
      setColumns(response.data.columns);
      setGridId(response.data.grid_id);

      if (response.data.grid_data) {
        const formattedGrid = response.data.rows.map(row =>
          response.data.columns.map(col => response.data.grid_data[`${row},${col}`] || "")
        );
        setGrid(formattedGrid);
      }

      // ✅ Load previous state (optional fallback)
      const savedUsed = JSON.parse(localStorage.getItem(`used_guesses_${response.data.grid_id}`)) || [];
      const savedIncorrect = JSON.parse(localStorage.getItem(`incorrect_guesses_${response.data.grid_id}`)) || {};
      const totalIncorrect = Object.values(savedIncorrect).reduce((acc, cell) => acc + cell.length, 0);

      setIsLoading(false);
    } catch (error) {
      console.error("Error initializing grid:", error);
      setIsLoading(false);
    }
  };

  initializeGrid();
}, [guestId, grid_id]); // ✅ rerun whenever guestId or grid_id changes


useEffect(() => {
  const hasSeenHowToPlay = localStorage.getItem("hasSeenHowToPlay");

  if (!hasSeenHowToPlay) {
    setIsHowToPlayOpen(true);
    localStorage.setItem("hasSeenHowToPlay", "true");
  }
}, []);


// ✅ Check if the grid ID in localStorage is different from the current grid
useEffect(() => {
  const existingGame = JSON.parse(localStorage.getItem('current_game'));

  if (guestId && gridId) {
    if (!existingGame || existingGame.grid_id !== gridId) {
      localStorage.setItem(
        'current_game',
        JSON.stringify({ guest_id: guestId, grid_id: gridId })
      );
    }
  }
}, [guestId, gridId]);


useEffect(() => {
  const modalSeenKey = "seenUpdateModal_2025_06_18";
  const now = new Date();

  // Convert current time to Eastern Time (EDT/EST)
  const nowUTC = now.getTime() + now.getTimezoneOffset() * 60000;
  const eastCoastOffset = -4 * 60; // EDT is UTC-4
  const nowEST = new Date(nowUTC + eastCoastOffset * 60000);

  // Target time: June 18, 2025 @ 4:00 AM Eastern
  const showTime = new Date("2025-06-18T04:00:00-04:00");

  const shouldShowModal = !localStorage.getItem(modalSeenKey);


  if (shouldShowModal) {
    setShowUpdateModal(true);
    localStorage.setItem(modalSeenKey, "true");
  }
}, []);



const startGame = async (guestId, gridId) => {
  try {
    const endpoint = gridId
      ? `/start-game?guest_id=${guestId}&grid_id=${gridId}`
      : `/start-game?guest_id=${guestId}`;

    const response = await axios.post(`${API_BASE_URL}${endpoint}`);

    if (response.data.completed) {
      setGameOver(true);
      setGuessesLeft(0);
    }

    if (response.data.game_id) {
      // ✅ Store the game ID with grid-specific key
      localStorage.setItem(`game_id_${gridId}`, response.data.game_id);
    }

    console.log("✅ Game started:", response.data);
  } catch (error) {
    console.error("Error starting game:", error.response?.data?.detail || error.message);
  }
};


const restoreGameFromBackend = async () => {
  if (!guestId || guestId === "undefined" || !gridId) return;

  try {
    const username = localStorage.getItem("username");
    const progressUrl = username
      ? `${API_BASE_URL}/game-progress?grid_id=${gridId}&username=${username}`
      : `${API_BASE_URL}/game-progress?grid_id=${gridId}&guest_id=${guestId}`;

    const response = await axios.get(progressUrl);

    if (response.data.status === "new") {
      // ✅ No game exists yet for this user — backend will start on first guess
      await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}&grid_id=${gridId}`);
      setGuessesLeft(9);
      setGameOver(false);
      setHydrated(true);
      return;
    }

    if (response.data.status === "in_progress" || response.data.status === "completed") {
      // ✅ Load grid structure from backend
      const layoutRes = await axios.get(`${API_BASE_URL}/grid/${gridId}`);
      const rowHeaders = layoutRes.data.rows;
      const columnHeaders = layoutRes.data.columns;
      setRows(rowHeaders);
      setColumns(columnHeaders);

      // ✅ Restore game state from backend guesses
      const restoredGrid = Array(3).fill(null).map(() => Array(3).fill(""));
      const restoredUsedGuesses = [];
      const restoredIncorrectGuesses = {};

      response.data.guesses.forEach(guess => {
        const rowIndex = rowHeaders.indexOf(guess.row);
        const colIndex = columnHeaders.indexOf(guess.column);
        if (rowIndex !== -1 && colIndex !== -1) {
          if (guess.is_correct) {
            restoredGrid[rowIndex][colIndex] = {
              name: guess.rider,
              image: guess.image_url || "",
              guess_percentage: 0
            };
            restoredUsedGuesses.push(guess.rider);
          } else {
            const cellKey = `${rowIndex}-${colIndex}`;
            if (!restoredIncorrectGuesses[cellKey]) {
              restoredIncorrectGuesses[cellKey] = [];
            }
            restoredIncorrectGuesses[cellKey].push(guess.rider);
          }
        }
      });

      setGrid(restoredGrid);
      setCorrectGuesses(new Set(restoredUsedGuesses));
      setIncorrectGuesses(restoredIncorrectGuesses);
      setGuessesLeft(response.data.remaining_attempts);
      setGameOver(response.data.status === "completed");

      if (response.data.status === "completed") {
        setReadyForSummaryPopup(true);
      }

      // ✅ Update rarity percentages from backend
      const updatePercentages = async () => {
        const updates = [];

        for (let rowIndex = 0; rowIndex < 3; rowIndex++) {
          for (let colIndex = 0; colIndex < 3; colIndex++) {
            const cell = restoredGrid[rowIndex][colIndex];
            if (cell?.name) {
              const rowLabel = rowHeaders[rowIndex];
              const colLabel = columnHeaders[colIndex];
              const url = `${API_BASE_URL}/current-guess-percentage?grid_id=${gridId}&row=${encodeURIComponent(rowLabel)}&column=${encodeURIComponent(colLabel)}&rider=${encodeURIComponent(cell.name)}`;

              updates.push(
                axios.get(url)
                  .then(res => {
                    restoredGrid[rowIndex][colIndex].guess_percentage = res.data.guess_percentage || 0;
                  })
                  .catch(err => console.error("Guess % fetch failed:", err))
              );
            }
          }
        }

        await Promise.all(updates);
        setGrid([...restoredGrid]); // ✅ Trigger UI update
      };

      await updatePercentages();
    }
  } catch (error) {
    console.error("Failed to restore from backend:", error);
  } finally {
    setHydrated(true);
  }
};


useEffect(() => {
  const readyToRestore = gridId && guestId && rows.length && columns.length;
  if (!readyToRestore) return;

  const runRestore = async () => {
    await restoreGameFromBackend();
    setHydrated(true);
  };

  runRestore();
}, [gridId, guestId, rows.length, columns.length]);


  // Fetch game summary when game ends
useEffect(() => {
  if (gameOver) {
      fetchGameSummary();
  }
}, [gameOver]);

// ✅ NEW: Automatically open summary modal when guesses hit 0
useEffect(() => {
  if (guessesLeft === 0) {
      console.log("Game over detected. Opening summary modal...");
      fetchGameSummary();
      console.log("Fetching summary for grid_id:", gridId);
      setGameOver(true); 
      setIsSummaryOpen(true); // ✅ Open summary modal when game ends
      setSelectedCell(null); // ✅ Ensure input box disappears when the summary opens
  }
}, [guessesLeft]);

// ✅ Open summary modal automatically for completed archived grids after hydration
useEffect(() => {
  if (
    hydrated &&
    readyForSummaryPopup &&
    !hasOpenedSummary &&
    gridId &&
    guestId
  ) {
    fetchGameSummary(true);
    setHasOpenedSummary(true);
  }
}, [hydrated, readyForSummaryPopup, hasOpenedSummary, gridId, guestId]);


useEffect(() => {
  setHasOpenedSummary(false);
}, [gridId]);

useEffect(() => {
  setReadyForSummaryPopup(false);
}, [gridId]);

const fetchGameSummary = async (autoOpen = false) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/game-summary?guest_id=${guestId}&grid_id=${gridId}`);
    const data = response.data;

    const formattedMostGuessed = rows.map(row =>
      columns.map(col => {
        const found = data.most_guessed_riders.find(item => item.row === row && item.col === col);
        return found || { rider: "No data", guess_percentage: 0, image: null };
      })
    );

    const formattedCorrectPercentages = rows.map(row =>
      columns.map(col =>
        data.cell_completion_rates.find(item => item.row === row && item.col === col) || { completion_percentage: 0 }
      )
    );

    setGameSummary({
      ...data,
      rarityScores: data.rarity_score,
      mostGuessedGrid: formattedMostGuessed,
      correctPercentageGrid: formattedCorrectPercentages
    });

    if (autoOpen) {
      setIsSummaryOpen(true);
      setHasOpenedSummary(true); // prevent re-trigger
    }

  } catch (error) {
    console.error("Error fetching game summary:", error);
  }
};

  // Handle cell selection
  const handleCellClick = (rowIndex, colIndex) => {
    if (guessesLeft === 0) return; // Prevent input after game over
  
    // ✅ If already selected, close it. Otherwise, open it
    setSelectedCell(prev =>
      prev?.row === rowIndex && prev?.col === colIndex ? null : { row: rowIndex, col: colIndex }
    );
  
    setRiderName("");
    setSuggestions([]);
  };
  
// ✅ Debounced autocomplete fetch
const debouncedFetchSuggestions = useRef(
  debounce(async (input) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/autocomplete?query=${input}`);
      if (response.data?.riders) {
        setSuggestions(response.data.riders);
      } else {
        setSuggestions([]);
      }
    } catch (error) {
      console.error("Error fetching autocomplete suggestions:", error);
      setSuggestions([]);
    }
  }, 500)
).current;

useEffect(() => {
  return () => {
    debouncedFetchSuggestions.cancel();
  };
}, []);


// Replace your old handleInputChange with this:
const handleInputChange = (event) => {
  const input = event.target.value;
  setRiderName(input);
  if (input.length >= 2) {
    debouncedFetchSuggestions(input);
  } else {
    setSuggestions([]);
  }
};


const handleSubmit = async (selectedRider = riderName) => {
  if (!selectedCell || selectedRider.trim() === "" || submittingGuess) return;
  if (guessesLeft <= 0) {
    alert("No more attempts left!");
    return;
  }

  setSubmittingGuess(true);

  try {
    if (!localStorage.getItem(`game_id_${gridId}`)) {
      const startResponse = await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}&grid_id=${gridId}`);
      if (startResponse.data.game_id) {
        localStorage.setItem(`game_id_${gridId}`, startResponse.data.game_id);
        setGameStarted(true);
      }
    }

    const requestBody = {
      rider: selectedRider,
      row: rows[selectedCell.row],
      column: columns[selectedCell.col],
      grid_id: gridId,
    };

    const response = await axios.post(
      `${API_BASE_URL}/guess?guest_id=${guestId}&grid_id=${gridId}`,
      requestBody,
      { headers: { "Content-Type": "application/json" } }
    );
setGuessesLeft(response.data.remaining_attempts);
    // ✅ Handle duplicate guess
    if (response.data.duplicate) {
      const cellKey = `${selectedCell.row}-${selectedCell.col}`;
      setIncorrectGuesses(prev => ({
        ...prev,
        [cellKey]: [...(prev[cellKey] || []), selectedRider]
      }));

      setRiderName(selectedRider); // ✅ Keep input filled
      debouncedFetchSuggestions(selectedRider); // ✅ Re-trigger autocomplete to keep dropdown
      setSuggestions(prev => {
        if (!prev.includes(selectedRider)) {
          return [selectedRider, ...prev];
        }
        return prev;
      });

      setSubmittingGuess(false);
      return;
    }

    // ✅ Handle incorrect guess
    if (!response.data.rider) {
      const cellKey = `${selectedCell.row}-${selectedCell.col}`;
      setIncorrectGuesses(prev => ({
        ...prev,
        [cellKey]: [...(prev[cellKey] || []), selectedRider]
      }));

      setRiderName(selectedRider); // ✅ Keep input filled
      debouncedFetchSuggestions(selectedRider);
      setSuggestions(prev => {
        if (!prev.includes(selectedRider)) {
          return [selectedRider, ...prev];
        }
        return prev;
      });

      setSubmittingGuess(false);
      return;
    }

    // ✅ Track guesses left
    

    // 🔒 Clear accidental overwrite of incorrect guess
    setGrid(prevGrid => {
  const newGrid = prevGrid.map(row => [...row]);

  const existing = newGrid[selectedCell.row][selectedCell.col];
  if (typeof existing === "string" || (typeof existing === "object" && existing?.name !== selectedRider)) {
    newGrid[selectedCell.row][selectedCell.col] = ""; // clear previous guess
  }

  return newGrid;
});


    // ✅ Track correct guesses
    setCorrectGuesses(prev => {
      const updatedGuesses = new Set([...prev, selectedRider]);
      localStorage.setItem(`used_guesses_${gridId}`, JSON.stringify([...updatedGuesses]));
      return updatedGuesses;
    });

    // ✅ Update grid with correct rider
    setGrid(prevGrid => {
      const newGrid = prevGrid.map(row => [...row]);
      newGrid[selectedCell.row][selectedCell.col] = {
        name: selectedRider,
        image: response.data.image_url || "",
        guess_percentage: response.data.guess_percentage || 0,
      };
      return newGrid;
    });

    setRiderName("");
    setSelectedCell(null);

    if (response.data.remaining_attempts === 0) {
      setGameOver(true);
      setReadyForSummaryPopup(true);
    }

  } catch (error) {
    console.error("Error submitting guess:", error);
    alert(error.response?.data?.detail || "An error occurred");
  } finally {
    setSubmittingGuess(false);
  }
};

const handleGiveUp = async () => {
  try {
    let storedGameId = localStorage.getItem(`game_id_${gridId}`);

    // ✅ Start game if none exists (preserves stateless DB linkage)
    if (!storedGameId) {
      const startResponse = await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}&grid_id=${gridId}`);
      if (startResponse.data.game_id) {
        storedGameId = startResponse.data.game_id;
        localStorage.setItem(`game_id_${gridId}`, startResponse.data.game_id);
        setGameStarted(true);
      }
    }

    // ✅ Submit give-up to backend
    await axios.post(`${API_BASE_URL}/give-up?guest_id=${guestId}&grid_id=${gridId}`);

    // ✅ Update frontend state to reflect end-of-game
    setGuessesLeft(0);
    setGameOver(true);
    setSelectedCell(null);
    setIsSummaryOpen(true);
    setReadyForSummaryPopup(true);

    // ✅ Optionally lock out any further guesses on this grid
    const updatedGrid = grid.map(row =>
      row.map(cell => {
        if (typeof cell === "object" && cell !== null && cell.name) {
          return cell; // preserve correct guesses
        }
        return ""; // lock empty cells
      })
    );
    setGrid(updatedGrid);

    // ✅ Optional: update localStorage for hydration consistency
    localStorage.setItem(`game_state_${gridId}`, JSON.stringify({
      grid: updatedGrid,
      incorrectGuesses,
      gameOver: true,
    }));

  } catch (error) {
    console.error("Error giving up:", error);
  }
};


const fetchLeaderboard = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/daily-leaderboard`);
    setLeaderboardData(response.data);
    setLeaderboardOpen(true);
  } catch (error) {
    console.error("Error loading leaderboard:", error);
  }
};
return (
  <>
    {/* ✅ Top banner appears on all pages now */}
    <div className="top-banner-wrapper">
      <div className="top-banner">
        <div className="banner-left">
          <span>smxmuse grids by</span>
          <img src="/smxmuse-logo.png" alt="smxmuse" className="banner-logo" />
        </div>
        <div className="banner-nav">
          <Link to="/" className="nav-link">Home</Link>
          <Link to="/gridarchive" className="nav-link">Grid Archive</Link>
          <Link to="/profile" className="nav-link">Profile</Link>
        </div>
        <div className="social-icons">
          <a href="https://www.instagram.com/smxmuse" target="_blank" rel="noopener noreferrer">
            <FontAwesomeIcon icon={faInstagram} className="social-icon" />
          </a>
          <a href="https://twitter.com/smxmuse" target="_blank" rel="noopener noreferrer">
            <FontAwesomeIcon icon={faXTwitter} className="social-icon" />
          </a>
          <button className="social-icon how-to-play-btn" onClick={() => setIsHowToPlayOpen(true)}>
            <FontAwesomeIcon icon={faQuestionCircle} />
          </button>
          <button className="social-icon how-to-play-btn" onClick={fetchLeaderboard}>
            🏆
          </button>
        </div>
      </div>
    </div>

    {isLoading ? (
      <div className="loading-screen"></div>
    ) : (
      <div className="container">
        <div className="game-layout">
          <div className="grid-wrapper">
            <div className="column-headers">
              <div className="grid-number-cell">Grid #{gridId}</div>
              {columns.map((col, index) => (
                <div key={index} className="header-cell">
                  {categoryFlags[col] ? (
                    <img src={categoryFlags[col]} alt={col} title={categoryDisplayNames[col] || col} className="header-flag" />
                  ) : categoryLogos[col] ? (
                    <img src={categoryLogos[col]} alt={col} title={categoryDisplayNames[col] || col} className="header-logo" />
                  ) : (
                    col
                  )}
                </div>
              ))}
            </div>

            <div className="grid-body">
              {rows.map((row, rowIndex) => (
                <div key={rowIndex} className="grid-row">
                  <div className="header-cell">
                    {categoryFlags[row] ? (
                      <img src={categoryFlags[row]} alt={row} title={categoryDisplayNames[row] || row} className="header-flag" />
                    ) : categoryLogos[row] ? (
                      <img src={categoryLogos[row]} alt={row} title={categoryDisplayNames[row] || row} className="header-logo" />
                    ) : (
                      row
                    )}
                  </div>

                  {grid[rowIndex].map((cell, colIndex) => (
                    <div
                      key={`${rowIndex}-${colIndex}`}
                      className={`grid-cell ${selectedCell?.row === rowIndex && selectedCell?.col === colIndex ? "selected" : ""}`}
                      onClick={() => handleCellClick(rowIndex, colIndex)}
                    >
                      {typeof cell === "object" && cell.image ? (
  <>
    <img src={cell.image} alt={cell.name} className="rider-image" />
    <div className="rider-name-banner">{cell.name}</div>
    {cell.guess_percentage !== undefined && cell.guess_percentage > 0 && (
      <div className="guess-percentage">{cell.guess_percentage}%</div>
    )}
  </>
) : null}



                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div className="side-panel-container">
            <div className="side-panel">
  {hydrated ? (
    <>
      {(guessesLeft !== null && guessesLeft > 0 && !gameOver) && (
        <>
          <p className="guess-counter">{guessesLeft}</p>
          <p className="guess-counter-label">Guesses Left</p>
        </>
      )}

      {(guessesLeft === 0 || gameOver) && (
        <>
          <p className="guess-counter">0</p>
          <p className="guess-counter-label">Guesses Left</p>
        </>
      )}

      {gameOver ? (
        <button className="summary-button" onClick={() => setIsSummaryOpen(true)}>View Summary</button>
      ) : (
        <button className="give-up-button" onClick={handleGiveUp}>Give Up</button>
      )}
    </>
  ) : (
    <>
      <p className="guess-counter">–</p>
      <p className="guess-counter-label">Guesses Left</p>
    </>
  )}
</div>
</div>
</div>

        {selectedCell && (
          <div className={`input-container ${selectedCell ? '' : 'hidden'}`}>
            <input 
              type="text" 
              placeholder="Enter rider name..." 
              className="input-box" 
              value={riderName} 
              onChange={handleInputChange} 
              autoFocus 
            />

            {suggestions.length > 0 && (
              <div className="autocomplete-list">
                <ul>
                  {suggestions
                    .filter(suggestion => !correctGuesses.has(suggestion))
                    .map((suggestion, index) => {
                      const isIncorrect = incorrectGuesses[`${selectedCell?.row}-${selectedCell?.col}`]?.includes(suggestion);
                      return (
                        <li key={index} className="suggestion-item">
                          <span className={isIncorrect ? "incorrect-guess" : ""}>{suggestion}</span>
                          {!isIncorrect && (
                            <button
                              className="select-button"
                              disabled={submittingGuess}
                              onClick={async () => {
                                setRiderName(suggestion);
                                await handleSubmit(suggestion);
                              }}
                            >
                              Select
                            </button>
                          )}
                        </li>
                      );
                    })}
                </ul>
              </div>
            )}
          </div>
        )}

        {isSummaryOpen && gameSummary && 
  gameSummary.mostGuessedGrid && 
  gameSummary.correctPercentageGrid &&
  gameSummary.mostGuessedGrid.length === 3 &&
  gameSummary.correctPercentageGrid.length === 3 && (
    <SummaryModal
      isOpen={isSummaryOpen}
      onClose={() => setIsSummaryOpen(false)}
      totalGames={gameSummary.total_games_played}
      averageScore={gameSummary.average_score}
      rarityScores={gameSummary.rarity_score}
      mostGuessedGrid={gameSummary.mostGuessedGrid}
      correctPercentageGrid={gameSummary.correctPercentageGrid}
      rows={rows}
      columns={columns}
      gridId={gridId}
      grid={grid}
      categoryFlags={categoryFlags}
      categoryLogos={categoryLogos}
      categoryDisplayNames={categoryDisplayNames}
    />
)}

        {isLeaderboardOpen && (
          <LeaderboardModal
            open={isLeaderboardOpen}
            onClose={() => setLeaderboardOpen(false)}
            leaderboardData={leaderboardData}
          />
        )}

        {isHowToPlayOpen && (
          <HowToPlayModal
            isOpen={isHowToPlayOpen}
            onClose={() => setIsHowToPlayOpen(false)}
          />
        )}
      </div>
    )}
    {showUpdateModal && (
  <UpdateModal onClose={() => setShowUpdateModal(false)} />
)}
  </>
);


}

export default Game;
