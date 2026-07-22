"""
=====================================================================
Module 5 - AI Commissioning Quality Assurance Copilot
=====================================================================
Integrated main script combining:
    1. AI-generated testing checklist
    2. Equipment image analysis (YOLOv8 defect detection)
    3. Sensor / voltage reading analysis
    4. Fault detection
    5. Automatic report generation
    6. AI recommendations

This file merges everything you previously had spread across:
    - sensor_analysis.py
    - train_yolo.py
    - detect.py
    - prepare_dataset.py
    - generate_synthetic_defects.py
    - config.py
    - helpers.py
    - report_generator.py

into a single, runnable, menu-driven program.

NOTE: "AI-generated testing checklist" and "AI recommendations" were
listed in your module spec but weren't in any of the files you sent,
so basic rule-based implementations have been added for them
(generate_testing_checklist / generate_recommendations). Extend them
with a real LLM call later if you want smarter output.
=====================================================================
"""

import os
import random
import shutil
from pathlib import Path
from datetime import datetime

import pandas as pd
from PIL import Image, ImageDraw

# cv2 / ultralytics are only imported lazily inside the functions that
# actually need them, so the rest of the script still runs even if
# those packages aren't installed yet.


# =====================================================================
# 1. CONFIG  (was: config.py)
# =====================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

PROJECT_DATA = PROJECT_ROOT / "project_data"
IMAGE_DIR = PROJECT_DATA / "09_Equipment_Images"
DEFECT_DIR = IMAGE_DIR / "Defect_Samples"
SENSOR_DIR = PROJECT_DATA / "10_Sensor_Readings"

MODULE5_DIR = PROJECT_ROOT / "module5"
DATASET_DIR = MODULE5_DIR / "dataset"
RUNS_DIR = MODULE5_DIR / "runs"
REPORTS_DIR = MODULE5_DIR / "reports"

ANNOTATION_FILE = DEFECT_DIR / "defect_annotations.csv"
DATA_YAML = DATASET_DIR / "data.yaml"
MODEL_PATH = RUNS_DIR / "commissioning_defect_detector" / "weights" / "best.pt"

TRAIN_RATIO = 0.8

EQUIPMENT_CATEGORIES = {
    "Generator": "EQ-GEN-303",
    "UPS": "EQ-UPS-101",
    "Cooling_System": "EQ-CHILL-202",
    "Battery_Storage": "EQ-BATT-404",
    "CRAH_Unit": "EQ-CRAH-505",
}

DEFECT_CLASSES = [
    "Scorch_Mark",
    "Corrosion",
    "Exposed_Wiring",
    "Panel_Crack",
]

CLASS_MAP = {name: idx for idx, name in enumerate(DEFECT_CLASSES)}

DEFECT_COLOR = {
    "Scorch_Mark": (70, 20, 20),
    "Corrosion": (130, 90, 30),
    "Exposed_Wiring": (255, 120, 20),
    "Panel_Crack": (210, 210, 210),
}

YOLO_MODEL = "yolov8n.pt"
IMAGE_SIZE = 640
BATCH_SIZE = 8
EPOCHS = 50

# Safe operating limits used for sensor + fault analysis
SAFE_LIMITS = {
    "Voltage": (220, 240),
    "Current": (0, 100),
    "Temperature": (0, 75),
}

# Checklist templates per equipment category
CHECKLIST_TEMPLATES = {
    "Generator": [
        "Verify fuel level and quality",
        "Check battery voltage and charger operation",
        "Inspect exhaust system for leaks",
        "Test automatic transfer switch (ATS) operation",
        "Confirm control panel alarms are clear",
    ],
    "UPS": [
        "Verify input/output voltage within spec",
        "Check battery string voltage and health",
        "Test transfer to battery mode (load bank test)",
        "Inspect cooling fans and filters",
        "Confirm alarm and monitoring system connectivity",
    ],
    "Cooling_System": [
        "Verify refrigerant pressure and levels",
        "Check compressor operation and current draw",
        "Inspect condenser/evaporator coils for fouling",
        "Confirm setpoint and control sequence operation",
        "Check for refrigerant leaks",
    ],
    "Battery_Storage": [
        "Verify cell/module voltage balance",
        "Check for corrosion at terminals",
        "Confirm BMS (battery management system) communication",
        "Inspect ventilation and thermal management",
        "Verify grounding and cabling integrity",
    ],
    "CRAH_Unit": [
        "Verify airflow and static pressure",
        "Check chilled water valve operation",
        "Inspect filters for blockage",
        "Confirm humidity control operation",
        "Test fan speed control (VFD) operation",
    ],
    "Default": [
        "Visual inspection for physical damage",
        "Verify power connections are secure",
        "Check sensor calibration",
        "Confirm labeling and documentation are complete",
        "Test alarm/notification functionality",
    ],
}


# =====================================================================
# 2. HELPERS  (was: helpers.py)
# =====================================================================

def ensure_directory(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def current_timestamp():
    """Return current timestamp as a string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate_risk_score(defect_detected, sensor_status):
    """
    Calculate overall equipment risk from defect + sensor status.
    sensor_status expected to be one of: "LOW", "MEDIUM", "HIGH".
    """
    if defect_detected and sensor_status == "HIGH":
        return "CRITICAL"
    if defect_detected or sensor_status == "HIGH":
        return "HIGH"
    if sensor_status == "MEDIUM":
        return "MEDIUM"
    return "LOW"


def load_image_cv2(image_path):
    """Load an image using OpenCV (lazy import)."""
    import cv2
    return cv2.imread(str(image_path))


def save_image_cv2(image_path, image):
    """Save image to disk using OpenCV (lazy import)."""
    import cv2
    cv2.imwrite(str(image_path), image)


# =====================================================================
# 3. SENSOR / VOLTAGE READING ANALYSIS  (was: sensor_analysis.py)
# =====================================================================

def analyze_sensor_data(csv_file):
    """
    Reads the latest row of a sensor CSV (Voltage, Current, Temperature)
    and flags each reading as Normal/Abnormal/High.
    Returns a dict report.
    """
    df = pd.read_csv(csv_file)
    latest = df.iloc[-1]

    v_lo, v_hi = SAFE_LIMITS["Voltage"]
    c_lo, c_hi = SAFE_LIMITS["Current"]
    t_lo, t_hi = SAFE_LIMITS["Temperature"]

    report = {
        "Voltage": latest["Voltage"],
        "Current": latest["Current"],
        "Temperature": latest["Temperature"],
        "Voltage_Status": "Normal" if v_lo <= latest["Voltage"] <= v_hi else "Abnormal",
        "Temperature_Status": "Normal" if latest["Temperature"] <= t_hi else "High",
        "Current_Status": "Normal" if latest["Current"] <= c_hi else "High",
    }

    return report


def sensor_overall_status(sensor_report):
    """
    Collapse the per-reading statuses into a single LOW/MEDIUM/HIGH
    level used for fault detection + risk scoring.
    """
    statuses = [
        sensor_report["Voltage_Status"],
        sensor_report["Temperature_Status"],
        sensor_report["Current_Status"],
    ]

    bad_count = sum(1 for s in statuses if s in ("Abnormal", "High"))

    if bad_count >= 2:
        return "HIGH"
    if bad_count == 1:
        return "MEDIUM"
    return "LOW"


# =====================================================================
# 4. SYNTHETIC DEFECT IMAGE GENERATION (was: generate_synthetic_defects.py)
#    -> used only to build a training dataset
# =====================================================================

def generate_synthetic_defect_images(images_per_equipment=6):
    """
    Creates synthetic equipment images with painted-on defects and an
    accompanying annotations CSV. Useful for bootstrapping a YOLO
    training set when you don't have real defect photos yet.
    """
    ensure_directory(DEFECT_DIR)

    annotations = []

    for category, equipment_id in EQUIPMENT_CATEGORIES.items():
        for i in range(1, images_per_equipment + 1):
            width, height = 640, 480

            img = Image.new("RGB", (width, height), (55, 58, 65))
            draw = ImageDraw.Draw(img)

            # Equipment body
            draw.rectangle(
                [60, 60, width - 60, height - 60],
                fill=(85, 90, 95),
                outline=(160, 160, 160),
                width=4,
            )

            defect = random.choice(DEFECT_CLASSES)

            x = random.randint(120, 420)
            y = random.randint(100, 280)
            w = random.randint(60, 120)
            h = random.randint(50, 100)

            color = DEFECT_COLOR[defect]

            if defect == "Scorch_Mark":
                draw.ellipse([x, y, x + w, y + h], fill=color)
                draw.ellipse([x + 10, y + 5, x + w - 5, y + h - 5], fill=(30, 10, 10))

            elif defect == "Corrosion":
                for _ in range(25):
                    rx = random.randint(x, x + w)
                    ry = random.randint(y, y + h)
                    r = random.randint(4, 10)
                    draw.ellipse([rx - r, ry - r, rx + r, ry + r], fill=color)

            elif defect == "Exposed_Wiring":
                for k in range(5):
                    draw.line([(x, y + k * 10), (x + w, y + h - k * 8)], fill=color, width=4)

            elif defect == "Panel_Crack":
                draw.line([x, y, x + w, y + h], fill=color, width=4)
                draw.line([x + 25, y + h, x + w - 20, y - 10], fill=color, width=3)
                draw.line(
                    [x + w // 2, y + h // 2, x + w // 2 + 35, y + h // 2 - 25],
                    fill=color,
                    width=2,
                )

            filename = f"{equipment_id}_{i}.jpg"
            filepath = DEFECT_DIR / filename
            img.save(filepath)

            annotations.append(
                {
                    "Image_Path": str(filepath),
                    "Equipment_ID": equipment_id,
                    "Category": category,
                    "Is_Defect": "Yes",
                    "Defect_Class": defect,
                    "BBox_X": x,
                    "BBox_Y": y,
                    "BBox_W": w,
                    "BBox_H": h,
                }
            )

    df = pd.DataFrame(annotations)
    df.to_csv(ANNOTATION_FILE, index=False)

    print("=" * 60)
    print("Synthetic defect dataset generated")
    print(f"Images       : {len(df)}")
    print(f"Annotations  : {ANNOTATION_FILE}")
    print("=" * 60)

    return ANNOTATION_FILE


# =====================================================================
# 5. DATASET PREPARATION - annotations -> YOLO format
#    (was: prepare_dataset.py)
# =====================================================================

def _convert_to_yolo(x, y, w, h, img_width=640, img_height=480):
    x_center = (x + w / 2) / img_width
    y_center = (y + h / 2) / img_height
    width = w / img_width
    height = h / img_height
    return x_center, y_center, width, height


def _process_split(records, split):
    for row in records:
        image_path = row["Image_Path"]
        image_name = os.path.basename(image_path)

        destination_image = DATASET_DIR / "images" / split / image_name
        shutil.copy(image_path, destination_image)

        class_id = CLASS_MAP[row["Defect_Class"]]

        x, y, w, h = _convert_to_yolo(
            row["BBox_X"], row["BBox_Y"], row["BBox_W"], row["BBox_H"]
        )

        label_file = DATASET_DIR / "labels" / split / image_name.replace(".jpg", ".txt")

        with open(label_file, "w") as f:
            f.write(f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")


def prepare_yolo_dataset(annotation_file=None, train_ratio=TRAIN_RATIO):
    """
    Converts the defect annotations CSV into a YOLOv8-ready dataset
    (images/train, images/val, labels/train, labels/val) plus a
    data.yaml file.
    """
    annotation_file = annotation_file or ANNOTATION_FILE

    for folder in ["images/train", "images/val", "labels/train", "labels/val"]:
        ensure_directory(DATASET_DIR / folder)

    df = pd.read_csv(annotation_file)
    records = df.to_dict("records")
    random.shuffle(records)

    split_index = int(len(records) * train_ratio)
    train_records = records[:split_index]
    val_records = records[split_index:]

    print(f"Training Images   : {len(train_records)}")
    print(f"Validation Images : {len(val_records)}")

    _process_split(train_records, "train")
    _process_split(val_records, "val")

    # Write data.yaml for YOLO training
    yaml_content = (
        f"path: {DATASET_DIR}\n"
        f"train: images/train\n"
        f"val: images/val\n\n"
        f"names:\n"
        + "\n".join(f"  {idx}: {name}" for name, idx in CLASS_MAP.items())
        + "\n"
    )
    with open(DATA_YAML, "w") as f:
        f.write(yaml_content)

    print(f"data.yaml written to {DATA_YAML}")
    return DATA_YAML


# =====================================================================
# 6. YOLO TRAINING  (was: train_yolo.py)
# =====================================================================

def train_yolo_model(epochs=EPOCHS, imgsz=IMAGE_SIZE, batch=BATCH_SIZE):
    """
    Trains a YOLOv8 model on the prepared dataset. Requires the
    `ultralytics` package (pip install ultralytics --break-system-packages).
    """
    from ultralytics import YOLO

    model = YOLO(YOLO_MODEL)

    print("=" * 60)
    print("Starting YOLOv8 Training...")
    print("=" * 60)

    model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        workers=2,
        project=str(RUNS_DIR),
        name="commissioning_defect_detector",
        exist_ok=True,
        pretrained=True,
    )

    print("=" * 60)
    print("Training Complete!")
    print("=" * 60)

    metrics = model.val()
    print(metrics)

    return model


# =====================================================================
# 7. AI-GENERATED TESTING CHECKLIST  (new)
# =====================================================================

def generate_testing_checklist(equipment_category):
    """
    Returns a commissioning testing checklist for the given equipment
    category. Falls back to a generic checklist if the category isn't
    recognized.
    """
    return CHECKLIST_TEMPLATES.get(equipment_category, CHECKLIST_TEMPLATES["Default"])


# =====================================================================
# 8. AI RECOMMENDATIONS  (new)
# =====================================================================

def generate_recommendations(detections, sensor_report=None):
    """
    Rule-based recommendation engine combining detected visual defects
    and sensor readings into actionable next steps.
    """
    recommendations = []

    defect_advice = {
        "Scorch_Mark": "Inspect for overheating/arcing at the affected connection; de-energize and re-torque terminals before re-commissioning.",
        "Corrosion": "Clean corroded contacts/surfaces and assess for moisture ingress; verify enclosure sealing.",
        "Exposed_Wiring": "Immediately isolate circuit and re-insulate/replace exposed conductors before energizing.",
        "Panel_Crack": "Evaluate structural integrity of the panel; replace if crack compromises enclosure rating (IP/NEMA).",
    }

    seen = set()
    for defect_name, confidence in detections:
        if defect_name in seen:
            continue
        seen.add(defect_name)
        advice = defect_advice.get(defect_name, "Investigate detected anomaly further.")
        recommendations.append(f"[{defect_name}] {advice} (confidence {confidence:.2f})")

    if sensor_report:
        if sensor_report["Voltage_Status"] != "Normal":
            recommendations.append(
                f"Voltage reading ({sensor_report['Voltage']}) is outside safe range "
                f"{SAFE_LIMITS['Voltage']}. Check supply stability and load balance."
            )
        if sensor_report["Current_Status"] != "Normal":
            recommendations.append(
                f"Current reading ({sensor_report['Current']}) exceeds safe limit "
                f"{SAFE_LIMITS['Current'][1]}. Check for overload or short-circuit conditions."
            )
        if sensor_report["Temperature_Status"] != "Normal":
            recommendations.append(
                f"Temperature reading ({sensor_report['Temperature']}) exceeds safe limit "
                f"{SAFE_LIMITS['Temperature'][1]}. Check cooling/ventilation."
            )

    if not recommendations:
        recommendations.append("No anomalies detected. Equipment appears within normal parameters.")

    return recommendations


# =====================================================================
# 9. REPORT GENERATION  (was: report_generator.py, extended)
# =====================================================================

def generate_report(equipment_name, detections, output_path,
                     sensor_report=None, risk_score=None,
                     checklist=None, recommendations=None):
    """
    Writes a full commissioning QA report combining defect detections,
    sensor analysis, risk score, testing checklist, and recommendations.
    """
    ensure_directory(Path(output_path).parent)

    with open(output_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("AI DATA CENTER EPC ASSISTANT\n")
        f.write("Commissioning Quality Assurance Report\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Equipment : {equipment_name}\n")
        f.write(f"Date      : {current_timestamp()}\n")
        if risk_score:
            f.write(f"Risk      : {risk_score}\n")
        f.write("\n")

        f.write("Detected Defects\n")
        f.write("-" * 40 + "\n")
        if not detections:
            f.write("No defects detected.\n")
        else:
            for defect, confidence in detections:
                f.write(f"{defect:<20} Confidence: {confidence:.2f}\n")
        f.write("\n")

        if sensor_report:
            f.write("Sensor Readings\n")
            f.write("-" * 40 + "\n")
            f.write(f"Voltage     : {sensor_report['Voltage']}  [{sensor_report['Voltage_Status']}]\n")
            f.write(f"Current     : {sensor_report['Current']}  [{sensor_report['Current_Status']}]\n")
            f.write(f"Temperature : {sensor_report['Temperature']}  [{sensor_report['Temperature_Status']}]\n")
            f.write("\n")

        if checklist:
            f.write("Testing Checklist\n")
            f.write("-" * 40 + "\n")
            for item in checklist:
                f.write(f"[ ] {item}\n")
            f.write("\n")

        if recommendations:
            f.write("AI Recommendations\n")
            f.write("-" * 40 + "\n")
            for rec in recommendations:
                f.write(f"- {rec}\n")
            f.write("\n")

        f.write("=" * 60 + "\n")
        f.write("End of Report\n")

    return output_path


# =====================================================================
# 10. EQUIPMENT IMAGE ANALYSIS + FAULT DETECTION (was: detect.py)
# =====================================================================

def _load_yolo_model():
    from ultralytics import YOLO
    try:
        return YOLO(str(MODEL_PATH))
    except Exception:
        return None


def detect_defects(image_input, filename_override=None):
    """
    Runs YOLOv8 defect detection on an image (path string or PIL Image).
    Returns a list of (defect_name, confidence) tuples.
    """
    model = _load_yolo_model()

    if model is None:
        print(f"\n[Error] Model weights not found at '{MODEL_PATH}'.")
        print("Run option 4 (Train YOLO Model) first.")
        return []

    results = model.predict(
        source=image_input,
        conf=0.05,
        save=True,
        project=str(RUNS_DIR / "detect" / "output"),
        name="detections",
        exist_ok=True,
    )

    detections = []
    print("\n" + "=" * 30)
    print("Detected Defects")
    print("=" * 30)

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            defect_name = model.names[cls]
            print(f"{defect_name} : {conf:.3f}")
            detections.append((defect_name, conf))

    return detections


def _resolve_equipment_name(image_input, filename_override):
    if filename_override:
        return filename_override.split(".")[0]
    if isinstance(image_input, str):
        return os.path.basename(image_input).split(".")[0]
    return "uploaded_equipment_image"


# =====================================================================
# 11. FULL QA COPILOT PIPELINE (ties everything together)
# =====================================================================

def run_qa_pipeline(image_path, sensor_csv=None, equipment_category=None,
                     filename_override=None):
    """
    End-to-end commissioning QA check for one piece of equipment:
      1. Run image-based defect detection
      2. Run sensor analysis (if a CSV is supplied)
      3. Compute overall risk score (fault detection)
      4. Generate a testing checklist
      5. Generate AI recommendations
      6. Write a full report to module5/reports/
    """
    equipment_name = _resolve_equipment_name(image_path, filename_override)

    # 1. Image analysis
    detections = detect_defects(image_path, filename_override=filename_override)
    defect_detected = len(detections) > 0

    # 2. Sensor analysis
    sensor_report = None
    sensor_status = "LOW"
    if sensor_csv:
        sensor_report = analyze_sensor_data(sensor_csv)
        sensor_status = sensor_overall_status(sensor_report)

    # 3. Fault detection / risk scoring
    risk_score = calculate_risk_score(defect_detected, sensor_status)

    # 4. Testing checklist
    checklist = generate_testing_checklist(equipment_category or "Default")

    # 5. AI recommendations
    recommendations = generate_recommendations(detections, sensor_report)

    # 6. Report
    ensure_directory(REPORTS_DIR)
    report_path = REPORTS_DIR / f"{equipment_name}_report.txt"

    generate_report(
        equipment_name,
        detections,
        report_path,
        sensor_report=sensor_report,
        risk_score=risk_score,
        checklist=checklist,
        recommendations=recommendations,
    )

    print(f"\nRisk Score : {risk_score}")
    print(f"Report saved to: {report_path}")

    return {
        "equipment_name": equipment_name,
        "detections": detections,
        "sensor_report": sensor_report,
        "risk_score": risk_score,
        "checklist": checklist,
        "recommendations": recommendations,
        "report_path": str(report_path),
    }


# =====================================================================
# 12. CLI MENU
# =====================================================================

def _menu():
    print("\n" + "=" * 60)
    print("MODULE 5 - AI Commissioning Quality Assurance Copilot")
    print("=" * 60)
    print("1. Analyze sensor CSV")
    print("2. Generate synthetic defect training images")
    print("3. Prepare YOLO dataset (from annotations)")
    print("4. Train YOLO model")
    print("5. Run full QA pipeline (image + sensor + report)")
    print("6. Generate testing checklist only")
    print("0. Exit")
    return input("Select an option: ").strip()


def main():
    while True:
        choice = _menu()

        if choice == "1":
            path = input("Sensor CSV path: ").strip()
            if not os.path.exists(path):
                print("File not found.")
                continue
            print(analyze_sensor_data(path))

        elif choice == "2":
            generate_synthetic_defect_images()

        elif choice == "3":
            prepare_yolo_dataset()

        elif choice == "4":
            train_yolo_model()

        elif choice == "5":
            image_path = input("Equipment image path: ").strip()
            if not os.path.exists(image_path):
                print("Image not found.")
                continue
            sensor_csv = input("Sensor CSV path (blank to skip): ").strip() or None
            if sensor_csv and not os.path.exists(sensor_csv):
                print("Sensor CSV not found, continuing without it.")
                sensor_csv = None
            print("Equipment categories:", ", ".join(EQUIPMENT_CATEGORIES.keys()))
            category = input("Equipment category (blank for default checklist): ").strip() or None

            run_qa_pipeline(image_path, sensor_csv=sensor_csv, equipment_category=category)

        elif choice == "6":
            print("Equipment categories:", ", ".join(EQUIPMENT_CATEGORIES.keys()))
            category = input("Equipment category: ").strip()
            for item in generate_testing_checklist(category):
                print(f"[ ] {item}")

        elif choice == "0":
            print("Exiting.")
            break

        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()