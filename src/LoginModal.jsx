import React, { useState } from "react";
import axios from "axios";
import "./LoginModal.css";

const API_BASE_URL = import.meta.env.VITE_API_URL;

const LoginModal = ({ onClose }) => {
  const [form, setForm] = useState({
    email_or_username: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

const handleSubmit = async (e) => {
  e.preventDefault();
  setError("");

  try {
    const guestId = localStorage.getItem("guest_id");

    const res = await axios.post(`${API_BASE_URL}/login`, {
      email_or_username: form.email_or_username,
      password: form.password,
      guest_id: guestId,  // ✅ Pass it
      remember_me: form.remember_me || false
    });

    const token = res.data.access_token;
    localStorage.setItem("access_token", token);
    localStorage.setItem("username", res.data.username);  // replace form.email_or_username
    setSuccess("Logged in successfully!");
    onClose();
    window.location.reload(); // ✅ Force refresh to show stats
  } catch (err) {
    setError(err.response?.data?.detail || "Something went wrong.");
  }
};


  return (
    <div className="login-modal-overlay">
      <div className="login-modal-content">
        <button className="login-close-button" onClick={onClose}>×</button>
        <h2>LOG IN</h2>
        <form onSubmit={handleSubmit}>
          <input
            name="email_or_username"
            placeholder="Email or Username"
            value={form.email_or_username}
            onChange={handleChange}
            required
          />
          <input
            type="password"
            name="password"
            placeholder="Password"
            value={form.password}
            onChange={handleChange}
            required
          />

<p
  className="forgot-password-link"
  onClick={() => window.location.href = "/reset-password"}
>
  Forgot your password?
</p>

          {error && <div className="login-error">{error}</div>}
          {success && <div className="login-success">{success}</div>}

          <button className="login-button" type="submit">Log In</button>
        </form>
      </div>
    </div>
  );
};

export default LoginModal;
