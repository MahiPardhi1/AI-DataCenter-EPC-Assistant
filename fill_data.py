import os
import random
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

PROJECT_ID = "PRJ-MUM-2026"
EQUIPMENT_IDS = ["EQ-UPS-101", "EQ-CHILL-202", "EQ-GEN-303", "EQ-BATT-404", "EQ-CRAH-505"]
VENDORS = ["VEND-DELTA", "VEND-YORK", "VEND-CATERPILLAR", "VEND-SCHNEIDER", "VEND-VERTIV"]

print("Initializing dataset generation based on target document parameters...")

def build_pdf_document(filepath, title, paragraphs, table_rows=None):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14, style="B")
    pdf.cell(0, 10, text=title, center=True)
    pdf.ln(12)
    pdf.set_font("Helvetica", size=11)
    for p in paragraphs:
        pdf.multi_cell(0, 8, text=p)
        pdf.ln(4)

    if table_rows:
        has_req_id = len(table_rows[0]) == 4
        pdf.ln(4)
        pdf.set_font("Helvetica", size=11, style="B")
        if has_req_id:
            col_widths = [30, 55, 40, 65]
            headers = ["Req ID", "Parameter", "Value", "Notes / Tolerance"]
        else:
            col_widths = [70, 45, 75]
            headers = ["Parameter", "Value", "Notes / Tolerance"]
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 9, text=h, border=1)
        pdf.ln(9)
        pdf.set_font("Helvetica", size=9 if has_req_id else 10)
        for row in table_rows:
            for w, v in zip(col_widths, row):
                pdf.cell(w, 8, text=str(v), border=1)
            pdf.ln(8)

    pdf.output(filepath)


def build_schematic_drawing(filepath, title, project_id, nodes, connections):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14, style="B")
    pdf.cell(0, 10, text=title, center=True)
    pdf.ln(6)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, text=f"Project Ref: {project_id}  |  Scale: 1:100 (illustrative, not to scale)", center=True)
    pdf.ln(14)

    box_w, box_h = 55, 24
    positions = {}
    for equipment_id, label, x, y in nodes:
        positions[equipment_id] = (x + box_w / 2, y + box_h / 2)
        pdf.set_draw_color(40, 40, 40)
        pdf.set_line_width(0.6)
        pdf.rect(x, y, box_w, box_h)
        pdf.set_xy(x, y + 4)
        pdf.set_font("Helvetica", size=9, style="B")
        pdf.cell(box_w, 6, text=label, align="C")
        pdf.set_xy(x, y + 13)
        pdf.set_font("Helvetica", size=8)
        pdf.cell(box_w, 6, text=equipment_id, align="C")

    pdf.set_draw_color(90, 90, 90)
    pdf.set_line_width(0.4)
    for from_id, to_id in connections:
        if from_id in positions and to_id in positions:
            cx1, cy1 = positions[from_id]
            cx2, cy2 = positions[to_id]
            pdf.line(cx1, cy1, cx2, cy2)

    pdf.output(filepath)


def build_scanned_pdf_document(filepath, title, paragraphs, page_w=1240, page_h=1754):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img = Image.new("RGB", (page_w, page_h), color=(250, 248, 240))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    y = 80
    draw.text((page_w / 2, y), title, font=title_font, fill=(20, 20, 20), anchor="ma")
    y += 100

    for p in paragraphs:
        words, line, lines = p.split(), "", []
        for w in words:
            test = f"{line} {w}".strip()
            if draw.textlength(test, font=body_font) > page_w - 160:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        for ln in lines:
            draw.text((80, y), ln, font=body_font, fill=(30, 30, 30))
            y += 42
        y += 30

    noise = Image.effect_noise((page_w, page_h), 8).convert("L")
    img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.03)

    tmp_png = filepath.replace(".pdf", "_scan.png")
    img.save(tmp_png)

    pdf = FPDF(unit="pt", format=(page_w, page_h))
    pdf.add_page()
    pdf.image(tmp_png, x=0, y=0, w=page_w, h=page_h)
    pdf.output(filepath)
    os.remove(tmp_png)


client_specs = [
    ("UPS_Specs.pdf", "Client Specification - Uninterruptible Power Supply", [
        f"Project: {PROJECT_ID} | Code: SPEC-ELE-001",
        "Requirement: Emergency backup topology must utilize Tier III concurrent maintainability configurations.",
        "Mandate: Static UPS modules must exhibit energy efficiency rating >= 96.5% at a 50% partial load threshold.",
        "Electrical Constants: Input operating voltage fixed at 415V, 3-Phase, 50Hz infrastructure."
    ], [
        ("", "Rated Capacity", "300 kVA / 270 kW", "Per module, N+1 config"),
        ("REQ-UPS-001", "Efficiency @ 50% Load", ">= 96.5 %", "Minimum acceptance threshold"),
        ("REQ-UPS-002", "Input Voltage", "415 V, 3-Phase", "+/- 10% tolerance"),
        ("REQ-UPS-002", "Input Frequency", "50 Hz", "+/- 2% tolerance"),
        ("", "Battery Autonomy", "10 minutes", "At full rated load"),
        ("REQ-UPS-003", "Topology", "Double Conversion, Tier III", "Concurrently maintainable"),
    ]),
    ("Chiller_Specs.pdf", "Client Specification - Mechanical Cooling Plant", [
        f"Project: {PROJECT_ID} | Code: SPEC-MECH-002",
        "Requirement: Chilled water distribution systems must maintain continuous N+1 redundancy.",
        "Mandate: Maximum operational power draw profile cannot exceed 45kW per compressor fan unit.",
        "Fluid Dynamics: Chilled water delivery set point configured precisely to 7.2 degrees Celsius."
    ], [
        ("", "Cooling Capacity", "1200 TR", "N+1 redundant array"),
        ("REQ-CHILL-001", "Max Compressor Draw", "45 kW", "Per fan unit, hard ceiling"),
        ("REQ-CHILL-002", "Chilled Water Supply Temp", "7.2 C", "+/- 0.5 C"),
        ("", "Chilled Water Return Temp", "12.5 C", "Design delta-T = 5.3 C"),
        ("REQ-CHILL-003", "Redundancy Level", "N+1", "Mandatory"),
    ]),
    ("Generator_Specs.pdf", "Client Specification - Emergency Backup Generation", [
        f"Project: {PROJECT_ID} | Code: SPEC-ELE-003",
        "Requirement: Standby diesel generators must kick in and assume critical facility load inside a maximum of 10 seconds.",
        "Mandate: Engine speed must dynamically govern at 1500 RPM to sustain steady 50Hz frequency output.",
        "Emissions: Exhaust treatment configurations must pass regional environmental safety metrics."
    ], [
        ("", "Rated Output", "3 MW", "Standby rating"),
        ("REQ-GEN-001", "Max Transfer Time", "10 seconds", "ATS engagement ceiling"),
        ("REQ-GEN-002", "Governed Speed", "1500 RPM", "For 50 Hz output"),
        ("", "Rated Frequency", "50 Hz", "+/- 1% steady state"),
        ("REQ-GEN-003", "Emissions Compliance", "CPCB-IV+", "Regional standard"),
    ]),
    ("Battery_Storage_Specs.pdf", "Client Specification - Direct Current Storage Architecture", [
        f"Project: {PROJECT_ID} | Code: SPEC-ELE-004",
        "Requirement: Valve-Regulated Lead-Acid (VRLA) cell layouts must fulfill 15 minutes of uninterrupted autonomy.",
        "Mandate: Individual battery modules must support stable operating ambient thresholds of 22 degrees Celsius."
    ], [
        ("REQ-BATT-001", "Autonomy", "15 minutes", "At full rated UPS load"),
        ("", "Cell Chemistry", "VRLA", "Valve-Regulated Lead-Acid"),
        ("REQ-BATT-002", "Ambient Operating Temp", "22 C", "+/- 2 C for rated life"),
        ("", "Design Life", "10 years", "At rated ambient temp"),
    ]),
    ("HVAC_CRAH_Specs.pdf", "Client Specification - Computer Room Air Handler System", [
        f"Project: {PROJECT_ID} | Code: SPEC-MECH-005",
        "Requirement: Precision CRAH frameworks must enforce downflow variable speed fan controls.",
        "Mandate: Moisture profiles must stay within 40% to 55% relative humidity to meet design baselines."
    ], [
        ("", "Airflow Configuration", "Downflow, VFD Fan", "Variable speed"),
        ("REQ-CRAH-001", "Relative Humidity Range", "40% - 55%", "Design baseline"),
        ("REQ-CRAH-002", "Supply Air Temp", "18 C", "Target setpoint"),
        ("", "Redundancy Level", "N+1", "Per cooling zone"),
    ])
]
for filename, title, text, table in client_specs:
    build_pdf_document(f"project_data/01_Client_Documents/Technical_Specifications/{filename}", title, text, table)

build_pdf_document(
    "project_data/01_Client_Documents/Scope_of_Work/SOW_Electrical_Mechanical_Package.pdf",
    "Scope of Work - Electrical & Mechanical Package",
    [
        f"Project: {PROJECT_ID} | Code: SOW-EM-001",
        "Package Boundary: Supply, installation, testing, and commissioning of UPS, chiller plant, standby generator, battery storage, and CRAH systems as detailed in the referenced technical specifications.",
        "Exclusions: Civil foundation works, structural steel fabrication, and fire suppression systems are outside this package and covered under separate SOW-CIVIL-001 and SOW-FIRE-001 documents.",
        "Handover Requirement: All Level 5 Integrated Systems Testing (IST) must be completed and signed off prior to substantial completion certification."
    ],
    [
        ("Package Value", "Confidential", "Refer commercial contract"),
        ("Contract Duration", "18 months", "From notice to proceed"),
        ("Defects Liability Period", "12 months", "Post handover"),
        ("Responsibility Split", "EPC Contractor", "Design, supply, install, commission"),
    ]
)

build_pdf_document(
    "project_data/01_Client_Documents/Design_Requirements/Design_Basis_Report.pdf",
    "Design Basis Report - Critical Infrastructure Systems",
    [
        f"Project: {PROJECT_ID} | Code: DBR-001",
        "Design Philosophy: Facility is designed to Uptime Institute Tier III equivalent standards with concurrently maintainable electrical and mechanical distribution paths.",
        "Redundancy Strategy: N+1 redundancy is mandated at the individual equipment level across UPS, chiller, and CRAH systems; 2N is not required for this phase.",
        "Design Margin: All critical electrical and mechanical systems must be sized with a minimum 20% headroom above calculated peak IT load to accommodate future scaling."
    ],
    [
        ("Target Tier Level", "Tier III Equivalent", "Uptime Institute framework"),
        ("Redundancy Level", "N+1", "Equipment level, this phase"),
        ("Design Margin", "20%", "Above calculated peak IT load"),
        ("Design Life", "20 years", "Core electrical/mechanical infra"),
    ]
)

build_scanned_pdf_document(
    "project_data/02_Vendor_Documents/Datasheets/Delta_UPS_Submittal.pdf",
    "Vendor Equipment Submittal - 300kVA System",
    [
        f"Supplier: {VENDORS[0]} | Target Equipment: {EQUIPMENT_IDS[0]}",
        "This submittal addresses requirements REQ-UPS-001 and REQ-UPS-002.",
        "Performance Parameters: Nominal infrastructure operational matching at 415V, 50Hz, 3-Phase supply.",
        "Factory acceptance test results log measured operating efficiency of 95.4 percent at the 50 percent partial load test point, recorded under eco-mode firmware settings.",
        "Note: Eco-mode optimization profiles are enabled by default in the standard factory configuration and can be adjusted on client request."
    ]
)

build_scanned_pdf_document(
    "project_data/02_Vendor_Documents/Datasheets/York_Chiller_Submittal.pdf",
    "Vendor Equipment Submittal - Centrifugal Chiller Plant",
    [
        f"Supplier: {VENDORS[1]} | Target Equipment: {EQUIPMENT_IDS[1]}",
        "This submittal addresses requirements REQ-CHILL-001, REQ-CHILL-002 and REQ-CHILL-003.",
        "Performance Parameters: Chilled water temperature output comfortably meets the 7.2C design target under full load.",
        "Compressor fan load logs from bench testing show a peak power draw of 52 kW recorded during sustained heavy-load operation.",
        "Redundancy Note: Standard factory configuration ships as a single N unit. N+1 concurrent redundancy is available as a field-installed upgrade module at additional cost and lead time, and is not included in the base offer.",
        "Note: Structural anchoring hardware is included in the standard shipment manifest."
    ]
)

vendor_docs = [
    ("Cat_Generator_Manual.pdf", "Manuals", "Vendor Product Manual - 3MW Standby Generator Set", [
        f"Supplier: {VENDORS[2]} | Target Equipment: {EQUIPMENT_IDS[2]}",
        "This manual addresses requirements REQ-GEN-001 and REQ-GEN-002.",
        "Performance Parameters: Automatic Transfer Switch (ATS) command loop initiates complete crank within 8.5 seconds.",
        "Engine Constants: Synchronous alternator arrays hold continuous load profile at 1500 RPM with 50Hz stability."
    ], [
        ("REQ-GEN-001", "Rated Output", "3 MW", "Matches client mandate"),
        ("REQ-GEN-001", "ATS Transfer Time", "8.5 seconds", "Within 10s client ceiling"),
        ("REQ-GEN-002", "Governed Speed", "1500 RPM", "Matches client mandate"),
        ("REQ-GEN-002", "Rated Frequency", "50 Hz", "+/- 0.5% steady state"),
    ]),
    ("Vertiv_CRAH_Manual.pdf", "Manuals", "Vendor Maintenance Manual - Downflow Thermal Units", [
        f"Supplier: {VENDORS[4]} | Target Equipment: {EQUIPMENT_IDS[4]}",
        "This manual addresses requirement REQ-CRAH-001.",
        "Operations Directive: Electronically commutated (EC) fans modulate response speeds via centralized BMS networks.",
        "Humidity Range: Handles internal moisture tracking boundaries from 35% to 60% efficiently."
    ], [
        ("", "Fan Type", "EC (Electronically Commutated)", "BMS-integrated"),
        ("REQ-CRAH-001", "Humidity Range", "35% - 60%", "Wider than 40-55% client spec"),
        ("", "Airflow Configuration", "Downflow", "Matches spec"),
        ("", "Maintenance Interval", "6 months", "Filter + fan bearing check"),
    ]),
    ("Schneider_Battery_Quotation.pdf", "Quotations", "Vendor Commercial Quotation - VRLA Battery Array", [
        f"Supplier: {VENDORS[3]} | Target Equipment: {EQUIPMENT_IDS[3]}",
        "This quotation addresses requirements REQ-BATT-001 and REQ-BATT-002.",
        "Financial Line Items: Emergency cell deployment bundle delivery matches project requirements.",
        "Autonomy Benchmarks: Confirmed standalone reserve coverage holds for 16.5 minutes at nominal discharge rates.",
        "Environmental Rating: Cells are manufacturer-rated for a stable operating range of 0C to 28C ambient, wider than the standard commercial VRLA range."
    ], [
        ("REQ-BATT-001", "Autonomy Delivered", "16.5 minutes", "Exceeds 15 min mandate"),
        ("", "Cell Chemistry", "VRLA", "Matches spec"),
        ("REQ-BATT-002", "Ambient Operating Rating", "0 C to 28 C", "Wider than client's 22C +/- 2C design point"),
        ("", "Unit Price (per cell)", "INR 18,400", "Quoted, ex-works"),
        ("", "Lead Time", "6 weeks", "Ex-factory Hyderabad"),
    ]),
    ("Delta_UPS_Commercial_Quotation.pdf", "Quotations", "Vendor Commercial Quotation - 300kVA UPS System", [
        f"Supplier: {VENDORS[0]} | Target Equipment: {EQUIPMENT_IDS[0]}",
        "Commercial Offer: Pricing below is valid against the technical submittal on file for this same equipment package.",
        "Payment Terms: 30% advance on order, 60% on dispatch, 10% on commissioning sign-off."
    ], [
        ("Unit Price", "INR 42,50,000", "Per 300kVA module, ex-works"),
        ("Quote Validity", "60 days", "From date of issue"),
        ("Warranty", "24 months", "Parts and labour"),
        ("Lead Time", "10 weeks", "Ex-factory"),
    ]),
]
for filename, subfolder, title, text, table in vendor_docs:
    build_pdf_document(f"project_data/02_Vendor_Documents/{subfolder}/{filename}", title, text, table)

vendor_equipment_map = {
    "Vendor_ID": VENDORS,
    "Equipment_ID": EQUIPMENT_IDS,
    "Contract_Ref": [f"CTR-{PROJECT_ID.split('-')[1]}-{100+i}" for i in range(len(VENDORS))],
    "Datasheet_Doc": [
        "Datasheets/Delta_UPS_Submittal.pdf",
        "Datasheets/York_Chiller_Submittal.pdf",
        "Manuals/Cat_Generator_Manual.pdf",
        "",
        "Manuals/Vertiv_CRAH_Manual.pdf",
    ],
    "Quotation_Doc": [
        "Quotations/Delta_UPS_Commercial_Quotation.pdf",
        "",
        "",
        "Quotations/Schneider_Battery_Quotation.pdf",
        "",
    ]
}
os.makedirs("project_data/02_Vendor_Documents", exist_ok=True)
pd.DataFrame(vendor_equipment_map).to_csv("project_data/02_Vendor_Documents/vendor_equipment_map.csv", index=False)

build_schematic_drawing(
    "project_data/03_Engineering_Drawings/Electrical/Electrical_SLD_Rev2.pdf",
    "Electrical Single Line Diagram (SLD) - Rev 2",
    PROJECT_ID,
    nodes=[
        ("EQ-UPS-101", "UPS Module", 20, 40),
        ("EQ-BATT-404", "Battery Bank", 20, 100),
        ("EQ-GEN-303", "Standby Generator", 110, 70),
        ("EQ-CRAH-505", "CRAH Panel Feed", 20, 160),
    ],
    connections=[("EQ-BATT-404", "EQ-UPS-101"), ("EQ-UPS-101", "EQ-GEN-303"), ("EQ-UPS-101", "EQ-CRAH-505")]
)

build_schematic_drawing(
    "project_data/03_Engineering_Drawings/Mechanical/Mechanical_Piping_Layout.pdf",
    "Mechanical Chilled Water Piping Layout",
    PROJECT_ID,
    nodes=[
        ("EQ-CHILL-202", "Centrifugal Chiller", 20, 40),
        ("EQ-CRAH-505", "CRAH Unit", 110, 40),
        ("EQ-GEN-303", "Standby Genset (Ref)", 65, 110),
    ],
    connections=[("EQ-CHILL-202", "EQ-CRAH-505")]
)

build_schematic_drawing(
    "project_data/03_Engineering_Drawings/HVAC/HVAC_Airflow_FloorPlan.pdf",
    "HVAC Airflow Floor Plan",
    PROJECT_ID,
    nodes=[
        ("EQ-CRAH-505", "CRAH Downflow Unit", 20, 40),
        ("EQ-CHILL-202", "Chiller Plant Feed", 110, 40),
    ],
    connections=[("EQ-CHILL-202", "EQ-CRAH-505")]
)

build_schematic_drawing(
    "project_data/03_Engineering_Drawings/Floor_Plans/Equipment_Room_Floor_Plan.pdf",
    "Data Hall & Equipment Room Floor Plan - Level 1",
    PROJECT_ID,
    nodes=[
        ("EQ-UPS-101", "Electrical Room - UPS", 20, 40),
        ("EQ-BATT-404", "Electrical Room - Battery", 110, 40),
        ("EQ-CHILL-202", "Mechanical Yard - Chiller", 20, 110),
        ("EQ-CRAH-505", "Data Hall - CRAH", 110, 110),
        ("EQ-GEN-303", "Generator Yard", 65, 180),
    ],
    connections=[
        ("EQ-UPS-101", "EQ-BATT-404"),
        ("EQ-CHILL-202", "EQ-CRAH-505"),
        ("EQ-UPS-101", "EQ-CHILL-202"),
        ("EQ-GEN-303", "EQ-UPS-101"),
    ]
)

rfi_logs = [
    ("RFI_024_Clash.pdf", "RFI-024: Structural Coordination Resolution", [
        "Status: CLOSED | Action Domain: ACT-E10",
        f"Description: Physical routing overlap discovered between overhead chilled lines and the main electrical busway near {EQUIPMENT_IDS[0]}.",
        "Resolution Directive: Structural engineering teams approved lowering water line hangers by 300mm. Electrical busways maintain original elevations."
    ]),
    ("Meeting_Minutes_Week14.pdf", "Minutes of Weekly Construction Coordination Meeting", [
        "Date: Recent Work Week | Chair: Project Controls Lead",
        f"Item 3.1: Logistics teams report customs hold anomalies affecting critical components under tracking ID {EQUIPMENT_IDS[0]}.",
        f"Item 5.4: General contractor confirms structural foundations for the main power generator block ({EQUIPMENT_IDS[2]}) are fully set."
    ])
]
rfi_filler = [
    ("RFI_025_General.pdf", "Project Coordination RFI Log #025", "VERIFIED / RESOLVED",
     "Cable tray routing clearances updated to match site structural framing parameters near the electrical room."),
    ("RFI_026_General.pdf", "Project Coordination RFI Log #026", "VERIFIED / RESOLVED",
     "Fire-rated penetration seals confirmed compliant at all mechanical room wall crossings."),
    ("RFI_027_General.pdf", "Project Coordination RFI Log #027", "OPEN - PENDING VENDOR RESPONSE",
     "Clarification requested on CRAH condensate drain routing conflict with the raised floor support grid; awaiting Vertiv confirmation."),
]
for filename, title, status, detail in rfi_filler:
    rfi_logs.append((filename, title, [
        f"Project Context Reference: {PROJECT_ID}",
        f"Status: {status}",
        f"Clarification Details: {detail}"
    ]))
for filename, title, text in rfi_logs:
    build_pdf_document(f"project_data/04_RFIs_Meeting_Minutes/{filename}", title, text)

inspection_reports = [
    (EQUIPMENT_IDS[0], "R. Iyer", "2026-03-14", "ACCEPTED", [
        "Anchor bolt torque verified at 420 Nm across all 8 mounting points, within the 400-450 Nm spec band.",
        "Busbar clearance to adjacent structural steel measured at 210mm, exceeding the 150mm minimum.",
        "No corrosion, physical damage, or foundation cracking observed on the plinth."
    ]),
    (EQUIPMENT_IDS[1], "R. Iyer", "2026-03-18", "ACCEPTED WITH REMARKS", [
        "Vibration isolation pads correctly seated on all 4 compressor mounting legs.",
        "Condensate drain slope measured at 1.2%, marginally below the 1.5% design recommendation -- flagged for re-grading before final tie-in.",
        "Refrigerant line insulation intact, no visible gaps."
    ]),
    (EQUIPMENT_IDS[2], "S. Menon", "2026-03-21", "ACCEPTED", [
        "Foundation block cured for 21 days prior to inspection, exceeding the 14-day minimum cure period.",
        "Anchor bolt torque verified at 610 Nm across all 12 mounting points, within spec.",
        "Exhaust flex connector alignment checked and confirmed free of pre-installation stress."
    ]),
    (EQUIPMENT_IDS[3], "S. Menon", "2026-03-22", "ACCEPTED", [
        "Battery rack seismic bracing torque-checked on all cross-members, within spec.",
        "Ambient room temperature at time of inspection: 21.8C, within the 22C +/- 2C design band.",
        "No electrolyte staining or terminal corrosion observed on any cell."
    ]),
    (EQUIPMENT_IDS[4], "R. Iyer", "2026-03-25", "ACCEPTED WITH REMARKS", [
        "Downflow unit levelness confirmed within 2mm across the base frame.",
        "Condensate pan drain line tested and confirmed clear; minor debris noted and removed.",
        "Duct collar seal at the supply plenum interface flagged for re-caulking before final commissioning."
    ]),
]
for eq, inspector, date, status, findings in inspection_reports:
    build_pdf_document(
        f"project_data/05_Inspection_Reports/QA_Field_Report_{eq}.pdf",
        f"Quality Inspection Field Report - {eq}",
        [
            f"Target Component Tracked: {eq} | Inspector: {inspector} | Date: {date}",
            "Inspection Class: Structural Safety & Pre-Installation Sign-off.",
            f"Status: {status}",
        ] + findings
    )

commissioning_reports = [
    (EQUIPMENT_IDS[0], "PASS", "Full IST load bank test completed across 0-100% load steps. Voltage and frequency held within tolerance for the complete test duration. No anomalies logged."),
    (EQUIPMENT_IDS[1], "PASS", "Chilled water supply temperature held at 7.1-7.3C across a 4-hour sustained run. Compressor draw stayed within the 45kW ceiling throughout."),
    (EQUIPMENT_IDS[2], "PROVISIONAL PASS - EXTENDED MONITORING REQUIRED",
     "Initial steady-state load evaluation (first ~35 minutes) showed voltage, frequency, and core temperature within standard performance boundaries. "
     "However, the test was run on a compressed schedule and did not complete a full sustained-load endurance cycle. "
     "Continuous BMS/SCADA telemetry monitoring was left active post-test as a condition of this provisional sign-off, pending a full extended load test "
     "to be scheduled before final handover. Any deviation flagged by continuous monitoring supersedes this provisional result."),
    (EQUIPMENT_IDS[3], "PASS", "Discharge test completed at full rated load. Autonomy measured at 16.2 minutes, exceeding the 15-minute design mandate."),
    (EQUIPMENT_IDS[4], "PASS", "Airflow and humidity control verified across a simulated full data hall load profile. Fan modulation response confirmed within BMS command tolerances."),
]
for eq, status, summary in commissioning_reports:
    build_pdf_document(
        f"project_data/08_Commissioning_Reports/Cx_Level5_TestLog_{eq}.pdf",
        f"Commissioning Level 5 Functional Test Report: {eq}",
        [
            f"System Asset Identifier: {eq}",
            "Execution Stage: Level 5 Integrated Systems Testing (IST).",
            "Acceptance Matrix Criteria: Verification of localized control interfaces, failsafe loops, and automatic failovers.",
            f"Status: {status}",
            f"Status Summary: {summary}"
        ]
    )

schedule_1 = {
    "Activity_ID": ["ACT-E10", "ACT-M20", "ACT-C30", "ACT-B40", "ACT-H50"],
    "Equipment_ID": EQUIPMENT_IDS,
    "Activity_Name": ["Electrical Hookup & UPS Mount", "Chilled Water Piping Connection", "Generator Load Testing", "Battery Bank Grid Setup", "CRAH Thermal Balancing"],
    "Planned_Duration_Days": [6, 10, 5, 4, 8],
    "Total_Float_Days": [3, 14, 0, 7, 12]
}
os.makedirs("project_data/06_Project_Schedule", exist_ok=True)
pd.DataFrame(schedule_1).to_csv("project_data/06_Project_Schedule/master_baseline_schedule.csv", index=False)
pd.DataFrame(schedule_1).to_csv("project_data/06_Project_Schedule/active_working_schedule.csv", index=False)

supply_1 = {
    "Equipment_ID": EQUIPMENT_IDS,
    "Project_ID": [PROJECT_ID] * 5,
    "Equipment_Name": ["300kVA Scalable UPS", "1200TR Centrifugal Chiller", "3MW Standby Generator", "VRLA Battery Cells", "Downflow CRAH Module"],
    "Vendor_ID": VENDORS,
    "Current_Transit_Status": ["Stuck at Port (Customs Hold)", "In Transit", "On-Site / Delivered", "In Transit", "Factory Floor Planning"],
    "Days_Delayed": [14, 0, 0, 2, 0]
}
os.makedirs("project_data/07_Supply_Chain_Data/Equipment_List", exist_ok=True)
os.makedirs("project_data/07_Supply_Chain_Data/Vendor_Details", exist_ok=True)
os.makedirs("project_data/07_Supply_Chain_Data/Shipment_Status", exist_ok=True)
pd.DataFrame(supply_1).to_csv("project_data/07_Supply_Chain_Data/Equipment_List/equipment_list.csv", index=False)

supply_2 = {"Vendor_ID": VENDORS, "Contact_Entity": ["Delta Logistics", "York India", "Cat Systems", "Schneider Supply", "Vertiv Delivery"], "Risk_Tier": ["Medium", "Low", "Low", "Low", "High"]}
pd.DataFrame(supply_2).to_csv("project_data/07_Supply_Chain_Data/Vendor_Details/vendor_master_profiles.csv", index=False)

supply_3 = {"Equipment_ID": EQUIPMENT_IDS, "Origin_Hub": ["Bangalore", "Chennai", "Mumbai Factory", "Hyderabad", "Pune"], "Est_Arrival_Date": ["2026-08-12", "2026-08-19", "2026-07-25", "2026-08-01", "2026-09-02"]}
pd.DataFrame(supply_3).to_csv("project_data/07_Supply_Chain_Data/Shipment_Status/shipment_logistics_tracking.csv", index=False)

os.makedirs("project_data/09_Compliance_Knowledge_Base", exist_ok=True)

_SEVERITY = {"High": 3, "Medium": 2, "Low": 1}

requirements_register_raw = [
    ("REQ-UPS-001", "UPS",     "EQ-UPS-101",  "Efficiency at 50% partial load",           ">= 96.5 %",                "High",   "High",   "Medium"),
    ("REQ-UPS-002", "UPS",     "EQ-UPS-101",  "Input voltage / frequency",                "415V 3-Phase 50Hz",        "Medium", "Medium", "Low"),
    ("REQ-UPS-003", "UPS",     "EQ-UPS-101",  "Topology (Tier III, concurrently maintainable)", "Double Conversion, Tier III", "High", "High", "Low"),
    ("REQ-CHILL-001", "Chiller", "EQ-CHILL-202", "Max compressor draw per fan unit",       "<= 45 kW",                 "High",   "Medium", "Medium"),
    ("REQ-CHILL-002", "Chiller", "EQ-CHILL-202", "Chilled water supply temperature",       "7.2 C +/- 0.5 C",          "Medium", "Medium", "Low"),
    ("REQ-CHILL-003", "Chiller", "EQ-CHILL-202", "Redundancy level",                       "N+1",                      "High",   "High",   "Medium"),
    ("REQ-GEN-001", "Generator", "EQ-GEN-303", "Max ATS transfer time",                    "<= 10 seconds",            "High",   "High",   "Low"),
    ("REQ-GEN-002", "Generator", "EQ-GEN-303", "Governed speed / frequency",               "1500 RPM / 50Hz",          "Medium", "Medium", "Low"),
    ("REQ-GEN-003", "Generator", "EQ-GEN-303", "Emissions compliance",                     "CPCB-IV+",                 "High",   "Medium", "Medium"),
    ("REQ-BATT-001", "Battery", "EQ-BATT-404", "Autonomy at full rated load",              ">= 15 minutes",            "High",   "High",   "Low"),
    ("REQ-BATT-002", "Battery", "EQ-BATT-404", "Ambient operating temperature",            "22 C +/- 2 C",             "Medium", "Medium", "Medium"),
    ("REQ-CRAH-001", "CRAH",   "EQ-CRAH-505", "Relative humidity range",                  "40% - 55%",                "Medium", "Low",    "Low"),
    ("REQ-CRAH-002", "CRAH",   "EQ-CRAH-505", "Supply air temperature setpoint",          "18 C",                     "Medium", "Medium", "Medium"),
]

requirements_register = []
for req_id, category, eq_id, req_text, client_value, criticality, impact, probability in requirements_register_raw:
    risk_score = _SEVERITY[criticality] * _SEVERITY[impact] * _SEVERITY[probability]
    requirements_register.append({
        "Requirement_ID": req_id,
        "Category": category,
        "Equipment_ID": eq_id,
        "Requirement_Text": req_text,
        "Client_Value": client_value,
        "Criticality": criticality,
        "Impact": impact,
        "Probability": probability,
        "Risk_Score": risk_score,
    })
pd.DataFrame(requirements_register).to_csv(
    "project_data/09_Compliance_Knowledge_Base/requirements_register.csv", index=False
)

remediation_knowledge_base = [
    ("REQ-UPS-001", "Non-Compliant", "Measured efficiency below client mandate.",
     "Request a higher-efficiency UPS model, or ask the vendor to disable the eco-mode firmware profile and re-submit an FAT report at standard operating mode."),
    ("REQ-UPS-003", "Missing Information", "Submittal does not confirm Tier III / concurrent maintainability.",
     "Request written confirmation of Tier III concurrently maintainable topology, or a third-party Tier certification letter, before technical approval."),
    ("REQ-CHILL-001", "Non-Compliant", "Compressor draw exceeds the client ceiling.",
     "Specify a lower-power compressor variant, or request a derated fan configuration and re-test."),
    ("REQ-CHILL-003", "Partial Compliance", "Base offer ships as N redundancy; N+1 is a chargeable upgrade.",
     "Negotiate inclusion of the N+1 upgrade module into the base scope, or raise a commercial variation order before contract award."),
    ("REQ-GEN-003", "Missing Information", "Vendor manual does not address emissions compliance.",
     "Request a CPCB-IV+ emissions test certificate from the vendor prior to technical sign-off."),
    ("REQ-BATT-002", "Non-Compliant", "Vendor's rated ambient range conflicts with the client's tighter design point.",
     "Re-verify battery room HVAC design against the vendor's actual rated range, or request a battery model with a tolerance band matching 22C +/- 2C."),
    ("REQ-CRAH-002", "Missing Information", "Vendor manual is silent on supply air temperature capability.",
     "Request written confirmation of achievable supply air temperature setpoint from the vendor before technical approval."),
]
pd.DataFrame(remediation_knowledge_base, columns=[
    "Requirement_ID", "Failure_Mode", "Observed_Issue", "Suggested_Action"
]).to_csv("project_data/09_Compliance_Knowledge_Base/remediation_knowledge_base.csv", index=False)

compliance_ground_truth = [
    ("REQ-UPS-001", "EQ-UPS-101", "VEND-DELTA", "Non-Compliant", ">= 96.5 %", "95.4 %",
     "Measured efficiency below client mandate; eco-mode firmware likely contributor."),
    ("REQ-UPS-002", "EQ-UPS-101", "VEND-DELTA", "Compliant", "415V 3-Phase 50Hz", "415V 50Hz 3-Phase",
     "Matches client input power spec."),
    ("REQ-UPS-003", "EQ-UPS-101", "VEND-DELTA", "Missing Information", "Tier III concurrently maintainable", "Not stated in submittal",
     "Vendor submittal does not confirm topology / Tier III compliance."),
    ("REQ-CHILL-001", "EQ-CHILL-202", "VEND-YORK", "Non-Compliant", "<= 45 kW", "52 kW",
     "Bench test draw exceeds client ceiling by 7 kW."),
    ("REQ-CHILL-002", "EQ-CHILL-202", "VEND-YORK", "Compliant", "7.2 C", "7.2 C",
     "Meets design target under full load."),
    ("REQ-CHILL-003", "EQ-CHILL-202", "VEND-YORK", "Partial Compliance", "N+1", "N (upgrade available)",
     "Standard factory config ships as N; N+1 only available as a chargeable field upgrade."),
    ("REQ-GEN-001", "EQ-GEN-303", "VEND-CATERPILLAR", "Compliant", "<= 10 seconds", "8.5 seconds",
     "Within client ceiling."),
    ("REQ-GEN-002", "EQ-GEN-303", "VEND-CATERPILLAR", "Compliant", "1500 RPM / 50Hz", "1500 RPM / 50Hz",
     "Matches client mandate."),
    ("REQ-GEN-003", "EQ-GEN-303", "VEND-CATERPILLAR", "Missing Information", "CPCB-IV+", "Not stated in manual",
     "Vendor manual does not address emissions compliance."),
    ("REQ-BATT-001", "EQ-BATT-404", "VEND-SCHNEIDER", "Compliant", ">= 15 minutes", "16.5 minutes",
     "Exceeds mandate."),
    ("REQ-BATT-002", "EQ-BATT-404", "VEND-SCHNEIDER", "Non-Compliant", "22 C +/- 2 C", "0 C to 28 C rated range",
     "Vendor's rated range extends beyond and conflicts with the tighter client design point."),
    ("REQ-CRAH-001", "EQ-CRAH-505", "VEND-VERTIV", "Compliant", "40% - 55%", "35% - 60%",
     "Vendor range is a superset of the client spec."),
    ("REQ-CRAH-002", "EQ-CRAH-505", "VEND-VERTIV", "Missing Information", "18 C", "Not stated in manual",
     "Vendor manual is silent on supply air temperature capability."),
]
pd.DataFrame(compliance_ground_truth, columns=[
    "Requirement_ID", "Equipment_ID", "Vendor_ID", "Compliance_Label",
    "Client_Value", "Vendor_Value", "Rationale"
]).to_csv("project_data/09_Compliance_Knowledge_Base/compliance_ground_truth.csv", index=False)

os.makedirs("project_data/10_Sensor_Readings", exist_ok=True)
base_time = datetime.now()


def generate_stream(equipment_id, total_records=30, drift_start=None, seed=None):
    rng = random.Random(seed)
    rows = []
    for i in range(total_records):
        if drift_start is None:
            drift_frac = 0.0
        else:
            drift_frac = max(0.0, min(1.0, (i - drift_start) / max(1, (total_records - drift_start))))

        voltage = 415 - drift_frac * 35 + rng.uniform(-3, 3)
        frequency = 50.0 - drift_frac * 4.5 + rng.uniform(-0.2, 0.25)
        temperature = 80 + drift_frac * 30 + rng.uniform(-2, 2)

        if drift_frac >= 0.6:
            status = "CRITICAL_TRANSIENT_FREQUENCY_DROP"
        elif drift_frac >= 0.25:
            status = "WARNING_TREND_DEVIATION"
        else:
            status = "NORMAL"

        rows.append({
            "Record_Index": i + 1,
            "Timestamp": (base_time + timedelta(seconds=i * 5)).strftime("%Y-%m-%d %H:%M:%S"),
            "Equipment_ID": equipment_id,
            "Voltage_L1_V": round(voltage, 2),
            "Frequency_Hz": round(frequency, 2),
            "Core_Temperature_C": round(temperature, 2),
            "BMS_Alert_Status": status
        })
    return rows


generator_rows = generate_stream("EQ-GEN-303", total_records=30, drift_start=21, seed=42)
ups_rows = generate_stream("EQ-UPS-101", total_records=30, drift_start=None, seed=7)

pd.DataFrame(generator_rows).to_csv("project_data/10_Sensor_Readings/generator_load_test_telemetry.csv", index=False)
pd.DataFrame(ups_rows).to_csv("project_data/10_Sensor_Readings/ups_healthy_baseline_telemetry.csv", index=False)

print("Complete interconnected dataset constructed successfully according to project guidelines!")
print("Client+Vendor+Drawing+RFI+Inspection+Commissioning PDFs, 9 Relational Tables/CSVs, 60 Time-Series Records.")
print("09_Compliance_Knowledge_Base added: requirements_register.csv, remediation_knowledge_base.csv, compliance_ground_truth.csv")