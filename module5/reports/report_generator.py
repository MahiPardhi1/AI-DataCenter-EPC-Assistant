from datetime import datetime


def generate_report(equipment_name, detections, output_path):

    with open(output_path, "w") as f:

        f.write("=" * 50 + "\n")
        f.write("AI DATA CENTER EPC ASSISTANT\n")
        f.write("Commissioning Defect Report\n")
        f.write("=" * 50 + "\n\n")

        f.write(f"Equipment : {equipment_name}\n")
        f.write(f"Date      : {datetime.now()}\n\n")

        if len(detections) == 0:

            f.write("No defects detected.\n")

        else:

            f.write("Detected Defects\n")
            f.write("-" * 30 + "\n")

            for defect, confidence in detections:

                f.write(
                    f"{defect:<20} Confidence: {confidence:.2f}\n"
                )

        f.write("\n")
        f.write("=" * 50 + "\n")
        f.write("End of Report\n")