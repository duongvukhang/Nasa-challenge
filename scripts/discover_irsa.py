#!/usr/bin/env python3
"""
IRSA TAP and ObsCore Discovery Utility for SPHEREx Archive.
Inspects the live TAP service schema at https://irsa.ipac.caltech.edu/TAP
for the spherex.obscore table and records actual columns, types, and sample data.
"""
import sys
import json
from pathlib import Path

def discover_tap():
    print("=" * 60)
    print("SPHEREx IRSA TAP Schema Discovery")
    print("Service: https://irsa.ipac.caltech.edu/TAP")
    print("=" * 60)

    try:
        import pyvo
    except ImportError:
        print("[ERROR] pyvo is not installed. Please install pyvo to run this script.")
        return False

    tap_url = "https://irsa.ipac.caltech.edu/TAP"
    try:
        service = pyvo.dal.TAPService(tap_url)
        print(f"Connecting to {tap_url}...")
        tables = service.tables
        
        target_table = None
        for table in tables:
            if "spherex" in table.name.lower():
                print(f"Found SPHEREx table: {table.name} (description: {table.description})")
                if "obscore" in table.name.lower():
                    target_table = table

        if target_table is None:
            print("[WARN] spherex.obscore not found in public table list, attempting direct ADQL query...")
            query = "SELECT TOP 1 * FROM spherex.obscore"
            res = service.search(query)
            print(f"Direct query successful! Available columns ({len(res.fieldnames)}):")
            for col in res.fieldnames:
                print(f"  - {col}")
            return True

        print(f"\nSchema for {target_table.name}:")
        for col in target_table.columns:
            print(f"  - {col.name:25s} | {str(col.datatype):15s} | {col.description or ''}")

        # Query a sample row
        print("\nQuerying 1 sample row from spherex.obscore...")
        res = service.search("SELECT TOP 1 * FROM spherex.obscore")
        if len(res) > 0:
            print("Sample row:")
            for k in res.fieldnames:
                print(f"  {k}: {res[0][k]}")
        return True

    except Exception as e:
        print(f"\n[NETWORK/DISCOVERY STATUS] Live TAP discovery failed or is blocked: {type(e).__name__}: {e}")
        print("Note: In sandboxed or offline environments without external network egress, live discovery cannot be completed.")
        return False

if __name__ == "__main__":
    success = discover_tap()
    sys.exit(0 if success else 1)
