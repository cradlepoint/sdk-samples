#!/usr/bin/env python3
import os
import shutil
import subprocess
from pathlib import Path

def find_cp_py_files():
    """Find all cp.py files in the repository"""
    cp_files = []
    for root, dirs, files in os.walk('.'):
        # Skip .git directory
        if '.git' in root:
            continue
        if 'cp.py' in files:
            cp_files.append(os.path.join(root, 'cp.py'))
    return cp_files

def get_reference_cp_py():
    """Get the reference cp.py from app_template"""
    reference_path = './app_template/cp.py'
    if os.path.exists(reference_path):
        return reference_path
    else:
        print(f"Error: Reference file {reference_path} not found")
        return None

def update_cp_py_files():
    """Update all cp.py files with the reference version"""
    cp_files = find_cp_py_files()
    print(f"Found {len(cp_files)} cp.py files")
    
    # Get the reference cp.py
    reference_cp = get_reference_cp_py()
    if not reference_cp:
        print("Reference cp.py not found. Exiting.")
        exit(1)
    
    print(f"Using reference: {reference_cp}")
    with open(reference_cp, 'r') as f:
        reference_content = f.read()
    
    updated_count = 0
    for cp_file in cp_files:
        try:
            # Skip the reference file itself
            if cp_file == reference_cp:
                print(f"Skipping reference file: {cp_file}")
                continue
            
            with open(cp_file, 'r') as f:
                current_content = f.read()
            
            # Only update if content is different
            if current_content != reference_content:
                with open(cp_file, 'w') as f:
                    f.write(reference_content)
                print(f"Updated: {cp_file}")
                updated_count += 1
            else:
                print(f"No changes needed: {cp_file}")
                
        except Exception as e:
            print(f"Error updating {cp_file}: {e}")
    
    return updated_count

if __name__ == "__main__":
    updated = update_cp_py_files()
    print(f"Updated {updated} cp.py files")
    # Exit with code 1 if files were updated (to trigger commit)
    exit(0)
