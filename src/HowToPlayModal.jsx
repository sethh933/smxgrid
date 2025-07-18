import React, { useEffect, useRef } from "react";
import "./HowToPlayModal.css";

const HowToPlayModal = ({ isOpen, onClose }) => {
  const modalRef = useRef(null);


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
        <p>Riders cannot be used twice.</p>
        <p>A new grid releases at 4:00am ET every day. </p>
        <p>Total Games Played is the count of all games completed that day.</p>
        <p>Average Score is the average of correct answers per game across all games completed that day.</p>
        <p>Rarity score is the sum of your guess percentages. Any cell unanswered upon the game's completion adds 100 to the score.</p> 
        <p>The percentage displayed in each cell after a correct guess shows how often that rider has been selected for that cell.</p>
        <p>This game only uses results and data from AMA Supercross and Motocross.</p>
        <p>If a row/column is a manufacturer, you can select a rider that has ridden for that manufacturer at any point in their career, 250 or 450 class.</p>
        <p>For example, if HON is a column and 250 MX Win is a row, Ken Roczen would be a valid answer because he has won a 250 MX overall and ridden for Honda at one point in his career, albeit not
            in the 250 class.</p>
        <p>If a row/column is a decade, for example "Raced in the 2010's", only riders that raced a Supercross main event or qualified for the motos at a Motocross event
            in that decade will be eligible answers. </p>
        <p>If a row/column is &lt;18 Years Old 250 MX Winner, eligible riders are all riders who won a 250 MX Overall at 18 years of age or younger.</p>
        <p>If a row/column is a Country or Continent, country of birth will be the determining factor for any multi-national riders.</p>
        <p><strong>Riders are available to be guessed in the game if they meet at least one of these criteria:</strong></p>
        <p>Raced at least one 250/450 SX Main Event since 1974.</p>
        <p>Raced at least one 125/250 SX Main Event since 1985.</p>
        <p>Raced at least one 250/450 or 500 MX event since 1972*.</p>
        <p>Raced at least one 125/250 MX event since 1974*.</p>
        <p>Raced at least one 250 or 450 MX Consolation race since 2009.</p>
        <p>Rode in timed qualifying in at least one MX event since 2009, 250 or 450.</p>
        <p>Rode in timed qualifying in at least one SX event since 2007, 250 or 450.</p>
        <p>Raced at least one 125/250 SX Heat Race since 2003.</p>
        <p>Raced at least one 250/450 SX Heat Race since 2003.</p>
        <p>Raced at least one 125/250 SX LCQ since 2003.</p>
        <p>Raced at least one 250/450 SX LCQ since 2003.</p>
        <p>*Historical MX data is incomplete from 1972-1997. Only riders who finished at least one moto inside the top 20 are guaranteed to be present in accessible historical records in that time frame.</p>
        <p>Email feedback@smxmuse.com or send me a DM on Instagram or X if you would like to provide any feedback about the game.</p>
    
    
      </div>
    </div>
  );
};

export default HowToPlayModal;

