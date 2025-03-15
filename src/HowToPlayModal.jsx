import React, { useEffect, useRef } from "react";
import "./HowToPlayModal.css";

const HowToPlayModal = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    const modalRef = useRef(null);

    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }

        return () => {
            document.body.style.overflow = "";
        };
    }, [isOpen]);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (modalRef.current && !modalRef.current.contains(event.target)) {
                onClose();
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className="modal-overlay">
            <div className="modal-content" ref={modalRef}>
                <h2>How to Play</h2>
                <p>🔹 Select a grid cell and enter the name of a motocross rider who matches the row & column criteria.</p>
                <p>🔹 You have <strong>9 guesses</strong> to complete the grid.</p>
                <p>🔹 Each correct answer earns a score based on rarity.</p>
                <p>🔹 Try to get the lowest possible rarity score!</p>
                <button className="close-button" onClick={onClose}>Close</button>
            </div>
        </div>
    );
};

export default HowToPlayModal;