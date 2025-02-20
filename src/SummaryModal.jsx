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

    console.log("Rendering Summary Modal with data:", {
        totalGames,
        averageScore,
        rarityScores,
        mostGuessedGrid,
        correctPercentageGrid
    });

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <h2>Game Summary</h2>

                <p><strong>Total Games Played:</strong> {totalGames}</p>
                <p><strong>Average Score:</strong> {averageScore}</p>

                {/* ✅ Rarity Scores */}
                <h3>Rarity Scores</h3>
                <ul>
    {rarityScores && Object.keys(rarityScores).length > 0 ? (
        Object.entries(rarityScores).map(([user, score]) => (
            <li key={user}>{user}: {score}</li>
        ))
    ) : (
        <p>No rarity scores available.</p>
    )}
</ul>


                {/* ✅ Most Guessed Grid */}
<h3>Most Popular Guesses</h3>
<div className="summary-grid">
    {mostGuessedGrid && mostGuessedGrid.length > 0 ? (
        mostGuessedGrid.map((row, rowIndex) => (
            <div key={rowIndex} className="summary-row">
                {row.map((cell, colIndex) => (
                    <div key={colIndex} className="summary-cell">
                        {cell.rider} ({cell.guess_percentage || 0}%)
                    </div>
                ))}
            </div>
        ))
    ) : (
        <p>No data available</p>
    )}
</div>

{/* ✅ Correct Guess Percentages Grid */}
<h3>Correct Guess Percentages</h3>
<div className="summary-grid">
    {correctPercentageGrid && correctPercentageGrid.length > 0 ? (
        correctPercentageGrid.map((row, rowIndex) => (
            <div key={rowIndex} className="summary-row">
                {row.map((cell, colIndex) => (
                    <div key={colIndex} className="summary-cell">
                        {cell.completion_percentage || 0}%
                    </div>
                ))}
            </div>
        ))
    ) : (
        <p>No data available</p>
    )}
</div>


                {/* ✅ Close Button */}
                <button onClick={onClose} className="close-button">Close</button>
            </div>
        </div>
    );
};

export default SummaryModal;
