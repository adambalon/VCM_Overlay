"""
Make a user an admin in Firestore.
"""

import firebase_service
from getpass import getpass

def make_user_admin_in_firestore():
    """Make the current user an admin in Firestore."""
    print("=== Make Admin Tool ===")
    
    # Initialize Firebase
    firebase_service.initialize()
    
    # Check if user is already logged in
    current_user = firebase_service.get_current_user()
    
    if not current_user:
        # User is not logged in, prompt for credentials
        email = input("Email: ")
        password = getpass("Password: ")
        
        success, message, user_data = firebase_service.sign_in_with_email_password(email, password)
        
        if not success:
            print(f"Login failed: {message}")
            return
        
        current_user = user_data
    
    try:
        print(f"\nMaking user {current_user['email']} an admin...")
        
        # Check if Firestore is available
        if firebase_service.firestore_db:
            user_id = current_user['uid']
            
            # Get current user document
            user_doc = firebase_service.firestore_db.collection('users').document(user_id).get()
            
            if user_doc.exists:
                # Update user role to admin
                firebase_service.firestore_db.collection('users').document(user_id).update({
                    'role': 'admin',
                    'trusted': True
                })
                print(f"User {current_user['email']} is now an admin!")
            else:
                # Create user document if it doesn't exist
                firebase_service.firestore_db.collection('users').document(user_id).set({
                    'email': current_user['email'],
                    'role': 'admin',
                    'trusted': True,
                    'created_at': firebase_service.firestore.SERVER_TIMESTAMP
                })
                print(f"Created new user profile for {current_user['email']} with admin role!")
        else:
            # Fallback to Realtime Database
            print("Firestore not available, updating Realtime Database instead...")
            if firebase_service.firebase:
                db = firebase_service.firebase.database()
                user_id = current_user['uid']
                db.child('users').child(user_id).update({
                    'role': 'admin',
                    'trusted': True
                }, token=current_user['token'])
                print(f"User {current_user['email']} is now an admin in Realtime Database!")
            else:
                print("Error: Firebase database is not available")
        
        print("\nAdmin privileges granted successfully!")
        
    except Exception as e:
        print(f"Error making user admin: {str(e)}")

if __name__ == "__main__":
    make_user_admin_in_firestore() 