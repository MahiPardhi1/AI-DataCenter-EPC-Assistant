import pandas as pd

def analyze_sensor_data(csv_file):

    df = pd.read_csv(csv_file)

    latest = df.iloc[-1]

    report = {}

    report["Voltage"] = latest["Voltage"]
    report["Current"] = latest["Current"]
    report["Temperature"] = latest["Temperature"]

    report["Voltage_Status"] = (
        "Normal"
        if 220 <= latest["Voltage"] <= 240
        else "Abnormal"
    )

    report["Temperature_Status"] = (
        "Normal"
        if latest["Temperature"] <= 75
        else "High"
    )

    report["Current_Status"] = (
        "Normal"
        if latest["Current"] <= 100
        else "High"
    )

    return report


if __name__ == "__main__":

    path = input("Sensor CSV Path : ")

    result = analyze_sensor_data(path)

    print(result)