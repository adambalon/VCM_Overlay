#!/usr/bin/env python3
"""
Creates a fixed version of the VCM Overlay application without hardcoded handles
and with proper window detection for parameter information.
"""

import os
import sys
import ctypes
import traceback
import json
import re
from ctypes import wintypes
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QTextEdit, QTabWidget, QLineEdit, 
                            QGroupBox, QGridLayout, QScrollArea, QSizeGrip, QSizePolicy)
from PyQt5.QtCore import QTimer, Qt, QEvent, QRect
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QBrush, QTextCursor
import datetime

# Import our parameter manager module
import param_manager

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
        
        # Operation buttons container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.setSpacing(5)
        
        # Add buttons for parameter operations
        self.save_button = QPushButton("SAVE DETAILS")
        self.save_button.clicked.connect(self.save_parameter_details)
        self.save_button.setToolTip("Save parameter details to local JSON file")
        button_layout.addWidget(self.save_button)
        
        self.submit_button = QPushButton("SUBMIT CHANGES")
        self.submit_button.clicked.connect(self.submit_parameter_changes)
        self.submit_button.setToolTip("Submit your changes for review")
        button_layout.addWidget(self.submit_button)
        
        # Second row of buttons
        button_container2 = QWidget()
        button_layout2 = QHBoxLayout(button_container2)
        button_layout2.setContentsMargins(0, 5, 0, 0)
        button_layout2.setSpacing(5)
        
        self.refresh_param_button = QPushButton("REFRESH PARAMETER")
        self.refresh_param_button.clicked.connect(self.refresh_current_parameter)
        self.refresh_param_button.setToolTip("Refresh parameter data from local files")
        button_layout2.addWidget(self.refresh_param_button)
        
        details_field_layout.addWidget(button_container)
        details_field_layout.addWidget(button_container2)
        
        # Status message for operations
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #AAAAAA; font-size: 8pt;")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignLeft)
        details_field_layout.addWidget(self.status_label)
        
        # Add the details field container to the content layout
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
        self.status_label.setText("PARAMETER DETECTED")
        
        # Extract specific parts
        try:
            # Extract Type (ECM/TCM)
            param_type = header_part.strip("[]") if header_part else ""
            self.param_type_label.setText(param_type)
            
            # Parse format: [ECM] 12600 - Main Spark vs. Airmass vs. RPM Open Throttle, High Octane: This is the High Octane spark...
            parts = text.split(None, 2)  # Split at most twice to get: ['[ECM]', '12600', '- Main Spark vs...']
            
            # Get ECM type for the JSON file
            ecm_type = param_manager.get_ecm_type_from_text(text)
            
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
                param_data, stored_details = param_manager.get_parameter_details(param_id, ecm_type)
                
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
        """Attempt to add the parameter to the JSON file if it doesn't exist"""
        try:
            success, message = param_manager.add_parameter(param_id, param_name, ecm_type)
            if success:
                self.log_debug(f"Added new parameter: {message}")
                self.status_label.setText(f"✓ {message}")
            else:
                # Not a failure, just means parameter already exists or something minor
                self.log_debug(f"Parameter not added: {message}")
        except Exception as e:
            self.log_debug(f"Error adding parameter to JSON: {str(e)}")
    
    def save_parameter_details(self):
        """Save the parameter details to the JSON file"""
        # Get current parameter information
        param_id = self.param_id_label.text().strip()
        param_details = self.param_details_text.toPlainText().strip()
        ecm_type = param_manager.get_ecm_type_from_text(self.last_parameter_text)
        
        if not param_id or not ecm_type:
            self.status_label.setText("❌ Cannot save: Missing parameter ID or ECM type")
            return
        
        try:
            success, message = param_manager.update_parameter_details(param_id, param_details, ecm_type)
            if success:
                self.log_debug(f"Updated parameter details: {message}")
                self.status_label.setText(f"✓ {message}")
            else:
                self.status_label.setText(f"❌ {message}")
        except Exception as e:
            self.log_debug(f"Error saving parameter details: {str(e)}")
            self.status_label.setText(f"❌ Error: {str(e)}")
    
    def submit_parameter_changes(self):
        """Submit parameter changes for review"""
        # Get current parameter information
        param_id = self.param_id_label.text().strip()
        param_name = self.param_name_label.text().strip()
        param_details = self.param_details_text.toPlainText().strip()
        ecm_type = param_manager.get_ecm_type_from_text(self.last_parameter_text)
        
        if not param_id or not ecm_type:
            self.status_label.setText("❌ Cannot submit: Missing parameter ID or ECM type")
            return
        
        self.status_label.setText("⟳ Submitting changes for review...")
        
        try:
            # Use the parameter manager to submit changes
            success, message = param_manager.submit_parameter_changes(param_id, param_name, ecm_type, param_details)
            
            if success:
                self.log_debug(f"Parameter changes submitted: {message}")
                self.status_label.setText(f"✓ {message}")
            else:
                self.status_label.setText(f"❌ {message}")
        except Exception as e:
            self.log_debug(f"Error submitting parameter changes: {str(e)}")
            self.status_label.setText(f"❌ Error: {str(e)}")
    
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
        
    def find_handles_near_cursor(self, x, y, distance=10):
        """Find window handles near cursor position"""
        nearby_handles = []
        
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_near_cursor(hwnd, lParam):
            try:
                rect = self.get_window_rect(hwnd)
                # Check if handle is within distance pixels
                if rect:
                    # Check if cursor is within distance pixels of any edge
                    if (x >= rect.left - distance and x <= rect.right + distance and
                        y >= rect.top - distance and y <= rect.bottom + distance):
                        nearby_handles.append(hwnd)
            except Exception as e:
                self.log_debug(f"Error in enum_windows_near_cursor: {str(e)}")
            return True
        
        try:
            user32.EnumWindows(enum_windows_near_cursor, 0)
        except Exception as e:
            self.log_debug(f"Error in EnumWindows for nearby handles: {str(e)}")
            
        return nearby_handles
    
    def is_parameter_text(self, text):
        """Check if text contains parameter information (starts with [ECM] or [TCM])"""
        if text and isinstance(text, str):
            return text.startswith('[ECM]') or text.startswith('[TCM]')
        return False
        
    def update_handle_from_input(self):
        """Update handle from user input in debug window"""
        handle_text = self.handle_update_input.text().strip()
        if handle_text:
            try:
                new_handle = int(handle_text)
                self.update_handle_number(new_handle)
                self.update_handle_status()
            except ValueError:
                self.log_debug("Invalid handle number format")
    
    def track_mouse(self):
        """Track mouse position and windows under cursor"""
        if not hasattr(self, 'debug_window') or not self.debug_window.isVisible():
            return
            
        # Get mouse position
        cursor_pos = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(cursor_pos))
        self.mouse_pos_label.setText(f"({cursor_pos.x}, {cursor_pos.y})")
        
        # Get window at cursor
        hwnd = user32.WindowFromPoint(cursor_pos)
        if hwnd:
            class_name = get_class_name(hwnd)
            window_text = get_window_text(hwnd)
            self.mouse_window_label.setText(f"Handle: {hwnd} ({class_name})")
            
            # Find all windows under cursor
            windows = []
            current_hwnd = hwnd
            while current_hwnd:
                windows.append({
                    'hwnd': current_hwnd,
                    'class': get_class_name(current_hwnd),
                    'text': get_window_text(current_hwnd),
                    'rect': self.get_window_rect(current_hwnd)
                })
                current_hwnd = user32.GetParent(current_hwnd)
            
            # Find handles within 10 pixels of cursor position
            nearby_handles_10px = self.find_handles_near_cursor(cursor_pos.x, cursor_pos.y, 10)
            
            # Create formatted HTML for better readability
            handle_text = """
            <style>
                .window-item {
                    margin-bottom: 15px;
                    padding: 8px;
                    border-radius: 5px;
                    background-color: rgba(40, 40, 50, 170);
                }
                .window-item.highlighted {
                    background-color: rgba(255, 136, 0, 200);
                    color: white;
                    border: 1px solid #FFB366;
                }
                .handle-title {
                    font-weight: bold;
                    font-size: 10pt;
                    margin-bottom: 5px;
                    padding-bottom: 3px;
                    border-bottom: 1px solid rgba(100, 100, 120, 120);
                }
                .property {
                    margin-left: 10px;
                    padding: 2px 0;
                }
                .parameter-info {
                    color: #66DD66;
                    font-weight: bold;
                    margin-top: 5px;
                    padding: 3px;
                    background-color: rgba(40, 80, 40, 120);
                    border-radius: 3px;
                }
                .near-cursor {
                    font-weight: bold;
                    padding: 2px 5px;
                    border-radius: 3px;
                    display: inline-block;
                    margin-top: 5px;
                }
                .yes-near {
                    background-color: #FF8800;
                    color: white;
                }
                .no-near {
                    background-color: rgba(60, 60, 70, 120);
                    color: #aaa;
                }
            </style>
            """
            
            for i, win in enumerate(windows):
                rect = win['rect']
                # Determine if handle is within 10px
                is_very_close = win['hwnd'] in nearby_handles_10px
                
                # Create a container div with conditional highlighting
                handle_text += f'<div class="window-item{" highlighted" if is_very_close else ""}">'
                
                # Handle and class name in the title
                handle_text += f'<div class="handle-title">#{i+1}: Handle: {win["hwnd"]}, Class: {win["class"]}</div>'
                
                # Window properties
                handle_text += f'<div class="property"><b>Text:</b> "{win["text"]}"</div>'
                handle_text += f'<div class="property"><b>Position:</b> ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})</div>'
                handle_text += f'<div class="property"><b>Size:</b> {rect.right-rect.left}x{rect.bottom-rect.top}</div>'
                
                # If it's an edit control, try to get its text
                if "edit" in win['class'].lower():
                    try:
                        edit_text = get_edit_text(win['hwnd'])
                        shortened_text = edit_text[:50] + "..." if len(edit_text) > 50 else edit_text
                        handle_text += f'<div class="property"><b>Edit Text:</b> "{shortened_text}"</div>'
                        
                        # Check if this contains parameter text
                        if self.is_parameter_text(edit_text):
                            handle_text += f'<div class="parameter-info">Contains Parameter Information!</div>'
                    except Exception as e:
                        handle_text += f'<div class="property"><b>Error getting edit text:</b> {str(e)}</div>'
                
                # Near cursor indicator
                if is_very_close:
                    handle_text += f'<div class="near-cursor yes-near">Under Cursor (≤10px)</div>'
                else:
                    handle_text += f'<div class="near-cursor no-near">Not Under Cursor</div>'
                
                handle_text += '</div>'  # Close the window-item div
            
            self.handle_list.setHtml(handle_text)
        else:
            self.mouse_window_label.setText("None")
            self.handle_list.setText("")
    
    def create_group_box(self, title, layout=None):
        """Create a styled group box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #AAAAAA;
                border: 1px solid #222222;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                background-color: #111111;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                font-size: 9pt;
            }
        """)
        
        if layout:
            group.setLayout(layout)
        
        return group
    
    def open_debug_window(self):
        """Open the debug window"""
        if self.debug_window and self.debug_window.isVisible():
            self.debug_window.activateWindow()
            return
            
        # Create debug window
        self.debug_window = QWidget()
        self.debug_window.setWindowTitle("VCM Overlay Debug")
        self.debug_window.setGeometry(600, 100, 800, 600)
        self.debug_window.setMinimumSize(600, 400)
        
        # Set frameless flag for the debug window too and keep on top
        self.debug_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.debug_window.setAttribute(Qt.WA_TranslucentBackground)  # Needed for rounded corners
        
        # For dragging the debug window
        self.debug_window_dragging = False
        self.debug_window_drag_position = None
        
        # Add mouse event handlers to debug window
        self.debug_window.mousePressEvent = self.debug_window_mousePressEvent
        self.debug_window.mouseReleaseEvent = self.debug_window_mouseReleaseEvent
        self.debug_window.mouseMoveEvent = self.debug_window_mouseMoveEvent
        
        # Set the style
        self.debug_window.setStyleSheet("""
            QWidget#debugMainWidget {
                background: #000000;
                color: #CCCCCC;
                border: 1px solid #222222;
                border-radius: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #222222;
                background: #111111;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #181818;
                color: #CCCCCC;
                padding: 8px 15px;
                border: 1px solid #222222;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #222222;
                color: #FFFFFF;
                font-weight: bold;
            }
            QTabBar::tab:!selected {
                margin-top: 3px;
            }
            QLabel {
                color: #CCCCCC;
            }
            QPushButton {
                background-color: #222222;
                color: #FFFFFF;
                border: none;
                padding: 5px 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QPushButton:pressed {
                background-color: #111111;
            }
            QLineEdit {
                background-color: #111111;
                color: white;
                border: 1px solid #222222;
                border-radius: 6px;
                padding: 5px;
            }
            QTextEdit {
                background-color: #111111;
                color: #CCCCCC;
                border: 1px solid #222222;
                border-radius: 6px;
                font-family: Consolas, monospace;
            }
            QGroupBox {
                font-weight: bold;
                color: #AAAAAA;
                border: 1px solid #222222;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                font-size: 9pt;
            }
            QScrollBar:vertical {
                background: #181818;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
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
                height: 30px;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid #222222;
            }
        """)
        
        # Main widget for rounded corners
        debug_main_widget = QWidget(self.debug_window)
        debug_main_widget.setObjectName("debugMainWidget")
        debug_main_widget.setGeometry(0, 0, 800, 600)
        
        # Main layout
        main_layout = QVBoxLayout(debug_main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Title bar with close button and status dot
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(12, 0, 12, 0)
        
        # Status indicator (green dot)
        debug_status_indicator = QLabel()
        debug_status_indicator.setFixedSize(10, 10)
        debug_status_indicator.setStyleSheet("background-color: #00FF00; border-radius: 5px;")
        title_bar_layout.addWidget(debug_status_indicator)
        
        title_label = QLabel("VCM OVERLAY DEBUG")
        title_label.setStyleSheet("font-weight: bold; font-size: 9pt; color: #AAAAAA;")
        title_bar_layout.addWidget(title_label)
        
        title_bar_layout.addStretch()
        
        # Add window controls
        min_button = QPushButton("–")
        min_button.setObjectName("minButton")
        min_button.setStyleSheet("background: transparent; color: #777777; font-weight: bold;")
        min_button.setFixedSize(18, 18)
        min_button.clicked.connect(self.debug_window.showMinimized)
        title_bar_layout.addWidget(min_button)
        
        close_button = QPushButton("✕")
        close_button.setObjectName("closeButton")
        close_button.clicked.connect(self.debug_window.close)
        close_button.setFixedSize(18, 18)
        title_bar_layout.addWidget(close_button)
        
        main_layout.addWidget(title_bar)
        
        # Content area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(12, 8, 12, 12)
        
        # Parameter edit handle management
        handle_group = self.create_group_box("PARAMETER EDIT HANDLE MANAGEMENT")
        handle_layout = QGridLayout()
        handle_group.setLayout(handle_layout)
        
        # Current handle info
        self.handle_number_label = QLabel(f"Current handle: {self.parameter_edit_control or 'None'}")
        handle_layout.addWidget(self.handle_number_label, 0, 0)
        
        self.handle_status_label = QLabel("Status: Unknown")
        self.update_handle_status()
        handle_layout.addWidget(self.handle_status_label, 0, 1)
        
        # Auto detect button
        auto_detect_btn = QPushButton("AUTO-DETECT PARAMETER EDIT CONTROL")
        auto_detect_btn.clicked.connect(self.auto_detect_parameter_edit_control)
        handle_layout.addWidget(auto_detect_btn, 1, 0, 1, 2)
        
        # Manual handle entry
        handle_layout.addWidget(QLabel("Enter handle manually:"), 2, 0)
        self.handle_update_input = QLineEdit()
        self.handle_update_input.setPlaceholderText("Enter window handle")
        handle_layout.addWidget(self.handle_update_input, 2, 1)
        
        update_handle_btn = QPushButton("UPDATE HANDLE")
        update_handle_btn.clicked.connect(self.update_handle_from_input)
        handle_layout.addWidget(update_handle_btn, 3, 0, 1, 2)
        
        content_layout.addWidget(handle_group)
        
        # Current parameter information
        param_info_group = self.create_group_box("CURRENT PARAMETER INFORMATION")
        param_info_layout = QVBoxLayout()
        param_info_group.setLayout(param_info_layout)
        
        self.param_info_text = QTextEdit()
        self.param_info_text.setReadOnly(True)
        if self.last_parameter_text:
            self.param_info_text.setText(self.last_parameter_text)
        param_info_layout.addWidget(self.param_info_text)
        
        content_layout.addWidget(param_info_group)
        
        # Tab widget for additional content
        tab_widget = QTabWidget()
        tab_widget.setContentsMargins(5, 5, 5, 5)
        content_layout.addWidget(tab_widget)
        
        # Debug log tab
        debug_tab = QWidget()
        debug_layout = QVBoxLayout(debug_tab)
        debug_layout.setContentsMargins(8, 8, 8, 8)
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setText("\n".join(self.debug_log))
        debug_layout.addWidget(self.debug_text)
        tab_widget.addTab(debug_tab, "DEBUG LOG")
        
        # Window information tab
        window_tab = QWidget()
        window_tab_layout = QVBoxLayout(window_tab)
        window_tab_layout.setContentsMargins(8, 8, 8, 8)
        
        # Mouse position tracking
        mouse_tracking_group = QGroupBox("MOUSE TRACKING")
        mouse_layout = QGridLayout()
        mouse_tracking_group.setLayout(mouse_layout)
        
        mouse_layout.addWidget(QLabel("Mouse Position:"), 0, 0)
        self.mouse_pos_label = QLabel("(0, 0)")
        mouse_layout.addWidget(self.mouse_pos_label, 0, 1)
        
        mouse_layout.addWidget(QLabel("Window under cursor:"), 1, 0)
        self.mouse_window_label = QLabel("None")
        mouse_layout.addWidget(self.mouse_window_label, 1, 1)
        
        window_tab_layout.addWidget(mouse_tracking_group)
        
        # Windows under cursor
        window_tab_layout.addWidget(QLabel("Windows under cursor:"))
        self.handle_list = QTextEdit()
        self.handle_list.setReadOnly(True)
        window_tab_layout.addWidget(self.handle_list)
        
        tab_widget.addTab(window_tab, "WINDOW INFORMATION")
        
        # Handle inspection tab
        handle_tab = QWidget()
        handle_tab_layout = QVBoxLayout(handle_tab)
        handle_tab_layout.setContentsMargins(8, 8, 8, 8)
        
        handle_lookup_group = QGroupBox("HANDLE LOOKUP")
        handle_lookup_layout = QHBoxLayout()
        handle_lookup_group.setLayout(handle_lookup_layout)
        
        handle_lookup_layout.addWidget(QLabel("Enter handle:"))
        self.handle_lookup_input = QLineEdit()
        handle_lookup_layout.addWidget(self.handle_lookup_input)
        
        lookup_btn = QPushButton("LOOK UP")
        handle_lookup_layout.addWidget(lookup_btn)
        
        handle_tab_layout.addWidget(handle_lookup_group)
        
        # Handle inspection results
        handle_tab_layout.addWidget(QLabel("Handle Inspection Results:"))
        self.handle_inspection_result = QTextEdit()
        self.handle_inspection_result.setReadOnly(True)
        handle_tab_layout.addWidget(self.handle_inspection_result)
        
        tab_widget.addTab(handle_tab, "HANDLE INSPECTION")
        
        # System info tab
        system_tab = QWidget()
        system_layout = QVBoxLayout(system_tab)
        system_layout.setContentsMargins(8, 8, 8, 8)
        
        system_info = QTextEdit()
        system_info.setReadOnly(True)
        system_info.setText(f"Python Version: {sys.version}\n"
                           f"Operating System: {os.name}\n"
                           f"Platform: {sys.platform}")
        system_layout.addWidget(system_info)
        
        tab_widget.addTab(system_tab, "SYSTEM INFORMATION")
        
        main_layout.addWidget(content_area)
        
        # Add resize grip for the debug window
        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 0, 12, 0)
        
        status_layout.addStretch()
        resize_grip = QSizeGrip(status_bar)
        resize_grip.setFixedSize(16, 16)
        status_layout.addWidget(resize_grip)
        
        main_layout.addWidget(status_bar)
        
        # Start mouse tracking timer
        self.mouse_timer = QTimer()
        self.mouse_timer.timeout.connect(self.track_mouse)
        self.mouse_timer.start(100)
        
        # Show the debug window
        self.debug_window.show()
        self.update_handle_status()
        
    def debug_window_mousePressEvent(self, event):
        """Handle mouse press for dragging frameless debug window"""
        if event.button() == Qt.LeftButton:
            self.debug_window_dragging = True
            self.debug_window_drag_position = event.globalPos() - self.debug_window.frameGeometry().topLeft()
            self.debug_window.setCursor(Qt.ClosedHandCursor)
            event.accept()
    
    def debug_window_mouseReleaseEvent(self, event):
        """Handle mouse release for dragging frameless debug window"""
        if event.button() == Qt.LeftButton:
            self.debug_window_dragging = False
            self.debug_window.setCursor(Qt.ArrowCursor)
            event.accept()
    
    def debug_window_mouseMoveEvent(self, event):
        """Handle mouse move for dragging frameless debug window"""
        if self.debug_window_dragging and event.buttons() == Qt.LeftButton:
            self.debug_window.move(event.globalPos() - self.debug_window_drag_position)
            event.accept()

    def refresh_current_parameter(self):
        """Refresh the current parameter data from local files"""
        param_id = self.param_id_label.text().strip()
        ecm_type = param_manager.get_ecm_type_from_text(self.last_parameter_text)
        
        if not param_id or not ecm_type:
            self.status_label.setText("❌ Cannot refresh: Missing parameter ID or ECM type")
            return
        
        self.status_label.setText("⟳ Loading parameter data...")
        
        try:
            # Get parameter details from the JSON file
            param_data, stored_details = param_manager.get_parameter_details(param_id, ecm_type)
            
            if param_data:
                # Update the UI with the stored parameter data
                stored_name = param_data.get("name", "")
                stored_desc = param_data.get("description", "")
                
                if stored_name:
                    self.param_name_label.setText(stored_name)
                
                if stored_desc:
                    self.param_desc_label.setText(stored_desc)
                
                # If we have stored details, update the details field
                if stored_details:
                    self.param_details_text.setText(stored_details)
                    self.log_debug(f"Refreshed parameter details for {param_id}")
                    self.status_label.setText(f"✓ Parameter data refreshed")
                else:
                    # Don't generate details text, leave it empty
                    self.param_details_text.clear()
                    self.status_label.setText(f"✓ Parameter refreshed, no details found")
            else:
                self.status_label.setText(f"❌ Parameter {param_id} not found in local data")
                
        except Exception as e:
            self.log_debug(f"Error refreshing parameter: {str(e)}")
            self.status_label.setText(f"❌ Error: {str(e)}")

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