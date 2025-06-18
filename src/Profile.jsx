import React, { useEffect, useState } from "react";
import axios from "axios";
import TopBanner from "./TopBanner";
import SignUpModal from "./SignUpModal";
import LoginModal from "./LoginModal";
import "./Profile.css";
import "./SummaryModal.css";

const API_BASE_URL = import.meta.env.VITE_API_URL;

const Profile = () => {
  const [username, setUsername] = useState(null);
  const [stats, setStats] = useState(null);
  const [modalType, setModalType] = useState(null); // 'signup' or 'login'

  useEffect(() => {
    const storedUsername = localStorage.getItem("username");
    setUsername(storedUsername);

    if (storedUsername) {
      axios
        .get(`${API_BASE_URL}/user-profile?username=${storedUsername}`)
        .then((res) => setStats(res.data))
        .catch(() => setStats(null));
    }
  }, []);

  const displayStats = stats
    ? {
        ...stats,
        avg_score:
          typeof stats.avg_score === "number" && !isNaN(stats.avg_score)
            ? stats.avg_score.toFixed(2)
            : "–",
        avg_rarity:
          typeof stats.avg_rarity === "number" && !isNaN(stats.avg_rarity)
            ? stats.avg_rarity.toFixed(2)
            : "–",
        lowest_rarity:
          typeof stats.lowest_rarity === "number" && !isNaN(stats.lowest_rarity)
            ? stats.lowest_rarity.toFixed(2)
            : "–",
      }
    : {
        grids_completed: "–",
        avg_score: "–",
        avg_rarity: "–",
        lowest_rarity: "–",
        current_streak: "–",
        top_riders: Array(9).fill({
          name: "",
          correct_guesses: "",
          image_url: null,
        }),
      };

  return (
    <>
      <TopBanner />
      <div className="profile-container">
        <h2 className={!username ? "pushed-down" : ""}>
  🏁 My Grid Stats{username ? `: ${username}` : ""}
</h2>
        {!username && (
          <>
            <div className="account-prompt">
              <p><strong>Sign up for a free account</strong> to see your stats here!</p>
              <button className="signup-button" onClick={() => setModalType("signup")}>Sign Up</button>
              <p><a href="#" onClick={() => setModalType("login")}>Already have an account? Log In.</a></p>
            </div>
            {modalType === "signup" && <SignUpModal onClose={() => setModalType(null)} />}
            {modalType === "login" && <LoginModal onClose={() => setModalType(null)} />}
          </>
        )}

        <div className="profile-summary">
          <div className="stat-box">Grids Completed<br /><span>{displayStats.grids_completed}</span></div>
          <div className="stat-box">Average Score<br /><span>{displayStats.avg_score}</span></div>
          <div className="stat-box">Average Rarity<br /><span>{displayStats.avg_rarity}</span></div>
          <div className="stat-box">Lowest Rarity<br /><span>{displayStats.lowest_rarity}</span></div>
          <div className="stat-box">Current Streak<br /><span>{displayStats.current_streak}</span></div>
        </div>

        <h3>Most Guessed Riders</h3>
        <div className="profile-grid-wrapper" style={{ marginTop: "1rem" }}>
          {[0, 1, 2].map((row) => (
            <div className="profile-grid-row" key={row}>
              {displayStats.top_riders.slice(row * 3, row * 3 + 3).map((r, i) => (
                <div key={i} className="profile-rider-cell">
                  {r.correct_guesses && <div className="guess-percentage">{r.correct_guesses}x</div>}
                  {r.image_url ? (
                    <img src={r.image_url} alt={r.name} className="profile-rider-image" />
                  ) : (
                    <div className="profile-rider-image" style={{ background: "#444" }} />
                  )}
                  {r.name && <div className="profile-rider-name-banner">{r.name}</div>}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

export default Profile;
