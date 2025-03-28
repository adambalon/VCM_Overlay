#!/usr/bin/env python3
"""
Parameter management module for VCM Overlay application.
Provides functions for loading, saving, and submitting parameter changes.
"""

import os
import json
import datetime
import uuid
import re

# Constants
WEB_DIR = "web"
DATA_DIR = os.path.join(WEB_DIR, "data")
ECM_FILE = os.path.join(DATA_DIR, "ecm.json")
TCM_FILE = os.path.join(DATA_DIR, "tcm.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending.json")

def get_ecm_type_from_text(parameter_text):
    """Extract the ECM type from the parameter text"""
    if not parameter_text:
        return None
    
    # Parse the ECM type from the parameter text
    # Format usually is [ECM] or [TCM] or [E38] etc.
    parts = parameter_text.split()
    if not parts:
        return None
    
    header = parts[0].strip("[]")
    
    # Handle TCM specifically
    if header == "TCM":
        return "tcm"  # Returned in lowercase for our new system
    
    # Extract ECM type
    if header == "ECM":
        # Look for E## in the text
        ecm_match = re.search(r'\b(E\d+)\b', parameter_text)
        if ecm_match:
            return "ecm"  # Simplified to just "ecm" for our new system
        return "ecm"  # Default to ecm if not specified
    
    # If it's already a specific ECM type like E38, E92, etc.
    if header.startswith("E") and len(header) <= 4:
        return "ecm"  # Simplified to just "ecm" for our new system
    
    return None

def load_parameter_file(param_type):
    """
    Load the parameter file for the specified type (ecm or tcm).
    Returns a tuple of (data, message).
    """
    if not param_type:
        return None, "No parameter type specified"
    
    try:
        # Determine file path based on parameter type
        if param_type.lower() == "tcm":
            file_path = TCM_FILE
        else:
            file_path = ECM_FILE
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Check if the file exists
        if not os.path.exists(file_path):
            # Create a new file with proper structure
            new_data = {
                "parameters": {}
            }
            with open(file_path, 'w') as f:
                json.dump(new_data, f, indent=2)
            return new_data, f"Created new file {file_path}"
        
        # Load the existing file
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Ensure proper structure exists
            if "parameters" not in data:
                data["parameters"] = {}
            
            # Count parameters
            param_count = len(data.get("parameters", {}))
            
            return data, f"Loaded {param_count} parameters from {file_path}"
    
    except json.JSONDecodeError:
        # If the file exists but is not valid JSON, initialize it
        new_data = {
            "parameters": {}
        }
        with open(file_path, 'w') as f:
            json.dump(new_data, f, indent=2)
        return new_data, f"Initialized empty JSON file {file_path}"
    
    except Exception as e:
        return None, f"Error loading parameter file: {str(e)}"

def save_parameter_file(param_type, data):
    """
    Save the parameter data to the JSON file.
    Returns a tuple of (success, message).
    """
    if not param_type:
        return False, "No parameter type specified"
    
    try:
        # Determine file path based on parameter type
        if param_type.lower() == "tcm":
            file_path = TCM_FILE
        else:
            file_path = ECM_FILE
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Format the JSON with indentation and sort keys for consistency
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        
        return True, f"Saved parameters to {file_path}"
    
    except Exception as e:
        return False, f"Error saving parameter file: {str(e)}"

def get_parameter_details(param_id, param_type):
    """
    Get parameter details from the JSON file.
    Returns tuple of (parameter_data, details_text).
    """
    if not param_id or not param_type:
        return None, None
    
    try:
        # Load the JSON file for the parameter type
        data, message = load_parameter_file(param_type)
        if data is None:
            return None, None
        
        # Check for parameter in parameters section
        if "parameters" in data and param_id in data["parameters"]:
            param_data = data["parameters"][param_id]
            return param_data, param_data.get("details", "")
            
        # Parameter not found
        return None, None
    
    except Exception as e:
        print(f"Error getting parameter details: {str(e)}")
        return None, None

def add_parameter(param_id, param_name, param_type):
    """
    Add a parameter to the JSON file if it doesn't exist.
    Returns a tuple of (success, message).
    """
    if not param_id or not param_name or not param_type:
        return False, "Missing parameter information"
    
    # Normalize parameter type
    param_type = param_type.lower()
    
    # Load the existing parameter file
    data, message = load_parameter_file(param_type)
    if data is None:
        return False, message
    
    # Check if the parameter already exists
    if "parameters" in data and param_id in data["parameters"]:
        return False, f"Parameter {param_id} already exists"
    
    # Add the parameter with minimal information
    if "parameters" not in data:
        data["parameters"] = {}
    
    data["parameters"][param_id] = {
        "name": param_name,
        "description": ""
        # No details field by default - allowing for manual entry only
    }
    
    # Save the updated file
    success, save_message = save_parameter_file(param_type, data)
    if success:
        return True, f"Added parameter {param_id} to {param_type}"
    else:
        return False, save_message

def update_parameter_details(param_id, details, param_type):
    """
    Update the details for an existing parameter.
    Returns a tuple of (success, message).
    """
    if not param_id or not param_type:
        return False, "Missing parameter information"
    
    # Normalize parameter type
    param_type = param_type.lower()
    
    # Load the existing parameter file
    data, message = load_parameter_file(param_type)
    if data is None:
        return False, message
    
    # Parse details from the text box format
    description = ""
    name = ""
    
    # Try to extract description and name from the details text
    lines = details.split('\n')
    for i, line in enumerate(lines):
        if line.startswith("Description:"):
            # Get the description (which might span multiple lines)
            desc_start = i
            desc_text = line[len("Description:"):].strip()
            
            # Collect additional lines until we hit another field or empty line
            for j in range(i+1, len(lines)):
                if not lines[j].strip() or lines[j].startswith("Full Text:"):
                    break
                desc_text += " " + lines[j].strip()
            
            description = desc_text
        elif line.startswith("Name:"):
            name = line[len("Name:"):].strip()
    
    # Look for parameter in parameters section
    if "parameters" in data and param_id in data["parameters"]:
        # Use existing name if not found in details
        if not name:
            name = data["parameters"][param_id].get("name", "")
        
        # Update the parameter
        data["parameters"][param_id]["description"] = description
        data["parameters"][param_id]["name"] = name
        data["parameters"][param_id]["details"] = details
    else:
        # Parameter doesn't exist, try to add it if we have enough information
        if name:
            # Add to parameters section
            if "parameters" not in data:
                data["parameters"] = {}
            
            data["parameters"][param_id] = {
                "name": name,
                "description": description,
                "details": details
            }
        else:
            return False, f"Parameter {param_id} not found in {param_type}"
    
    # Save the updated file
    success, save_message = save_parameter_file(param_type, data)
    if success:
        return True, f"Updated details for parameter {param_id} in {param_type}"
    else:
        return False, save_message

def submit_parameter_changes(param_id, param_name, param_type, details):
    """
    Submit parameter changes to the pending file for review.
    Returns a tuple of (success, message).
    """
    try:
        # Normalize parameter type
        param_type = param_type.lower()
        
        # Create a unique submission ID
        submission_id = f"{param_type}-{param_id}-{str(uuid.uuid4())[:8]}"
        
        # Create the submission data
        submission = {
            "id": submission_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": param_type,
            "param_id": param_id,
            "name": param_name,
            "description": "",  # Add description if available
            "details": details,
            "status": "pending"
        }
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
        
        # Load existing pending changes or create new structure
        if os.path.exists(PENDING_FILE):
            try:
                with open(PENDING_FILE, 'r') as f:
                    pending_data = json.load(f)
            except json.JSONDecodeError:
                pending_data = {"submissions": []}
        else:
            pending_data = {"submissions": []}
        
        # Add the new submission
        if "submissions" not in pending_data:
            pending_data["submissions"] = []
            
        pending_data["submissions"].append(submission)
        
        # Save the updated pending changes
        with open(PENDING_FILE, 'w') as f:
            json.dump(pending_data, f, indent=2, sort_keys=True)
        
        return True, f"Changes submitted for admin review. Your changes will be applied after review."
    except Exception as e:
        return False, f"Error submitting parameter changes: {str(e)}" 