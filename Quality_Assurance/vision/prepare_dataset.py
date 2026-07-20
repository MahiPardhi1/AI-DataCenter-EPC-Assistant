import os
import shutil
import random
import pandas as pd

# -----------------------------
# Paths
# -----------------------------

ANNOTATION_FILE = "project_data/09_Equipment_Images/Defect_Samples/defect_annotations.csv"

OUTPUT_DATASET = "module5/dataset"

TRAIN_RATIO = 0.8

# -----------------------------
# Defect Classes
# -----------------------------

CLASS_MAP = {
    "Scorch_Mark": 0,
    "Corrosion": 1,
    "Exposed_Wiring": 2,
    "Panel_Crack": 3
}

# -----------------------------
# Create folders
# -----------------------------

folders = [
    "images/train",
    "images/val",
    "labels/train",
    "labels/val"
]

for folder in folders:
    os.makedirs(os.path.join(OUTPUT_DATASET, folder), exist_ok=True)

# -----------------------------
# Read annotations
# -----------------------------

df = pd.read_csv(ANNOTATION_FILE)

records = df.to_dict("records")

random.shuffle(records)

split_index = int(len(records) * TRAIN_RATIO)

train_records = records[:split_index]
val_records = records[split_index:]

print(f"Training Images : {len(train_records)}")
print(f"Validation Images : {len(val_records)}")


# ---------------------------------------
# Function to convert bbox to YOLO format
# ---------------------------------------

def convert_to_yolo(x, y, w, h, img_width=600, img_height=400):

    x_center = (x + w / 2) / img_width
    y_center = (y + h / 2) / img_height

    width = w / img_width
    height = h / img_height

    return x_center, y_center, width, height


# ---------------------------------------
# Process train / validation sets
# ---------------------------------------

def process_dataset(records, split):

    for row in records:

        image_path = row["Image_Path"]

        image_name = os.path.basename(image_path)

        destination_image = os.path.join(
            OUTPUT_DATASET,
            "images",
            split,
            image_name
        )

        shutil.copy(image_path, destination_image)

        class_id = CLASS_MAP[row["Defect_Class"]]

        x, y, w, h = convert_to_yolo(
            row["BBox_X"],
            row["BBox_Y"],
            row["BBox_W"],
            row["BBox_H"]
        )

        label_file = os.path.join(
            OUTPUT_DATASET,
            "labels",
            split,
            image_name.replace(".jpg", ".txt")
        )

        with open(label_file, "w") as f:
            f.write(
                f"{class_id} "
                f"{x:.6f} "
                f"{y:.6f} "
                f"{w:.6f} "
                f"{h:.6f}"
            )


process_dataset(train_records, "train")
process_dataset(val_records, "val")