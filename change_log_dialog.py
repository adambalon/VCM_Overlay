"""
Change Log Dialog for VCM Overlay

This module defines the ChangeLogDialog class, which displays a user's contributions
(pending, approved, and rejected) in a tabbed interface.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
                           QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, 
                           QHeaderView, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import datetime

# Import Firebase service
try:
    import firebase_service
    FIREBASE_AVAILABLE = True
    print("Firebase service successfully imported in change_log_dialog")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    print(f"Firebase service not available in change_log_dialog. Error: {str(e)}")


class ChangeLogDialog(QDialog):
    """Dialog to display user contributions (pending, accepted, rejected)"""
    def __init__(self, parent=None):
        super(ChangeLogDialog, self).__init__(parent)
        self.setWindowTitle("Your Change Log")
        self.resize(800, 600)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        
        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #111111;
                color: #CCCCCC;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            QLabel {
                color: #CCCCCC;
            }
            QTableWidget {
                background-color: #181818;
                color: #CCCCCC;
                gridline-color: #333333;
                border: 1px solid #333333;
                border-radius: 4px;
            }
            QTableWidget::item {
                background-color: #181818;
                color: #CCCCCC;
            }
            QHeaderView::section {
                background-color: #222222;
                color: #FFFFFF;
                border: 1px solid #333333;
                padding: 4px;
            }
            QLineEdit {
                background-color: #181818;
                color: #CCCCCC;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #2C3E50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #34495E;
            }
            QPushButton:pressed {
                background-color: #1A2530;
            }
        """)
        
        # Get current user and data
        self.current_user = firebase_service.get_current_user()
        self.user_email = self.current_user.get('email') if self.current_user else None
        self.user_id = self.current_user.get('uid') if self.current_user else None
        self.contributions = []
        
        # Setup UI
        self.init_ui()
        
        # Load initial data
        self.load_contributions()
    
    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title bar with close button
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #1a1a1a; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 10, 0)
        
        # Title label
        title_label = QLabel(f"Change Log for {self.user_email}")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #AA3333;
                color: #FFFFFF;
                border-radius: 12px;
                font-weight: bold;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #FF5555;
            }
        """)
        close_btn.clicked.connect(self.accept)
        title_bar_layout.addWidget(close_btn)
        
        layout.addWidget(title_bar)
        
        # Make title bar draggable
        title_bar.mousePressEvent = self.title_bar_mouse_press
        title_bar.mouseMoveEvent = self.title_bar_mouse_move
        
        # Content container
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # User info
        user_info_layout = QHBoxLayout()
        user_info_label = QLabel(f"Viewing contributions for: {self.user_email}")
        user_info_label.setStyleSheet("color: #AAAAAA;")
        user_info_layout.addWidget(user_info_label)
        user_info_layout.addStretch()
        content_layout.addLayout(user_info_layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search terms...")
        self.search_input.textChanged.connect(self.filter_results)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        content_layout.addLayout(search_layout)
        
        # Tab widget for different contribution statuses
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #181818;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #222222;
                color: #AAAAAA;
                border: 1px solid #333333;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #333333;
                color: #FFFFFF;
            }
            QTabBar::tab:hover {
                background-color: #2C3E50;
            }
        """)
        
        # Create tabs for different statuses
        self.all_tab = QWidget()
        self.pending_tab = QWidget()
        self.approved_tab = QWidget()
        self.rejected_tab = QWidget()
        
        # Setup tab layouts
        self.setup_tab(self.all_tab, "all")
        self.setup_tab(self.pending_tab, "pending")
        self.setup_tab(self.approved_tab, "approved")
        self.setup_tab(self.rejected_tab, "rejected")
        
        # Add tabs to widget
        self.tab_widget.addTab(self.all_tab, "All Contributions")
        self.tab_widget.addTab(self.pending_tab, "Pending")
        self.tab_widget.addTab(self.approved_tab, "Approved")
        self.tab_widget.addTab(self.rejected_tab, "Rejected")
        
        content_layout.addWidget(self.tab_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_contributions)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        content_layout.addLayout(button_layout)
        layout.addLayout(content_layout)
    
    def title_bar_mouse_press(self, event):
        """Handle mouse press events on the title bar"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def title_bar_mouse_move(self, event):
        """Handle mouse move events for dragging the window"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def setup_tab(self, tab, status):
        """Setup a tab with a table for displaying contributions"""
        tab_layout = QVBoxLayout(tab)
        
        # Create table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Date", "Parameter", "Old Value", "New Value", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Enable cell double-click to see full content
        table.cellDoubleClicked.connect(self.show_cell_details)
        
        # Store reference to the table
        tab.table = table
        tab_layout.addWidget(table)
    
    def load_contributions(self):
        """Load user contributions from Firebase"""
        if not FIREBASE_AVAILABLE or not self.user_id:
            return
            
        try:
            # Show loading indicator
            for tab in [self.all_tab, self.pending_tab, self.approved_tab, self.rejected_tab]:
                tab.table.setRowCount(0)
                tab.table.insertRow(0)
                tab.table.setItem(0, 0, QTableWidgetItem("Loading..."))
            
            # Get user's contributions from Firebase
            self.contributions = firebase_service.get_user_contributions(self.user_id)
            
            # Update UI with contributions
            self.update_tables()
            
        except Exception as e:
            print(f"Error loading contributions: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to load contributions: {str(e)}")
    
    def update_tables(self):
        """Update all tables with the latest data"""
        # Clear search filter first
        self.search_input.clear()
        
        # Process for each status tab
        self.update_table(self.all_tab.table, "all")
        self.update_table(self.pending_tab.table, "pending")
        self.update_table(self.approved_tab.table, "approved")
        self.update_table(self.rejected_tab.table, "rejected")
    
    def update_table(self, table, status):
        """Update a specific table with contributions matching the status"""
        table.setRowCount(0)
        
        filtered_data = self.contributions
        if status != "all":
            filtered_data = [item for item in self.contributions if item.get('status', '').lower() == status.lower()]
        
        for row, contribution in enumerate(filtered_data):
            table.insertRow(row)
            
            # Format date
            date_str = contribution.get('timestamp', '')
            if isinstance(date_str, (int, float)):
                date = datetime.datetime.fromtimestamp(date_str / 1000)
                date_str = date.strftime('%Y-%m-%d %H:%M')
                
            # Get values
            param_name = contribution.get('parameter_name', '')
            
            # Get old value and new value, ensuring they're not None
            old_value = contribution.get('old_value', '')
            if old_value is None:
                old_value = ''
            
            new_value = contribution.get('new_value', '')
            if new_value is None:
                new_value = ''
                
            # Format values to ensure they display well
            old_value = str(old_value)
            new_value = str(new_value)
            
            # Truncate values if too long for display
            max_display_length = 40
            old_display = old_value
            new_display = new_value
            
            if len(old_display) > max_display_length:
                old_display = old_display[:max_display_length] + "..."
            
            if len(new_display) > max_display_length:
                new_display = new_display[:max_display_length] + "..."
            
            status_text = contribution.get('status', '').capitalize()
            
            # Set table items
            date_item = QTableWidgetItem(date_str)
            param_item = QTableWidgetItem(param_name)
            old_item = QTableWidgetItem(old_display)
            new_item = QTableWidgetItem(new_display)
            status_item = QTableWidgetItem(status_text)
            
            # Store full values as data for viewing in detail
            old_item.setData(Qt.UserRole, old_value)
            new_item.setData(Qt.UserRole, new_value)
            
            # Color code the status
            if status_text.lower() == 'pending':
                status_item.setBackground(QColor(255, 255, 150))  # Light yellow
                status_item.setForeground(QColor(0, 0, 0))        # Black text for better visibility
            elif status_text.lower() == 'approved':
                status_item.setBackground(QColor(150, 255, 150))  # Light green
                status_item.setForeground(QColor(0, 0, 0))        # Black text for better visibility
            elif status_text.lower() == 'rejected':
                status_item.setBackground(QColor(255, 150, 150))  # Light red
                status_item.setForeground(QColor(0, 0, 0))        # Black text for better visibility
            
            table.setItem(row, 0, date_item)
            table.setItem(row, 1, param_item)
            table.setItem(row, 2, old_item)
            table.setItem(row, 3, new_item)
            table.setItem(row, 4, status_item)
    
    def filter_results(self):
        """Filter results based on search input"""
        search_text = self.search_input.text().lower()
        
        for tab in [self.all_tab, self.pending_tab, self.approved_tab, self.rejected_tab]:
            table = tab.table
            
            for row in range(table.rowCount()):
                # Default is visible
                table.setRowHidden(row, False)
                
                if search_text:
                    # Check if any cell in the row contains the search text
                    match_found = False
                    for col in range(table.columnCount()):
                        item = table.item(row, col)
                        if item and search_text in item.text().lower():
                            match_found = True
                            break
                    
                    # Hide row if no match found
                    if not match_found:
                        table.setRowHidden(row, True)
    
    def show_cell_details(self, row, column):
        """Show details of a cell when double-clicked"""
        # Only show details for old and new values
        if column < 2 or column > 3:
            return
            
        # Get the current tab and table
        current_tab = self.tab_widget.currentWidget()
        table = current_tab.table
        
        # Get the item
        item = table.item(row, column)
        if not item:
            return
        
        # Get the column name
        column_name = table.horizontalHeaderItem(column).text()
        
        # Get the value (prefer the data stored in UserRole)
        value = item.data(Qt.UserRole) if item.data(Qt.UserRole) else item.text()
        
        # Format the value for display
        if value:
            # Create a message box with the details
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"Contribution Detail")
            msg_box.setText(f"{column_name}:")
            msg_box.setDetailedText(str(value))
            
            # Style the message box for dark theme
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #222222;
                    color: #CCCCCC;
                }
                QLabel {
                    color: #CCCCCC;
                }
                QPushButton {
                    background-color: #2C3E50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #34495E;
                }
            """)
            
            msg_box.exec_() 