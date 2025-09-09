import firebase_admin
from firebase_admin import credentials, firestore
import csv
import re

# === הגדרות ===
csv_filename = "file.csv"
userID = "001"
user_suffix = "001"

# === אתחול Firebase ===
cred = credentials.Certificate("Firebase_Key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# === קריאת הקובץ עם מפריד ; ===
with open(csv_filename, mode='r', encoding='utf-8') as file:
    reader = csv.reader(file, delimiter=';')
    headers = next(reader)  # שורת כותרות

    for row in reader:
        if not row or len(row) != len(headers):
            continue  # דלג על שורות לא תקינות

        # צור מילון מהכותרות והערכים
        data = {headers[i].strip(): row[i].strip() for i in range(len(headers))}

        # הוספת userID
        data["userID"] = userID

        # חילוץ DATE ו-TIME מתוך השורה
        raw_date = data.get("DATE", "nodate")
        raw_time = data.get("TIME", "notime")

        # ננקה את הערכים ממפרידים לא חוקיים במסמכים
        safe_date = re.sub(r"[^0-9]", "", raw_date)     # למשל 20250714
        safe_time = re.sub(r"[^0-9]", "", raw_time)     # למשל 135000

        # יצירת מזהה ייחודי בלי user_ אלא רק המספר
        doc_id = f"{user_suffix}_{safe_date}_{safe_time}"

        # הוספה לקולקציה הראשית Data
        db.collection("Data").document(doc_id).set(data)

print("✅ All documents uploaded successfully with clean IDs.")

