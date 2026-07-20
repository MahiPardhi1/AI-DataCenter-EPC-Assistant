"""
Module 5 Configuration
AI Commissioning Quality Assurance Copilot
"""

from pathlib import Path

# -----------------------------
# Project Root
# -----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# -----------------------------
# Data Directories
# -----------------------------
PROJECT_DATA = PROJECT_ROOT / "project_data"

IMAGE_DIR = PROJECT_DATA / "09_Equipment_Images"
DEFECT_DIR = IMAGE_DIR / "Defect_Samples"
SENSOR_DIR = PROJECT_DATA / "10_Sensor_Readings"

# -----------------------------
# Module 5 Directories
# -----------------------------
MODULE5_DIR = PROJECT_ROOT / "module5"
DATASET_DIR = MODULE5_DIR / "dataset"
VISION_DIR = MODULE5_DIR / "vision"

YOLO_DATASET_DIR = DATASET_DIR / "yolo_dataset"

# -----------------------------
# Equipment Categories
# -----------------------------
EQUIPMENT_CATEGORIES = [
    "Generator",
    "UPS",
    "Cooling_System",
    "Battery_Storage",
    "CRAH_Unit"
]

# -----------------------------
# Defect Classes
# -----------------------------
DEFECT_CLASSES = [
    "Scorch_Mark",
    "Corrosion",
    "Exposed_Wiring",
    "Panel_Crack"
]

# -----------------------------
# YOLO Model
# -----------------------------
YOLO_MODEL = "yolov8n.pt"

# -----------------------------
# Training Parameters
# -----------------------------
IMAGE_SIZE = 640
BATCH_SIZE = 8
EPOCHS = 50

# -----------------------------
# Safe Sensor Limits
# -----------------------------
SAFE_LIMITS = {
    "Voltage": (210, 250),
    "Current": (0, 1200),
    "Temperature": (15, 85)
}