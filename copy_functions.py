#!/usr/bin/env python
import os
import shutil
import sys
import json
from pathlib import Path

def copy_functions():
    """Copy function handlers from host to Docker volume."""
    # Source directory
    src_dir = Path('functions')
    if not src_dir.exists():
        print(f"Error: Source directory 'functions' does not exist")
        return False
    
    # Target directory inside Docker volume
    target_dir = Path('/app/functions')
    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created target directory: {target_dir}")
        except Exception as e:
            print(f"Error creating target directory: {e}")
            return False
    
    # Get list of function directories
    function_dirs = [d for d in src_dir.iterdir() if d.is_dir()]
    
    if not function_dirs:
        print(f"No function directories found in {src_dir}")
        return False
    
    # Copy each function's handler
    for func_dir in function_dirs:
        func_id = func_dir.name
        target_func_dir = target_dir / func_id
        
        # Create target function directory
        target_func_dir.mkdir(parents=True, exist_ok=True)
        
        # Look for handler files
        for ext in ['py', 'js']:
            handler_file = func_dir / f'handler.{ext}'
            if handler_file.exists():
                target_handler = target_func_dir / f'handler.{ext}'
                try:
                    shutil.copy2(handler_file, target_handler)
                    # Make sure permissions are correct
                    os.chmod(target_func_dir, 0o777)
                    os.chmod(target_handler, 0o777)
                    print(f"Copied {handler_file} to {target_handler}")
                except Exception as e:
                    print(f"Error copying {handler_file}: {e}")
                break
        else:
            print(f"Warning: No handler file found in {func_dir}")
    
    return True

if __name__ == "__main__":
    if os.geteuid() == 0:  # Check if running as root
        success = copy_functions()
        if success:
            print("Functions copied successfully")
        else:
            print("Failed to copy functions")
    else:
        print("This script must be run as root to modify files in the Docker volume")
        print("Try: sudo python copy_functions.py") 