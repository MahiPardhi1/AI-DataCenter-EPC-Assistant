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
        "https://weldpower.com/wp-content/uploads/2025/01/ee30aaf7-984e-4c5e-a2b6-e011e517884a_cdv_photo_003.jpg",
        "https://media.licdn.com/dms/image/v2/D4E12AQFjg5OIfModyQ/article-inline_image-shrink_1000_1488/article-inline_image-shrink_1000_1488/0/1683299615422?e=2147483647&v=beta&t=GR9ih1Jv5fH2cxg0ZMlucz3rxUg9kLCFE8GRezNtt1I",
        "https://insideclimatenews.org/wp-content/uploads/2025/01/GettyImages-2194970695.jpg",
        "https://www.reactpower.com/wp-content/uploads/2019/05/CAT-3456-Generator-Set-1-1-1-scalia-blog-default.jpg",
        "https://genesalenergy.com/en/wp-content/uploads/sites/5/2023/07/GE-datacenter-GEN138FI.jpg"
    ],
    "project_data/09_Equipment_Images/UPS": [
        "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS7TLCPjZhBIhvB1YpDEQLwg-B2aB5gE3sIIBBo3QkifqejcZNtq87TSbk&s=10",
        "https://i0.wp.com/www.prostarsolar.net/wp-content/uploads/2026/03/How-a-Modular-UPS-System-Ensures-Power-Reliability-in-Data-Centers.jpg?resize=1024%2C573&ssl=1",
        "https://digitalpower.huawei.com/attachments/data-center-facility/9a74151d47c04f95a9802c57331a5abc.jpeg",
        "https://d3qut6qyo6tw2j.cloudfront.net/wp-content/uploads/2014/08/09164109/UPS-in-Data-Centers.jpg",
        "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRudGjHUH6aGnALu4K3ozpXPMS8LX9AxPOol38vjtYSpaELa1K80-y2KHo&s=10"
    ],
    "project_data/09_Equipment_Images/Cooling_System": [
        "https://aligneddc.com/wp-content/uploads/2025/10/DSC00059-1024x683.jpg",
        "https://cdn.pagethink.com/cdn-cgi/image/width=3300,height=1820,fit=cover/content/uploads/insights/115025_N57_jpg201.jpg",
        "https://www.issmechanical.com/wp-content/uploads/2024/07/Chilers-system-for-data-center.jpg",
        "https://omdia.tech.informa.com/-/media/tech/omdia/marketing/pr/2022-jul/data-center-cooling-towers_shutterstock_1020042415.jpg?rev=f3699efde7d14437a651ee2477a4b9cb",
        "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRiBEwaKsM-qO68kSiZ9KGtI2EHw4I-MvfG2lAIe5pM5GlJo2rTyBkyQi4&s=10"
    ],
    "project_data/09_Equipment_Images/Battery_Storage": [
        "https://sp-ao.shortpixel.ai/client/to_auto,q_glossy,ret_img,w_1500,h_979/https://zincfive.com/wp-content/uploads/2024/08/BC-2-500-Data-Center-Clean-3-1.png",
        "https://datacenterresources.com/wp-content/uploads/2016/02/Data_Center_Battery_Replacement.jpg",
        "https://assets.serverroomenvironments.co.uk/thumbnails/facebook_open_graph_large_1324671_1581188239.jpg",
        "https://sp-ao.shortpixel.ai/client/to_auto,q_glossy,ret_img,w_2000,h_1318/https://zincfive.com/wp-content/uploads/2023/05/ZincFive-BC-2-Data-Center-06.png",
        "https://img.cablinginstall.com/files/base/ebm/cim/image/2019/04/content_dam_cim_online_articles_2019_04_hpl_application.png?auto=format&w=1000&h=562&fit=clip&dpr=2"
    ],
    "project_data/09_Equipment_Images/CRAH_Unit": [
        "https://media.tranetechnologies.com/is/image/TraneTechnologies/tc-computer-room-air-handler-crah-closed-transparent:medium-4-3",
        "https://www.kaltra.com/wp-content/uploads/2020/12/ft_crah-unit-845x521.png",
        "https://www.canatec.com.sg/wp-content/uploads/2025/06/CRAC_SMART_COOLING_2025_TOP_PIC_B.png",
        "https://dcnnmagazine.com/wp-content/uploads/2025/08/img-25.jpg",
        "https://www.daikin-ce.com/en_us/press-releases/2025/daikin-expands-data-center-cooling-portfolio/_jcr_content/root/main_container/content_container/simple_container/twocolumncontainer_1279793339/column-container-1/image_893446153.coreimg.jpeg/1744893894455/pro-crah-1200x1200-v01-2.jpeg"
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