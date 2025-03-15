import React from "react";
import "./HowToPlayModal.css";

const HowToPlayModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="howto-modal-overlay">
      <div className="howto-modal-content">
        <button className="howto-close-button" onClick={onClose}>X</button>
        <h2>What is smxmuse?</h2>
        <p>Smxmuse is a brand I started to showcase stats and analysis for all things Supercross and Motocross from a database I created. Please follow my social media pages (@smxmuse)
            if you are interested in pre race notes, race recaps, and general analysis and breakdowns of our sport.
        <h2>What is smxmuse grids?</h2>
        <p>Smxmuse grids is a daily 3x3 grid trivia game powered by my database to test your knowledge about Supercross and Motocross. </p>
        <h2>How to Play</h2>
            
            
            
        </p>
      </div>
    </div>
  );
};

export default HowToPlayModal;
