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

    console.log("Summary Modal Data:", {
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

{/* ✅ Most Guessed Grid - 3x3 Layout */}
<h3>Most Popular Guesses</h3>
<div className="summary-grid">
    {mostGuessedGrid && mostGuessedGrid.length > 0 ? (
        mostGuessedGrid.flat().map((cell, index) => (
            <div key={index} className="summary-cell rider-cell">
                {/* ✅ Guess Percentage in Top Left */}
                <div className="guess-percentage">{cell.guess_percentage || 0}%</div>

                {/* ✅ Rider Image */}
                {cell.image ? (
                    <img src={cell.image} alt={cell.rider} className="rider-image" />
                ) : (
                    <div className="no-image">No Image</div>
                )}

                {/* ✅ Rider Name Banner */}
                <div className="rider-name-banner">{cell.rider}</div>
            </div>
        ))
    ) : (
        <p>No data available</p>
    )}
</div>

{/* ✅ Correct Guess Percentages - 3x3 Layout */}
<h3>Correct Guess Percentages</h3>
<div className="summary-grid">
    {correctPercentageGrid && correctPercentageGrid.length > 0 ? (
        correctPercentageGrid.flat().map((cell, index) => (
            <div key={index} className="summary-cell rider-cell">
                {/* ✅ Centered Percentage */}
                <div className="centered-percentage">
                    {cell.completion_percentage || 0}%
                </div>
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
