import firebase_admin
from firebase_admin import credentials, firestore

# Load the service account file
cred = credentials.Certificate("Firebase_Key.json")
firebase_admin.initialize_app(cred)

# Connect to the Firestore database
db = firestore.client()

# Example of adding a document
doc_ref = db.collection("Users").document("005")
doc_ref.set({
    "username": "Aaderet",
    "password": "Aaderet1",
    "provider": "Golan Telecom"
})

print("Document written successfully.")
