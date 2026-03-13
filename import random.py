filename = "ConfigDAQ_202603021032.txt"
date_suffix = "202603021021"

content = [
    "Test Name:",
    "Uji",
    "Folder Test:",
    r"C:\Users\HRW_PC\Desktop\2026",
    "Duration:",
    "300"
]

# Membuat Baris 7 sampai 14 (Sensor01 - Sensor08)
for i in range(1, 9):
    sensor_name = f"Sensor0{i}" if i < 10 else f"Sensor{i}"
    cal_file = f"calCH{i}_{date_suffix}"
    line = f"{sensor_name};{cal_file};kPa"
    content.append(line)

# Menulis ke file
with open(filename, "w") as f:
    f.write("\n".join(content))

print(f"File '{filename}' berhasil dibuat!")