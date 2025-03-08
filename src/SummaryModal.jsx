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
    columns,
    gridId,  // ✅ Add grid ID for reference
    grid     // ✅ Add grid state to track filled/unfilled cells
}) => {
    if (!isOpen) return null;  // Hide the modal if not open

    console.log("Summary Modal Data:", {
        totalGames,
        averageScore,
        rarityScores,
        mostGuessedGrid,
        correctPercentageGrid,
        gridId
    });

    
    // ✅ Function to count correctly guessed cells
    const countCorrectGuesses = () => {
        return grid.flat().filter(cell => cell && cell.name).length;
    };

    // ✅ Function to generate the shareable text format
    const generateShareText = () => {
        const correctGuesses = countCorrectGuesses();
        const totalCells = 9;
        const rarityScore = rarityScores !== undefined ? rarityScores : "N/A";

        // ✅ Generate emoji-based grid (🟩 for correct, ⬛ for unanswered)
        const gridEmoji = grid.map(row =>
            row.map(cell => (cell && cell.name ? "🟩" : "⬛")).join("")
        ).join("\n");

        return `🏁 SMXMuse Grid ${gridId} ${correctGuesses}/${totalCells}:\nRarity: ${rarityScore}\n$correctGuesses === totalCells ? "Final Grid:"\n${gridEmoji}\n\nPlay at:\nhttps://smxmuse.com/`;
    };

    // ✅ Function to copy text to clipboard
    const handleCopyResults = () => {
        const shareText = generateShareText();
        navigator.clipboard.writeText(shareText)
            .then(() => alert("Results copied to clipboard!"))
            .catch(err => console.error("Error copying text: ", err));
    };

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <h2>Game Summary</h2>
                <p><strong>Total Games Played:</strong> {totalGames}</p>
                <p><strong>Average Score:</strong> {parseFloat(averageScore).toFixed(2)}</p>
                <p><strong>Rarity Score:</strong> {rarityScores !== undefined ? rarityScores : "N/A"}</p>

                                {/* ✅ Share Button */}
                                <button className="share-button" onClick={handleCopyResults}>
                    Copy Results for Sharing
                </button>


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
