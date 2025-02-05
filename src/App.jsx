import React, { useState } from "react";
import "./App.css";

function App() {
  const [grid, setGrid] = useState(Array(3).fill(Array(3).fill(""))); // 3x3 empty grid
  const [guessesLeft, setGuessesLeft] = useState(9);
  const [selectedCell, setSelectedCell] = useState(null); // Track selected cell
  const [riderName, setRiderName] = useState(""); // Input value

  const handleCellClick = (rowIndex, colIndex) => {
    setSelectedCell({ row: rowIndex, col: colIndex });
  };

  const handleInputChange = (event) => {
    setRiderName(event.target.value);
  };

  const handleSubmit = () => {
    if (selectedCell) {
      const newGrid = grid.map((row, rIndex) =>
        row.map((cell, cIndex) =>
          rIndex === selectedCell.row && cIndex === selectedCell.col ? riderName : cell
        )
      );
      setGrid(newGrid);
      setSelectedCell(null);
      setRiderName(""); // Clear input after submission
      setGuessesLeft(guessesLeft - 1);
    }
  };

  return (
    <div className="container">
      <h1>Motocross Grid Game</h1>
      <p>Guesses Left: {guessesLeft}</p>
      <div className="grid-container">
        {grid.map((row, rowIndex) =>
          row.map((cell, colIndex) => (
            <div
              key={`${rowIndex}-${colIndex}`}
              className={`grid-cell ${selectedCell?.row === rowIndex && selectedCell?.col === colIndex ? "selected" : ""}`}
              onClick={() => handleCellClick(rowIndex, colIndex)}
            >
              {cell}
            </div>
          ))
        )}
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
          <button className="submit-button" onClick={handleSubmit}>Submit</button>
        </div>
      )}
    </div>
  );
}

export default App;







