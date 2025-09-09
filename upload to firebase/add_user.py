import firebase_admin
from firebase_admin import credentials, firestore

# טוען את קובץ ה-service account
cred = credentials.Certificate("Firebase_Key.json")
firebase_admin.initialize_app(cred)

# התחברות למסד הנתונים Firestore
db = firestore.client()

# דוגמה להוספת מסמך
doc_ref = db.collection("Users").document("005")
doc_ref.set({
    "username": "Aaderet",
    "password": "Aaderet1",
    "provider": "Golan Telecom"
})

print("Document written successfully.")
