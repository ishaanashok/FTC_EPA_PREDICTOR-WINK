#!/usr/bin/env python3
"""
Environment loader utility for FTC Teams Fetcher

This utility loads environment variables from a .env file.
"""

import os
from pathlib import Path


def load_env_file(env_file_path: str = '.env'):
    """
    Load environment variables from a .env file
    
    Args:
        env_file_path: Path to the .env file
    """
    env_file = Path(env_file_path)
    
    if not env_file.exists():
        return False
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Split on first = sign
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Set environment variable
                    os.environ[key] = value
        
        return True
        
    except Exception as e:
        print(f"Error loading .env file: {e}")
        return False


# Auto-load .env file when this module is imported
if Path('.env').exists():
    load_env_file()
