import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";
import SummaryModal from "./SummaryModal.jsx"; // ✅ Import Summary Modal


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


  // Fetch grid data from backend
  useEffect(() => {
    const initializeGrid = async () => {
      try {
        const response = await axios.get("http://localhost:8000/grid");  // ✅ Fetch Active Grid from SQL
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
      } catch (error) {
        console.error("Error initializing grid:", error);
      }
    };

    initializeGrid();
  }, []);

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
  }
}, [guessesLeft]);


const fetchGameSummary = async () => {
  try {
      const response = await axios.get("http://localhost:8000/game-summary");
      const data = response.data;

      console.log("Game Summary API Response:", data);

      // ✅ Transform the most guessed riders into a 3x3 grid (Include Image)
      const formattedMostGuessed = rows.map(row =>
        columns.map(col => {
            const found = data.most_guessed_riders.find(item => item.row === row && item.col === col);
            return found || { rider: "No data", guess_percentage: 0, image: null };
        })
    );

      // ✅ Transform correct guess percentages into a 3x3 grid
      const formattedCorrectPercentages = rows.map(row =>
          columns.map(col =>
              data.cell_completion_rates.find(item => item.row === row && item.col === col) || { completion_percentage: 0 }
          )
      );

      console.log("Formatted Most Guessed Grid:", formattedMostGuessed);
      console.log("Formatted Correct Guess Percentages:", formattedCorrectPercentages);

      setGameSummary({
          ...data,
          mostGuessedGrid: formattedMostGuessed,
          correctPercentageGrid: formattedCorrectPercentages
      });

  } catch (error) {
      console.error("Error fetching game summary:", error);
  }
};



  // Handle cell selection
  const handleCellClick = (rowIndex, colIndex) => {
    if (guessesLeft === 0) return;

    setSelectedCell({ row: rowIndex, col: colIndex });
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
            
            const response = await axios.get(`http://localhost:8000/autocomplete?query=${input}`);
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

  

  // Handle guess submission
  const handleSubmit = async (selectedRider = riderName) => {
    if (!selectedCell || selectedRider.trim() === "") return;

    if (guessesLeft <= 0) {
        alert("No more attempts left!");
        return;
    }

    try {
        const requestBody = {
            rider: selectedRider,
            row: rows[selectedCell.row], 
            column: columns[selectedCell.col], 
        };

        console.log("Submitting guess:", requestBody); // ✅ Debugging log

        const response = await axios.post(
            `http://localhost:8000/guess?user_id=1`,  // ✅ Add user_id as query param
            requestBody,
            { headers: { "Content-Type": "application/json" } }
        );

        console.log("Guess response:", response.data); // ✅ Debugging log
        alert(response.data.message);

        if (response.data.message.includes("✅")) {
            setGrid(prevGrid => {
                const newGrid = prevGrid.map(row => [...row]);
                newGrid[selectedCell.row][selectedCell.col] = {
                    name: selectedRider,
                    image: response.data.image_url || "",
                };
                return newGrid;
            });

            setIncorrectGuesses(prev => {
                const updatedGuesses = { ...prev };
                delete updatedGuesses[`${selectedCell.row},${selectedCell.col}`];
                return updatedGuesses;
            });
        } else {
            setIncorrectGuesses(prev => ({
                ...prev,
                [`${selectedCell.row},${selectedCell.col}`]: selectedRider,
            }));
        }

        setGuessesLeft(response.data.remaining_attempts);
        setRiderName("");
        setSelectedCell(null);
    } catch (error) {
        console.error("Error submitting guess:", error);
        alert(error.response?.data?.detail || "An error occurred");
    }
};

  

  // Handle Give Up
  const handleGiveUp = async () => {
    try {
        const response = await axios.post("http://localhost:8000/give-up");
        alert(response.data.message);
        setGuessesLeft(0);
        setGameOver(true);
        setIsSummaryOpen(true); // ✅ Open summary modal when giving up
    } catch (error) {
        console.error("Error giving up:", error);
    }
};


  return (
    <div className="container">
      <h1>smxmuse grid</h1>
      <div className="give-up-container">
  <p>Guesses Left: {guessesLeft}</p>
  {gameOver ? (
    <button className="summary-button" onClick={() => setIsSummaryOpen(true)}>View Summary</button>
  ) : (
    <button className="give-up-button" onClick={handleGiveUp}>Give Up</button>
  )}
</div>
        <>
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
          

          {selectedCell && (
  <div className="input-container">
    <input 
      type="text" 
      placeholder="Enter rider name..." 
      className="input-box" 
      value={riderName} 
      onChange={handleInputChange} 
      autoFocus 
    />

    {/* ✅ Autocomplete Dropdown Below Input */}
    {suggestions.length > 0 && (
      <div className="autocomplete-list">
        <ul>
          {suggestions.map((suggestion, index) => (
            <li key={index} className="suggestion-item">
              <span>{suggestion}</span>
              <button
                className="select-button"
                onClick={async () => {
                  setRiderName(suggestion); // ✅ Updates the input field
                  await handleSubmit(suggestion); // ✅ Automatically submits
                }}
              >
                Select
              </button>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
)}
        </>
        {isSummaryOpen && gameSummary && (
    <SummaryModal 
        isOpen={isSummaryOpen}
        onClose={() => setIsSummaryOpen(false)}
        totalGames={gameSummary.total_games_played}
        averageScore={gameSummary.average_score}
        rarityScores={gameSummary.rarity_scores}
        mostGuessedGrid={gameSummary.mostGuessedGrid || []}  // ✅ Ensure proper data passing
        correctPercentageGrid={gameSummary.correctPercentageGrid || []}  // ✅ Ensure proper data passing
    />
)}

    </div>
  );
}

export default App;