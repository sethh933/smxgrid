import React, { useState } from "react";
import "./SignUpModal.css";
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL;

const SignUpModal = ({ onClose }) => {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    username: "",
    email: "",
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
      const res = await axios.post(`${API_BASE_URL}/register`, {
        guest_id: guestId,
        email: form.email,
        username: form.username,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
      });

      const token = res.data.access_token;
      localStorage.setItem("access_token", token);
      localStorage.setItem("username", form.username);
      setSuccess("Account created successfully!");
      onClose(); // ✅ Close modal first
      window.location.reload(); // ✅ Reload to trigger profile/stat hydration

    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong.");
    }
  };

  return (
    <div className="signup-modal-overlay">
      <div className="signup-modal-content">
        <button className="signup-close-button" onClick={onClose}>×</button>
        <h2>CREATE AN ACCOUNT</h2>
        <form onSubmit={handleSubmit}>
          <div className="signup-row">
            <input
              name="first_name"
              placeholder="First Name"
              value={form.first_name}
              onChange={handleChange}
              required
            />
            <input
              name="last_name"
              placeholder="Last Name"
              value={form.last_name}
              onChange={handleChange}
              required
            />
          </div>
          <input
            name="username"
            placeholder="Username"
            value={form.username}
            onChange={handleChange}
            required
          />
          <input
            type="email"
            name="email"
            placeholder="Email Address"
            value={form.email}
            onChange={handleChange}
            required
          />
          <input
            type="password"
            name="password"
            placeholder="Create Password"
            value={form.password}
            onChange={handleChange}
            required
          />
          <small style={{ color: "#999", fontSize: "0.8rem", marginBottom: "1rem", display: "block" }}>
            Password must be at least 8 characters and contain a letter and a number.
          </small>

          {error && <div className="error">{error}</div>}
          {success && <div className="success">{success}</div>}

          <button className="signup-button" type="submit">Create Account</button>
        </form>
      </div>
    </div>
  );
};

export default SignUpModal;
