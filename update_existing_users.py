import firebase_service
import sys

def main():
    """Update existing users with quirky screennames"""
    print("Initializing Firebase...")
    firebase_service.initialize()
    
    if not firebase_service.firestore_db:
        print("Firestore not available, cannot update users")
        return False
    
    try:
        # Get all users
        users_ref = firebase_service.firestore_db.collection('users').get()
        print(f"Found {len(users_ref)} users")
        
        # Define quirky screennames for specific emails
        screenname_map = {
            "acbalon@yahoo.com": "PixelWizard42",
            "acbalon@gmail.com": "TurboCoder7"
        }
        
        # Update each user
        for user_doc in users_ref:
            user_id = user_doc.id
            user_data = user_doc.to_dict()
            email = user_data.get('email', '')
            
            # Skip users that already have screennames
            if 'screenname' in user_data and user_data['screenname']:
                print(f"User {email} already has screenname: {user_data['screenname']}")
                continue
            
            # Get screenname from map or generate a default one
            if email in screenname_map:
                screenname = screenname_map[email]
            else:
                # Generate a default screenname from email
                username_part = email.split('@')[0]
                screenname = f"{username_part}User"
            
            # Update user
            firebase_service.firestore_db.collection('users').document(user_id).update({
                'screenname': screenname
            })
            
            print(f"Updated user {email} with screenname: {screenname}")
        
        print("User update complete!")
        return True
    except Exception as e:
        print(f"Error updating users: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 