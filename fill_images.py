import os
import requests

# Target directories from your dataset summary file
categories = {
    "project_data/09_Equipment_Images/Generator": [
        "https://images.unsplash.com/photo-1622126978371-2911f93618bf?auto=format&fit=crop&w=600&q=80", # Industrial generator
        "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80", # Engine block
        "https://images.unsplash.com/photo-1605810230434-7631ac76ec81?auto=format&fit=crop&w=600&q=80", # Factory turbine
        "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=600&q=80", # Heavy machinery
        "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=600&q=80"  # Diesel power set
    ],
    "project_data/09_Equipment_Images/UPS": [
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=600&q=80", # Server battery racks
        "https://images.unsplash.com/photo-1563770660941-20978e870e26?auto=format&fit=crop&w=600&q=80", # Data center power rows
        "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=600&q=80", # Network infrastructure power
        "https://images.unsplash.com/photo-1600132806370-bf17e65e942f?auto=format&fit=crop&w=600&q=80", # Industrial lithium cabinets
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=80"  # Microcontroller power arrays
    ],
    "project_data/09_Equipment_Images/Cooling_System": [
        "https://images.unsplash.com/photo-1585338107529-13afc5f02586?auto=format&fit=crop&w=600&q=80", # Industrial HVAC infrastructure
        "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=600&q=80", # Large cooling ventilation
        "https://images.unsplash.com/photo-1527689368864-3a821dbccc34?auto=format&fit=crop&w=600&q=80", # Plant room pipelines
        "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=600&q=80", # Pressure valves
        "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?auto=format&fit=crop&w=600&q=80"  # Complex chilling tubes
    ],
    "project_data/09_Equipment_Images/Transformer": [
        "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?auto=format&fit=crop&w=600&q=80", # High voltage electrical grid
        "https://images.unsplash.com/photo-1623227866282-9d5e29116554?auto=format&fit=crop&w=600&q=80", # Substation transformer coils
        "https://images.unsplash.com/photo-1509395062183-67c5ad6faff9?auto=format&fit=crop&w=600&q=80", # Utility power station
        "https://images.unsplash.com/photo-1569003339405-ea396a5a8a90?auto=format&fit=crop&w=600&q=80", # Electrical lines entering unit
        "https://images.unsplash.com/photo-1548345680-f5475ea5df84?auto=format&fit=crop&w=600&q=80"  # High-output grid box
    ],
    "project_data/09_Equipment_Images/Electrical_Panel": [
        "https://images.unsplash.com/photo-1621905252507-b354bc25edac?auto=format&fit=crop&w=600&q=80", # Open circuit breaker assembly
        "https://images.unsplash.com/photo-1599837565318-67429bde7162?auto=format&fit=crop&w=600&q=80", # Industrial control wiring panels
        "https://images.unsplash.com/photo-1581092918056-0c4c3dad3785?auto=format&fit=crop&w=600&q=80", # Electronic relays
        "https://images.unsplash.com/photo-1617791160505-6f006e121980?auto=format&fit=crop&w=600&q=80", # Server infrastructure distribution
        "https://images.unsplash.com/photo-1498084393753-b411b2d26b34?auto=format&fit=crop&w=600&q=80"  # Complex fuse mapping matrix
    ]
}

print("⏳ Fetching real high-quality infrastructure images from the repository...")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

for folder, urls in categories.items():
    os.makedirs(folder, exist_ok=True)
    folder_name = folder.split("/")[-1]
    
    for index, url in enumerate(urls):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                file_name = f"{folder}/{folder_name.lower()}_sample_{index + 1}.jpg"
                with open(file_name, "wb") as f:
                    f.write(response.content)
                print(f"✅ Downloaded: {file_name}")
            else:
                print(f"❌ HTTP Error {response.status_code} for {folder_name} Sample {index + 1}")
        except Exception as e:
            print(f"❌ Network issue downloading item {index + 1} for {folder_name}: {e}")

print("🖼️ Image sync complete! Expand your '09_Equipment_Images' subfolders to review the real photo files.")