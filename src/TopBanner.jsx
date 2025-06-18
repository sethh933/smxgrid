import React, { useState } from "react";
import { Link } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faInstagram, faXTwitter } from "@fortawesome/free-brands-svg-icons";
import { faQuestionCircle } from "@fortawesome/free-solid-svg-icons";
import HowToPlayModal from "./HowToPlayModal";
import LeaderboardModal from "./dailyleaderboard";
import axios from "axios";

const TopBanner = () => {
  const [isHowToPlayOpen, setIsHowToPlayOpen] = useState(false);
  const [isLeaderboardOpen, setIsLeaderboardOpen] = useState(false);
  const [leaderboardData, setLeaderboardData] = useState([]);

  const fetchLeaderboard = async () => {
    try {
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/daily-leaderboard`);
      setLeaderboardData(response.data);
      setIsLeaderboardOpen(true);
    } catch (error) {
      console.error("Error loading leaderboard:", error);
    }
  };

  return (
    <>
      <div className="top-banner-wrapper">
        <div className="top-banner">
          <div className="banner-left">
            <span>smxmuse grids by</span>
            <img src="/smxmuse-logo.png" alt="smxmuse" className="banner-logo" />
          </div>

          <div className="banner-nav">
            <Link to="/" className="nav-link">Home</Link>
            <Link to="/gridarchive" className="nav-link">Grid Archive</Link>
            <Link to="/profile" className="nav-link">Profile</Link>
          </div>

          <div className="social-icons">
            <a href="https://www.instagram.com/smxmuse" target="_blank" rel="noopener noreferrer">
              <FontAwesomeIcon icon={faInstagram} className="social-icon" />
            </a>
            <a href="https://twitter.com/smxmuse" target="_blank" rel="noopener noreferrer">
              <FontAwesomeIcon icon={faXTwitter} className="social-icon" />
            </a>
            <button className="social-icon how-to-play-btn" onClick={() => setIsHowToPlayOpen(true)}>
              <FontAwesomeIcon icon={faQuestionCircle} />
            </button>
            <button className="social-icon how-to-play-btn" onClick={fetchLeaderboard}>
              🏆
            </button>
          </div>
        </div>
      </div>

      {/* Modals */}
      {isHowToPlayOpen && (
        <HowToPlayModal
          isOpen={isHowToPlayOpen}
          onClose={() => setIsHowToPlayOpen(false)}
        />
      )}

      {isLeaderboardOpen && (
        <LeaderboardModal
          open={isLeaderboardOpen}
          onClose={() => setIsLeaderboardOpen(false)}
          leaderboardData={leaderboardData}
        />
      )}
    </>
  );
};

export default TopBanner;
