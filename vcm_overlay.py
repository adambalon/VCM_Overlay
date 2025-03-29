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

                            QGroupBox, QGridLayout, QScrollArea, QSizeGrip, QSizePolicy, QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QListWidget, QListWidgetItem)

from PyQt5.QtCore import QTimer, Qt, QEvent, QRect, QSize

from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QBrush, QTextCursor, QIcon

import datetime

import uuid

import urllib.request

import urllib.error



# Import Firebase service module
try:
    import firebase_service
    FIREBASE_AVAILABLE = True
    print("Firebase service successfully imported")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    print(f"Firebase service not available. Error: {str(e)}")
    print("Authentication and cloud features disabled.")



# Define constants for parameter types
MODULE_TYPES = ["ECM", "TCM", "BCM", "PCM", "ICM", "OTHER"]
DEFAULT_MODULE_TYPE = "ECM"

# Global variables for Firebase state
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



class LoginDialog(QDialog):
    """Dialog for Firebase authentication"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VCM Overlay - Login")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Set up UI elements
        title_label = QLabel("Sign in to VCM Overlay")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title_label)
        
        # Email/password login
        form_layout = QFormLayout()
        
        # Email field
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Enter your email address")
        form_layout.addRow("Email:", self.email_edit)
        
        # Password field
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Enter your password")
        form_layout.addRow("Password:", self.password_edit)
        
        layout.addLayout(form_layout)
        
        # Login button
        login_button = QPushButton("Login")
        login_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #388e3c;
            }
        """)
        login_button.clicked.connect(self.handle_login)
        
        # Create account button
        create_button = QPushButton("Create Account")
        create_button.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
            QPushButton:pressed {
                background-color: #455A64;
            }
        """)
        create_button.clicked.connect(self.handle_create_account)
        
        # Add buttons to a horizontal layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(login_button)
        buttons_layout.addWidget(create_button)
        layout.addLayout(buttons_layout)
        
        # Add a status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #F44336; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        # Add cancel button
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def handle_login(self):
        """Handle login button click"""
        email = self.email_edit.text().strip()
        password = self.password_edit.text()
        
        if not email or not password:
            self.status_label.setText("Please enter both email and password")
            return
        
        self.status_label.setText("Signing in...")
        
        try:
            success, message, user_data = firebase_service.sign_in_with_email_password(email, password)
            
            if success:
                self.status_label.setText(f"Signed in as {user_data.get('email', 'Unknown')}")
                self.accept()  # Close dialog with success
            else:
                self.status_label.setText(f"Login failed: {message}")
                
                # Display a more user-friendly message
                error_msg = "Could not sign in with the provided credentials."
                if "400" in message or "Invalid email or password" in message:
                    error_msg = "Invalid email or password. Please check your credentials and try again."
                
                QMessageBox.warning(self, "Authentication Failed", error_msg)
        except Exception as e:
            error_str = str(e)
            self.status_label.setText(f"Error: {error_str}")
            
            # Handle HTTP 400 error specifically
            if "400" in error_str:
                QMessageBox.warning(self, "Authentication Failed", 
                                   "Invalid email or password. Please check your credentials and try again.")
            else:
                QMessageBox.critical(self, "Error", f"An error occurred: {error_str}")
    
    def handle_create_account(self):
        """Handle create account button click"""
        email = self.email_edit.text().strip()
        password = self.password_edit.text()
        
        if not email or not password:
            self.status_label.setText("Please enter both email and password")
            return
        
        if len(password) < 6:
            self.status_label.setText("Password must be at least 6 characters")
            QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters.")
            return
        
        self.status_label.setText("Creating account...")
        
        try:
            success, message, user_data = firebase_service.create_user_with_email_password(email, password)
            
            if success:
                self.status_label.setText("Account created successfully!")
                
                # Ask if user wants to sign in with the new account
                result = QMessageBox.question(
                    self,
                    "Account Created",
                    "Your account has been created successfully. Would you like to sign in now?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if result == QMessageBox.Yes:
                    # Attempt to sign in with the new account
                    success, login_message, user_data = firebase_service.sign_in_with_email_password(email, password)
                    if success:
                        self.status_label.setText(f"Signed in as {user_data.get('email', 'Unknown')}")
                        self.accept()  # Close dialog with success
                    else:
                        self.status_label.setText(f"Auto sign-in failed: {login_message}")
            else:
                self.status_label.setText(f"Account creation failed: {message}")
                QMessageBox.warning(self, "Account Creation Failed", 
                                   f"Could not create account.\n{message}")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")


class VCMOverlay(QMainWindow):

    """Main application window for VCM Parameter ID Monitor"""

    def __init__(self, parent=None, no_git=False):
        """Initialize the overlay window"""
        super(VCMOverlay, self).__init__(parent)
        
        # Set up window flags
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("VCM Parameter Monitor")
        
        # Dragging and resizing variables
        self.dragging = False
        self.resizing = False
        self.drag_position = None
        self.old_size = None
        self.resize_corner_size = 20  # Size of the "grab area" in the bottom right
        
        # Set minimum size
        self.setMinimumSize(360, 400)
        
        # Flag to disable git operations (for development)
        self.no_git = no_git
        
        # Last parameter text to avoid redundant updates
        self.last_parameter_text = ""
        
        # Initialize debug log buffer
        self.debug_log = []
        
        # Detection flag
        self.detection_enabled = False
        
        # Parameter detection variables
        self.current_parameter_edit_hwnd = None
        
        # Initialize UI
        self.initUI()
        
        # Initialize Firebase services if available
        self.log_debug("Initializing Firebase services...")
        if FIREBASE_AVAILABLE:
            firebase_initialized = self.init_firebase()
            if firebase_initialized:
                self.log_debug("Firebase initialized successfully")
            else:
                self.log_debug("Firebase initialization failed")

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
            }
            QPushButton:hover {
                background-color: #333333;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #111111;
            }
        """)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)
        
        # Title bar
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setStyleSheet("""
            #titleBar {
                background-color: #222222;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid #333333;
            }
        """)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Title and status indicator
        title_container = QWidget()
        title_container_layout = QHBoxLayout(title_container)
        title_container_layout.setContentsMargins(0, 0, 0, 0)
        title_container_layout.setSpacing(8)
        
        # Green status dot
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(10, 10)
        self.status_indicator.setStyleSheet("background-color: #00FF00; border-radius: 5px;")
        title_container_layout.addWidget(self.status_indicator)
        
        # Title text
        title_label = QLabel("VCM Parameter Monitor")
        title_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #FFFFFF;")
        title_container_layout.addWidget(title_label)
        
        title_bar_layout.addWidget(title_container)
        
        # Add user login status/button to title bar
        self.auth_container = QWidget()
        auth_layout = QHBoxLayout(self.auth_container)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        auth_layout.setSpacing(5)
        
        # User label (shows email when logged in)
        self.user_label = QLabel("")
        self.user_label.setStyleSheet("color: #AAAAAA; font-size: 8pt;")
        auth_layout.addWidget(self.user_label)
        
        # Login/logout button
        self.auth_button = QPushButton("Login")
        self.auth_button.setStyleSheet("""
            QPushButton {
                background-color: #333366;
                color: #FFFFFF;
                border: none;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 8pt;
            }
            QPushButton:hover {
                background-color: #444488;
            }
        """)
        self.auth_button.clicked.connect(self.handle_auth_button)
        auth_layout.addWidget(self.auth_button)
        
        title_bar_layout.addWidget(self.auth_container)
        
        # Window control buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        
        minimize_btn = QPushButton("−")
        minimize_btn.setFixedSize(16, 16)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border-radius: 8px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #444444;
                color: #FFFFFF;
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        btn_layout.addWidget(minimize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #AA3333;
                color: #FFFFFF;
                border-radius: 8px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #FF5555;
            }
        """)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        title_bar_layout.addWidget(btn_container)
        
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
        
        # Save to Firebase button - rename to just "SAVE PARAMETER"
        self.save_to_cloud_button = QPushButton("SAVE PARAMETER")
        self.save_to_cloud_button.clicked.connect(self.save_to_firebase)
        self.save_to_cloud_button.setToolTip("Save parameter details to Firestore database")
        self.save_to_cloud_button.setStyleSheet("""
            QPushButton {
                background-color: #336699;  /* Blue color for save */
                color: #FFFFFF;
                border: none;
                padding: 8px 15px;
                border-radius: 6px;
                font-size: 8pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4477AA;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #225588;
            }
            QPushButton:disabled {
                background-color: #223344;
                color: #666666;
            }
        """)
        # Disable the button if not logged in or Firebase not available
        self.save_to_cloud_button.setEnabled(False)
        git_button_layout.addWidget(self.save_to_cloud_button)
        
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
        
        # Update authentication status
        self.update_auth_status()

    def handle_auth_button(self):
        """Handle login/logout button click"""
        if not FIREBASE_AVAILABLE:
            QMessageBox.information(self, "Local Mode", 
                "Firebase authentication is not available.\nRunning in local mode only.")
            return
        
        # Get current user
        current_user = firebase_service.get_current_user()
        
        if current_user:
            # User is signed in, handle logout
            reply = QMessageBox.question(self, "Confirm Logout", 
                "Are you sure you want to sign out?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                
            if reply == QMessageBox.Yes:
                success = firebase_service.sign_out()
                if success:
                    self.update_auth_status()
                    self.log_debug("User signed out")
        else:
            # User is not signed in, show login dialog
            dialog = LoginDialog(self)
            result = dialog.exec_()
            
            if result == QDialog.Accepted:
                self.update_auth_status()
                self.log_debug("User signed in via dialog")
            else:
                self.log_debug("Login cancelled")

    def update_auth_status(self):
        """Update authentication status in UI"""
        current_user = firebase_service.get_current_user()
        
        if current_user:
            # User is logged in
            self.user_label.setText(f"Signed in as: {current_user.get('email', 'Unknown')}")
            self.auth_button.setText("Logout")
            self.save_to_cloud_button.setEnabled(True)
            
            # Enable parameter fields
            self.param_details_text.setReadOnly(False)
            self.param_details_text.setStyleSheet("""
                QTextEdit {
                    background-color: #181818;
                    color: #CCCCCC;
                    border: 1px solid #222222;
                    border-radius: 6px;
                    font-family: Consolas, monospace;
                    font-size: 9.5pt;
                    padding: 5px;
                }
            """)
            self.parameter_header_label.setStyleSheet("""
                font-size: 10pt; 
                font-weight: bold; 
                color: #FFFFFF;
            """)
            
            # Check if the user is an admin
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
                self.log_debug(f"Error checking admin status: {str(e)}")
                is_admin = False
            
            # Show/hide admin features based on status
            if is_admin:
                self.log_debug("User is an admin, showing admin features")
                # Create admin button if it doesn't exist
                if not hasattr(self, 'admin_button') or not self.admin_button:
                    self.admin_button = QPushButton("Manage Pending")
                    self.admin_button.setStyleSheet("""
                        QPushButton {
                            background-color: #336633;
                            color: #FFFFFF;
                            border: none;
                            padding: 3px 8px;
                            border-radius: 4px;
                            font-size: 8pt;
                        }
                        QPushButton:hover {
                            background-color: #448844;
                        }
                    """)
                    self.admin_button.clicked.connect(self.run_manage_pending)
                    
                    # Add to auth container layout
                    if hasattr(self, 'auth_container') and self.auth_container:
                        self.auth_container.layout().insertWidget(1, self.admin_button)
                        
                # Make sure it's visible
                if hasattr(self, 'admin_button') and self.admin_button:
                    self.admin_button.show()
            else:
                # Hide admin button if it exists
                if hasattr(self, 'admin_button') and self.admin_button:
                    self.admin_button.hide()
        else:
            # No user logged in
            self.user_label.setText("Not signed in")
            self.auth_button.setText("Login")
            self.save_to_cloud_button.setEnabled(False)
            
            # Disable parameter fields
            self.param_details_text.setReadOnly(True)
            self.param_details_text.setStyleSheet("""
                QTextEdit {
                    background-color: #181818;
                    color: #555555; /* Dimmed text color */
                    border: 1px solid #222222;
                    border-radius: 6px;
                    font-family: Consolas, monospace;
                    font-size: 9.5pt;
                    padding: 5px;
                }
            """)
            self.parameter_header_label.setStyleSheet("""
                font-size: 10pt; 
                font-weight: bold; 
                color: #555555; /* Dimmed text color */
            """)
            
            # Clear parameter fields
            self.param_id_label.setText("")
            self.param_name_label.setText("")
            self.param_desc_label.setText("")
            self.param_details_text.clear()
            self.parameter_header_label.setText("LOGIN REQUIRED")
            
            # Hide admin button if it exists
            if hasattr(self, 'admin_button') and self.admin_button:
                self.admin_button.hide()

    def run_manage_pending(self):
        """Open the manage pending parameters dialog"""
        if not FIREBASE_AVAILABLE:
            QMessageBox.warning(self, "Firebase Not Available", 
                "Firebase is not available. Cannot manage pending parameters.")
            return
        
        try:
            self.log_debug("Opening manage pending parameters dialog...")
            dialog = ManagePendingDialog(self)
            dialog.exec_()
        except Exception as e:
            self.log_debug(f"Error opening manage pending dialog: {str(e)}")
            QMessageBox.critical(self, "Error", 
                f"Failed to open manage pending dialog: {str(e)}")

    def save_to_firebase(self):
        """Save current parameter to Firebase"""
        if not FIREBASE_AVAILABLE:
            self.git_status_label.setText("⚠ Firebase is not available")
            return
        
        # Get current user
        current_user = firebase_service.get_current_user()
        if not current_user:
            # Prompt to sign in
            reply = QMessageBox.question(self, "Authentication Required", 
                "You need to sign in to save parameters to Firebase.\nWould you like to sign in now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                
            if reply == QMessageBox.Yes:
                self.handle_auth_button()
                # Check if user is signed in after login dialog
                current_user = firebase_service.get_current_user()
                if not current_user:
                    return  # Login cancelled or failed
            else:
                return  # User declined to sign in
        
        # Get parameter ID and type
        param_id = self.param_id_label.text()
        param_type = self.param_type_label.text()
        param_name = self.param_name_label.text()
        param_desc = self.param_desc_label.text()
        param_details = self.param_details_text.toPlainText()
        
        if not param_id:
            self.git_status_label.setText("⚠ No parameter selected")
            return
        
        # Prepare parameter data
        param_data = {
            "id": param_id,
            "type": param_type,
            "name": param_name,
            "description": param_desc,
            "details": param_details,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Save to Firebase
        success, message = firebase_service.save_parameter_to_firebase(param_id, param_data)
        
        if success:
            self.git_status_label.setText(f"✓ {message}")
            self.log_debug(f"Saved parameter {param_id} to Firebase")
        else:
            self.git_status_label.setText(f"⚠ {message}")
            self.log_debug(f"Failed to save parameter to Firebase: {message}")
            
            # Show error message
            QMessageBox.warning(self, "Firebase Error", 
                f"Failed to save parameter to Firebase:\n{message}")

    def init_firebase(self):
        """Initialize Firebase services"""
        global firebase_initialized
        
        if not FIREBASE_AVAILABLE:
            self.log_debug("Firebase not available, running in local mode")
            return False
        
        try:
            # Initialize Firebase
            success = firebase_service.initialize()
            
            if success:
                firebase_initialized = True
                self.save_to_cloud_button.setEnabled(True)
                self.log_debug("Firebase initialized successfully")
                self.update_auth_status()
                return True
            else:
                self.log_debug("Firebase initialization failed")
                return False
        except Exception as e:
            self.log_debug(f"Error initializing Firebase: {str(e)}")
            return False

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
        
        # If not logged in, don't process parameters
        if not firebase_service.get_current_user():
            self.status_label.setText("LOGIN REQUIRED")
            self.parameter_header_label.setText("LOGIN REQUIRED")
            return
        
        self.status_label.setText("PARAMETER DETECTED")
        
        # Display the raw parameter text header (either ECM or TCM)
        header_part = text.split()[0] if text.split() else ""
        self.parameter_header_label.setText(header_part)
        
        # Clear all labels but set a fixed height to prevent layout shifts
        self.param_type_label.setText("")
        self.param_id_label.setText("")
        self.param_name_label.setText("")
        self.param_desc_label.setText("")
        self.param_details_text.clear()  # Clear the details text box
        self.git_status_label.setText("")  # Clear status message
        
        # Extract specific parts
        try:
            # Extract Type (ECM/TCM)
            param_type = header_part.strip("[]") if header_part else ""
            self.param_type_label.setText(param_type)
            
            # Parse format: [ECM] 12600 - Main Spark vs. Airmass vs. RPM Open Throttle, High Octane: This is the High Octane spark...
            parts = text.split(None, 2)  # Split at most twice to get: ['[ECM]', '12600', '- Main Spark vs...']
            
            # Get ECM type for the database query
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
            
            # Check Firebase for parameter details
            if param_id and FIREBASE_AVAILABLE and firebase_service.get_current_user():
                self.log_debug(f"Checking Firebase for parameter {param_id}...")
                try:
                    if firebase_service.firestore_db:
                        # Try to fetch from parameters collection first
                        param_ref = firebase_service.firestore_db.collection('parameters').where('param_id', '==', param_id).limit(1).get()
                        
                        if param_ref and len(param_ref) > 0:
                            cloud_param = param_ref[0].to_dict()
                            
                            # Get cloud data
                            cloud_name = cloud_param.get("name", "")
                            cloud_desc = cloud_param.get("description", "")
                            cloud_details = cloud_param.get("details", "")
                            
                            # Use cloud values if more detailed
                            if cloud_name and (not param_name or len(cloud_name) > len(param_name)):
                                param_name = cloud_name
                                self.param_name_label.setText(cloud_name)
                            
                            if cloud_desc and (not param_desc or len(cloud_desc) > len(param_desc)):
                                param_desc = cloud_desc
                                self.param_desc_label.setText(cloud_desc)
                            
                            if cloud_details:
                                self.param_details_text.setText(cloud_details)
                                self.log_debug(f"Loaded parameter details from Firestore for {param_id}")
                                self.git_status_label.setText("📡 Parameter data from Firestore")
                        
                        # Check pending collection as well
                        pending_ref = firebase_service.firestore_db.collection('pending').where('param_id', '==', param_id).limit(1).get()
                        
                        if pending_ref and len(pending_ref) > 0:
                            pending_param = pending_ref[0].to_dict()
                            
                            # Get pending data
                            pending_name = pending_param.get("name", "")
                            pending_desc = pending_param.get("description", "")
                            pending_details = pending_param.get("details", "")
                            
                            # Use pending values if more detailed
                            if pending_name and (not param_name or len(pending_name) > len(param_name)):
                                param_name = pending_name
                                self.param_name_label.setText(pending_name)
                            
                            if pending_desc and (not param_desc or len(pending_desc) > len(param_desc)):
                                param_desc = pending_desc
                                self.param_desc_label.setText(pending_desc)
                            
                            if pending_details:
                                self.param_details_text.setText(pending_details)
                                self.log_debug(f"Loaded parameter details from Firestore pending for {param_id}")
                                self.git_status_label.setText("📡 Parameter data from pending collection")
                    
                    elif firebase_service.firebase:
                        # Try Realtime Database
                        current_user = firebase_service.get_current_user()
                        db = firebase_service.firebase.database()
                        
                        # Check parameters collection
                        param_data = db.child('parameters').child(param_id).get(token=current_user['token']).val()
                        
                        if param_data:
                            # Get cloud data
                            cloud_name = param_data.get("name", "")
                            cloud_desc = param_data.get("description", "")
                            cloud_details = param_data.get("details", "")
                            
                            # Use cloud values if more detailed
                            if cloud_name and (not param_name or len(cloud_name) > len(param_name)):
                                param_name = cloud_name
                                self.param_name_label.setText(cloud_name)
                            
                            if cloud_desc and (not param_desc or len(cloud_desc) > len(param_desc)):
                                param_desc = cloud_desc
                                self.param_desc_label.setText(cloud_desc)
                            
                            if cloud_details:
                                self.param_details_text.setText(cloud_details)
                                self.log_debug(f"Loaded parameter details from Realtime Database for {param_id}")
                                self.git_status_label.setText("📡 Parameter data from database")
                        
                        # Check pending collection
                        pending_data = db.child('pending').child(param_id).get(token=current_user['token']).val()
                        
                        if pending_data:
                            # Get pending data
                            pending_name = pending_data.get("name", "")
                            pending_desc = pending_data.get("description", "")
                            pending_details = pending_data.get("details", "")
                            
                            # Use pending values if more detailed
                            if pending_name and (not param_name or len(pending_name) > len(param_name)):
                                param_name = pending_name
                                self.param_name_label.setText(pending_name)
                            
                            if pending_desc and (not param_desc or len(pending_desc) > len(param_desc)):
                                param_desc = pending_desc
                                self.param_desc_label.setText(pending_desc)
                            
                            if pending_details:
                                self.param_details_text.setText(pending_details)
                                self.log_debug(f"Loaded parameter details from Realtime Database pending for {param_id}")
                                self.git_status_label.setText("📡 Parameter data from pending collection")
                
                except Exception as e:
                    self.log_debug(f"Error checking Firebase for parameter {param_id}: {str(e)}")
                    self.git_status_label.setText(f"⚠ Error checking Firestore: {str(e)}")

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
        """This method is now just a stub - we no longer use JSON files"""
        # This method is kept as a stub to avoid breaking any existing code references
        # We're now using Firestore exclusively
        pass

    def save_parameter_details(self):
        """This method is now just a stub - we now use Firestore exclusively"""
        # This method is kept as a stub to avoid breaking any existing code references
        # Instead of saving to JSON, we now direct users to save to Firestore
        if not FIREBASE_AVAILABLE:
            QMessageBox.information(self, "Firebase Required", 
                "Firebase is required for saving parameters. Please check your configuration.")
            return
        
        if not firebase_service.get_current_user():
            QMessageBox.information(self, "Login Required", 
                "You must be logged in to save parameter details.")
            # Prompt to sign in
            self.handle_auth_button()
        else:
            # Just call save_to_firebase directly
            self.save_to_firebase()

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
            if not self.current_parameter_edit_hwnd or not user32.IsWindow(self.current_parameter_edit_hwnd):
                self.current_parameter_edit_hwnd = None  # Mark as invalid
                return
                
            # Get the current text
            try:
                text = get_edit_text(self.current_parameter_edit_hwnd)
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
        if self.current_parameter_edit_hwnd:
            try:
                # Check if handle is valid
                if not user32.IsWindow(self.current_parameter_edit_hwnd):
                    self.log_debug(f"Edit control {self.current_parameter_edit_hwnd} is not a valid window")
                    self.parameter_header_label.setText("No parameter detected - searching...")
                    self.auto_detect_parameter_edit_control()
                    return
                
                # Get text from edit control
                text = get_edit_text(self.current_parameter_edit_hwnd)
                if self.is_parameter_text(text):
                    # Parse and display parameter information
                    self.update_parameter_info(text)
                    self.update_title_handle_indicator(self.current_parameter_edit_hwnd, True)
                else:
                    self.log_debug(f"Edit control {self.current_parameter_edit_hwnd} does not contain parameter text")
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
        old_handle = self.current_parameter_edit_hwnd
        self.current_parameter_edit_hwnd = handle_num
        
        if handle_num != old_handle:
            self.log_debug(f"Parameter detection activated - monitoring edit control {handle_num}")
        
        # Update handle info in debug window if it's open
        if hasattr(self, 'handle_number_label') and self.handle_number_label:
            self.handle_number_label.setText(f"Current handle: {handle_num}")
            
    def update_handle_status(self):
        """Update the handle status in the debug window"""
        if hasattr(self, 'handle_status_label') and self.handle_status_label:
            if self.current_parameter_edit_hwnd:
                if user32.IsWindow(self.current_parameter_edit_hwnd):
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
    """This function is now a stub - we no longer use JSON files"""
    # We're now using Firestore exclusively
    return {}

def save_parameter_file(ecm_type, data):
    """This function is now a stub - we no longer use JSON files"""
    # We're now using Firestore exclusively
    return False



def add_parameter_to_json(param_id, param_name, ecm_type):
    """This function is now a stub - we no longer use JSON files"""
    # We're now using Firestore exclusively
    return False, "JSON files are no longer used - please use Firebase"



def update_parameter_details(param_id, details, ecm_type):
    """This function is now a stub - we no longer use JSON files"""
    # We're now using Firestore exclusively
    return False, "JSON files are no longer used - please use Firebase"



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
    """This function is now a stub - we no longer use JSON files"""
    # We're now using Firestore exclusively
    return None, None



class ManagePendingDialog(QDialog):
    """Dialog for managing pending parameter submissions"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Pending Parameters")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        # Store the current user
        self.current_user = firebase_service.get_current_user()
        
        # Main layout
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title_label = QLabel("Pending Parameter Submissions")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Create tab widget for different modules
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Add tabs for different parameter types
        self.create_tabs()
        
        # Buttons at the bottom
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh List")
        refresh_button.clicked.connect(self.refresh_all_tabs)
        button_layout.addWidget(refresh_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Load pending parameters
        self.load_pending_parameters()
    
    def create_tabs(self):
        """Create tabs for different module types"""
        self.tabs = {}
        
        # Create a tab for each module type
        for module_type in MODULE_TYPES:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            
            # Create a list widget for the parameters
            list_widget = QListWidget()
            list_widget.setSelectionMode(QListWidget.SingleSelection)
            list_widget.itemSelectionChanged.connect(lambda t=module_type: self.on_parameter_selected(t))
            tab_layout.addWidget(list_widget)
            
            # Details section
            details_group = QGroupBox("Parameter Details")
            details_layout = QFormLayout(details_group)
            
            # Parameter ID
            param_id_label = QLabel("")
            details_layout.addRow("Parameter ID:", param_id_label)
            
            # Parameter Name
            param_name_label = QLabel("")
            param_name_label.setWordWrap(True)
            details_layout.addRow("Name:", param_name_label)
            
            # Submitted By
            submitted_by_label = QLabel("")
            details_layout.addRow("Submitted By:", submitted_by_label)
            
            # Submission Date
            submitted_at_label = QLabel("")
            details_layout.addRow("Submitted At:", submitted_at_label)
            
            # Parameter Details
            param_details_text = QTextEdit()
            param_details_text.setReadOnly(True)
            param_details_text.setStyleSheet("""
                background-color: #181818;
                color: #CCCCCC;
                border: 1px solid #222222;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 9.5pt;
            """)
            details_layout.addRow("Details:", param_details_text)
            
            tab_layout.addWidget(details_group)
            
            # Action buttons
            action_layout = QHBoxLayout()
            
            approve_button = QPushButton("Approve")
            approve_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #388e3c;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            approve_button.clicked.connect(lambda checked=False, t=module_type: self.approve_parameter(t))
            approve_button.setEnabled(False)
            action_layout.addWidget(approve_button)
            
            reject_button = QPushButton("Reject")
            reject_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            reject_button.clicked.connect(lambda checked=False, t=module_type: self.reject_parameter(t))
            reject_button.setEnabled(False)
            action_layout.addWidget(reject_button)
            
            tab_layout.addLayout(action_layout)
            
            # Store the UI elements for this tab
            self.tabs[module_type] = {
                'tab': tab,
                'list_widget': list_widget,
                'param_id_label': param_id_label,
                'param_name_label': param_name_label,
                'submitted_by_label': submitted_by_label,
                'submitted_at_label': submitted_at_label,
                'param_details_text': param_details_text,
                'approve_button': approve_button,
                'reject_button': reject_button,
                'parameters': []  # Will store the actual parameter data
            }
            
            # Add the tab to the tab widget
            self.tab_widget.addTab(tab, f"{module_type} Parameters")
    
    def load_pending_parameters(self):
        """Load pending parameters from Firestore/Realtime Database"""
        if not firebase_service.firestore_db and not firebase_service.firebase:
            QMessageBox.warning(self, "Database Error", "No database connection available")
            return
        
        for module_type in self.tabs:
            self.load_module_parameters(module_type)
    
    def load_module_parameters(self, module_type):
        """Load pending parameters for a specific module type"""
        tab_data = self.tabs[module_type]
        list_widget = tab_data['list_widget']
        list_widget.clear()
        tab_data['parameters'] = []
        
        try:
            if firebase_service.firestore_db:
                # Using Firestore
                pending_params = firebase_service.firestore_db.collection('pending').where('type', '==', module_type).get()
                
                if not pending_params:
                    item = QListWidgetItem("No pending parameters")
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    list_widget.addItem(item)
                    return
                
                for param in pending_params:
                    param_data = param.to_dict()
                    param_data['id'] = param.id  # Store document ID
                    param_data['param_id'] = param_data.get('param_id', 'Unknown')
                    
                    # Format the timestamp
                    submitted_at = param_data.get('submitted_at')
                    if submitted_at and hasattr(submitted_at, 'timestamp'):
                        import datetime
                        dt = datetime.datetime.fromtimestamp(submitted_at.timestamp())
                        param_data['submitted_at_formatted'] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        param_data['submitted_at_formatted'] = "Unknown"
                    
                    # Add to parameter list
                    tab_data['parameters'].append(param_data)
                    
                    # Create list item
                    item_text = f"{param_data.get('param_id', 'Unknown')} - {param_data.get('name', 'Unnamed')}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, len(tab_data['parameters']) - 1)  # Store index
                    list_widget.addItem(item)
            
            elif firebase_service.firebase:
                # Using Realtime Database
                db = firebase_service.firebase.database()
                pending_params = db.child('pending').get(token=self.current_user['token']).val()
                
                if not pending_params:
                    item = QListWidgetItem("No pending parameters")
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    list_widget.addItem(item)
                    return
                
                for param_id, param_data in pending_params.items():
                    if param_data.get('type', '').upper() == module_type:
                        param_data['id'] = param_id  # Store parameter ID
                        param_data['param_id'] = param_id
                        
                        # Format the timestamp
                        submitted_at = param_data.get('submitted_at')
                        if submitted_at:
                            import datetime
                            dt = datetime.datetime.fromtimestamp(submitted_at / 1000)  # Convert from milliseconds
                            param_data['submitted_at_formatted'] = dt.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            param_data['submitted_at_formatted'] = "Unknown"
                        
                        # Add to parameter list
                        tab_data['parameters'].append(param_data)
                        
                        # Create list item
                        item_text = f"{param_id} - {param_data.get('name', 'Unnamed')}"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, len(tab_data['parameters']) - 1)  # Store index
                        list_widget.addItem(item)
            
            if not tab_data['parameters']:
                item = QListWidgetItem("No pending parameters")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                list_widget.addItem(item)
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load pending parameters: {str(e)}")
            print(f"Error loading pending parameters: {str(e)}")
    
    def on_parameter_selected(self, module_type):
        """Handle parameter selection in list widget"""
        tab_data = self.tabs[module_type]
        list_widget = tab_data['list_widget']
        
        # Enable/disable buttons based on selection
        has_selection = len(list_widget.selectedItems()) > 0
        tab_data['approve_button'].setEnabled(has_selection)
        tab_data['reject_button'].setEnabled(has_selection)
        
        if has_selection:
            # Get selected parameter
            selected_item = list_widget.selectedItems()[0]
            param_index = selected_item.data(Qt.UserRole)
            param_data = tab_data['parameters'][param_index]
            
            # Update UI
            tab_data['param_id_label'].setText(str(param_data.get('param_id', 'Unknown')))
            tab_data['param_name_label'].setText(param_data.get('name', 'Unnamed'))
            tab_data['submitted_by_label'].setText(param_data.get('submitted_by', 'Unknown'))
            tab_data['submitted_at_label'].setText(param_data.get('submitted_at_formatted', 'Unknown'))
            tab_data['param_details_text'].setText(param_data.get('details', ''))
        else:
            # Clear UI
            tab_data['param_id_label'].setText("")
            tab_data['param_name_label'].setText("")
            tab_data['submitted_by_label'].setText("")
            tab_data['submitted_at_label'].setText("")
            tab_data['param_details_text'].setText("")
    
    def approve_parameter(self, module_type):
        """Approve the selected parameter"""
        tab_data = self.tabs[module_type]
        list_widget = tab_data['list_widget']
        
        if not list_widget.selectedItems():
            return
        
        selected_item = list_widget.selectedItems()[0]
        param_index = selected_item.data(Qt.UserRole)
        param_data = tab_data['parameters'][param_index]
        
        # Confirm approval
        reply = QMessageBox.question(
            self,
            "Confirm Approval",
            f"Are you sure you want to approve parameter {param_data.get('param_id', 'Unknown')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            if firebase_service.firestore_db:
                # Using Firestore
                # Prepare data for approved parameters
                approved_data = param_data.copy()
                doc_id = approved_data.pop('id', None)  # Remove the document ID from data
                
                # Remove client-side only fields
                if 'submitted_at_formatted' in approved_data:
                    approved_data.pop('submitted_at_formatted')
                
                # Set approved status
                approved_data['status'] = 'approved'
                approved_data['approved_by'] = self.current_user.get('email', 'Unknown')
                approved_data['approved_at'] = firebase_service.firestore.SERVER_TIMESTAMP
                
                # Check if parameter already exists in parameters collection
                param_id = param_data.get('param_id')
                param_ref = firebase_service.firestore_db.collection('parameters').where('param_id', '==', param_id).limit(1).get()
                
                if param_ref and len(param_ref) > 0:
                    # Update existing parameter
                    existing_param = param_ref[0]
                    firebase_service.firestore_db.collection('parameters').document(existing_param.id).update(approved_data)
                else:
                    # Add as new parameter
                    firebase_service.firestore_db.collection('parameters').add(approved_data)
                
                # Delete from pending collection instead of just updating status
                firebase_service.firestore_db.collection('pending').document(doc_id).delete()
            
            elif firebase_service.firebase:
                # Using Realtime Database
                db = firebase_service.firebase.database()
                
                # Prepare data for approved parameters
                approved_data = param_data.copy()
                param_id = approved_data.pop('id', None)  # Remove the document ID from data
                
                # Remove client-side only fields
                if 'submitted_at_formatted' in approved_data:
                    approved_data.pop('submitted_at_formatted')
                
                # Set approved status
                approved_data['status'] = 'approved'
                approved_data['approved_by'] = self.current_user.get('email', 'Unknown')
                approved_data['approved_at'] = {".sv": "timestamp"}
                
                # Save to parameters
                db.child('parameters').child(param_id).set(approved_data, token=self.current_user['token'])
                
                # Delete from pending collection instead of just updating
                db.child('pending').child(param_id).remove(token=self.current_user['token'])
            
            # Show success message
            QMessageBox.information(self, "Parameter Approved", f"Parameter {param_data.get('param_id', 'Unknown')} has been approved and added to the database.")
            
            # Refresh the list
            self.load_module_parameters(module_type)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to approve parameter: {str(e)}")
            print(f"Error approving parameter: {str(e)}")
    
    def reject_parameter(self, module_type):
        """Reject the selected parameter"""
        tab_data = self.tabs[module_type]
        list_widget = tab_data['list_widget']
        
        if not list_widget.selectedItems():
            return
        
        selected_item = list_widget.selectedItems()[0]
        param_index = selected_item.data(Qt.UserRole)
        param_data = tab_data['parameters'][param_index]
        
        # Confirm rejection
        reply = QMessageBox.question(
            self,
            "Confirm Rejection",
            f"Are you sure you want to reject parameter {param_data.get('param_id', 'Unknown')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            if firebase_service.firestore_db:
                # Using Firestore
                doc_id = param_data.get('id')
                
                # Delete the pending parameter
                firebase_service.firestore_db.collection('pending').document(doc_id).delete()
            
            elif firebase_service.firebase:
                # Using Realtime Database
                db = firebase_service.firebase.database()
                param_id = param_data.get('id')
                
                # Delete the pending parameter
                db.child('pending').child(param_id).remove(token=self.current_user['token'])
            
            # Show success message
            QMessageBox.information(self, "Parameter Rejected", f"Parameter {param_data.get('param_id', 'Unknown')} has been rejected and removed from the pending list.")
            
            # Refresh the list
            self.load_module_parameters(module_type)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reject parameter: {str(e)}")
            print(f"Error rejecting parameter: {str(e)}")
    
    def refresh_all_tabs(self):
        """Refresh all parameter lists"""
        self.load_pending_parameters()
        QMessageBox.information(self, "Refresh Complete", "Parameter lists have been refreshed.")



# Main application

def main():
    print("Starting VCM Overlay application...")
    app = QApplication(sys.argv)
    print("QApplication created")
    
    # Create main application window
    window = VCMOverlay()
    print("VCMOverlay instance created")
    
    # Show main window
    window.show()
    print("Window show() called")
    
    # Start monitoring immediately
    window.enable_parameter_detection()
    
    # If Firebase is available, check if already logged in
    if FIREBASE_AVAILABLE:
        current_user = firebase_service.get_current_user()
        if current_user:
            print(f"Already logged in as: {current_user.get('email', 'Unknown')}")
        else:
            # Optional: Show login dialog at startup
            # Uncomment the following lines to enable auto-prompt for login
            # dialog = LoginDialog(window)
            # dialog.exec_()
            print("Not logged in")
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main() 

