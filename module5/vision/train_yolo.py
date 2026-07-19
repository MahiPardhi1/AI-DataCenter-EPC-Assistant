from ultralytics import YOLO
import os

# Path to dataset yaml
DATA_YAML = "module5/dataset/data.yaml"

# Load pretrained YOLOv8 Nano model
model = YOLO("yolov8n.pt")

print("=" * 60)
print("Starting YOLOv8 Training...")
print("=" * 60)

# Train
model.train(
    data=DATA_YAML,
    epochs=50,
    imgsz=640,
    batch=8,
    workers=2,
    project="module5/runs",
    name="commissioning_defect_detector",
    exist_ok=True
    pretrained=True
)

print("=" * 60)
print("Training Complete!")
print("=" * 60)

# Validate
metrics = model.val()

print(metrics)
