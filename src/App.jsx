import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Game from "./gamescreen"; // your renamed main game component
import GridArchive from "./gridarchive";
import Profile from "./Profile";
import ResetPassword from "./resetpassword";
import ResetPasswordConfirm from "./resetpasswordconfirm";
import TopBanner from "./TopBanner"; // ✅ ADD THIS


function App() {
  return (
    <Router>
      <TopBanner /> {/* ✅ Add this above Routes so it doesn’t re-mount */}
      <Routes>
        <Route path="/" element={<Game />} />
        <Route path="/grid/:grid_id" element={<Game />} />
        <Route path="/gridarchive" element={<GridArchive />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/reset-password-confirm" element={<ResetPasswordConfirm />} />
      </Routes>
    </Router>
  );
}

export default App;
