import React from "react";
import "./UpdateModal.css";

export default function UpdateModal({ onClose }) {
  return (
    <div className="update-modal-overlay">
      <div className="update-modal">
        <h2 className="update-modal-title">🚨 New Updates (June 18)</h2>
        <p className="update-modal-subtitle">I’ve launched some major features:</p>
        <ul className="update-modal-list">
          <li><strong>🔓 Accounts:</strong> Sign up to save progress and sync across devices. Any devices you log into with the same account, 
           the data from each will be synced to your account.</li>
          <li><strong>📊 Profile Pages:</strong> Track your average score, streak, rarity, and top guessed riders.</li>
          <li><strong>🗃️ Grid Archive:</strong> Replay any past grid — perfect for practice or catching up.</li>
          <li><strong>💾 Persistent Games:</strong> Your progress is now saved when switching between devices that are logged into the same account.</li>
          <li><strong>🏆 Daily Rarity Leaderboard:</strong> Click the trophy icon in the top banner to see the rarity leaderboard for each day's grid.</li>
        </ul>
        <button className="update-modal-button" onClick={onClose}>Got it!</button>
      </div>
    </div>
  );
}
