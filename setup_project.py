import os

folders = [
    "project_data/01_Client_Documents/Technical_Specifications",
    "project_data/01_Client_Documents/Scope_of_Work",
    "project_data/01_Client_Documents/Design_Requirements",
    "project_data/02_Vendor_Documents/Quotations",
    "project_data/02_Vendor_Documents/Datasheets",
    "project_data/02_Vendor_Documents/Manuals",
    "project_data/03_Engineering_Drawings/Electrical",
    "project_data/03_Engineering_Drawings/Mechanical",
    "project_data/03_Engineering_Drawings/HVAC",
    "project_data/03_Engineering_Drawings/Floor_Plans",
    "project_data/04_RFIs_Meeting_Minutes",
    "project_data/05_Inspection_Reports",
    "project_data/06_Project_Schedule",
    "project_data/07_Supply_Chain_Data/Equipment_List",
    "project_data/07_Supply_Chain_Data/Shipment_Status",
    "project_data/07_Supply_Chain_Data/Vendor_Details",
    "project_data/08_Commissioning_Reports",
    "project_data/09_Equipment_Images/Generator",
    "project_data/09_Equipment_Images/UPS",
    "project_data/09_Equipment_Images/Cooling_System",
    "project_data/09_Equipment_Images/Battery_Storage",
    "project_data/09_Equipment_Images/CRAH_Unit",
    "project_data/09_Equipment_Images/Defect_Samples",
    "project_data/10_Sensor_Readings"
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)

print("✅ All data directories generated successfully!")