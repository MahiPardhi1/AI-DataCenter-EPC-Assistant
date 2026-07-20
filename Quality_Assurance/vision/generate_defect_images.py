import os
import random
import pandas as pd
from PIL import Image, ImageDraw

# ==========================
# OUTPUT DIRECTORY
# ==========================

OUTPUT_DIR = "project_data/09_Equipment_Images/Defect_Samples"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================
# EQUIPMENT
# ==========================

EQUIPMENT = {
    "Generator": "EQ-GEN-303",
    "UPS": "EQ-UPS-101",
    "Cooling_System": "EQ-CHILL-202",
    "Battery_Storage": "EQ-BATT-404",
    "CRAH_Unit": "EQ-CRAH-505"
}

# ==========================
# DEFECT CLASSES
# ==========================

DEFECTS = [
    "Scorch_Mark",
    "Corrosion",
    "Exposed_Wiring",
    "Panel_Crack"
]

# Colors for synthetic defects
DEFECT_COLOR = {
    "Scorch_Mark": (70, 20, 20),
    "Corrosion": (130, 90, 30),
    "Exposed_Wiring": (255, 120, 20),
    "Panel_Crack": (210, 210, 210)
}

annotations = []

# ==========================
# GENERATE IMAGES
# ==========================

for category, equipment_id in EQUIPMENT.items():

    for i in range(1,7):          # 6 images each

        width = 640
        height = 480

        img = Image.new(
            "RGB",
            (width,height),
            (55,58,65)
        )

        draw = ImageDraw.Draw(img)

        # Equipment body
        draw.rectangle(
            [60,60,width-60,height-60],
            fill=(85,90,95),
            outline=(160,160,160),
            width=4
        )

        defect = random.choice(DEFECTS)

        x = random.randint(120,420)
        y = random.randint(100,280)

        w = random.randint(60,120)
        h = random.randint(50,100)

        color = DEFECT_COLOR[defect]

        # ======================
        # Draw defect
        # ======================

        if defect=="Scorch_Mark":

            draw.ellipse(
                [x,y,x+w,y+h],
                fill=color
            )

            draw.ellipse(
                [x+10,y+5,x+w-5,y+h-5],
                fill=(30,10,10)
            )

        elif defect=="Corrosion":

            for _ in range(25):

                rx=random.randint(x,x+w)
                ry=random.randint(y,y+h)

                r=random.randint(4,10)

                draw.ellipse(
                    [rx-r,ry-r,rx+r,ry+r],
                    fill=color
                )

        elif defect=="Exposed_Wiring":

            for k in range(5):

                draw.line(
                    [
                        (x,y+k*10),
                        (x+w,y+h-k*8)
                    ],
                    fill=color,
                    width=4
                )

        elif defect=="Panel_Crack":

            draw.line(
                [x,y,x+w,y+h],
                fill=color,
                width=4
            )

            draw.line(
                [x+25,y+h,
                 x+w-20,y-10],
                fill=color,
                width=3
            )

            draw.line(
                [x+w//2,
                 y+h//2,
                 x+w//2+35,
                 y+h//2-25],
                fill=color,
                width=2
            )

        filename = f"{equipment_id}_{i}.jpg"

        filepath = os.path.join(
            OUTPUT_DIR,
            filename
        )

        img.save(filepath)

        annotations.append({

            "Image_Path":filepath,

            "Equipment_ID":equipment_id,

            "Category":category,

            "Is_Defect":"Yes",

            "Defect_Class":defect,

            "BBox_X":x,

            "BBox_Y":y,

            "BBox_W":w,

            "BBox_H":h

        })

# ==========================
# SAVE CSV
# ==========================

df = pd.DataFrame(annotations)

csv_path = os.path.join(
    OUTPUT_DIR,
    "defect_annotations.csv"
)

df.to_csv(csv_path,index=False)

print("="*60)
print("DONE!")
print(f"Generated {len(df)} defect images")
print(csv_path)
print("="*60)