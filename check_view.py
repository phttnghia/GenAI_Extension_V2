#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check view structure"""

from config.settings import settings
import pyodbc

try:
    print("🔌 Connecting to database...")
    conn_str = (
        f'DRIVER={settings.AZURE_SQL_DRIVER};'
        f'SERVER={settings.AZURE_SQL_SERVER};'
        f'DATABASE={settings.AZURE_SQL_DATABASE};'
        f'UID={settings.AZURE_SQL_USER};'
        f'PWD={settings.AZURE_SQL_PASSWORD};'
        f'Connection Timeout=15;'
        'Encrypt=yes;'
        'TrustServerCertificate=no;'
    )
    
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("✅ Connected!")
    print("\n📋 View columns:")
    
    # Get first row to check structure
    cursor.execute('''
        SELECT TOP 1 * 
        FROM [bug-management_dm_test].[vw_bug_report_by_testplan]
    ''')
    
    # Print column names
    for col_desc in cursor.description:
        print(f"  ✓ {col_desc[0]}")
    
    # Get first row data
    row = cursor.fetchone()
    if row:
        print("\n📊 Sample data (first row):")
        for i, col_desc in enumerate(cursor.description):
            print(f"  {col_desc[0]}: {row[i]}")
    
    # Count rows
    cursor.execute('SELECT COUNT(*) FROM [bug-management_dm_test].[vw_bug_report_by_testplan]')
    count = cursor.fetchone()[0]
    print(f"\n📈 Total rows in view: {count}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}")
    print(f"   {str(e)}")
    import traceback
    traceback.print_exc()
