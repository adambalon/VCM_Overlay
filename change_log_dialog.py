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
        
        # Title and user info
        title_layout = QHBoxLayout()
        title_label = QLabel(f"<h2>Change Log for {self.user_email}</h2>")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search terms...")
        self.search_input.textChanged.connect(self.filter_results)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Tab widget for different contribution statuses
        self.tab_widget = QTabWidget()
        
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
        
        layout.addWidget(self.tab_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_contributions)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
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
            old_value = contribution.get('old_value', '')
            new_value = contribution.get('new_value', '')
            status_text = contribution.get('status', '').capitalize()
            
            # Set table items
            table.setItem(row, 0, QTableWidgetItem(date_str))
            table.setItem(row, 1, QTableWidgetItem(param_name))
            table.setItem(row, 2, QTableWidgetItem(str(old_value)))
            table.setItem(row, 3, QTableWidgetItem(str(new_value)))
            table.setItem(row, 4, QTableWidgetItem(status_text))
            
            # Color code the status
            status_item = table.item(row, 4)
            if status_text.lower() == 'pending':
                status_item.setBackground(QColor(255, 255, 150))  # Light yellow
            elif status_text.lower() == 'approved':
                status_item.setBackground(QColor(150, 255, 150))  # Light green
            elif status_text.lower() == 'rejected':
                status_item.setBackground(QColor(255, 150, 150))  # Light red
    
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