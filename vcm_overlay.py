#!/usr/bin/env python3

"""

VCM Overlay Application



Provides a parameter detection and information display for VCM Editor.

Allows saving and managing parameter details in JSON format.

"""



import os

import sys

import ctypes

import traceback

import json

import subprocess

import re

from ctypes import wintypes

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 

                            QLabel, QPushButton, QTextEdit, QTabWidget, QLineEdit, 

                            QGroupBox, QGridLayout, QScrollArea, QSizeGrip, QSizePolicy)

from PyQt5.QtCore import QTimer, Qt, QEvent, QRect

from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QBrush, QTextCursor

import datetime

import uuid

import urllib.request

import urllib.error



# Define constants for parameter types
MODULE_TYPES = ["ECM", "TCM", "BCM", "PCM", "ICM", "OTHER"]
DEFAULT_MODULE_TYPE = "ECM"

# Global variables for Firebase state
FIREBASE_AVAILABLE = False
firebase_initialized = False

# Parameter types for user interface
PARAMETER_CATEGORIES = {
    "ECM": "Engine Control Module", 
    "TCM": "Transmission Control Module",
    "BCM": "Body Control Module",
    "PCM": "Powertrain Control Module",
    "ICM": "Instrument Control Module",
    "OTHER": "Other Module Types"
}



# ECM Parameter Management Functions
def get_ecm_type_from_text(text):
    """
    Extract module type from parameter text
    Returns the module type as a string (ECM, TCM, BCM, etc.)
    """
    if not text:
        return DEFAULT_MODULE_TYPE
        
    # Check for specific module types in the text
    if "TCM" in text.upper():
        return "TCM"
    elif "BCM" in text.upper():
        return "BCM"
    elif "PCM" in text.upper():
        return "PCM"
    elif "ICM" in text.upper():
        return "ICM"
    
    # Default to ECM for other parameters
    return "ECM"



def parse_parameter_text(text):

    """

    Parse parameter text to extract parameter ID, name, and ECM type

    Returns a tuple of (param_id, param_name, ecm_type)

    """

    if not text:

        return None, None, DEFAULT_MODULE_TYPE

        

    # Extract parameter ID using regex

    param_id_match = re.search(r'Parameter\s+#?(\d+)', text)

    if param_id_match:

        param_id = param_id_match.group(1)

    else:

        # Try alternative format

        param_id_match = re.search(r'#?(\d+)', text)

        if param_id_match:

            param_id = param_id_match.group(1)

        else:

            return None, None, DEFAULT_MODULE_TYPE

    

    # Extract parameter name (text after parameter ID)

    name_match = re.search(fr'Parameter\s+#?{param_id}\s+-\s+(.+?)(?:\r\n|\n|$)', text)

    if name_match:

        param_name = name_match.group(1).strip()

    else:

        # Use a default name if not found

        param_name = f"Parameter {param_id}"

    

    # Get ECM type

    ecm_type = get_ecm_type_from_text(text)

    

    return param_id, param_name, ecm_type



# Windows API constants and helper functions
user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)



# Constants
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E



# Setup Windows API function argument and return types
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND



def get_window_text(hwnd):

    """Get text from a window handle"""

    length = user32.GetWindowTextLengthW(hwnd) + 1

    buffer = ctypes.create_unicode_buffer(length)

    user32.GetWindowTextW(hwnd, buffer, length)

    return buffer.value



def get_class_name(hwnd):

    """Get class name from a window handle"""

    buffer = ctypes.create_unicode_buffer(256)

    user32.GetClassNameW(hwnd, buffer, 256)

    return buffer.value



def get_edit_text(hwnd):

    """Get text from an edit control"""

    length = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0) + 1

    buffer = ctypes.create_unicode_buffer(length)

    user32.SendMessageW(hwnd, WM_GETTEXT, length, ctypes.addressof(buffer))

    return buffer.value



class VCMOverlay(QMainWindow):

    """Main application window for VCM Parameter ID Monitor"""

    def __init__(self):

        super().__init__()

        self.parameter_edit_control = None

        self.detection_enabled = False

        self.debug_window = None

        self.last_parameter_text = ""

        

        # Allow resizing while keeping frameless and on top

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self.setAttribute(Qt.WA_TranslucentBackground)  # Needed for rounded corners

        

        # For window dragging and resizing

        self.dragging = False

        self.resizing = False

        self.drag_position = None

        self.resize_corner_size = 20

        

        # Green dot blinking for status indicator

        self.status_dot_visible = True

        self.blink_timer = QTimer()

        self.blink_timer.timeout.connect(self.toggle_status_dot)

        self.blink_timer.start(500)  # Blink every 500ms

        

        self.initUI()

        self.log_debug("VCMOverlay window created")

        

    def toggle_status_dot(self):

        """Toggle the status dot visibility to create blinking effect"""

        self.status_dot_visible = not self.status_dot_visible

        if hasattr(self, 'status_indicator'):

            if self.status_dot_visible:

                self.status_indicator.setStyleSheet("background-color: #00FF00; border-radius: 5px;")

            else:

                self.status_indicator.setStyleSheet("background-color: #003300; border-radius: 5px;")

        

    def initUI(self):

        """Initialize the main UI"""

        self.setWindowTitle("VCM Parameter Monitor")

        

        # Position in top right of screen - calculate position based on screen size

        screen_geometry = QApplication.desktop().availableGeometry()

        self.setGeometry(screen_geometry.width() - 520, 20, 500, 550)  # Increased height to 550

        self.setMinimumSize(400, 450)  # Increased minimum height to 450

        

        # Create an inner container with rounded corners

        self.setStyleSheet("""

            QMainWindow {

                background: transparent;

            }

        """)

        

        # Main widget and layout

        central_widget = QWidget()

        central_widget.setObjectName("centralWidget")

        central_widget.setStyleSheet("""

            #centralWidget {

                background-color: #000000;

                border: 1px solid #222222;

                border-radius: 12px;

            }

            QLabel {

                color: #CCCCCC;

                font-size: 9pt;

            }

            QPushButton {

                background-color: #222222;

                color: #FFFFFF;

                border: none;

                padding: 5px 10px;

                border-radius: 6px;

                font-size: 8pt;

                font-weight: bold;

            }

            QPushButton:hover {

                background-color: #333333;

                color: #FFFFFF;

            }

            QPushButton:pressed {

                background-color: #111111;

            }

            QTextEdit {

                background-color: #111111;

                color: #CCCCCC;

                border: 1px solid #222222;

                border-radius: 6px;

                font-family: Consolas, monospace;

            }

            #closeButton {

                background-color: transparent;

                color: #777777;

                font-weight: bold;

                border: none;

                padding: 0px;

                font-size: 12px;

                min-width: 18px;

                min-height: 18px;

            }

            #closeButton:hover {

                background-color: #444444;

                color: white;

                border-radius: 9px;

            }

            #titleBar {

                background: #111111;

                border-top-left-radius: 12px;

                border-top-right-radius: 12px;

                height: 30px;

                border-bottom: 1px solid #222222;

            }

            #resizeGrip {

                background: transparent;

                image: url('resize-grip.png');

            }

            QFrame#divider {

                background-color: #222222;

            }

        """)

        

        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(8)

        

        # Title bar with close button and status indicator

        title_bar = QWidget()

        title_bar.setObjectName("titleBar")

        title_bar_layout = QHBoxLayout(title_bar)

        title_bar_layout.setContentsMargins(12, 0, 12, 0)

        

        # Status indicator (green dot)

        self.status_indicator = QLabel()

        self.status_indicator.setFixedSize(10, 10)

        self.status_indicator.setStyleSheet("background-color: #00FF00; border-radius: 5px;")

        title_bar_layout.addWidget(self.status_indicator)

        

        title_label = QLabel("VCM PARAMETER MONITOR")

        title_label.setStyleSheet("font-weight: bold; font-size: 9pt; color: #AAAAAA;")

        title_bar_layout.addWidget(title_label)

        

        title_bar_layout.addStretch()

        

        # Add window controls

        min_button = QPushButton("–")

        min_button.setObjectName("minButton")

        min_button.setStyleSheet("background: transparent; color: #777777; font-weight: bold;")

        min_button.setFixedSize(18, 18)

        min_button.clicked.connect(self.showMinimized)

        title_bar_layout.addWidget(min_button)

        

        close_button = QPushButton("✕")

        close_button.setObjectName("closeButton")

        close_button.setStyleSheet("""

            QPushButton#closeButton {

                background-color: transparent;

                color: #777777;

                font-weight: bold;

                border: none;

                border-radius: 9px;

                padding: 0px;

                font-size: 12px;

            }

            QPushButton#closeButton:hover {

                background-color: #FF4444;

                color: white;

                border-radius: 9px;

            }

        """)

        close_button.clicked.connect(self.close)

        close_button.setFixedSize(18, 18)

        title_bar_layout.addWidget(close_button)

        

        main_layout.addWidget(title_bar)

        

        # Content area with padding

        content_widget = QWidget()

        content_layout = QVBoxLayout(content_widget)

        content_layout.setContentsMargins(12, 4, 12, 12)

        content_layout.setSpacing(10)

        

        # Parameter display

        param_group = QWidget()

        param_group.setObjectName("paramGroup")

        param_group.setStyleSheet("""

            #paramGroup {

                background-color: #111111;

                border: 1px solid #222222;

                border-radius: 8px;

            }

        """)

        param_layout = QVBoxLayout(param_group)

        param_layout.setContentsMargins(10, 10, 10, 10)

        param_layout.setSpacing(3)  # Reduced spacing for tighter packing

        

        # Parameter header display

        param_header_container = QWidget()

        param_header_container.setObjectName("paramHeader")

        param_header_container.setStyleSheet("""

            #paramHeader {

                background: #181818;

                border: 1px solid #222222;

                border-radius: 6px;

            }

        """)

        param_header_layout = QHBoxLayout(param_header_container)

        param_header_layout.setContentsMargins(8, 3, 8, 3)  # Reduced vertical padding

        

        self.parameter_header_label = QLabel("NO PARAMETER DETECTED")

        self.parameter_header_label.setAlignment(Qt.AlignCenter)

        self.parameter_header_label.setStyleSheet("""

            font-size: 10pt; 

            font-weight: bold; 

            color: #AAAAAA;

        """)

        param_header_layout.addWidget(self.parameter_header_label)

        

        param_layout.addWidget(param_header_container)

        

        # Parameter details container

        details_container = QWidget()

        details_container.setObjectName("detailsContainer")

        details_container.setStyleSheet("""

            #detailsContainer {

                background-color: transparent;

            }

        """)

        

        param_details_layout = QGridLayout(details_container)

        param_details_layout.setVerticalSpacing(3)  # Reduced spacing for tighter packing

        param_details_layout.setHorizontalSpacing(10)

        param_details_layout.setContentsMargins(5, 5, 5, 5)  # Reduced margins

        param_details_layout.setColumnStretch(1, 1)

        

        # Add labels for parameter fields with simplified styling

        label_style = "color: #777777; font-size: 9pt; font-weight: bold;"

        value_style = "font-size: 9.5pt; color: #CCCCCC;"

        

        # Reposition all labels to the top by changing the row order

        row = 0  # Start from row 0

        

        param_details_layout.addWidget(QLabel("TYPE:"), row, 0)

        self.param_type_label = QLabel("")

        self.param_type_label.setStyleSheet(f"{value_style}")

        param_details_layout.addWidget(self.param_type_label, row, 1)

        row += 1

        

        param_details_layout.addWidget(QLabel("ID:"), row, 0)

        self.param_id_label = QLabel("")

        self.param_id_label.setStyleSheet(f"{value_style}")

        param_details_layout.addWidget(self.param_id_label, row, 1)

        row += 1

        

        param_details_layout.addWidget(QLabel("NAME:"), row, 0)

        self.param_name_label = QLabel("")

        self.param_name_label.setStyleSheet(f"{value_style}")

        self.param_name_label.setWordWrap(True)  # Enable word wrap

        self.param_name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        param_details_layout.addWidget(self.param_name_label, row, 1)

        row += 1

        

        param_details_layout.addWidget(QLabel("DESC:"), row, 0)

        self.param_desc_label = QLabel("")

        self.param_desc_label.setStyleSheet(f"{value_style}")

        self.param_desc_label.setWordWrap(True)  # Enable word wrap

        self.param_desc_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.param_desc_label.setMinimumHeight(30)  # Set minimum height for description

        param_details_layout.addWidget(self.param_desc_label, row, 1)

        

        # Style the label columns

        for i in range(param_details_layout.rowCount()):

            label_item = param_details_layout.itemAtPosition(i, 0)

            if label_item and label_item.widget():

                label_item.widget().setStyleSheet(label_style)

                label_item.widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        

        # Add the parameter info container to the param layout

        param_layout.addWidget(details_container)

        

        # Create a separate container for the details field

        details_field_container = QWidget()

        details_field_container.setObjectName("detailsFieldContainer")

        details_field_container.setStyleSheet("""

            #detailsFieldContainer {

                background-color: #111111;

                border: 1px solid #222222;

                border-radius: 8px;

            }

        """)

        details_field_layout = QVBoxLayout(details_field_container)

        details_field_layout.setContentsMargins(10, 10, 10, 10)

        details_field_layout.setSpacing(3)

        

        # Add a label for the details field

        details_header = QWidget()

        details_header.setObjectName("detailsHeader")

        details_header.setStyleSheet("""

            #detailsHeader {

                background: #181818;

                border: 1px solid #222222;

                border-radius: 6px;

            }

        """)

        details_header_layout = QHBoxLayout(details_header)

        details_header_layout.setContentsMargins(8, 3, 8, 3)

        

        details_label = QLabel("PARAMETER DETAILS")

        details_label.setAlignment(Qt.AlignCenter)

        details_label.setStyleSheet("""

            font-size: 10pt; 

            font-weight: bold; 

            color: #AAAAAA;

        """)

        details_header_layout.addWidget(details_label)

        

        details_field_layout.addWidget(details_header)

        

        # Create an editable text box for the details field

        self.param_details_text = QTextEdit()

        self.param_details_text.setStyleSheet("""

            background-color: #181818;

            color: #CCCCCC;

            border: 1px solid #222222;

            border-radius: 6px;

            font-family: Consolas, monospace;

            font-size: 9.5pt;

            padding: 5px;

        """)

        self.param_details_text.setMinimumHeight(200)  # Make it quite tall

        details_field_layout.addWidget(self.param_details_text)

        

        # Create Git button group

        git_button_group = QGroupBox("Parameter Management")

        git_button_group.setStyleSheet("""

            QGroupBox {

                border: none;

                margin-top: 12px;

                color: #888888;

                font-size: 8pt;

            }

            QGroupBox::title {

                subcontrol-origin: margin;

                left: 10px;

            }

        """)

        git_button_layout = QHBoxLayout(git_button_group)

        

        # Save Details button

        self.git_save_button = QPushButton("SAVE DETAILS")

        self.git_save_button.clicked.connect(self.save_parameter_details)

        self.git_save_button.setToolTip("Save parameter details to local JSON file")

        self.git_save_button.setStyleSheet("""

            QPushButton {

                background-color: #222222;

                color: #FFFFFF;

                border: none;

                padding: 8px 15px;

                border-radius: 6px;

                font-size: 8pt;

                font-weight: bold;

            }

            QPushButton:hover {

                background-color: #333333;

                color: #FFFFFF;

            }

            QPushButton:pressed {

                background-color: #111111;

            }

        """)

        git_button_layout.addWidget(self.git_save_button)

        

        # Check Status button

        self.check_status_button = QPushButton("CHECK STATUS")

        self.check_status_button.clicked.connect(self.check_parameter_status)

        self.check_status_button.setToolTip("Check the status of this parameter")

        self.check_status_button.setStyleSheet("""

            QPushButton {

                background-color: #333366;

                color: #FFFFFF;

                border: none;

                padding: 8px 15px;

                border-radius: 6px;

                font-size: 8pt;

                font-weight: bold;

            }

            QPushButton:hover {

                background-color: #444488;

                color: #FFFFFF;

            }

            QPushButton:pressed {

                background-color: #222244;

            }

        """)

        git_button_layout.addWidget(self.check_status_button)

        

        # Add the button group to the layout

        details_field_layout.addWidget(git_button_group)

        

        # Add status label

        self.git_status_label = QLabel("")

        self.git_status_label.setStyleSheet("color: #AAAAAA; font-size: 8pt;")

        self.git_status_label.setWordWrap(True)

        self.git_status_label.setAlignment(Qt.AlignLeft)

        details_field_layout.addWidget(self.git_status_label)

        

        content_layout.addWidget(param_group, 1)  # Give parameter group a stretch factor of 1

        content_layout.addWidget(details_field_container, 3)  # Give details field a higher stretch factor

        content_layout.addStretch(0)  # Minimal stretch after components to minimize empty space

        

        # Button row with rounded style

        button_container = QWidget()

        button_container.setObjectName("buttonContainer")

        button_container.setStyleSheet("""

            #buttonContainer {

                background: #111111;

                border: 1px solid #222222;

                border-radius: 8px;

            }

        """)

        button_layout = QHBoxLayout(button_container)

        button_layout.setSpacing(10)

        button_layout.setContentsMargins(10, 5, 10, 5)

        

        self.enable_detection_button = QPushButton("ENABLE DETECTION")

        self.enable_detection_button.clicked.connect(self.enable_parameter_detection)

        button_layout.addWidget(self.enable_detection_button)

        

        debug_button = QPushButton("DEBUG")

        debug_button.clicked.connect(self.open_debug_window)

        button_layout.addWidget(debug_button)

        

        content_layout.addWidget(button_container)

        

        # Status bar

        status_container = QWidget()

        status_container.setObjectName("statusContainer")

        status_container.setStyleSheet("""

            #statusContainer {

                background: #111111;

                border: 1px solid #222222;

                border-radius: 8px;

            }

        """)

        status_layout = QHBoxLayout(status_container)

        status_layout.setContentsMargins(10, 3, 10, 3)

        

        self.status_label = QLabel("READY")

        self.status_label.setStyleSheet("color: #777777; font-size: 8pt;")

        status_layout.addWidget(self.status_label)

        

        status_layout.addStretch()

        

        # Corner resize grip

        resize_grip = QSizeGrip(status_container)

        resize_grip.setFixedSize(16, 16)

        status_layout.addWidget(resize_grip)

        

        content_layout.addWidget(status_container)

        

        main_layout.addWidget(content_widget)

        

        # Timer for parameter checking

        self.timer = QTimer()

        self.timer.timeout.connect(self.check_parameter_edit_control)



        # Debug log

        self.debug_log = []

        

        # Create a dummy QLabel for Value to avoid breaking code elsewhere

        self.param_value_label = QLabel("")

        self.param_value_label.hide()



    def mousePressEvent(self, event):

        """Handle mouse press for dragging and resizing"""

        if event.button() == Qt.LeftButton:

            # Check if we're in the resize corner

            bottom_right = self.rect().bottomRight()

            rect = QRect(bottom_right.x() - self.resize_corner_size, 

                        bottom_right.y() - self.resize_corner_size,

                        self.resize_corner_size, self.resize_corner_size)

            

            if rect.contains(event.pos()):

                self.resizing = True

                self.drag_position = event.globalPos()

                self.old_size = self.size()

                self.setCursor(Qt.SizeFDiagCursor)

            else:

                # For dragging the window

                self.dragging = True

                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()

                self.setCursor(Qt.ClosedHandCursor)

            

            event.accept()

            

    def mouseReleaseEvent(self, event):

        """Handle mouse release for dragging and resizing"""

        if event.button() == Qt.LeftButton:

            self.dragging = False

            self.resizing = False

            self.setCursor(Qt.ArrowCursor)

            event.accept()

            

    def mouseMoveEvent(self, event):

        """Handle mouse move for dragging and resizing"""

        if self.dragging and event.buttons() == Qt.LeftButton:

            self.move(event.globalPos() - self.drag_position)

            event.accept()

        elif self.resizing and event.buttons() == Qt.LeftButton:

            # Calculate new size

            delta = event.globalPos() - self.drag_position

            new_width = max(self.minimumWidth(), self.old_size.width() + delta.x())

            new_height = max(self.minimumHeight(), self.old_size.height() + delta.y())

            self.resize(new_width, new_height)

            event.accept()



    def log_debug(self, message):

        """Log debug message to console and debug window"""

        print(message)

        self.debug_log.append(message)

        if hasattr(self, 'debug_text') and self.debug_text:

            self.debug_text.append(message)

    

    def get_window_rect(self, hwnd):

        """Get the rectangle coordinates for a window"""

        rect = wintypes.RECT()

        result = user32.GetWindowRect(hwnd, ctypes.byref(rect))

        if result:

            return rect

        return None



    def open_debug_window(self):

        """Open the debug window"""

        self.log_debug("Debug window is not available in this version")

        self.status_label.setText("DEBUG MODE NOT AVAILABLE")



    def enable_parameter_detection(self):

        """Enable automatic parameter detection"""

        if not self.timer.isActive():

            self.log_debug("Parameter detection activated")

            self.parameter_header_label.setText("Searching for parameters...")

            self.status_label.setText("SEARCHING FOR PARAMETERS...")

            self.detection_enabled = True

            self.auto_detect_parameter_edit_control()  # Start by auto-detecting

            self.timer.start(100)  # Check every 100ms

            self.enable_detection_button.setText("DISABLE DETECTION")

        else:

            self.log_debug("Parameter detection deactivated")

            self.status_label.setText("DETECTION DISABLED")

            self.detection_enabled = False

            self.timer.stop()

            self.enable_detection_button.setText("ENABLE DETECTION")

    

    def update_parameter_info(self, text):

        """Update the parameter information display with extended fields"""

        if not text or text == self.last_parameter_text:

            return  # Don't update if no change

        

        self.last_parameter_text = text

        self.status_label.setText("PARAMETER DETECTED")

        

        # Display the raw parameter text header (either ECM or TCM)

        header_part = text.split()[0] if text.split() else ""

        self.parameter_header_label.setText(header_part)

        

        # Clear all labels but set a fixed height to prevent layout shifts

        self.param_type_label.setText("")

        self.param_id_label.setText("")

        self.param_name_label.setText("")

        # self.param_value_label.setText("")  # Keep this to avoid breaking code but field is hidden

        self.param_desc_label.setText("")

        self.param_details_text.clear()  # Clear the details text box

        self.git_status_label.setText("")  # Clear git status message

        

        # Extract specific parts

        try:

            # Extract Type (ECM/TCM)

            param_type = header_part.strip("[]") if header_part else ""

            self.param_type_label.setText(param_type)

            

            # Parse format: [ECM] 12600 - Main Spark vs. Airmass vs. RPM Open Throttle, High Octane: This is the High Octane spark...

            parts = text.split(None, 2)  # Split at most twice to get: ['[ECM]', '12600', '- Main Spark vs...']

            

            # Get ECM type for the JSON file

            ecm_type = get_ecm_type_from_text(text)

            

            # Extract ID (number after type)

            param_id = None

            if len(parts) >= 2:

                id_part = parts[1].strip()

                # Extract only the numeric part if there are non-numeric characters

                import re

                id_match = re.match(r'(\d+)', id_part)

                if id_match:

                    param_id = id_match.group(1)

                    self.param_id_label.setText(param_id)

            

            # Extract Name and Description (split by colon)

            param_name = ""

            param_desc = ""

            if len(parts) >= 3:

                remainder = parts[2].strip()

                

                # Check if there's a colon that separates name and description

                if ':' in remainder:

                    name_part, desc_part = remainder.split(':', 1)

                    

                    # If name starts with a dash and space, remove it

                    if name_part.startswith('- '):

                        name_part = name_part[2:]

                    elif name_part.startswith('-'):

                        name_part = name_part[1:]

                    

                    param_name = name_part.strip()

                    param_desc = desc_part.strip()

                    self.param_name_label.setText(param_name)

                    self.param_desc_label.setText(param_desc)

                else:

                    # No description, just name

                    name_part = remainder

                    if name_part.startswith('- '):

                        name_part = name_part[2:]

                    elif name_part.startswith('-'):

                        name_part = name_part[1:]

                    

                    param_name = name_part.strip()

                    self.param_name_label.setText(param_name)

            

            # Check if this parameter already exists in the JSON file

            # and try to get details from the JSON file (but don't automatically pull)

            if ecm_type and param_id:

                # Get the parameter data from the JSON file without Git operations

                param_data, stored_details = get_parameter_details_from_json(param_id, ecm_type)

                

                if param_data:

                    # Update the UI with the stored parameter data

                    stored_name = param_data.get("name", "")

                    stored_desc = param_data.get("description", "")

                    

                    # Use stored values if they exist and are more detailed

                    if stored_name and (not param_name or len(stored_name) > len(param_name)):

                        param_name = stored_name

                        self.param_name_label.setText(stored_name)

                    

                    if stored_desc and (not param_desc or len(stored_desc) > len(param_desc)):

                        param_desc = stored_desc

                        self.param_desc_label.setText(stored_desc)

                    

                    # If we have stored details, use those (but NEVER generate new ones)

                    if stored_details:

                        self.param_details_text.setText(stored_details)

                        self.log_debug(f"Loaded parameter details from JSON for {param_id}")

                    # Leave details empty otherwise - no auto-generated content

                

                # Try to automatically add the parameter if it's not in the JSON file and we have a name

                if param_name:

                    self.try_add_parameter_to_json(param_id, param_name, ecm_type)

            

            # Update the param info text in the debug window

            if hasattr(self, 'param_info_text') and self.param_info_text:

                formatted_info = f"""Type: {self.param_type_label.text()}

ID: {self.param_id_label.text()}

Name: {self.param_name_label.text()}

Description: {self.param_desc_label.text()}

Details: {self.param_details_text.toPlainText()}"""

                self.param_info_text.setText(formatted_info)

                

        except Exception as e:

            self.log_debug(f"Error parsing parameter text: {str(e)}")

            self.status_label.setText("ERROR PARSING PARAMETER")

            

    def try_add_parameter_to_json(self, param_id, param_name, ecm_type):
        """Try to add the parameter to the appropriate JSON file"""
        if not param_id:
            return
        
        # Add parameter to the JSON file
        if add_parameter_to_json(param_id, param_name, ecm_type):
            print(f"Added parameter {param_id} to {ecm_type.lower()}")
        else:
            print(f"Parameter not added: Parameter {param_id} already exists in {ecm_type.lower()}")
    

    def save_parameter_details(self):

        """Save the current parameter details to the local JSON file"""

        param_id = self.param_id_label.text().strip()

        current_details = self.param_details_text.toPlainText().strip()

        

        if not param_id:

            self.git_status_label.setText("⚠ No parameter selected")

            return

        

        ecm_type = get_ecm_type_from_text(self.last_parameter_text)

        

        # Update the parameter

        success, message = update_parameter_details(param_id, current_details, ecm_type)

        

        if success:

            self.git_status_label.setText(f"✅ Parameter details saved locally")

            # Add to git staging area

            try:

                git_add_and_commit(f"data/{ecm_type.lower()}.json", f"Updated parameter {param_id}")

                self.log_debug(f"Updated parameter {param_id} and committed to Git")

            except Exception as e:

                self.log_debug(f"Updated parameter {param_id} but Git commit failed: {str(e)}")

        else:

            self.git_status_label.setText(f"⚠ Error saving: {message}")



    def check_parameter_status(self):

        """Check the status of the current parameter"""

        param_id = self.param_id_label.text().strip()

        if not param_id:

            self.git_status_label.setText("⚠ No parameter selected")

            return

            

        current_details = self.param_details_text.toPlainText()

        

        # First check if there's any status indicator in the text

        if " - Approved" in current_details:

            # Set approved style

            self.mark_as_approved(param_id, get_ecm_type_from_text(self.last_parameter_text))

            self.git_status_label.setText("✅ This parameter has been approved")

            return

            

        if " - Rejected" in current_details:

            # Set rejected style

            self.param_details_text.setStyleSheet("""

                QTextEdit {

                    background-color: #111111;

                    color: #FF5555; /* Red color for rejected */

                    border: 1px solid #222222;

                    border-radius: 6px;

                    font-family: Consolas, monospace;

                }

            """)

            self.git_status_label.setText("❌ This parameter has been rejected")

            return

            

        # No status indicator

        self.git_status_label.setText("📝 Parameter details saved locally")



    def mark_as_approved(self, param_id, ecm_type):

        """Mark the current parameter as approved"""

        # Update the details text area styling

        self.param_details_text.setStyleSheet("""

            QTextEdit {

                background-color: #111111;

                color: #55FF55; /* Green color for approved */

                border: 1px solid #222222;

                border-radius: 6px;

                font-family: Consolas, monospace;

            }

        """)

        self.log_debug(f"Parameter {param_id} marked as approved")



    def monitor_parameter_text(self):

        """Poll the parameter edit control for changes"""

        if not self.detection_enabled:

            return

            

        try:

            if not self.parameter_edit_control or not user32.IsWindow(self.parameter_edit_control):

                self.parameter_edit_control = None  # Mark as invalid

                return

                

            # Get the current text

            try:

                text = get_edit_text(self.parameter_edit_control)

            except Exception as e:

                self.log_debug(f"Failed to get text from edit control: {str(e)}")

                return

                

            # Check if the text changed

            if text != self.last_parameter_text:

                self.log_debug("Parameter text changed")

                self.last_parameter_text = text

                

                # Only process valid parameter text

                if self.is_parameter_text(text):

                    # Parse the parameter text

                    parsed_data = parse_parameter_text(text)

                    

                    if parsed_data:

                        # Use our new method to update the display and check for pending/approved status

                        self.update_parameter_display({

                            "text": text,

                            "param_id": parsed_data[0],

                            "param_name": parsed_data[1]

                        })

                        

                        # Try to add the parameter to the JSON file if it doesn't exist

                        try:

                            param_id = parsed_data[0]

                            param_name = parsed_data[1]

                            ecm_type = get_ecm_type_from_text(text)

                            

                            success, message = add_parameter_to_json(param_id, param_name, ecm_type)

                            if success:

                                self.log_debug(f"Added parameter: {message}")

                            else:

                                self.log_debug(message)  # Parameter already exists

                        except Exception as e:

                            self.log_debug(f"Error adding parameter to JSON: {str(e)}")

                    else:

                        self.log_debug("Could not parse parameter text")

                else:

                    self.log_debug("Text doesn't appear to be parameter text")

                    

        except Exception as e:

            self.log_debug(f"Error in monitor_parameter_text: {str(e)}")



    def check_parameter_edit_control(self):

        """Check if the parameter edit control is valid and update the UI"""

        if self.parameter_edit_control:

            try:

                # Check if handle is valid

                if not user32.IsWindow(self.parameter_edit_control):

                    self.log_debug(f"Edit control {self.parameter_edit_control} is not a valid window")

                    self.parameter_header_label.setText("No parameter detected - searching...")

                    self.auto_detect_parameter_edit_control()

                    return

                

                # Get text from edit control

                text = get_edit_text(self.parameter_edit_control)

                if self.is_parameter_text(text):

                    # Parse and display parameter information

                    self.update_parameter_info(text)

                    self.update_title_handle_indicator(self.parameter_edit_control, True)

                else:

                    self.log_debug(f"Edit control {self.parameter_edit_control} does not contain parameter text")

                    self.parameter_header_label.setText("Invalid parameter format - searching...")

                    self.auto_detect_parameter_edit_control()

            except Exception as e:

                self.log_debug(f"Error in check_parameter_edit_control: {str(e)}")

                self.parameter_header_label.setText("Error checking parameter - searching...")

                self.auto_detect_parameter_edit_control()

        else:

            self.log_debug("No parameter edit control set - auto-detecting...")

            self.auto_detect_parameter_edit_control()

            

    def auto_detect_parameter_edit_control(self):

        """Auto-detect the parameter edit control by looking for text starting with [ECM] or [TCM]"""

        try:

            # Find VCM Editor window

            vcm_editor_hwnd = self.find_vcm_editor_window()

            if not vcm_editor_hwnd:

                self.log_debug("Could not find VCM Editor window")

                return

                

            # Find edit controls in VCM Editor window

            edit_controls = self.find_edit_controls(vcm_editor_hwnd)

            

            # Check each edit control for parameter text

            for control in edit_controls:

                try:

                    text = get_edit_text(control)

                    if self.is_parameter_text(text):

                        self.log_debug(f"Found parameter edit control: {control}")

                        self.update_handle_number(control)

                        self.update_handle_status()

                        return

                except Exception as e:

                    self.log_debug(f"Error checking edit control {control}: {str(e)}")

                    continue

            

            self.log_debug("Could not find parameter edit control")

            self.parameter_header_label.setText("No parameter detected - please set manually")

        except Exception as e:

            self.log_debug(f"Error in auto_detect_parameter_edit_control: {str(e)}")

            

    def update_handle_number(self, handle_num):

        """Update the parameter edit control handle number"""

        old_handle = self.parameter_edit_control

        self.parameter_edit_control = handle_num

        

        if handle_num != old_handle:

            self.log_debug(f"Parameter detection activated - monitoring edit control {handle_num}")

        

        # Update handle info in debug window if it's open

        if hasattr(self, 'handle_number_label') and self.handle_number_label:

            self.handle_number_label.setText(f"Current handle: {handle_num}")

            

    def update_handle_status(self):

        """Update the handle status in the debug window"""

        if hasattr(self, 'handle_status_label') and self.handle_status_label:

            if self.parameter_edit_control:

                if user32.IsWindow(self.parameter_edit_control):

                    self.handle_status_label.setText("Status: Valid")

                    self.handle_status_label.setStyleSheet("color: #00FF00; font-weight: bold;")

                else:

                    self.handle_status_label.setText("Status: Invalid")

                    self.handle_status_label.setStyleSheet("color: #FF5555; font-weight: bold;")

            else:

                self.handle_status_label.setText("Status: Not Set")

                self.handle_status_label.setStyleSheet("color: #AAAAAA; font-weight: bold;")

                

    def update_title_handle_indicator(self, handle, is_valid=False):

        """Update the window title to show current handle and status"""

        try:

            status = "✓" if is_valid else "✗"

            title = f"VCM Parameter ID Monitor - Handle: {handle} {status}"

            self.setWindowTitle(title)

        except Exception as e:

            self.log_debug(f"Error updating title: {str(e)}")

            

    def find_vcm_editor_window(self):

        """Find the VCM Editor window by title"""

        result = [None]

        

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, lParam):

            try:

                window_text = get_window_text(hwnd)

                if window_text and "VCM Editor" in window_text:

                    result[0] = hwnd

                    return False  # Stop enumeration

            except Exception as e:

                self.log_debug(f"Error in enum_windows_callback: {str(e)}")

            return True

        

        try:

            user32.EnumWindows(enum_windows_callback, 0)

        except Exception as e:

            self.log_debug(f"Error in EnumWindows: {str(e)}")

            

        return result[0]

        

    def find_edit_controls(self, parent_hwnd, max_depth=5, current_depth=0):

        """Find all edit controls in a parent window with depth limit"""

        if current_depth > max_depth:

            return []

            

        edit_controls = []

        seen_handles = set()  # Track seen handles to avoid duplicates

        

        # Define callback function for EnumChildWindows

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_child_proc(hwnd, lParam):

            try:

                if hwnd in seen_handles:

                    return True  # Skip if already seen

                    

                seen_handles.add(hwnd)

                class_name = get_class_name(hwnd)

                

                # Check if it's an edit control

                if "edit" in class_name.lower():

                    edit_controls.append(hwnd)

                    

                    # Try to get text to see if it's a parameter control (prioritize these)

                    try:

                        text = get_edit_text(hwnd)

                        if text and (text.startswith('[ECM]') or text.startswith('[TCM]')):

                            # Move this to the front as it's likely what we want

                            edit_controls.remove(hwnd)

                            edit_controls.insert(0, hwnd)

                    except:

                        pass

                

                # Recursively check child windows

                child_controls = self.find_edit_controls(hwnd, max_depth, current_depth + 1)

                edit_controls.extend(child_controls)

            except Exception as e:

                self.log_debug(f"Error in enum_child_proc: {str(e)}")

                

            return True

            

        try:

            # Enumerate child windows

            user32.EnumChildWindows(parent_hwnd, enum_child_proc, 0)

        except Exception as e:

            self.log_debug(f"Error in EnumChildWindows: {str(e)}")

            

        return edit_controls



    def parse_parameter_text(self, text):

        """Parse parameter text to extract parameter ID and name"""

        if not text:

            return None

            

        try:

            return parse_parameter_text(text)[:2]  # Return just id and name

        except Exception as e:

            self.log_debug(f"Error parsing parameter text: {str(e)}")

            return None



    def is_parameter_text(self, text):

        """Check if text contains parameter information (starts with [ECM] or [TCM])"""

        if text and isinstance(text, str):

            return text.startswith('[ECM]') or text.startswith('[TCM]')

        return False



# JSON and Git Operations Functions

def load_parameter_file(ecm_type):
    """
    Load parameter data from a JSON file
    
    Args:
        ecm_type: The module type (ECM, TCM, etc.)
        
    Returns:
        dict: The parameter data, or an empty dict if the file doesn't exist
    """
    # Use lowercase filename for compatibility
    filename = f"data/{ecm_type.lower()}.json"
    
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Create an empty structure
            return {"parameters": {}}
    except Exception as e:
        print(f"Error loading parameter file {filename}: {str(e)}")
        return {"parameters": {}}

def save_parameter_file(ecm_type, data):
    """
    Save parameter data to a JSON file
    
    Args:
        ecm_type: The module type (ECM, TCM, etc.)
        data: The parameter data to save
        
    Returns:
        bool: True if the save was successful, False otherwise
    """
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Use lowercase filename for compatibility
    filename = f"data/{ecm_type.lower()}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving parameter file {filename}: {str(e)}")
        return False



def add_parameter_to_json(param_id, param_name, ecm_type):
    """
    Add a parameter to the JSON file for the specified module type
    
    Args:
        param_id: The parameter ID
        param_name: The parameter name
        ecm_type: The module type (ECM, TCM, etc.)
        
    Returns:
        bool: True if the parameter was added, False otherwise
    """
    if not param_id:
        return False
    
    # Load existing data
    data = load_parameter_file(ecm_type)
    
    # Get the existing parameters or create an empty dict
    if "parameters" not in data:
        data["parameters"] = {}
    
    # Check if the parameter already exists
    if param_id in data["parameters"]:
        # Parameter already exists
        print(f"Parameter {param_id} already exists in {ecm_type.lower()}")
        return False
    
    # Add the parameter
    data["parameters"][param_id] = {
        "name": param_name,
        "description": "",
        "details": "",
        "added_time": datetime.datetime.now().isoformat()
    }
    
    # Save the updated data
    if save_parameter_file(ecm_type, data):
        print(f"Added parameter {param_id} to {ecm_type.lower()}")
        return True
    
    return False



def update_parameter_details(param_id, details, ecm_type):
    """
    Update the details for a parameter in the JSON file
    
    Args:
        param_id: The parameter ID
        details: The parameter details text
        ecm_type: The module type (ECM, TCM, etc.)
        
    Returns:
        bool: True if the parameter was updated, False otherwise
    """
    if not param_id:
        return False
    
    # Load existing data
    data = load_parameter_file(ecm_type)
    
    # Ensure we have a parameters section
    if "parameters" not in data:
        data["parameters"] = {}
    
    # Check if the parameter exists
    if param_id not in data["parameters"]:
        print(f"Parameter {param_id} not found in {ecm_type.lower()}")
        return False
    
    # Update the details
    data["parameters"][param_id]["details"] = details
    data["parameters"][param_id]["updated_time"] = datetime.datetime.now().isoformat()
    
    # Save the updated data
    if save_parameter_file(ecm_type, data):
        print(f"Updated details for parameter {param_id} in {ecm_type.lower()}")
        return True
    
    return False



def git_add_and_commit(file_path, commit_message):

    """Add a file and commit changes to the Git repository"""

    try:

        # Check if git is available

        which_git = subprocess.run(

            ["where", "git"] if os.name == "nt" else ["which", "git"],

            capture_output=True,

            text=True

        )

        

        if which_git.returncode != 0:

            return False, "Git executable not found in PATH"

            

        # Check if current directory is a git repository

        is_git_repo = subprocess.run(

            ["git", "rev-parse", "--is-inside-work-tree"],

            capture_output=True,

            text=True

        )

        

        if is_git_repo.returncode != 0:

            return False, "Not a Git repository"

        

        # Check if file exists before adding

        if not os.path.exists(file_path):

            return False, f"File {file_path} does not exist"

        

        # Add the file

        add_result = subprocess.run(

            ["git", "add", file_path],

            capture_output=True,

            text=True,

            check=False

        )

        

        if add_result.returncode != 0:

            return False, f"Git add failed: {add_result.stderr.strip()}"

        

        # Commit the changes

        commit_result = subprocess.run(

            ["git", "commit", "-m", commit_message],

            capture_output=True,

            text=True,

            check=False

        )

        

        # Check if the commit was successful (it might fail if there are no changes)

        if commit_result.returncode != 0:

            if "nothing to commit" in commit_result.stdout + commit_result.stderr:

                return False, "No changes to commit"

            else:

                return False, commit_result.stderr.strip()

        

        return True, commit_result.stdout.strip()

    except subprocess.CalledProcessError as e:

        return False, f"Git operation failed: {e.stderr.strip() if hasattr(e, 'stderr') else str(e)}"

    except Exception as e:

        return False, f"Error: {str(e)}"



def git_push():

    """Push changes to the remote Git repository"""

    try:

        # Check if git is available

        which_git = subprocess.run(

            ["where", "git"] if os.name == "nt" else ["which", "git"],

            capture_output=True,

            text=True

        )

        

        if which_git.returncode != 0:

            return False, "Git executable not found in PATH"

            

        # Check if current directory is a git repository

        is_git_repo = subprocess.run(

            ["git", "rev-parse", "--is-inside-work-tree"],

            capture_output=True,

            text=True

        )

        

        if is_git_repo.returncode != 0:

            return False, "Not a Git repository"

        

        # Push to remote

        result = subprocess.run(

            ["git", "push"],

            capture_output=True,

            text=True,

            check=False

        )

        

        if result.returncode != 0:

            return False, f"Git push failed: {result.stderr.strip()}"

            

        return True, result.stdout.strip()

    except subprocess.CalledProcessError as e:

        return False, f"Git push failed: {e.stderr.strip() if hasattr(e, 'stderr') else str(e)}"

    except Exception as e:

        return False, f"Error: {str(e)}"



def create_pending_submission(param_id, param_name, param_description, param_details, ecm_type):

    """Create a pending submission entry for the admin interface"""

    # Create the web/data directory if it doesn't exist

    # Some clean-up of unused code that referenced the web folder

    pass



def format_json(obj, indent=2):

    """Format a JSON object with proper indentation"""

    return json.dumps(obj, indent=indent, sort_keys=True)



def get_parameter_details_from_json(param_id, ecm_type):

    """

    Get parameter details from the JSON file

    Returns tuple of (parameter_data, details_text)

    """

    if not param_id or not ecm_type:

        return None, None

    

    try:

        # Load the JSON file for the ECM type

        data, message = load_parameter_file(ecm_type)

        if data is None:

            return None, None

        

        # Check for parameter in parameters section first

        if "parameters" in data and param_id in data["parameters"]:

            param_data = data["parameters"][param_id]

            return param_data, param_data.get("details", "")

        

        # Check if parameter exists at root level (file inconsistency)

        elif param_id in data and param_id != "name" and param_id != "description" and param_id != "parameters":

            param_data = data[param_id]

            return param_data, param_data.get("details", "")

            

        # Parameter not found

        return None, None

    

    except Exception as e:

        print(f"Error getting parameter details: {str(e)}")

        return None, None



# Main application

def main():

    print("Starting VCM Overlay application...")

    app = QApplication(sys.argv)

    print("QApplication created")

    

    ex = VCMOverlay()

    print("Window show() called")

    ex.show()

    

    # Start monitoring immediately

    ex.enable_parameter_detection()

    

    sys.exit(app.exec_())



if __name__ == '__main__':

    main() 

