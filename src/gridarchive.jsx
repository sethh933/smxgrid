import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import TopBanner from "./TopBanner";
import "./gridarchive.css";

const PREVIEW_SIZE = 20;

export default function GridArchive() {
  const [archiveData, setArchiveData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const fetchArchive = useCallback(async (all, signal) => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const guestId = localStorage.getItem("guest_id");
      const username = localStorage.getItem("username");

      if (!guestId && !username) return;

      const identity = username ? { username } : { guest_id: guestId };
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/grid-archive`, {
        params: { ...identity, show_all: all, limit: PREVIEW_SIZE + 1 },
        signal,
      });
      setArchiveData(response.data);
      setShowAll(all);
    } catch (error) {
      if (!axios.isCancel(error)) {
        console.error("Failed to fetch archive:", error);
        setLoadError(true);
      }
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchArchive(false, controller.signal);
    return () => controller.abort();
  }, [fetchArchive]);

  const displayedData = showAll ? archiveData : archiveData.slice(0, PREVIEW_SIZE);

  return (
  <>
    <TopBanner />
    <div className="flex flex-col items-center px-4 py-6 w-full">
      <div className="w-full max-w-5xl">
        {(!isLoading || archiveData.length > 0) && (
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
                  {displayedData.map((entry) => {
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

            {loadError && (
              <p role="alert" className="text-center">Couldn’t load the archive. Please try again.</p>
            )}
            {loadError && archiveData.length === 0 && (
              <button onClick={() => fetchArchive(false)} className="archive-button">
                Retry
              </button>
            )}
            {!showAll && archiveData.length > PREVIEW_SIZE && (
              <div className="w-full flex justify-center py-6">
                <button
                  onClick={() => fetchArchive(true)}
                  disabled={isLoading}
                  className="archive-button"
                >
                  {isLoading ? "Loading…" : "Show All"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  </>
);
}

