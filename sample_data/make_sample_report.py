"""Creates SYNTHETIC sample files (fictional person, fictional values) for demonstrating the upload features:
  - sample_lab_report.pdf    test report  -> Health Records > Upload test report
  - sample_prescription.pdf  prescription -> Medicines > Add from prescription
Run: python sample_data/make_sample_report.py
"""
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent
TODAY = date.today()


def write(path: Path, lines: list[tuple[str, int]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 790
    for text, size in lines:
        c.setFont("Helvetica-Bold" if size > 12 else "Helvetica", size)
        c.drawString(50, y, text)
        y -= 24
    c.save()
    print("created", path)


write(HERE / "sample_lab_report.pdf", [
    ("SAMPLE LAB REPORT (synthetic data, not a real patient)", 16),
    ("Patient Name: Demo User      Age: 28", 10),
    (f"Collected on: {(TODAY - timedelta(days=2)):%d/%m/%Y}", 10),
    ("Test                     Result       Reference range", 10),
    ("Hemoglobin 12.4 g/dL (12.0 - 15.5)", 11),
    ("WBC 7.1 x10^3/uL (4.0 - 11.0)", 11),
    ("Platelets 265 x10^3/uL (150 - 450)", 11),
    ("Fasting Glucose 104 mg/dL (70 - 99)", 11),
    ("Total Cholesterol 182 mg/dL (0 - 200)", 11),
    ("Vitamin D 24 ng/mL (30 - 100)", 11),
    ("TSH 2.4 uIU/mL (0.4 - 4.0)", 11),
])

write(HERE / "sample_prescription.pdf", [
    ("Dr. Neha Kapoor (sample), MBBS MD", 16),
    ("Sunrise Clinic (sample)  -  synthetic prescription for demonstration only", 10),
    ("Patient Name: Demo User      Age: 28", 10),
    (f"Date: {TODAY:%d/%m/%Y}", 10),
    ("Diagnosis: Seasonal allergy (sample)", 10),
    ("Rx", 14),
    ("1. Tab Cetirizine 10 mg 0-0-1 after food x 10 days", 11),
    ("2. Cap Omeprazole 20 mg OD before breakfast for 14 days", 11),
    ("3. Syp Cough Syrup 5 ml TDS x 5 days", 11),
    ("4. Tab Paracetamol 650 mg SOS", 11),
    ("5. Vitamin D3 60000 IU once weekly for 8 weeks", 11),
    ("Advice: drink plenty of water. Follow up after 2 weeks.", 10),
])
