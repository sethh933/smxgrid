import React, { useState } from "react";
import axios from "axios";
import TopBanner from "./TopBanner";

const API_BASE_URL = import.meta.env.VITE_API_URL;

export default function ResetPassword() {
  const [identifier, setIdentifier] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("");
    setError("");

    try {
      await axios.post(`${API_BASE_URL}/forgot-password`, { identifier });
      setStatus("If that account exists, a reset link has been sent.");
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    }
  };

  return (
    <>
      <TopBanner />
      <div className="reset-password-container" style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        minHeight: "calc(100vh - 80px)",
        paddingTop: "80px",
        color: "white"
      }}>
        <h2 style={{ marginBottom: "10px" }}>Forgot Password</h2>
        <p style={{ marginBottom: "25px", maxWidth: "400px", textAlign: "center" }}>
          Enter your email or username to send the email to reset your password.
        </p>
        <form onSubmit={handleSubmit} style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          maxWidth: "400px",
          padding: "0 20px"
        }}>
          <input
            type="text"
            placeholder="Email or Username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
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
            Send Reset Link
          </button>
          {status && <p style={{ color: "limegreen", marginTop: "15px", textAlign: "center" }}>{status}</p>}
          {error && <p style={{ color: "red", marginTop: "15px", textAlign: "center" }}>{error}</p>}
        </form>
      </div>
    </>
  );
}
