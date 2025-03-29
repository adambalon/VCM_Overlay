"""
Manage pending parameters utility for admin users.
"""

import firebase_service
from getpass import getpass
import json
from datetime import datetime

def manage_pending_parameters():
    """View and manage pending parameters as an admin."""
    print("=== Pending Parameters Management Tool ===")
    
    # Initialize Firebase
    if not firebase_service.initialize():
        print("Failed to initialize Firebase.")
        return
    
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
    
    # Verify admin status
    is_admin = False
    
    try:
        if firebase_service.firestore_db:
            # Check admin status in Firestore
            user_doc = firebase_service.firestore_db.collection('users').document(current_user['uid']).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                is_admin = user_data.get('role') == 'admin' and user_data.get('trusted', False)
        else:
            # Check admin status in Realtime Database
            db = firebase_service.firebase.database()
            user_data = db.child('users').child(current_user['uid']).get(token=current_user['token']).val()
            is_admin = user_data and user_data.get('role') == 'admin' and user_data.get('trusted', False)
    except Exception as e:
        print(f"Error checking admin status: {str(e)}")
    
    if not is_admin:
        print("Error: You must be an admin to manage pending parameters.")
        return
    
    print(f"\nLogged in as admin: {current_user['email']}")
    
    # List pending parameters
    try:
        if firebase_service.firestore_db:
            # Get pending parameters from Firestore
            pending_params = firebase_service.firestore_db.collection('pending').get()
            
            if not pending_params or len(pending_params) == 0:
                print("No pending parameters found.")
                return
            
            print("\n=== Pending Parameters ===")
            param_list = []
            
            for i, param in enumerate(pending_params):
                param_data = param.to_dict()
                param_data['id'] = param.id  # Store document ID for later reference
                
                # Format date if present
                submitted_at = param_data.get('submitted_at')
                if submitted_at:
                    if hasattr(submitted_at, 'timestamp'):
                        # Convert Firestore timestamp to datetime
                        dt = datetime.fromtimestamp(submitted_at.timestamp())
                        submitted_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                
                param_list.append(param_data)
                
                print(f"{i+1}. Parameter ID: {param_data.get('param_id', 'Unknown')}")
                print(f"   Name: {param_data.get('name', 'Unnamed')}")
                print(f"   Submitted by: {param_data.get('submitted_by', 'Unknown')}")
                print(f"   Submitted at: {submitted_at}")
                print(f"   Status: {param_data.get('status', 'Unknown')}")
                print(f"   Type: {param_data.get('type', 'Unknown')}")
                print(f"   Module Type: {param_data.get('module_type', 'Unknown')}")
                print("   ---")
            
            # Process pending parameters
            while True:
                choice = input("\nEnter parameter number to manage (or 'q' to quit): ")
                
                if choice.lower() == 'q':
                    break
                
                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(param_list):
                        print("Invalid selection. Please try again.")
                        continue
                    
                    param_data = param_list[idx]
                    doc_id = param_data['id']
                    
                    print(f"\nSelected parameter: {param_data.get('param_id', 'Unknown')}")
                    print("Parameter details:")
                    # Print all parameter details in a readable format
                    for key, value in param_data.items():
                        if key == 'id':
                            continue
                        if hasattr(value, 'timestamp'):
                            value = datetime.fromtimestamp(value.timestamp()).strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  {key}: {value}")
                    
                    action = input("\nAction (a=approve, r=reject, s=skip): ").lower()
                    
                    if action == 'a':
                        # Copy to parameters collection
                        approved_data = param_data.copy()
                        del approved_data['id']  # Remove document ID
                        approved_data['status'] = 'approved'
                        approved_data['approved_by'] = current_user['email']
                        approved_data['approved_at'] = firebase_service.firestore.SERVER_TIMESTAMP
                        
                        # Find existing parameter or add new one
                        param_id = param_data.get('param_id')
                        param_ref = firebase_service.firestore_db.collection('parameters').where('param_id', '==', param_id).limit(1).get()
                        
                        if param_ref and len(param_ref) > 0:
                            # Update existing parameter
                            existing_param = param_ref[0]
                            firebase_service.firestore_db.collection('parameters').document(existing_param.id).update(approved_data)
                        else:
                            # Create new parameter
                            firebase_service.firestore_db.collection('parameters').add(approved_data)
                        
                        # Update pending status
                        firebase_service.firestore_db.collection('pending').document(doc_id).update({
                            'status': 'approved',
                            'approved_by': current_user['email'],
                            'approved_at': firebase_service.firestore.SERVER_TIMESTAMP
                        })
                        
                        print(f"Parameter {param_id} approved and added to parameters collection.")
                    
                    elif action == 'r':
                        reason = input("Rejection reason: ")
                        
                        # Update status to rejected
                        firebase_service.firestore_db.collection('pending').document(doc_id).update({
                            'status': 'rejected',
                            'rejected_by': current_user['email'],
                            'rejected_at': firebase_service.firestore.SERVER_TIMESTAMP,
                            'rejection_reason': reason
                        })
                        
                        print(f"Parameter {param_data.get('param_id')} rejected.")
                    
                    elif action == 's':
                        continue
                    
                    else:
                        print("Invalid action. Please try again.")
                
                except Exception as e:
                    print(f"Error processing parameter: {str(e)}")
        
        else:
            # Get pending parameters from Realtime Database
            db = firebase_service.firebase.database()
            pending_params = db.child('pending').get(token=current_user['token']).val()
            
            if not pending_params:
                print("No pending parameters found.")
                return
            
            print("\n=== Pending Parameters ===")
            param_list = []
            
            for i, (param_id, param_data) in enumerate(pending_params.items()):
                param_data['id'] = param_id  # Store parameter ID for later reference
                param_list.append(param_data)
                
                # Format timestamp if present
                submitted_at = param_data.get('submitted_at')
                if submitted_at:
                    dt = datetime.fromtimestamp(submitted_at / 1000)  # Convert from milliseconds
                    submitted_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"{i+1}. Parameter ID: {param_id}")
                print(f"   Name: {param_data.get('name', 'Unnamed')}")
                print(f"   Submitted by: {param_data.get('submitted_by', 'Unknown')}")
                print(f"   Submitted at: {submitted_at}")
                print(f"   Status: {param_data.get('status', 'Unknown')}")
                print(f"   Type: {param_data.get('type', 'Unknown')}")
                print(f"   Module Type: {param_data.get('module_type', 'Unknown')}")
                print("   ---")
            
            # Process pending parameters
            while True:
                choice = input("\nEnter parameter number to manage (or 'q' to quit): ")
                
                if choice.lower() == 'q':
                    break
                
                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(param_list):
                        print("Invalid selection. Please try again.")
                        continue
                    
                    param_data = param_list[idx]
                    param_id = param_data['id']
                    
                    print(f"\nSelected parameter: {param_id}")
                    print("Parameter details:")
                    # Print all parameter details in a readable format
                    for key, value in param_data.items():
                        if key == 'id':
                            continue
                        print(f"  {key}: {value}")
                    
                    action = input("\nAction (a=approve, r=reject, s=skip): ").lower()
                    
                    if action == 'a':
                        # Copy to parameters collection
                        approved_data = param_data.copy()
                        approved_data['status'] = 'approved'
                        approved_data['approved_by'] = current_user['email']
                        approved_data['approved_at'] = {".sv": "timestamp"}
                        
                        # Remove internal ID
                        if 'id' in approved_data:
                            del approved_data['id']
                        
                        # Save to parameters
                        db.child('parameters').child(param_id).set(
                            approved_data, 
                            token=current_user['token']
                        )
                        
                        # Update pending status
                        db.child('pending').child(param_id).update({
                            'status': 'approved',
                            'approved_by': current_user['email'],
                            'approved_at': {".sv": "timestamp"}
                        }, token=current_user['token'])
                        
                        print(f"Parameter {param_id} approved and added to parameters collection.")
                    
                    elif action == 'r':
                        reason = input("Rejection reason: ")
                        
                        # Update status to rejected
                        db.child('pending').child(param_id).update({
                            'status': 'rejected',
                            'rejected_by': current_user['email'],
                            'rejected_at': {".sv": "timestamp"},
                            'rejection_reason': reason
                        }, token=current_user['token'])
                        
                        print(f"Parameter {param_id} rejected.")
                    
                    elif action == 's':
                        continue
                    
                    else:
                        print("Invalid action. Please try again.")
                
                except Exception as e:
                    print(f"Error processing parameter: {str(e)}")
    
    except Exception as e:
        print(f"Error listing pending parameters: {str(e)}")
    
    print("\nPending parameters management complete.")

if __name__ == "__main__":
    manage_pending_parameters() 