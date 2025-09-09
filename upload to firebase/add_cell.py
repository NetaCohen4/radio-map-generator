import firebase_admin
from firebase_admin import credentials, firestore

# Load service account key
cred = credentials.Certificate("Firebase_Key.json")
firebase_admin.initialize_app(cred)

# Connect to Firestore
db = firestore.client()

# Collect details from user input
# cellID = input("Enter Cell ID: ")
# name = input("Enter Base Station Name: ")
# provider = input("Enter Provider: ")
# lat = float(input("Enter Latitude: "))
# lon = float(input("Enter Longitude: "))
# generation = input("Enter Generation (e.g., 3G, 4G, 5G): ")
cellID = "6"

# Add document to BaseStations collection
doc_ref = db.collection("BaseStations").document(cellID)
doc_ref.set({
    "cellID": cellID,
    "name": "university",
    "provider": "PHI",
    "lat": 32.106432,
    "lon": 35.177255,
    "generation": "5G"
})

print(f"Base station added successfully with CellID.")

