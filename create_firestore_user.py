import firebase_service
from getpass import getpass
import time

def create_firestore_user():
    """Creates a new user directly in Firestore and makes them an admin"""
    print("=== Create Firestore User Tool ===")
    
    # Initialize Firebase
    firebase_service.initialize()
    
    # Check if Firestore is available
    if not firebase_service.firestore_db:
        print("Error: Firestore is not initialized!")
        return
    
    print("\nCreate a new user account:")
    email = input("Email: ")
    password = getpass("Password: ")
    
    # Create the user
    success, message, user_data = firebase_service.create_user_with_email_password(email, password)
    
    if not success:
        print(f"Failed to create user: {message}")
        return
    
    print(f"\nUser created successfully: {email}")
    
    # Get Firestore reference
    firestore_db = firebase_service.firestore_db
    
    # Make the user an admin directly in Firestore
    try:
        user_ref = firestore_db.collection('users').document(user_data['uid'])
        
        # Create or update user document with admin privileges
        user_ref.set({
            'email': email,
            'created_at': firebase_service.firestore.SERVER_TIMESTAMP,
            'role': 'admin',
            'trusted': True
        })
        
        print(f"User {email} has been set as an admin in Firestore!")
        
        # Log in with the new account to verify
        print("\nLogging in with new account to verify...")
        time.sleep(1)  # Small delay to ensure Firestore update completes
        
        verify_success, verify_message, verify_data = firebase_service.sign_in_with_email_password(email, password)
        
        if verify_success:
            print("✓ Login successful!")
            
            # Verify user in Firestore
            user_doc = user_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                print("\nUser document in Firestore:")
                print(f"Email: {user_data.get('email')}")
                print(f"Role: {user_data.get('role')}")
                print(f"Trusted: {user_data.get('trusted')}")
                print("\n✓ User created successfully and verified in Firestore!")
            else:
                print("⚠ User document not found in Firestore after creation.")
        else:
            print(f"⚠ Login verification failed: {verify_message}")
    
    except Exception as e:
        print(f"Error updating user in Firestore: {str(e)}")

if __name__ == "__main__":
    create_firestore_user() 