import React, { useEffect, useRef } from "react";
import './dailyleaderboard.css';

export default function LeaderboardModal({ open, onClose, leaderboardData }) {
    const modalRef = useRef(null);

    useEffect(() => {
    const handleClickOutside = (event) => {
        if (modalRef.current && !modalRef.current.contains(event.target)) {
            onClose(); // Close modal if clicking outside of it
        }
    };

    document.addEventListener("mousedown", handleClickOutside);

    // Lock background scroll
    document.body.classList.add("modal-open");

    return () => {
        document.removeEventListener("mousedown", handleClickOutside);
        document.body.classList.remove("modal-open"); // Restore scroll
    };
}, []);


    if (!open) return null;

    return (
        <div className="leaderboard-modal-overlay">
            <div className="leaderboard-modal-content" ref={modalRef}>
                <button className="summary-close-button" onClick={onClose}>X</button>
                <h2>Daily Grid Rarity Leaderboard</h2>
                <table className="w-full text-sm mt-4 leaderboard-table">
                    <thead className="bg-gray-800 text-white">
                        <tr>
                            <th className="py-2 px-3 text-left">Place</th>
                            <th className="py-2 px-3 text-left">Username</th>
                            <th className="py-2 px-3 text-left">Rarity Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {leaderboardData.map((entry, index) => (
                            <tr key={index} className="border-b border-gray-700">
                                <td className="py-1 px-3">{index + 1}</td>
                                <td className="py-1 px-3">{entry.username || "Guest"}</td>
                                <td className="py-1 px-3">{entry.rarity_score.toFixed(2)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

