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

def create_user_with_email_password(email, password):
    """Create a new user with email and password.
    
    Args:
        email (str): User's email
        password (str): User's password
        
    Returns:
        tuple: (success, message, user_data)
            success (bool): True if user creation was successful
            message (str): Success or error message
            user_data (dict): User data if successful, None otherwise
    """
    if not auth_instance:
        return False, "Firebase is not initialized", None
    
    try:
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
                firestore_db.collection('users').document(user_data['uid']).set({
                    'email': user_data['email'],
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'role': 'user',  # Default role
                    'trusted': False  # Not trusted by default
                })
                print(f"User profile created in Firestore successfully")
            else:
                print("Firestore not available, falling back to Realtime Database")
                # Add user to Realtime Database with basic profile
                if db_instance:
                    db_instance.child('users').child(user_data['uid']).set({
                        'email': user_data['email'],
                        'created_at': {".sv": "timestamp"},
                        'role': 'user',  # Default role
                        'trusted': False  # Not trusted by default
                    }, token=user_data['token'])
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
        # Add user info and timestamp to the data
        enriched_data = param_data.copy()
        enriched_data['updated_by'] = current_user.get('email', 'Unknown')
        
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
                
                # Don't append " - cloud saved" to details anymore, we're showing status in the UI
                
                # Check if parameter already exists
                param_ref = firestore_db.collection('parameters').where('param_id', '==', param_id).limit(1).get()
                
                if param_ref and len(param_ref) > 0:
                    # Update existing parameter
                    existing_param = param_ref[0]
                    firestore_db.collection('parameters').document(existing_param.id).update(enriched_data)
                    return True, f"Parameter {param_id} updated in parameters collection"
                else:
                    # Create new parameter
                    enriched_data['param_id'] = param_id  # Ensure param_id is in the document
                    enriched_data['approved_by'] = current_user.get('email', 'Unknown')
                    enriched_data['approved_at'] = firestore.SERVER_TIMESTAMP
                    firestore_db.collection('parameters').add(enriched_data)
                    return True, f"Parameter {param_id} added to parameters collection"
            else:
                # Regular users save to pending collection
                print(f"User is not admin, saving parameter {param_id} to pending collection...")
                
                # Don't append " - pending review" to details anymore, we're showing status in the UI
                
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
                
                # Don't append " - cloud saved" to details anymore, we're showing status in the UI
                
                # Add approval info for admins
                enriched_data['approved_by'] = current_user.get('email', 'Unknown')
                enriched_data['approved_at'] = {".sv": "timestamp"}
                
                db.child('parameters').child(param_id).set(enriched_data, token=current_user['token'])
                return True, f"Parameter {param_id} saved to parameters"
            else:
                # Regular users save to pending
                print(f"User is not admin, saving parameter {param_id} to pending node...")
                
                # Don't append " - pending review" to details anymore, we're showing status in the UI
                
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

# Initialize Firebase when module is imported
initialize() 