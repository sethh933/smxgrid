"""Pure, adjustable scoring for daily grids; weights are relative probabilities."""

import json
import math
from pathlib import Path

HISTORY_DAYS = 7
DEPTH_HALF_SATURATION = 10
CATEGORY_EXPONENT = 2
DEPTH_EXPONENT = 2
RECENCY_STRENGTH = 1


def load_ratings(criteria, path=None):
    path = path or Path(__file__).with_name("criteria_ratings.json")
    with open(path, encoding="utf-8") as file:
        ratings = json.load(file)
    missing = set(criteria) - ratings.keys()
    if missing:
        raise ValueError(f"Missing category ratings: {sorted(missing)}")
    if any(type(value) is not int or not 1 <= value <= 5 for value in ratings.values()):
        raise ValueError("Category ratings must be integers from 1 to 5")
    return ratings


def score_grid(criteria, grid_data, ratings, recent_grids=()):
    """Reward depth with diminishing returns; shallow cells weigh down the mean.

    Ten answers gives half depth credit; larger pools always earn more credit.
    Recent grids must be ordered newest first. Each history entry is six names.
    """
    counts = [len(riders) for riders in grid_data.values()]
    if len(criteria) != 6 or len(counts) != 9 or min(counts) == 0:
        raise ValueError("Scoring requires six criteria and nine nonempty cells")
    category_average = sum(ratings[name] for name in criteria) / 6
    depth = math.exp(sum(math.log(count / (count + DEPTH_HALF_SATURATION))
                         for count in counts) / 9)
    recent = list(recent_grids)[:HISTORY_DAYS]
    repeat_load = sum(
        len({name for name in criteria if ratings[name] >= 3} & set(previous)) / 6
        * (HISTORY_DAYS - age) / HISTORY_DAYS
        for age, previous in enumerate(recent)
    )
    recency = 1 / (1 + RECENCY_STRENGTH * repeat_load)
    weight = (category_average / 5) ** CATEGORY_EXPONENT * depth ** DEPTH_EXPONENT * recency
    return {
        "category_average": category_average,
        "answer_counts": counts,
        "minimum_answers": min(counts),
        "depth_score": depth,
        "recency_factor": recency,
        "weight": weight,
    }
