import React, { useEffect, useRef } from "react";
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
    gridId,
    grid
}) => {
    if (!isOpen) return null; // Don't render if modal is closed

    const modalRef = useRef(null); // ✅ Reference for modal content

    // ✅ Console log for debugging (kept exactly as you had it)
    console.log("Summary Modal Data:", {
        totalGames,
        averageScore,
        rarityScores,
        mostGuessedGrid,
        correctPercentageGrid,
        gridId
    });

    // ✅ Disable scrolling when modal is open
    useEffect(() => {
        if (isOpen) {
            document.body.classList.add("modal-open");
        } else {
            document.body.classList.remove("modal-open");
        }
        return () => {
            document.body.classList.remove("modal-open");
        };
    }, [isOpen]);
    


    // ✅ Close modal if clicking outside of it
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (modalRef.current && !modalRef.current.contains(event.target)) {
                onClose(); // ✅ Close modal if clicking outside
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

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

        return `🏁 SMXMuse Grid ${gridId} ${correctGuesses}/${totalCells}:
Rarity: ${rarityScore}
${correctGuesses === totalCells ? "Final Grid:" : ""}
${gridEmoji}

Play at:
https://smxmuse.com/`;
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
            <div className="modal-content" ref={modalRef}>
                <h2>Game Summary</h2>
                <p><strong>Total Games Played:</strong> {totalGames}</p>
                <p><strong>Average Score:</strong> {parseFloat(averageScore).toFixed(2)}</p>
                <p><strong>Rarity Score:</strong> {rarityScores !== undefined ? rarityScores : "N/A"}</p>

                {/* ✅ Share Button */}
                <button className="share-button" onClick={handleCopyResults}>
                    Copy Results for Sharing
                </button>

                {/* ✅ Most Popular Guesses Grid */}
                <h2>Most Popular Guesses</h2>
                <div className="grid-wrapper">
                <div className="summary-column-headers">
                <div className="summary-empty-cell"></div>

    {columns.map((col, index) => (
        <div key={index} className="summary-header-cell">{col}</div>
    ))}
</div>


                    <div className="grid-body">
                        {rows.map((row, rowIndex) => (
                            <div key={rowIndex} className="summary-grid-row">
                                <div className="summary-header-cell">{row}</div>
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
                <h2>Correct Guess Percentages</h2>
                <div className="grid-wrapper">
                <div className="summary-column-headers">
                <div className="summary-empty-cell"></div>
    {columns.map((col, index) => (
        <div key={index} className="summary-header-cell">{col}</div>
    ))}
</div>


                    <div className="grid-body">
                        {rows.map((row, rowIndex) => (
                            <div key={rowIndex} className="summary-grid-row">
                                <div className="summary-header-cell">{row}</div>
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

