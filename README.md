# VCM Editor Overlay

An overlay application that provides custom descriptions for VCM Editor parameters based on selected ECM and TCM types.

## Features

- Automatically detects and attaches to VCM Editor windows
- Displays custom descriptions for parameters when you hover over them
- Supports multiple ECM and TCM types via selectable dropdown menus
- Description data stored in easy-to-edit JSON files
- Provides parameter name, description, and detailed information
- Translucent overlay stays on top but doesn't interfere with VCM Editor
- Movable overlay window with close button

## Setup

1. Make sure you have Python 3.6+ installed
2. Install the required dependencies:

```
pip install -r requirements.txt
```

3. Run the application:

```
python vcm_overlay.py
```

## Configuration

The application stores parameter descriptions in JSON files organized by ECM and TCM types.

### Directory Structure

```
vcm_descriptions/
├── ecmt.json           # Main configuration file
├── ECM/
│   ├── E38.json        # E38 parameter descriptions
│   └── E92.json        # E92 parameter descriptions
└── TCM/
    # TCM parameter descriptions (future)
```

### Adding Custom ECM Types

1. Create a new JSON file in the `vcm_descriptions/ECM/` directory, for example `MY_ECM.json`.
2. Use the following structure:

```json
{
    "name": "My ECM Type",
    "description": "Description of this ECM type",
    "parameters": {
        "12345": {
            "id": "12345",
            "name": "Parameter Name",
            "description": "Short description of parameter",
            "details": "Detailed information about the parameter"
        },
        // Add more parameters...
    }
}
```

3. Add your ECM type to the `ecmt.json` configuration file:

```json
{
    "ecm_types": [
        // existing types...
        {
            "id": "MY_ECM",
            "name": "My ECM Type",
            "file": "MY_ECM.json"
        }
    ],
    "tcm_types": [
        // tcm types...
    ]
}
```

## Implementation Notes

The application is designed to read the VCM Editor status bar to detect parameter IDs without using OCR. The current implementation includes:

- Window detection and positioning
- UI for parameter display
- Configuration loading
- Parameter lookup and display

For practical use, you'll need to adapt the screen reading mechanisms to match your specific VCM Editor version and layout.

## License

This project is for personal use and educational purposes. 