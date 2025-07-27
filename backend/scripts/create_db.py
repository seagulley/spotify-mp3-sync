#!/usr/bin/env python3
"""Create database with correct schema"""

from models import create_tables

if __name__ == "__main__":
    print("Creating database tables...")
    create_tables()
    print("Database created successfully!") 