import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import axios from "axios";
import TopBanner from "./TopBanner";

const API_BASE_URL = import.meta.env.VITE_API_URL;

export default function ResetPasswordConfirm() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("");
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      await axios.post(`${API_BASE_URL}/reset-password-confirm`, {
        token,
        new_password: password
      });
      setStatus("✅ Password has been reset successfully. You may now log in.");
      setPassword("");
      setConfirmPassword("");
      setTimeout(() => navigate("/profile"), 2000); // route to login/profile after success
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    }
  };

  return (
    <>
      <TopBanner />
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        minHeight: "calc(100vh - 80px)",
        paddingTop: "80px",
        color: "white"
      }}>
        <h2 style={{ marginBottom: "10px" }}>Choose a New Password</h2>
        <form onSubmit={handleSubmit} style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          maxWidth: "400px",
          padding: "0 20px"
        }}>
          <input
            type="password"
            placeholder="New Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              padding: "10px",
              marginBottom: "15px",
              fontSize: "16px",
              borderRadius: "5px",
              border: "1px solid #555",
              backgroundColor: "#2b2b2b",
              color: "white"
            }}
          />
          <input
            type="password"
            placeholder="Confirm Password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            style={{
              padding: "10px",
              marginBottom: "15px",
              fontSize: "16px",
              borderRadius: "5px",
              border: "1px solid #555",
              backgroundColor: "#2b2b2b",
              color: "white"
            }}
          />
                    <p className="password-hint">
  Password must be at least 8 characters and include a letter and number.
</p>
          <button
            type="submit"
            style={{
              backgroundColor: "#2e6df6",
              color: "white",
              padding: "10px",
              fontSize: "16px",
              border: "none",
              borderRadius: "5px",
              cursor: "pointer"
            }}
          >
            Reset Password
          </button>
          {status && <p style={{ color: "limegreen", marginTop: "15px", textAlign: "center" }}>{status}</p>}
          {error && <p style={{ color: "red", marginTop: "15px", textAlign: "center" }}>{error}</p>}
        </form>
      </div>
    </>
  );
}
