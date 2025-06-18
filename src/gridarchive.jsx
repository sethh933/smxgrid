import React, { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import TopBanner from "./TopBanner";
import "./gridarchive.css";

export default function GridArchive() {
  const [archiveData, setArchiveData] = useState([]);
  const [isLoading, setIsLoading] = useState(true); // 👈 Added

  useEffect(() => {
  const fetchArchive = async () => {
    const guestId = localStorage.getItem("guest_id");
    const username = localStorage.getItem("username");

    if (!guestId && !username) return;

    try {
      const response = await axios.get(
        username
          ? `${import.meta.env.VITE_API_URL}/grid-archive?username=${username}`
          : `${import.meta.env.VITE_API_URL}/grid-archive?guest_id=${guestId}`
      );
      setArchiveData(response.data);
    } catch (error) {
      console.error("Failed to fetch archive:", error);
    } finally {
      setIsLoading(false);
    }
  };

  fetchArchive();
}, []);

  return (
  <>
    <TopBanner />
    <div className="flex flex-col items-center px-4 py-6 w-full">
      <div className="w-full max-w-5xl">
        {!isLoading && (
          <>
<div className="archive-wrapper">
  <table className="grid-archive-table">
              <thead className="text-left text-gray-300 uppercase text-xs tracking-wider">
                <tr>
                  <th className="w-[15%] px-3">Grid</th>
                  <th className="w-[25%] px-3">Date</th>
                  <th className="w-[30%] px-3">Score</th>
                  <th className="w-[30%] px-3">Rarity</th>
                </tr>
              </thead>
              <tbody>
                {archiveData.map((entry) => {
                  const isCompleted = Number(entry.completed) === 1;
                  const hasStarted = entry.score !== null && entry.score !== undefined;

                  let scoreText;
                  if (isCompleted) {
                    scoreText = `${entry.score} / 9`;
                  } else if (hasStarted) {
                    scoreText = "Continue Playing";
                  } else {
                    scoreText = "Play Now!";
                  }

                  const rarityText =
                    isCompleted && entry.rarity_score != null
                      ? entry.rarity_score.toFixed(0)
                      : "-";

                  return (
                    <tr key={`${entry.grid_id}-${entry.date}`} className="bg-[#181818] hover:bg-[#202020] rounded">
                      <td className="px-3 py-2">
                        <Link to={`/grid/${entry.grid_id}`} className="text-blue-400 underline">
                          {entry.grid_id}
                        </Link>
                      </td>
                      <td className="px-3 py-2">{entry.date}</td>
                      <td className="px-3 py-2">
                        <Link to={`/grid/${entry.grid_id}`} className="text-blue-400 underline">
                          {scoreText}
                        </Link>
                      </td>
                      <td className="px-3 py-2">{rarityText}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </>
        )}
      </div>
    </div>
  </>
);
}
