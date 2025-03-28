#!/usr/bin/env python3
"""
Clear details fields from all JSON parameter files in the vcm_descriptions directory.
This script preserves parameter names and descriptions but removes detailed information
for a clean slate.
"""

import os
import json

def clear_parameter_details(folder='vcm_descriptions'):
    """Remove 'details' field from all parameters in JSON files"""
    files_processed = 0
    parameters_cleared = 0
    
    # Walk through all files in the vcm_descriptions directory
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    # Load the JSON file
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    modified = False
                    
                    # Check parameters in the 'parameters' section
                    if 'parameters' in data:
                        for param_id in data['parameters']:
                            if 'details' in data['parameters'][param_id]:
                                del data['parameters'][param_id]['details']
                                parameters_cleared += 1
                                modified = True
                    
                    # Check for parameters at root level (inconsistent format)
                    for key in list(data.keys()):
                        if key not in ['name', 'description', 'parameters'] and isinstance(data[key], dict):
                            if 'details' in data[key]:
                                del data[key]['details']
                                parameters_cleared += 1
                                modified = True
                    
                    # Save the modified file if changes were made
                    if modified:
                        with open(file_path, 'w') as f:
                            json.dump(data, f, indent=2, sort_keys=True)
                        print(f"Cleared details from {file_path}")
                        files_processed += 1
                    
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
    
    print(f"\nSummary: Cleared {parameters_cleared} parameter details from {files_processed} files.")

if __name__ == "__main__":
    clear_parameter_details()
    print("All parameter details have been cleared.") 