import os
import requests
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# Folder names now map 1:1 onto your actual EQUIPMENT_IDS, instead of
# "Transformer" / "Electrical_Panel" which had no corresponding asset in the
# schedule / supply-chain / commissioning data. This closes the relational
# gap so Module 5 images can be joined back to the same Equipment_ID used
# everywhere else in the platform.
# ---------------------------------------------------------
FOLDER_TO_EQUIPMENT = {
    "Generator": "EQ-GEN-303",
    "UPS": "EQ-UPS-101",
    "Cooling_System": "EQ-CHILL-202",
    "Battery_Storage": "EQ-BATT-404",
    "CRAH_Unit": "EQ-CRAH-505",
}

categories = {
    "project_data/09_Equipment_Images/Generator": [
        "https://images.unsplash.com/photo-1622126978371-2911f93618bf?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1605810230434-7631ac76ec81?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=600&q=80"
    ],
    "project_data/09_Equipment_Images/UPS": [
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1563770660941-20978e870e26?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1600132806370-bf17e65e942f?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=80"
    ],
    "project_data/09_Equipment_Images/Cooling_System": [
        "https://images.unsplash.com/photo-1585338107529-13afc5f02586?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1527689368864-3a821dbccc34?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?auto=format&fit=crop&w=600&q=80"
    ],
    "project_data/09_Equipment_Images/Battery_Storage": [
        "https://images.unsplash.com/photo-1620825141079-49c62a4a2f89?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1611605698335-8b1569810432?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1620825141234-4e93cb3d6a8f?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1509391366360-2e959784a276?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1611873893930-e73f5cbba6ac?auto=format&fit=crop&w=600&q=80"
    ],
    "project_data/09_Equipment_Images/CRAH_Unit": [
        "https://images.unsplash.com/photo-1585338107529-13afc5f02586?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1581092918056-0c4c3dad3785?auto=format&fit=crop&w=600&q=80"
    ],
}

print("⏳ Fetching real high-quality infrastructure images from the repository...")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

annotation_rows = []  # collects one row per image for the ground-truth CSV


def make_placeholder(path, label, w=600, h=400):
    """
    Network-safe fallback: if a stock photo download fails (dead link, rate
    limit, offline demo laptop), generate a clean local placeholder instead
    of silently skipping the file. Keeps folder counts and the annotation
    CSV consistent no matter what happens on the day of the demo.
    """
    img = Image.new("RGB", (w, h), color=(60, 65, 75))
    draw = ImageDraw.Draw(img)
    
    # Cross-platform font fallback (Windows Arial -> Linux DejaVu -> Default)
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
            
    draw.rectangle([20, 20, w - 20, h - 20], outline=(150, 155, 165), width=3)
    draw.text((w / 2, h / 2), label, font=font, fill=(220, 220, 220), anchor="mm")
    img.save(path)


for folder, urls in categories.items():
    os.makedirs(folder, exist_ok=True)
    folder_name = folder.split("/")[-1]
    equipment_id = FOLDER_TO_EQUIPMENT[folder_name]

    for index, url in enumerate(urls):
        file_name = f"{folder}/{equipment_id}_sample_{index + 1}.jpg"
        downloaded = False
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                with open(file_name, "wb") as f:
                    f.write(response.content)
                downloaded = True
                print(f"✅ Downloaded: {file_name}")
            else:
                print(f"⚠️ HTTP {response.status_code} for {file_name} — using local placeholder instead")
        except Exception as e:
            print(f"⚠️ Network issue for {file_name}: {e} — using local placeholder instead")

        if not downloaded:
            make_placeholder(file_name, f"{equipment_id}\n(placeholder - image unavailable)")

        annotation_rows.append({
            "Image_Path": file_name,
            "Equipment_ID": equipment_id,
            "Is_Defect": "No",
            "Defect_Class": "None",
            "BBox_X": "", "BBox_Y": "", "BBox_W": "", "BBox_H": ""
        })

# ---------------------------------------------------------
# Synthetic, annotated "defect" images.
#
# The original 25 images were all clean stock photos of healthy equipment --
# there was nothing in Folder 09 for a defect-detection model to find, even
# though Module 5's whole pitch is "automate punch-lists from site images."
# These are generated locally (no external dependency, no licensing risk)
# with a known, exact bounding box for each defect, so you have real
# ground truth to train against or evaluate a YOLOv8 model on.
# ---------------------------------------------------------
DEFECT_TYPES = {
    "Scorch_Mark": (90, 40, 40),      # dark red-brown burn mark
    "Corrosion": (120, 100, 60),      # rust/corrosion patch
    "Exposed_Wiring": (230, 140, 20), # bright orange exposed conductor
    "Panel_Crack": (200, 200, 200),   # light crack line against dark panel
}

defect_dir = "project_data/09_Equipment_Images/Defect_Samples"
os.makedirs(defect_dir, exist_ok=True)

defect_plan = [
    ("EQ-GEN-303", "Scorch_Mark"),
    ("EQ-UPS-101", "Exposed_Wiring"),
    ("EQ-CHILL-202", "Corrosion"),
    ("EQ-BATT-404", "Corrosion"),
    ("EQ-CRAH-505", "Panel_Crack"),
    ("EQ-GEN-303", "Exposed_Wiring"),
]

for i, (equipment_id, defect_class) in enumerate(defect_plan):
    w, h = 600, 400
    img = Image.new("RGB", (w, h), color=(45, 48, 55))  # equipment body
    draw = ImageDraw.Draw(img)
    # simple panel/body silhouette so it doesn't look like a blank canvas
    draw.rectangle([60, 60, w - 60, h - 60], outline=(90, 95, 105), width=4)

    # place the defect at a known, fixed bounding box
    bx, by, bw, bh = 220, 150, 140, 90
    color = DEFECT_TYPES[defect_class]
    if defect_class == "Panel_Crack":
        draw.line([bx, by, bx + bw, by + bh], fill=color, width=6)
        draw.line([bx + 20, by + bh, bx + bw - 10, by - 10], fill=color, width=4)
    else:
        draw.ellipse([bx, by, bx + bw, by + bh], fill=color)

    # Cross-platform font fallback (Windows Arial -> Linux DejaVu -> Default)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except Exception:
            font = ImageFont.load_default()
            
    draw.text((10, h - 25), f"{equipment_id} - {defect_class} (synthetic QA sample)", font=font, fill=(200, 200, 200))

    file_name = f"{defect_dir}/{equipment_id}_defect_{i+1}.jpg"
    img.save(file_name)
    print(f"🛠️ Generated synthetic defect sample: {file_name}")

    annotation_rows.append({
        "Image_Path": file_name,
        "Equipment_ID": equipment_id,
        "Is_Defect": "Yes",
        "Defect_Class": defect_class,
        "BBox_X": bx, "BBox_Y": by, "BBox_W": bw, "BBox_H": bh
    })

# ---------------------------------------------------------
# Ground-truth annotation CSV -- this is what actually makes Folder 09
# usable for a CV pipeline (training, evaluation, or even just a demo table
# next to the YOLOv8 output).
# ---------------------------------------------------------
pd.DataFrame(annotation_rows).to_csv(
    "project_data/09_Equipment_Images/image_annotations.csv", index=False
)

print("🖼️ Image sync complete! Clean samples + synthetic defect samples + image_annotations.csv are ready.")