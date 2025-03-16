import React, { useEffect, useRef } from "react";
import "./HowToPlayModal.css";

const HowToPlayModal = ({ isOpen, onClose }) => {
  const modalRef = useRef(null);

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

  const handleClickOutside = (event) => {
    if (modalRef.current && !modalRef.current.contains(event.target)) {
      onClose();
    }
  };

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    } else {
      document.removeEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="howto-modal-overlay">
      <div className="howto-modal-content" ref={modalRef}>
        <button className="howto-close-button" onClick={onClose}>X</button>
        <h2>What is smxmuse?</h2>
        <p>Smxmuse is a brand I started to showcase stats and analysis for all things Supercross and Motocross from a database I created. Please follow my social media pages (@smxmuse)
            if you are interested in pre race notes, race recaps, and general analysis and breakdowns of our sport.</p>
        <h2>What is smxmuse grids?</h2>
        <p>Smxmuse grids is a daily 3x3 grid trivia game powered by my database to test your knowledge about Supercross and Motocross.</p>
        <h2>How to Play</h2>
        <p>Select a rider that fits the criteria for each cell's row and column.</p>
        <p>You have nine guesses to complete the grid.</p>
        <p>The primary goal is to correctly guess all nine cells.</p>
        <p>The secondary goal is to have a low rarity score. The more rare the rider, the lower the rarity score.</p>
        <p>Rarity score is the sum of your guess percentages. Any cell unanswered upon the game's completion adds 100 to the score.</p> 
        <p>The percentage displayed in each cell after a correct guess shows how often that rider has been selected for that cell.</p>
        <p>Riders cannot be used twice.</p>
        <p>If a row/column is a manufacturer, you can select a rider that has ridden for that manufacturer at any point in their career, 250 or 450 class.</p>
        <p>For example, if HON is a column and 250 MX Win is a row, Ken Roczen would be a valid answer because he has won a 250 MX overall and ridden for Honda at one point in his career, albeit not
            in the 250 class.</p>
      </div>
    </div>
  );
};

export default HowToPlayModal;

