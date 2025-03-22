import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";
import SummaryModal from "./SummaryModal.jsx"; // ✅ Import Summary Modal
import { v4 as uuidv4 } from 'uuid';
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faInstagram, faXTwitter } from "@fortawesome/free-brands-svg-icons";
import { faQuestionCircle } from "@fortawesome/free-solid-svg-icons";
import HowToPlayModal from "./HowToPlayModal";

const API_BASE_URL = import.meta.env.VITE_API_URL;

function App() {
  const [grid, setGrid] = useState(Array(3).fill(Array(3).fill(""))); // 3x3 empty grid
  const [rows, setRows] = useState([]);
  const [columns, setColumns] = useState([]);
  const [guessesLeft, setGuessesLeft] = useState(9);
  const [selectedCell, setSelectedCell] = useState(null);
  const [riderName, setRiderName] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [incorrectGuesses, setIncorrectGuesses] = useState({});
  const [gameSummary, setGameSummary] = useState(null);
  const [gameOver, setGameOver] = useState(false);
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);
  const [guestId, setGuestId] = useState(null);
  const [gridId, setGridId] = useState(null); // Track the active grid ID
  const [correctGuesses, setCorrectGuesses] = useState(new Set());
  const [isLoading, setIsLoading] = useState(true); // ✅ New loading state
  const [isHowToPlayOpen, setIsHowToPlayOpen] = useState(false);
  const [submittingGuess, setSubmittingGuess] = useState(false);





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


// ✅ Generate or Retrieve UUID from LocalStorage
useEffect(() => {
  let storedGuestId = localStorage.getItem('guest_id');
  if (!storedGuestId) {
    storedGuestId = uuidv4(); // Generate a new UUID
    localStorage.setItem('guest_id', storedGuestId);
  }
  setGuestId(storedGuestId);
}, []);

useEffect(() => {
  if (guestId) {
    startGame(guestId);
  }
}, [guestId]);


// ✅ Fetch grid data from backend only after guestId is set
useEffect(() => {
  if (!guestId) return; // Wait until guestId is available

  const initializeGrid = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/grid?guest_id=${guestId}`);
      console.log("Fetched Grid Data:", response.data);
      setRows(response.data.rows);
      setColumns(response.data.columns);
  
      if (response.data.grid_data) {
        const formattedGrid = response.data.rows.map(row =>
          response.data.columns.map(col => response.data.grid_data[`${row},${col}`] || "")
        );
        setGrid(formattedGrid);
      } else {
        console.error("Grid data is empty:", response.data);
      }
  
      setGuessesLeft(response.data.remaining_attempts);
      setGridId(response.data.grid_id); // ✅ Store the grid ID for the daily game

      setIsLoading(false); // ✅ Everything is loaded, remove loading state
    } catch (error) {
      console.error("Error initializing grid:", error);
      setIsLoading(false); // ✅ Remove loading state even on error
    }
  };

  initializeGrid();
}, [guestId]);  // ✅ Runs when guestId is available


useEffect(() => {
  if (!guestId || !gridId) return; // Wait until both guestId and gridId are available

  const checkExistingGame = async () => {
    try {
      const response = await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}`);
      console.log("Start game response:", response.data);

      // ✅ Store game_id only if it exists
      if (response.data.game_id) {
        localStorage.setItem("game_id", response.data.game_id);
      }
    } catch (error) {
      console.error("Error checking existing game:", error.response?.data?.detail || error.message);
    }
  };

  checkExistingGame();
}, [guestId, gridId]); // ✅ Runs only when guestId and gridId are available

useEffect(() => {
  const hasSeenHowToPlay = localStorage.getItem("hasSeenHowToPlay");

  if (!hasSeenHowToPlay) {
    setIsHowToPlayOpen(true);
    localStorage.setItem("hasSeenHowToPlay", "true");
  }
}, []);



const resetGameForNewDay = () => {
  const previousGames = JSON.parse(localStorage.getItem("previous_games")) || {};

  // ✅ Save the completed game before clearing it
  if (gridId && localStorage.getItem(`game_state_${gridId}`)) {
    previousGames[`game_state_${gridId}`] = JSON.parse(localStorage.getItem(`game_state_${gridId}`));
  }

  localStorage.setItem("previous_games", JSON.stringify(previousGames));

  // ✅ Clear only the current game state but keep previous grids
  localStorage.removeItem(`game_state_${gridId}`);
  localStorage.setItem(
    'current_game',
    JSON.stringify({ guest_id: guestId, grid_id: gridId })
  );

  setGameOver(false);
  setGuessesLeft(9);
  setGrid(Array(3).fill(Array(3).fill(""))); 
  setSelectedCell(null);
  setIncorrectGuesses({});
  setGameSummary(null);
};




// ✅ Check if the grid ID in localStorage is different from the current grid
useEffect(() => {
  const existingGame = JSON.parse(localStorage.getItem('current_game'));

  if (guestId && gridId) {
    if (!existingGame || existingGame.grid_id !== gridId) {
      resetGameForNewDay();
      startGame(guestId);
      localStorage.setItem(
        'current_game',
        JSON.stringify({ guest_id: guestId, grid_id: gridId })
      );
    }
  }
}, [guestId, gridId]);


const startGame = async (guestId) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}`);
    console.log("Game started:", response.data);
  } catch (error) {
    console.error("Error starting game:", error.response?.data?.detail || error.message);
  }
};

useEffect(() => {
  if (!gridId) return;

  const savedGameState = localStorage.getItem(`game_state_${gridId}`);
  const savedIncorrectGuesses = localStorage.getItem(`incorrect_guesses_${gridId}`);
  const savedUsedGuesses = localStorage.getItem(`used_guesses_${gridId}`);

  let loadedGrid = Array(3).fill(Array(3).fill(""));

  if (savedGameState) {
    console.log("Loading saved game state...");
    const parsedState = JSON.parse(savedGameState);
    loadedGrid = parsedState.grid || loadedGrid;
    setGrid(loadedGrid);
    setGuessesLeft(parsedState.guessesLeft ?? 9);
    setGameOver(parsedState.gameOver ?? false);
  }

  if (savedIncorrectGuesses) {
    setIncorrectGuesses(JSON.parse(savedIncorrectGuesses));
  }

  if (savedUsedGuesses) {
    setCorrectGuesses(new Set(JSON.parse(savedUsedGuesses)));
  }

  // ✅ Dynamically update guess percentages after loading saved grid
  if (gridId && loadedGrid) {
    loadedGrid.forEach((row, rowIndex) => {
      row.forEach(async (cell, colIndex) => {
        if (cell && cell.name) {
          try {
            const response = await axios.get(
              `${API_BASE_URL}/current-guess-percentage?grid_id=${gridId}&row=${encodeURIComponent(rows[rowIndex])}&column=${encodeURIComponent(columns[colIndex])}&rider=${encodeURIComponent(cell.name)}`
            );
            const updatedPercentage = response.data.guess_percentage;

            // Update the grid cell with the refreshed percentage
            loadedGrid[rowIndex][colIndex].guess_percentage = updatedPercentage;
            setGrid([...loadedGrid]);  // Trigger re-render
          } catch (error) {
            console.error(`Error updating percentage for ${cell.name}:`, error);
          }
        }
      });
    });
  }

}, [gridId, rows, columns]); // ✅ Add rows & columns as dependencies too




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
      setGameOver(true); 
      setIsSummaryOpen(true); // ✅ Open summary modal when game ends
      setSelectedCell(null); // ✅ Ensure input box disappears when the summary opens
  }
}, [guessesLeft]);


const fetchGameSummary = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/game-summary?guest_id=${guestId}`);
    const data = response.data;

    console.log("Game Summary API Response:", data);

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

    console.log("Formatted Most Guessed Grid:", formattedMostGuessed);
    console.log("Formatted Correct Guess Percentages:", formattedCorrectPercentages);

    setGameSummary({
      ...data,
      rarityScores: data.rarity_score,  // ✅ Ensure rarity score is stored
      mostGuessedGrid: formattedMostGuessed,
      correctPercentageGrid: formattedCorrectPercentages
    });

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
  

  // Handle input change
  const handleInputChange = async (event) => {
    const input = event.target.value;
    setRiderName(input);

    if (input.length >= 2) {
        try {
            console.log(`Fetching autocomplete for: ${input}`);
            
            const response = await axios.get(`${API_BASE_URL}/autocomplete?query=${input}`);
            console.log("Autocomplete response:", response.data);
            
            if (response.data && response.data.riders) {
                setSuggestions(response.data.riders);
            } else {
                setSuggestions([]);
            }
        } catch (error) {
            console.error("Error fetching autocomplete suggestions:", error);
            setSuggestions([]); // ✅ Ensure it resets on failure
        }
    } else {
        setSuggestions([]);
    }
};

  

const handleSubmit = async (selectedRider = riderName) => {
  if (!selectedCell || selectedRider.trim() === "" || submittingGuess) return;  // Block if already submitting
  if (guessesLeft <= 0) {
    alert("No more attempts left!");
    return;
  }
  setSubmittingGuess(true);  // 🚨 Start lock
  try {
    // ✅ Ensure the game exists before submitting the first guess
    if (!localStorage.getItem("game_id")) {
      console.log("No game found, starting a new game...");
      await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}`);
    }

    const requestBody = {
      rider: selectedRider,
      row: rows[selectedCell.row],
      column: columns[selectedCell.col],
    };

    console.log("Submitting guess:", requestBody);

    const response = await axios.post(
      `${API_BASE_URL}/guess?guest_id=${guestId}`,
      requestBody,
      { headers: { "Content-Type": "application/json" } }
    );

    console.log("Guess response:", response.data);
    // alert(response.data.message);

    setGuessesLeft(response.data.remaining_attempts);

    if (!response.data.rider) {
      setIncorrectGuesses(prev => {
        const updatedIncorrectGuesses = {
          ...prev,
          [`${selectedCell.row}-${selectedCell.col}`]: [
            ...(prev[`${selectedCell.row}-${selectedCell.col}`] || []),
            selectedRider,
          ],
        };
    
        // ✅ Store incorrect guesses in localStorage
        localStorage.setItem(`incorrect_guesses_${gridId}`, JSON.stringify(updatedIncorrectGuesses));
    
        return updatedIncorrectGuesses;
      });
    
      return;
    }
    

    if (response.data.rider) {
      setCorrectGuesses(prev => {
        const updatedGuesses = new Set([...prev, selectedRider]);
    
        // ✅ Store updated correct guesses in localStorage
        localStorage.setItem(`used_guesses_${gridId}`, JSON.stringify([...updatedGuesses]));
    
        return updatedGuesses;
      });
    }
    
    

    setGrid(prevGrid => {
      const newGrid = prevGrid.map(row => [...row]);
      newGrid[selectedCell.row][selectedCell.col] = {
        name: selectedRider,
        image: response.data.image_url || "",
        guess_percentage: response.data.guess_percentage || 0,
      };

      // ✅ Save updated game state to localStorage
      const gameState = {
        grid: newGrid,
        guessesLeft: response.data.remaining_attempts,
        incorrectGuesses,
        gameOver: response.data.remaining_attempts === 0,
      };
      localStorage.setItem(`game_state_${gridId}`, JSON.stringify(gameState));

      return newGrid;
    });

    setRiderName("");
    setSelectedCell(null);

  } catch (error) {
    console.error("Error submitting guess:", error);
    alert(error.response?.data?.detail || "An error occurred");
  } finally {
    setSubmittingGuess(false);  // ✅ End lock no matter what
  }
};



const handleGiveUp = async () => {
  try {
    let storedGameId = localStorage.getItem("game_id");

    // ✅ Ensure the game is started before giving up
    if (!storedGameId) {
      console.log("No game found, starting a new game before giving up...");
      const startResponse = await axios.post(`${API_BASE_URL}/start-game?guest_id=${guestId}`);
      console.log("Game started for Give Up:", startResponse.data);

      if (startResponse.data.game_id) {
        storedGameId = startResponse.data.game_id;
        localStorage.setItem("game_id", storedGameId);
      }
    }

    // ✅ Now proceed with the give-up process
    const response = await axios.post(`${API_BASE_URL}/give-up?guest_id=${guestId}`);
    // alert(response.data.message);

    setGuessesLeft(0);
    setGameOver(true);
    setIsSummaryOpen(true);
    setSelectedCell(null);

    // ✅ Save updated game state
    localStorage.setItem(`game_state_${gridId}`, JSON.stringify({
      grid,
      guessesLeft: 0,
      incorrectGuesses,
      gameOver: true
    }));

  } catch (error) {
    console.error("Error giving up:", error);
  }
};

  
  


return (
  <>
    {isLoading ? (
      // ✅ Show only ONE loading screen (No banner!)
      <div className="loading-screen">
      </div>
    ) : (
      <>
<div className="top-banner-wrapper">
  <div className="top-banner">
    <div className="banner-left">
      <span>smxmuse grids by</span>
      <img src="/smxmuse-logo.png" alt="smxmuse" className="banner-logo" />
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
    </div>
  </div>
</div>





<div className="container">
    {/* ✅ Wrap Grid and Side Panel */}
    <div className="game-layout">
        {/* ✅ Grid Section */}
        <div className="grid-wrapper">
            <div className="column-headers">
                <div className="empty-cell"></div>
                {columns.map((col, index) => (
                    <div key={index} className="header-cell">{col}</div>
                ))}
            </div>

            <div className="grid-body">
                {rows.map((row, rowIndex) => (
                    <div key={rowIndex} className="grid-row">
                        <div className="header-cell">{row}</div>
                        {grid[rowIndex].map((cell, colIndex) => (
                            <div
                                key={`${rowIndex}-${colIndex}`}
                                className={`grid-cell ${selectedCell?.row === rowIndex && selectedCell?.col === colIndex ? "selected" : ""}`}
                                onClick={() => handleCellClick(rowIndex, colIndex)}
                            >
                                {cell && cell.image ? (
                                    <>
                                        <img src={cell.image} alt={cell.name} className="rider-image" />
                                        <div className="rider-name-banner">{cell.name}</div>
                                        {cell.guess_percentage !== undefined && cell.guess_percentage > 0 && (
                                            <div className="guess-percentage">{cell.guess_percentage}%</div>
                                        )}
                                    </>
                                ) : (
                                    cell.name || ""
                                )}
                            </div>
                        ))}
                    </div>
                ))}
            </div>
        </div>

        {/* ✅ Align Side Panel to the Third Row (HON) */}
        <div className="side-panel-container">
            <div className="side-panel">
                <p className="guess-counter">{guessesLeft}</p>
                <p className="guess-counter-label">Guesses Left</p>
                {gameOver ? (
                    <button className="summary-button" onClick={() => setIsSummaryOpen(true)}>View Summary</button>
                ) : (
                    <button className="give-up-button" onClick={handleGiveUp}>Give Up</button>
                )}
            </div>
        </div>
    </div>



        {/* ✅ Input Container */}
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

            {/* ✅ Autocomplete Dropdown */}
            {suggestions.length > 0 && (
              <div className="autocomplete-list">
                <ul>
                {suggestions
  .filter(suggestion => !correctGuesses.has(suggestion)) // ✅ Remove already used guesses
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

        {/* ✅ Summary Modal */}
        {isSummaryOpen && gameSummary && (
          <SummaryModal
            isOpen={isSummaryOpen}
            onClose={() => setIsSummaryOpen(false)}
            totalGames={gameSummary.total_games_played}
            averageScore={gameSummary.average_score}
            rarityScores={gameSummary.rarity_score}
            mostGuessedGrid={gameSummary.mostGuessedGrid || []}
            correctPercentageGrid={gameSummary.correctPercentageGrid || []}
            rows={rows}
            columns={columns}
            gridId={gridId}
            grid={grid}
/>
          )}
          {isHowToPlayOpen && <HowToPlayModal isOpen={isHowToPlayOpen} onClose={() => setIsHowToPlayOpen(false)} />}

        </div>
      </>
    )}
  </>
);



  
}

export default App;