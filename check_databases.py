import firebase_service
from getpass import getpass

def check_databases():
    """Checks both Realtime Database and Firestore for users"""
    print("=== Database Check Tool ===")
    
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
        print(f"\nChecking databases as user: {current_user['email']}")
        
        # Check Firestore
        firestore_db = firebase_service.firestore_db
        if firestore_db:
            print("\n--- FIRESTORE USERS ---")
            users_collection = firestore_db.collection("users").get()
            if not users_collection:
                print("No users found in Firestore")
            else:
                for user_doc in users_collection:
                    user_data = user_doc.to_dict()
                    print(f"User ID: {user_doc.id}")
                    print(f"Email: {user_data.get('email', 'Unknown')}")
                    print(f"Role: {user_data.get('role', 'Unknown')}")
                    print(f"Trusted: {user_data.get('trusted', False)}")
                    print("-" * 30)
        else:
            print("\nFirestore is not initialized")
        
        # Check Realtime Database
        if firebase_service.firebase:
            print("\n--- REALTIME DATABASE USERS ---")
            db = firebase_service.firebase.database()
            try:
                users = db.child("users").get(token=current_user['token'])
                if users.val():
                    user_data = users.val()
                    for user_id, user_info in user_data.items():
                        print(f"User ID: {user_id}")
                        print(f"Email: {user_info.get('email', 'Unknown')}")
                        print(f"Role: {user_info.get('role', 'Unknown')}")
                        print(f"Trusted: {user_info.get('trusted', False)}")
                        print("-" * 30)
                else:
                    print("No users found in Realtime Database")
            except Exception as e:
                print(f"Error accessing Realtime Database: {str(e)}")
        else:
            print("\nRealtime Database is not initialized")
        
        # Ask if user wants to delete data from Realtime Database
        if input("\nDo you want to delete your user data from Realtime Database? (y/n): ").lower() == 'y':
            try:
                db = firebase_service.firebase.database()
                db.child("users").child(current_user['uid']).remove(token=current_user['token'])
                print("User data deleted from Realtime Database")
                
                # Ask if user wants to delete all parameters too
                if input("Do you want to delete all parameters from Realtime Database? (y/n): ").lower() == 'y':
                    db.child("parameters").remove(token=current_user['token'])
                    print("All parameters deleted from Realtime Database")
            except Exception as e:
                print(f"Error deleting data: {str(e)}")
        
        print("\nDone!")
        
    except Exception as e:
        print(f"Error checking databases: {str(e)}")

if __name__ == "__main__":
    check_databases() 