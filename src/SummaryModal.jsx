import React from "react";
import "./SummaryModal.css"; // ✅ Styling file (create this too)

const SummaryModal = ({ 
    isOpen, 
    onClose, 
    totalGames, 
    averageScore, 
    rarityScores, 
    mostGuessedGrid, 
    correctPercentageGrid 
}) => {
    if (!isOpen) return null; // ✅ Hide when not open

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <h2>Game Summary</h2>

                <p><strong>Total Games Played:</strong> {totalGames}</p>
                <p><strong>Average Score:</strong> {averageScore}</p>

                {/* ✅ Rarity Scores */}
                <h3>Rarity Scores</h3>
                <ul>
                    {Object.entries(rarityScores).map(([user, score]) => (
                        <li key={user}>{user}: {score}</li>
                    ))}
                </ul>

                {/* ✅ Most Guessed Grid */}
                <h3>Most Popular Guesses</h3>
                <div className="summary-grid">
                    {mostGuessedGrid.map((row, rowIndex) => (
                        <div key={rowIndex} className="summary-row">
                            {row.map((cell, colIndex) => (
                                <div key={colIndex} className="summary-cell">
                                    {cell.rider} ({cell.guess_percentage}%)
                                </div>
                            ))}
                        </div>
                    ))}
                </div>

                {/* ✅ Correct Guess Percentages Grid */}
                <h3>Correct Guess Percentages</h3>
                <div className="summary-grid">
                    {correctPercentageGrid.map((row, rowIndex) => (
                        <div key={rowIndex} className="summary-row">
                            {row.map((cell, colIndex) => (
                                <div key={colIndex} className="summary-cell">
                                    {cell.completion_percentage}%
                                </div>
                            ))}
                        </div>
                    ))}
                </div>

                {/* ✅ Close Button */}
                <button onClick={onClose} className="close-button">Close</button>
            </div>
        </div>
    );
};

export default SummaryModal;
