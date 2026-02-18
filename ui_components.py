import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os

class FileListTree(ctk.CTkFrame):
    def __init__(self, master, columns=("size", "status"), show_checkboxes=False, **kwargs):
        super().__init__(master, **kwargs)
        self.show_checkboxes = show_checkboxes
        self.columns = columns
        self._item_data = {} # iid -> data mapping
        
        # Grid Configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Style
        self._setup_style()
        
        # Treeview
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="extended")
        
        # Headings
        header_text = "Dosya Adı"
        if self.show_checkboxes:
            self.tree.heading("#0", text=f" ☑ {header_text}", anchor="w", command=self._toggle_all)
        else:
            self.tree.heading("#0", text=f" {header_text}", anchor="w")
            
        if "size" in columns:
            self.tree.heading("size", text="Boyut", anchor="e")
            self.tree.column("size", width=80, anchor="e")
            
        if "status" in columns:
            self.tree.heading("status", text="Durum", anchor="w")
            self.tree.column("status", width=100, anchor="w")
            
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbar
        self.scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        # Events
        if self.show_checkboxes:
            self.tree.bind("<Button-1>", self._on_click)

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Dark Theme Configuration
        bg_color = "#2b2b2b"
        fg_color = "#dce4ee"
        selected_bg = "#1f538d"
        heading_bg = "#3a3a3a"
        
        style.configure("Treeview", 
                        background=bg_color,
                        foreground=fg_color,
                        fieldbackground=bg_color,
                        borderwidth=0,
                        rowheight=28,
                        font=("Segoe UI", 10))
        
        style.configure("Treeview.Heading",
                        background=heading_bg,
                        foreground="#ffffff",
                        borderwidth=1,
                        relief="flat",
                        padding=5,
                        font=("Segoe UI", 10, "bold"))
        
        style.map("Treeview", 
                  background=[('selected', selected_bg)],
                  foreground=[('selected', '#ffffff')])
                  
        style.map("Treeview.Heading",
                  background=[('active', '#4a4a4a')])

    def add_item(self, text, is_folder=False, size_str="", status="", parent="", iid=None, data=None):
        """Add a generic item to the tree"""
        # Icons using unicode
        icon = "📂 " if is_folder else "📄 "
        if self.show_checkboxes:
            # Default checked
            icon = "☑ " + icon
        
        values = []
        if "size" in self.columns: values.append(size_str)
        if "status" in self.columns: values.append(status)
        
        try:
            new_id = self.tree.insert(parent, "end", iid=iid, text=f" {icon}{text}", values=values, open=True)
            if data is not None:
                self._item_data[new_id] = data
            return new_id
        except tk.TclError:
            # ID collision or other error, fallback to auto ID
            new_id = self.tree.insert(parent, "end", text=f" {icon}{text}", values=values, open=True)
            if data is not None:
                self._item_data[new_id] = data
            return new_id

    def add_path_item(self, path, is_folder=False, size_str="", status="", data=None):
        """
        Add item by relative path (e.g. 'folder/sub/file.txt').
        Automatically creates intermediate folders.
        Values are assigned only to the leaf node.
        """
        parts = path.replace("\\", "/").split("/")
        current_parent = ""
        
        # Create folder structure
        for i, part in enumerate(parts[:-1]):
            folder_path = "/".join(parts[:i+1])
            # Check existence
            if not self.tree.exists(folder_path):
                # Create folder node
                self.add_item(part, is_folder=True, parent=current_parent, iid=folder_path)
            current_parent = folder_path
            
        # Create leaf node
        name = parts[-1]
        # Use full path as IID for uniqueness
        leaf_id = path
        if not self.tree.exists(leaf_id):
            self.add_item(name, is_folder=is_folder, size_str=size_str, status=status, parent=current_parent, iid=leaf_id, data=data)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self._item_data.clear()

    def _on_click(self, event):
        """Handle checkbox clicks"""
        region = self.tree.identify("region", event.x, event.y)
        if region == "tree":
             # Check horizontal position to see if click is on the checkmark area
             # Column #0 width is variable, but usually checkmark is at the beginning.
             # Simply toggle if clicked broadly on the label.
             item_id = self.tree.identify_row(event.y)
             if item_id:
                col = self.tree.identify_column(event.x)
                if col == "#0":
                    self._toggle_check(item_id)

    def _toggle_check(self, item_id):
        text = self.tree.item(item_id, "text")
        if "☑" in text:
            new_text = text.replace("☑", "☐", 1)
            checked = False
        elif "☐" in text:
            new_text = text.replace("☐", "☑", 1)
            checked = True
        else:
            return 
            
        self.tree.item(item_id, text=new_text)
        
        # Propagate to children (if folder)
        self._set_check_recursive(item_id, checked)

    def _set_check_recursive(self, item_id, checked):
        text = self.tree.item(item_id, "text")
        if checked:
            new_text = text.replace("☐", "☑", 1)
        else:
            new_text = text.replace("☑", "☐", 1)
        self.tree.item(item_id, text=new_text)
        
        for child in self.tree.get_children(item_id):
            self._set_check_recursive(child, checked)

    def _toggle_all(self):
        children = self.tree.get_children("")
        if not children: return
        
        # Determine state based on first item
        first_text = self.tree.item(children[0], "text")
        should_check = "☐" in first_text
        
        for child in children:
            self._set_check_recursive(child, should_check)

    def get_checked_data(self):
        """Return list of data objects associated with checked items"""
        collected = []
        
        def traverse(parent):
            for iid in self.tree.get_children(parent):
                text = self.tree.item(iid, "text")
                is_checked = "☑" in text
                
                # We collect data if present and checked
                if is_checked and iid in self._item_data:
                    collected.append(self._item_data[iid])
                    
                traverse(iid)
        
        traverse("")
        return collected

    def get_item_count(self):
        return len(self.tree.get_children(""))

    def set_item_value(self, item_id, column, value):
        """Update a specific column value for an item"""
        if self.tree.exists(item_id):
            self.tree.set(item_id, column, value)

    def find_item_by_data(self, data_value):
        """Find item ID by its data value (slow, linear search)"""
        # Linear search through _item_data values
        for iid, data in self._item_data.items():
            if data == data_value:
                return iid
        return None
