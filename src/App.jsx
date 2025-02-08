import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [grid, setGrid] = useState(Array(3).fill(Array(3).fill(""))); // 3x3 empty grid
  const [rows, setRows] = useState([]);
  const [columns, setColumns] = useState([]);
  const [guessesLeft, setGuessesLeft] = useState(9);
  const [selectedCell, setSelectedCell] = useState(null);
  const [riderName, setRiderName] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [incorrectGuesses, setIncorrectGuesses] = useState({}); // Tracks incorrect guesses per cell

  // Fetch game data from backend
  useEffect(() => {
    const initializeGrid = async () => {
      try {
        await axios.post("http://localhost:8000/generate-grid");
        const response = await axios.get("http://localhost:8000/grid");

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

  // Handle cell selection
  const handleCellClick = (rowIndex, colIndex) => {
    setSelectedCell({ row: rowIndex, col: colIndex });
    setRiderName(""); // Reset rider input when selecting a new cell
  };

  // Handle input change
  const handleInputChange = async (event) => {
    const input = event.target.value;
    setRiderName(input);

    if (input.length >= 2) {
      try {
        const response = await axios.get(`http://localhost:8000/autocomplete?query=${input}`);
        setSuggestions(response.data.riders);
      } catch (error) {
        console.error("Error fetching autocomplete suggestions:", error);
      }
    } else {
      setSuggestions([]);
    }
  };

  // Submit guess to backend
  const handleSubmit = async () => {
    if (!selectedCell || riderName.trim() === "") return;
  
    if (guessesLeft <= 0) {
      alert("No more attempts left!");
      return;
    }
  
    try {
      const response = await axios.post(
        "http://localhost:8000/guess",
        {
          rider: riderName,
          row: rows[selectedCell.row], // Convert row index to actual row label
          column: columns[selectedCell.col], // Convert column index to actual column label
        },
        {
          headers: { "Content-Type": "application/json" },
        }
      );
  
      alert(response.data.message);
  
      if (response.data.message.includes("✅")) {
        setGrid(prevGrid => {
          const newGrid = prevGrid.map(row => [...row]); // Copy grid
          newGrid[selectedCell.row][selectedCell.col] = {
            name: riderName,
            image: response.data.image_url || "", // ✅ Store the image URL
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
          [`${selectedCell.row},${selectedCell.col}`]: riderName,
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
  

  return (
    <div className="container">
      <h1>Motocross Grid Game</h1>
      <p>Guesses Left: {guessesLeft}</p>

      <div className="grid-wrapper">
        <div className="column-headers">
          <div className="empty-cell"></div>
          {columns.map((col, index) => (
            <div key={index} className="header-cell">
              {col}
            </div>
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
        <div className="rider-name-banner">{cell.name}</div> {/* ✅ Name banner added */}
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
          />
          <ul className="autocomplete-list">
            {suggestions.map((suggestion, index) => {
              const isIncorrect =
                incorrectGuesses[`${selectedCell.row},${selectedCell.col}`] === suggestion;

              return (
                <li
                  key={index}
                  onClick={() => setRiderName(suggestion)}
                  style={{ color: isIncorrect ? "red" : "white" }} // ✅ Make incorrect guesses red
                >
                  {suggestion}
                </li>
              );
            })}
          </ul>
          <button className="submit-button" onClick={handleSubmit}>
            Submit
          </button>
        </div>
      )}
    </div>
  );
}

export default App;










