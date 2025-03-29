"""
Firebase service module for VCM Overlay application.
Handles authentication and database operations.
"""

import os
import json
import time
import pyrebase
import firebase_admin
from firebase_admin import credentials, auth as admin_auth, firestore
from firebase_config import firebase_config, database_config, auth_config

# Global variables
firebase = None
auth_instance = None
db_instance = None  # For Realtime Database
firestore_db = None  # For Firestore
current_user = None
firebase_app = None

def initialize():
    """Initialize Firebase services.
    
    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    global firebase, auth_instance, db_instance, firestore_db, firebase_app
    
    try:
        # Initialize Pyrebase for authentication
        firebase = pyrebase.initialize_app(firebase_config)
        auth_instance = firebase.auth()
        
        # Get the service account key file path
        service_account_path = auth_config.get("service_account_key_file")
        
        # Check if we should use Firestore
        use_firestore = database_config.get("use_firestore", False)
        
        if use_firestore:
            try:
                # Initialize Firebase Admin SDK with the service account
                if not firebase_admin._apps:
                    if os.path.exists(service_account_path):
                        cred = credentials.Certificate(service_account_path)
                        firebase_app = firebase_admin.initialize_app(cred)
                        print(f"Firebase Admin SDK initialized with service account")
                    else:
                        firebase_app = firebase_admin.initialize_app()
                        print("Firebase Admin SDK initialized with default credentials")
                
                # Get a reference to the Firestore database
                firestore_db = firestore.client()
                print(f"Using Firestore with project ID: {firebase_config.get('projectId', 'Not specified')}")
            except Exception as admin_error:
                print(f"Error initializing Firebase Admin SDK: {str(admin_error)}")
                print("Falling back to Realtime Database")
                use_firestore = False
                
        if not use_firestore:
            # Use Pyrebase's database for Realtime Database
            db_instance = firebase.database()
            print(f"Using Realtime Database with URL: {firebase_config.get('databaseURL', 'Not specified')}")
        
        print("Firebase initialized successfully")
        
        return True
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        return False

def sign_in_with_email_password(email, password):
    """Sign in with email and password.
    
    Args:
        email (str): User's email
        password (str): User's password
        
    Returns:
        tuple: (success, message, user_data)
            success (bool): True if sign-in was successful
            message (str): Success or error message
            user_data (dict): User data if successful, None otherwise
    """
    global current_user
    
    if not auth_instance:
        return False, "Firebase is not initialized", None
    
    try:
        user = auth_instance.sign_in_with_email_and_password(email, password)
        
        # Get user info
        user_info = auth_instance.get_account_info(user['idToken'])
        
        # Store user data
        current_user = {
            "uid": user['localId'],
            "email": user['email'],
            "token": user['idToken'],
            "refreshToken": user['refreshToken'],
            "expiresIn": user['expiresIn']
        }
        
        # Check if user profile exists in Firestore and create if it doesn't
        if firestore_db:
            try:
                # Check if user document exists
                user_doc = firestore_db.collection('users').document(current_user['uid']).get()
                
                if not user_doc.exists:
                    print(f"User profile doesn't exist in Firestore for {email}. Creating one...")
                    # Create user profile in Firestore
                    firestore_db.collection('users').document(current_user['uid']).set({
                        'email': current_user['email'],
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'role': 'user',  # Default role
                        'trusted': False  # Not trusted by default
                    })
                    print(f"User profile created in Firestore successfully")
            except Exception as db_error:
                print(f"Error checking/creating user profile in Firestore: {str(db_error)}")
        
        return True, "Authentication successful", current_user
    except Exception as e:
        error_message = str(e)
        print(f"Authentication error details: {error_message}")
        
        # Extract Firebase error message
        if "INVALID_PASSWORD" in error_message:
            return False, "Invalid password", None
        elif "EMAIL_NOT_FOUND" in error_message:
            return False, "Email not found", None
        elif "INVALID_EMAIL" in error_message:
            return False, "Invalid email format", None
        elif "400" in error_message:
            # Handle HTTP 400 errors - typically invalid credentials
            return False, "Invalid email or password", None
        else:
            return False, f"Authentication error: {error_message}", None

def check_screenname_availability(screenname):
    """Check if a screenname is available.
    
    Args:
        screenname (str): Screenname to check
        
    Returns:
        bool: True if screenname is available, False if already taken
    """
    if not firestore_db:
        print("Firestore not available, cannot check screenname")
        return False
    
    try:
        # Query users collection for screenname
        users_ref = firestore_db.collection('users').where('screenname', '==', screenname).limit(1).get()
        
        # If no results, screenname is available
        return len(users_ref) == 0
    except Exception as e:
        print(f"Error checking screenname availability: {str(e)}")
        return False

def create_user_with_email_password(email, password, screenname=None):
    """Create a new user with email and password.
    
    Args:
        email (str): User's email
        password (str): User's password
        screenname (str, optional): User's screenname
        
    Returns:
        tuple: (success, message, user_data)
            success (bool): True if user creation was successful
            message (str): Success or error message
            user_data (dict): User data if successful, None otherwise
    """
    if not auth_instance:
        return False, "Firebase is not initialized", None
    
    try:
        # If screenname is provided, check if it's available
        if screenname:
            if not check_screenname_availability(screenname):
                return False, "Screenname is already taken", None
        
        # Create user with Firebase Auth
        user = auth_instance.create_user_with_email_and_password(email, password)
        
        # Get user info
        user_info = auth_instance.get_account_info(user['idToken'])
        
        user_data = {
            "uid": user['localId'],
            "email": user['email'],
            "token": user['idToken'],
            "refreshToken": user['refreshToken'],
            "expiresIn": user['expiresIn']
        }
        
        # Save user profile to appropriate database
        try:
            if firestore_db:
                # Add user to Firestore with basic profile
                print(f"Creating user profile in Firestore for {email}...")
                user_profile = {
                    'email': user_data['email'],
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'role': 'user',  # Default role
                    'trusted': False  # Not trusted by default
                }
                
                # Add screenname if provided
                if screenname:
                    user_profile['screenname'] = screenname
                
                # Save to Firestore
                firestore_db.collection('users').document(user_data['uid']).set(user_profile)
                print(f"User profile created in Firestore successfully")
            else:
                print("Firestore not available, falling back to Realtime Database")
                # Add user to Realtime Database with basic profile
                if db_instance:
                    user_profile = {
                        'email': user_data['email'],
                        'created_at': {".sv": "timestamp"},
                        'role': 'user',  # Default role
                        'trusted': False  # Not trusted by default
                    }
                    
                    # Add screenname if provided
                    if screenname:
                        user_profile['screenname'] = screenname
                    
                    # Save to Realtime Database
                    db_instance.child('users').child(user_data['uid']).set(
                        user_profile, token=user_data['token'])
                    print(f"User profile created in Realtime Database")
        except Exception as db_error:
            print(f"Error creating user profile in database: {str(db_error)}")
        
        return True, "User created successfully", user_data
    except Exception as e:
        error_message = str(e)
        # Extract Firebase error message
        if "EMAIL_EXISTS" in error_message:
            return False, "Email already exists", None
        elif "WEAK_PASSWORD" in error_message:
            return False, "Password should be at least 6 characters", None
        elif "INVALID_EMAIL" in error_message:
            return False, "Invalid email format", None
        else:
            return False, f"User creation error: {error_message}", None

def sign_out():
    """Sign out the current user.
    
    Returns:
        bool: True if sign-out was successful, False otherwise.
    """
    global current_user
    
    if current_user:
        current_user = None
        return True
    
    return False

def get_current_user():
    """Get the current signed-in user.
    
    Returns:
        dict: Current user data, or None if no user is signed in.
    """
    return current_user

def refresh_token():
    """Refresh the user's authentication token.
    
    Returns:
        bool: True if token refresh was successful, False otherwise.
    """
    global current_user
    
    if not current_user or not auth_instance:
        return False
    
    try:
        refresh_token = current_user.get('refreshToken')
        if not refresh_token:
            return False
        
        user = auth_instance.refresh(refresh_token)
        
        # Update user data
        current_user['token'] = user['idToken']
        current_user['refreshToken'] = user['refreshToken']
        current_user['expiresIn'] = user['expiresIn']
        
        return True
    except Exception as e:
        print(f"Error refreshing token: {str(e)}")
        return False

def save_parameter_to_firebase(param_id, param_data):
    """Save parameter data to Firebase.
    
    Args:
        param_id (str): Parameter ID
        param_data (dict): Parameter data
        
    Returns:
        tuple: (success, message)
            success (bool): True if save was successful
            message (str): Success or error message
    """
    if not firebase:
        return False, "Firebase is not initialized"
    
    if not current_user:
        print("No authenticated user. Cannot save to Firebase without authentication.")
        return False, "You must be signed in to save to Firebase"
    
    try:
        # Check if there are actual changes to the parameter
        has_changes, existing_data = check_parameter_changes(param_id, param_data)
        
        if not has_changes:
            # Special case: No actual changes detected
            return True, "NO_CHANGES"
        
        # Add user info and timestamp to the data
        enriched_data = param_data.copy()
        enriched_data['updated_by'] = current_user.get('email', 'Unknown')
        
        # Explicitly add old and new values for change tracking
        if existing_data:
            # For important fields, track old and new values
            for field in ['name', 'description', 'details']:
                if field in param_data:
                    # Save new value
                    enriched_data[f'new_{field}'] = param_data[field]
                    # Save old value if it exists in existing data
                    if field in existing_data:
                        enriched_data[f'old_{field}'] = existing_data[field]
                    else:
                        enriched_data[f'old_{field}'] = ""
        else:
            # No existing data, so old values are empty
            for field in ['name', 'description', 'details']:
                if field in param_data:
                    enriched_data[f'new_{field}'] = param_data[field]
                    enriched_data[f'old_{field}'] = ""
            
        # Ensure we have old_value and new_value fields for the change log
        if 'new_details' in enriched_data and 'old_details' in enriched_data:
            # Use details as the primary change value if available
            enriched_data['new_value'] = enriched_data['new_details']
            enriched_data['old_value'] = enriched_data['old_details']
        elif 'new_description' in enriched_data and 'old_description' in enriched_data:
            # Fall back to description
            enriched_data['new_value'] = enriched_data['new_description']
            enriched_data['old_value'] = enriched_data['old_description']
        elif 'new_name' in enriched_data and 'old_name' in enriched_data:
            # Last resort is name
            enriched_data['new_value'] = enriched_data['new_name']
            enriched_data['old_value'] = enriched_data['old_name']
            
        # Check if we should use Firestore or Realtime Database
        if firestore_db:
            # Get user role from Firestore
            user_id = current_user['uid']
            user_doc = firestore_db.collection('users').document(user_id).get()
            
            user_is_admin = False
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_is_admin = user_data.get('role') == 'admin' and user_data.get('trusted', False)
            
            # Add Firestore-specific fields
            enriched_data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            if user_is_admin:
                # Admin users save directly to parameters collection
                print(f"User is admin, saving parameter {param_id} directly to parameters collection...")
                
                # Add param_id to ensure it's searchable
                enriched_data['param_id'] = param_id
                
                # Check if parameter already exists
                param_ref = firestore_db.collection('parameters').where('param_id', '==', param_id).limit(1).get()
                
                if param_ref and len(param_ref) > 0:
                    # Update existing parameter
                    existing_param = param_ref[0]
                    firestore_db.collection('parameters').document(existing_param.id).update(enriched_data)
                    return True, f"Parameter {param_id} updated in parameters collection"
                else:
                    # Create new parameter
                    enriched_data['approved_by'] = current_user.get('email', 'Unknown')
                    enriched_data['approved_at'] = firestore.SERVER_TIMESTAMP
                    firestore_db.collection('parameters').add(enriched_data)
                    return True, f"Parameter {param_id} added to parameters collection"
            else:
                # Regular users save to pending collection
                print(f"User is not admin, saving parameter {param_id} to pending collection...")
                
                # Add pending-specific fields
                enriched_data['param_id'] = param_id
                enriched_data['submitted_by'] = current_user.get('email', 'Unknown')
                enriched_data['submitted_at'] = firestore.SERVER_TIMESTAMP
                enriched_data['status'] = 'pending'
                
                # Check if already in pending
                pending_ref = firestore_db.collection('pending').where('param_id', '==', param_id).limit(1).get()
                
                if pending_ref and len(pending_ref) > 0:
                    # Update existing pending entry
                    existing_pending = pending_ref[0]
                    firestore_db.collection('pending').document(existing_pending.id).update(enriched_data)
                    return True, f"Parameter {param_id} updated in pending collection"
                else:
                    # Create new pending entry
                    firestore_db.collection('pending').add(enriched_data)
                    return True, f"Parameter {param_id} added to pending collection"
        else:
            # Using Realtime Database
            # Refresh token if necessary
            if not refresh_token():
                return False, "Failed to refresh authentication token"
                
            # Determine where to save based on user role
            db = firebase.database()
            
            # Get user role from database
            try:
                user_data = db.child('users').child(current_user['uid']).get(token=current_user['token']).val()
                user_is_admin = user_data and user_data.get('role') == 'admin' and user_data.get('trusted', False)
            except:
                user_is_admin = False
            
            # Add timestamp
            enriched_data['updated_at'] = {".sv": "timestamp"}
            
            if user_is_admin:
                # Admin users save directly to parameters
                print(f"User is admin, saving parameter {param_id} directly to parameters node...")
                
                # Add approval info for admins
                enriched_data['approved_by'] = current_user.get('email', 'Unknown')
                enriched_data['approved_at'] = {".sv": "timestamp"}
                
                db.child('parameters').child(param_id).set(enriched_data, token=current_user['token'])
                return True, f"Parameter {param_id} saved to parameters"
            else:
                # Regular users save to pending
                print(f"User is not admin, saving parameter {param_id} to pending node...")
                
                # Add submission info
                enriched_data['submitted_by'] = current_user.get('email', 'Unknown')
                enriched_data['submitted_at'] = {".sv": "timestamp"}
                enriched_data['status'] = 'pending'
                
                db.child('pending').child(param_id).set(enriched_data, token=current_user['token'])
                return True, f"Parameter {param_id} saved to pending"
                
    except Exception as e:
        error_message = str(e)
        print(f"Error saving parameter: {error_message}")
        
        if "PERMISSION_DENIED" in error_message:
            return False, "You don't have permission to save this parameter"
        elif "UNAUTHORIZED" in error_message or "401" in error_message:
            # Token might have expired
            if refresh_token():
                # Try again with refreshed token
                return save_parameter_to_firebase(param_id, param_data)
            else:
                return False, "Authentication error: Please sign in again"
        else:
            return False, f"Error saving parameter: {error_message}"

def get_parameter_from_firebase(param_id):
    """Get parameter data from Firebase.
    
    Args:
        param_id (str): Parameter ID
        
    Returns:
        tuple: (success, message, data)
            success (bool): True if retrieval was successful
            message (str): Success or error message
            data (dict): Parameter data if successful, None otherwise
    """
    if not firebase:
        return False, "Firebase is not initialized", None
    
    if not current_user:
        return False, "You must be signed in to retrieve from Firebase", None
    
    try:
        if firestore_db:
            # First check approved parameters
            param_doc = firestore_db.collection('parameters').document(param_id).get()
            
            if param_doc.exists:
                return True, "Parameter retrieved successfully", param_doc.to_dict()
            
            # If not found in approved, check pending parameters
            pending_doc = firestore_db.collection('pending').document(param_id).get()
            
            if pending_doc.exists:
                pending_data = pending_doc.to_dict()
                
                # Check if user is the creator or has elevated privileges
                is_moderator = False
                try:
                    user_doc = firestore_db.collection('users').document(current_user['uid']).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        is_moderator = user_data.get('role') in ['admin', 'moderator']
                except Exception as user_error:
                    print(f"Error checking user role: {str(user_error)}")
                
                if pending_data.get('updated_by') == current_user.get('email') or is_moderator:
                    return True, "Parameter retrieved from pending collection", pending_data
                else:
                    return False, "You don't have permission to view this pending parameter", None
        else:
            # Use Realtime Database
            db = firebase.database()
            
            # Try different module types
            for module_type in ["ECM", "TCM", "BCM", "PCM", "ICM", "OTHER"]:
                path = f"parameters/{module_type}/{param_id}"
                print(f"Checking for parameter at path: {path}")
                
                param_data = db.child(path).get(token=current_user['token'])
                
                if param_data.val():
                    print(f"Parameter found at {path}")
                    return True, "Parameter retrieved successfully", param_data.val()
        
        # If we reach here, the parameter wasn't found
        return False, "Parameter not found in Firebase", None
            
    except Exception as e:
        return False, f"Error retrieving parameter: {str(e)}", None

def get_user_contributions(user_id):
    """Get all contributions (pending, approved, rejected) for a specific user.
    
    Args:
        user_id (str): The user ID to retrieve contributions for.
        
    Returns:
        list: A list of contribution dictionaries.
    """
    if not current_user or (not firestore_db and not db_instance):
        return []
        
    contributions = []
    
    try:
        # Use Firestore if available
        if firestore_db:
            # First get user email from Firestore
            user_doc = firestore_db.collection('users').document(user_id).get()
            user_email = user_doc.to_dict().get('email') if user_doc.exists else None
            
            if not user_email:
                print(f"Could not find email for user ID {user_id}")
                return []
            
            # Get pending submissions
            pending_params = firestore_db.collection('pending').where('submitted_by', '==', user_email).get()
            for param in pending_params:
                param_data = param.to_dict()
                param_data['id'] = param.id
                param_data['status'] = 'pending'
                
                # Convert timestamp if it exists
                if 'submitted_at' in param_data and hasattr(param_data['submitted_at'], 'timestamp'):
                    param_data['timestamp'] = param_data['submitted_at'].timestamp() * 1000  # Convert to milliseconds
                
                # Add parameter name if not present
                if 'name' in param_data and 'parameter_name' not in param_data:
                    param_data['parameter_name'] = param_data['name']
                
                # Make sure we have old_value and new_value fields - with improved extraction
                ensure_old_new_values(param_data)
                
                contributions.append(param_data)
            
            # Get approved parameters
            approved_params = firestore_db.collection('parameters').where('updated_by', '==', user_email).get()
            for param in approved_params:
                param_data = param.to_dict()
                param_data['id'] = param.id
                param_data['status'] = 'approved'
                
                # Convert timestamp if it exists
                if 'approved_at' in param_data and hasattr(param_data['approved_at'], 'timestamp'):
                    param_data['timestamp'] = param_data['approved_at'].timestamp() * 1000  # Convert to milliseconds
                elif 'updated_at' in param_data and hasattr(param_data['updated_at'], 'timestamp'):
                    param_data['timestamp'] = param_data['updated_at'].timestamp() * 1000  # Convert to milliseconds
                
                # Add parameter name if not present
                if 'name' in param_data and 'parameter_name' not in param_data:
                    param_data['parameter_name'] = param_data['name']
                
                # Make sure we have old_value and new_value fields - with improved extraction
                ensure_old_new_values(param_data)
                
                contributions.append(param_data)
            
            # Get rejected parameters (stored in a separate collection)
            rejected_params = firestore_db.collection('rejected_parameters').where('submitted_by', '==', user_email).get()
            for param in rejected_params:
                param_data = param.to_dict()
                param_data['id'] = param.id
                param_data['status'] = 'rejected'
                
                # Convert timestamp if it exists
                if 'rejected_at' in param_data and hasattr(param_data['rejected_at'], 'timestamp'):
                    param_data['timestamp'] = param_data['rejected_at'].timestamp() * 1000  # Convert to milliseconds
                
                # Add parameter name if not present
                if 'name' in param_data and 'parameter_name' not in param_data:
                    param_data['parameter_name'] = param_data['name']
                
                # Make sure we have old_value and new_value fields - with improved extraction
                ensure_old_new_values(param_data)
                
                contributions.append(param_data)
            
            # Sort by timestamp, newest first
            contributions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
        else:
            # Use Realtime Database
            db = firebase.database()
            
            # First get user email
            user_data = db.child('users').child(user_id).get(token=current_user['token']).val()
            user_email = user_data.get('email') if user_data else None
            
            if not user_email:
                print(f"Could not find email for user ID {user_id}")
                return []
            
            # Get pending parameters
            pending_params = db.child('pending').get(token=current_user['token']).val() or {}
            for param_id, param_data in pending_params.items():
                if param_data.get('submitted_by') == user_email:
                    contribution = param_data.copy()
                    contribution['id'] = param_id
                    contribution['status'] = 'pending'
                    contribution['timestamp'] = contribution.get('submitted_at', 0)
                    
                    # Add parameter name if not present
                    if 'name' in contribution and 'parameter_name' not in contribution:
                        contribution['parameter_name'] = contribution['name']
                    
                    # Make sure we have old_value and new_value fields - with improved extraction
                    ensure_old_new_values(contribution)
                    
                    contributions.append(contribution)
            
            # Get approved parameters
            approved_params = db.child('parameters').get(token=current_user['token']).val() or {}
            for param_id, param_data in approved_params.items():
                if param_data.get('updated_by') == user_email:
                    contribution = param_data.copy()
                    contribution['id'] = param_id
                    contribution['status'] = 'approved'
                    contribution['timestamp'] = contribution.get('approved_at', 0) or contribution.get('updated_at', 0)
                    
                    # Add parameter name if not present
                    if 'name' in contribution and 'parameter_name' not in contribution:
                        contribution['parameter_name'] = contribution['name']
                    
                    # Make sure we have old_value and new_value fields - with improved extraction
                    ensure_old_new_values(contribution)
                    
                    contributions.append(contribution)
            
            # Get rejected parameters
            rejected_params = db.child('rejected_parameters').get(token=current_user['token']).val() or {}
            for param_id, param_data in rejected_params.items():
                if param_data.get('submitted_by') == user_email:
                    contribution = param_data.copy()
                    contribution['id'] = param_id
                    contribution['status'] = 'rejected'
                    contribution['timestamp'] = contribution.get('rejected_at', 0)
                    
                    # Add parameter name if not present
                    if 'name' in contribution and 'parameter_name' not in contribution:
                        contribution['parameter_name'] = contribution['name']
                    
                    # Make sure we have old_value and new_value fields - with improved extraction
                    ensure_old_new_values(contribution)
                    
                    contributions.append(contribution)
            
            # Sort by timestamp, newest first
            contributions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    
    except Exception as e:
        print(f"Error retrieving user contributions: {str(e)}")
    
    return contributions

def ensure_old_new_values(param_data):
    """Ensure param_data has old_value and new_value fields by extracting from available fields.
    
    Args:
        param_data (dict): Parameter data to enhance
    """
    # Check if old_value and new_value already exist and are not empty
    has_old = 'old_value' in param_data and param_data['old_value']
    has_new = 'new_value' in param_data and param_data['new_value']
    
    # If both exist, no need to do anything
    if has_old and has_new:
        return
    
    # Check for new-style fields first (new_details, old_details, etc.)
    if 'new_details' in param_data and 'old_details' in param_data:
        # Use details as the primary change value if available
        param_data['new_value'] = param_data['new_details']
        param_data['old_value'] = param_data['old_details']
    elif 'new_description' in param_data and 'old_description' in param_data:
        # Fall back to description
        param_data['new_value'] = param_data['new_description']
        param_data['old_value'] = param_data['old_description']
    elif 'new_name' in param_data and 'old_name' in param_data:
        # Last resort is name
        param_data['new_value'] = param_data['new_name']
        param_data['old_value'] = param_data['old_name']
    # If we only need one of the values, try to fill it
    elif not has_new:
        # For new value, use these fields in priority order
        if 'details' in param_data:
            param_data['new_value'] = param_data['details']
        elif 'description' in param_data:
            param_data['new_value'] = param_data['description']
        elif 'name' in param_data:
            param_data['new_value'] = param_data['name']
    
    # Last resort - extract from details field if available
    if (not has_old or not has_new) and 'details' in param_data:
        old_val, new_val = extract_values_from_details(param_data['details'])
        if not has_old and old_val:
            param_data['old_value'] = old_val
        if not has_new and new_val:
            param_data['new_value'] = new_val
    
    # Ensure fields exist even if empty
    if 'old_value' not in param_data:
        param_data['old_value'] = ""
    if 'new_value' not in param_data:
        param_data['new_value'] = ""

def extract_values_from_details(details):
    """Extract old and new values from a details string.
    
    Args:
        details (str): The details text to parse
        
    Returns:
        tuple: (old_value, new_value)
    """
    if not details or not isinstance(details, str):
        return None, None
    
    old_value = None
    new_value = None
    
    # Common patterns to look for:
    # Option 1: "Old Value: X, New Value: Y"
    if "Old Value:" in details and "New Value:" in details:
        try:
            split_old = details.split("Old Value:", 1)[1]
            old_part = split_old.split("New Value:", 1)[0].strip()
            if old_part.endswith(","):
                old_part = old_part[:-1].strip()
            old_value = old_part
            
            new_part = split_old.split("New Value:", 1)[1].strip()
            new_value = new_part
        except:
            pass
    
    # Option 2: "Changed from X to Y"
    elif "Changed from" in details and "to" in details:
        try:
            split_changed = details.split("Changed from", 1)[1]
            old_part = split_changed.split("to", 1)[0].strip()
            if old_part.endswith(","):
                old_part = old_part[:-1].strip()
            old_value = old_part
            
            new_part = split_changed.split("to", 1)[1].strip()
            new_value = new_part
        except:
            pass
    
    # Option 3: Try to extract from a detailed formatted text
    elif ":" in details:
        try:
            lines = details.split("\n")
            for i, line in enumerate(lines):
                if ":" in line and i < len(lines) - 1:
                    # Check if the next line might be a value
                    potential_old = lines[i+1].strip()
                    # And check if there's another line that might be new value
                    if i < len(lines) - 2 and lines[i+2].strip() and not ":" in lines[i+2]:
                        potential_new = lines[i+2].strip()
                        old_value = potential_old
                        new_value = potential_new
                        break
        except:
            pass
    
    return old_value, new_value

def check_parameter_changes(param_id, param_data):
    """Check if the submitted parameter data differs from existing data in the parameters collection.
    
    Args:
        param_id (str): Parameter ID
        param_data (dict): Parameter data to compare
        
    Returns:
        tuple: (has_changes, existing_data)
            has_changes (bool): True if there are differences, False if data is the same
            existing_data (dict): Existing parameter data if found, None otherwise
    """
    if not firebase or not current_user:
        return True, None  # Assume changes if we can't verify
    
    try:
        existing_data = None
        
        # Check existing parameter
        if firestore_db:
            # Search in parameters collection (approved parameters)
            param_ref = firestore_db.collection('parameters').where('param_id', '==', param_id).limit(1).get()
            
            if param_ref and len(param_ref) > 0:
                existing_data = param_ref[0].to_dict()
        else:
            # Using Realtime Database
            db = firebase.database()
            # Try to get the parameter
            param_data_ref = db.child('parameters').child(param_id).get(token=current_user['token'])
            if param_data_ref.val():
                existing_data = param_data_ref.val()
        
        # If no existing data, then this is a new parameter (has changes)
        if not existing_data:
            return True, None
        
        # Check for differences in important fields
        important_fields = ['name', 'description', 'details']
        
        for field in important_fields:
            # If the field exists in both and values are different
            if field in param_data and field in existing_data:
                # Compare stripped values to ignore whitespace differences
                new_value = str(param_data[field]).strip() if param_data[field] else ""
                existing_value = str(existing_data[field]).strip() if existing_data[field] else ""
                
                if new_value != existing_value:
                    return True, existing_data
        
        # If we reach here, no significant changes were found
        return False, existing_data
        
    except Exception as e:
        print(f"Error checking parameter changes: {str(e)}")
        return True, None  # If error, assume there are changes to be safe

# Initialize Firebase when module is imported
initialize() 