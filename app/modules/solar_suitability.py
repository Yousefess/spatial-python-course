# modules/solar_suitability.py
# Built in Session 08: normalizing each factor to a shared 0-1 scale,
# combining them with a weighted sum, applying the water exclusion
# mask, and classifying the final score. This is the module app.py's
# weight sliders call on every rerun.

import numpy as np


def normalize_slope(slope, max_slope=45):
    """Normalize slope so 0 degrees scores 1 (best) and max_slope or more scores 0 (worst)."""
    clipped = np.clip(slope, 0, max_slope)
    return 1 - (clipped / max_slope)


def normalize_aspect(aspect):
    """Score aspect by closeness to south (180 degrees). Flat pixels (-1) score 0."""
    distance_from_south = np.abs(aspect - 180)
    distance_from_south = np.minimum(distance_from_south, 360 - distance_from_south)
    score = 1 - (distance_from_south / 180)
    return np.where(aspect == -1, 0, score)


def normalize_ndvi(ndvi):
    """Normalize NDVI so low vegetation scores 1 (best) and high vegetation scores 0 (worst)."""
    clipped = np.clip(ndvi, -1, 1)
    return 1 - ((clipped + 1) / 2)


def calculate_final_score(slope_score, aspect_score, ndvi_score, access_score, weights):
    """Combine four normalized 0-1 layers into one weighted score, scaled to 0-100."""
    combined = (
        slope_score * weights["slope"]
        + aspect_score * weights["aspect"]
        + ndvi_score * weights["ndvi"]
        + access_score * weights["access"]
    )
    return combined * 100


def apply_water_mask(score, water_mask):
    """Force any pixel flagged as water to a score of 0, regardless of its other factors."""
    return np.where(water_mask == 1, 0, score)


def classify_suitability(score, low_threshold=40, high_threshold=70):
    """Classify a continuous suitability score into 3 classes: 0=unsuitable, 1=moderate, 2=suitable."""
    classified = np.zeros_like(score, dtype="uint8")
    classified[(score >= low_threshold) & (score < high_threshold)] = 1
    classified[score >= high_threshold] = 2
    return classified


def classify_multi(score, thresholds):
    """Classify a continuous score into len(thresholds) + 1 classes using a
    list of ascending thresholds, e.g. [20, 40, 60, 80] -> 5 classes.
    Generalizes classify_suitability to any number of classes, used by the
    app's "3 or 5 classes" toggle without changing the original function."""
    classified = np.zeros_like(score, dtype="uint8")
    for class_value, threshold in enumerate(thresholds, start=1):
        classified[score >= threshold] = class_value
    return classified
