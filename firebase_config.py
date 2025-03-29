"""
Firebase configuration for VCM Overlay application.
"""

# Firebase configuration
firebase_config = {
    "apiKey": "AIzaSyBs2oPQ9F1hEZOPgL6iPLxPb-DjUrXpieI",
    "authDomain": "vcmoverlay.firebaseapp.com",
    "databaseURL": "https://vcmoverlay-default-rtdb.firebaseio.com",
    "projectId": "vcmoverlay",
    "storageBucket": "vcmoverlay.appspot.com",
    "messagingSenderId": "829730758478",
    "appId": "1:829730758478:web:170ed470372e980ee2081f"
}

# Firebase Authentication configuration
auth_config = {
    "service_account_key_file": "serviceAccountKey.json", # Path to your service account key file
    "sign_in_options": ["email", "google"],
    "persistent_auth": True
}

# Database options
database_config = {
    "use_firestore": True  # Set to True to use Firestore, False to use Realtime Database
} 