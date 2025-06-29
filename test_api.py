#!/usr/bin/env python3
"""Simple test script to check if the API server starts up correctly"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Test if we can import the main module
    from main import app, logger
    print("✓ Successfully imported main module")
    
    # Test if we can create the FastAPI app
    print(f"✓ FastAPI app created: {app}")
    
    # Test if we can access the get_available_font function
    from main import get_available_font
    font = get_available_font()
    print(f"✓ Available font: {font}")
    
    print("\n✅ API module imports successfully!")
    print("The API should be able to start now.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Missing dependencies. Please install requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ Other error: {e}")
    sys.exit(1)