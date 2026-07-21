from ultralytics import YOLO
import os
import sys

# Allow importing report_generator.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports")))

from report_generator import generate_report

# Load trained model safely with error handling
MODEL_PATH = "module5/runs/commissioning_defect_detector/weights/best.pt"

try:
    model = YOLO(MODEL_PATH)
except Exception as e:
    model = None


def detect(image_path):
    if model is None:
        print(f"\n[Error] Model weights not found at '{MODEL_PATH}'.")
        print("Please run 'train_yolo.py' first to train the model before running defect detection.")
        return

    results = model.predict(
        source=image_path,
        conf=0.05,
        save=True,
        project="runs/detect/module5/output",
        name="detections",
        exist_ok=True
    )

    detections = []

    print("\n==============================")
    print("Detected Defects")
    print("==============================")

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])

            defect_name = model.names[cls]

            print(f"{defect_name} : {conf:.3f}")

            detections.append((defect_name, conf))

    equipment = os.path.basename(image_path).split(".")[0]

    report_path = f"module5/reports/{equipment}_report.txt"

    generate_report(
        equipment,
        detections,
        report_path
    )

    print("\nReport Generated:")
    print(report_path)


if __name__ == "__main__":
    image_path = input("Enter image path: ")

    if not os.path.exists(image_path):
        print("Image not found!")
    else:
        detect(image_path)