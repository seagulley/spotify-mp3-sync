#!/usr/bin/env python3
"""
Test runner for Spotify MP3 Sync
Runs all tests in the test directory
"""

import sys
import os
import subprocess
import pytest

def run_tests():
    """Run all tests in the test directory"""
    print("🧪 Running Spotify MP3 Sync Tests")
    print("=" * 40)
    
    # Add the project root to Python path (one level up from test directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Run pytest on the current test directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # Run pytest with verbose output
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_dir, 
            "-v",
            "--tb=short"
        ], capture_output=False, text=True)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
        else:
            print(f"\n❌ Some tests failed (exit code: {result.returncode})")
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1
    
    return result.returncode

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code) 