"""
Helper functions for Module 5
"""

from pathlib import Path
import cv2
import pandas as pd
from datetime import datetime


def ensure_directory(path):
    """
    Create directory if it doesn't exist.
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def load_image(image_path):
    """
    Load an image using OpenCV.
    """
    return cv2.imread(str(image_path))


def save_image(image_path, image):
    """
    Save image to disk.
    """
    cv2.imwrite(str(image_path), image)


def load_csv(csv_path):
    """
    Read a CSV file into a DataFrame.
    """
    return pd.read_csv(csv_path)


def current_timestamp():
    """
    Return current timestamp.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate_risk_score(defect_detected, sensor_status):
    """
    Calculate overall equipment risk.
    """

    if defect_detected and sensor_status == "HIGH":
        return "CRITICAL"

    if defect_detected or sensor_status == "HIGH":
        return "HIGH"

    if sensor_status == "MEDIUM":
        return "MEDIUM"

    return "LOW"