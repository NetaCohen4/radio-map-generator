import firebase_admin
from firebase_admin import credentials, firestore
import csv
import re

# === Settings ===
csv_filename = "file.csv"
userID = "001"
user_suffix = "001"

# === Initialize Firebase ===
cred = credentials.Certificate("Firebase_Key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# === Read CSV file with ';' delimiter ===
with open(csv_filename, mode='r', encoding='utf-8') as file:
    reader = csv.reader(file, delimiter=';')
    headers = next(reader)  # Header row

    for row in reader:
        if not row or len(row) != len(headers):
            continue  # Skip invalid rows

        # Create dictionary from headers and values
        data = {headers[i].strip(): row[i].strip() for i in range(len(headers))}

        # Add userID
        data["userID"] = userID

        # Extract DATE and TIME from the row
        raw_date = data.get("DATE", "nodate")
        raw_time = data.get("TIME", "notime")

        # Clean the values from illegal separators in documents
        safe_date = re.sub(r"[^0-9]", "", raw_date)     # e.g., 20250714
        safe_time = re.sub(r"[^0-9]", "", raw_time)     # e.g., 135000

        # Create unique ID without user_ prefix, only the number
        doc_id = f"{user_suffix}_{safe_date}_{safe_time}"

        # Add to main collection Data
        db.collection("Data").document(doc_id).set(data)

print("✅ All documents uploaded successfully with clean IDs.")
