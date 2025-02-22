import React from "react";
import "./SummaryModal.css";

const SummaryModal = ({
    isOpen,
    onClose,
    totalGames,
    averageScore,
    rarityScores,
    mostGuessedGrid,
    correctPercentageGrid,
    rows,
    columns
}) => {
    if (!isOpen) return null;  // Hide the modal if not open

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

                {/* ✅ Most Popular Guesses Grid */}
                <h3>Most Popular Guesses</h3>
                <div className="grid-wrapper">
                    {/* Column Headers */}
                    <div className="column-headers">
                        <div className="empty-cell"></div>
                        {columns.map((col, index) => (
                            <div key={index} className="header-cell">{col}</div>
                        ))}
                    </div>

                    {/* Grid Body */}
                    <div className="grid-body">
                        {rows.map((row, rowIndex) => (
                            <div key={rowIndex} className="grid-row">
                                <div className="header-cell">{row}</div>
                                {mostGuessedGrid[rowIndex].map((cell, colIndex) => (
                                    <div key={`${rowIndex}-${colIndex}`} className="summary-cell rider-cell">
                                        <div className="guess-percentage">{cell.guess_percentage || 0}%</div>
                                        {cell.image ? (
                                            <img src={cell.image} alt={cell.rider} className="rider-image" />
                                        ) : (
                                            <div className="no-image">No Image</div>
                                        )}
                                        <div className="rider-name-banner">{cell.rider}</div>
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>

                {/* ✅ Correct Guess Percentages Grid */}
                <h3>Correct Guess Percentages</h3>
                <div className="grid-wrapper">
                    {/* Column Headers */}
                    <div className="column-headers">
                        <div className="empty-cell"></div>
                        {columns.map((col, index) => (
                            <div key={index} className="header-cell">{col}</div>
                        ))}
                    </div>

                    {/* Grid Body */}
                    <div className="grid-body">
                        {rows.map((row, rowIndex) => (
                            <div key={rowIndex} className="grid-row">
                                <div className="header-cell">{row}</div>
                                {correctPercentageGrid[rowIndex].map((cell, colIndex) => (
                                    <div key={`${rowIndex}-${colIndex}`} className="summary-cell rider-cell">
                                        <div className="centered-percentage">
                                            {cell.completion_percentage || 0}%
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>

                {/* ✅ Close Button */}
                <button onClick={onClose} className="close-button">Close</button>
            </div>
        </div>
    );
};

export default SummaryModal;
