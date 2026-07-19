from ultralytics import YOLO
import cv2

# Load trained model
model = YOLO("module5/runs/commissioning_defect_detector/weights/best.pt")

def detect(image_path):
    results = model.predict(
        source=image_path,
        conf=0.4,
        save=True
    )

    for r in results:
        print("Detections:")
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])

            print(
                model.names[cls],
                round(conf, 3)
            )

    return results


if __name__ == "__main__":
    image = input("Enter image path: ")
    detect(image)