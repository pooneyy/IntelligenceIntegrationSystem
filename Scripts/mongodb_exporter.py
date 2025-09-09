import json
import argparse
import subprocess
from typing import Dict, Optional, Tuple
import os


def export_mongodb_data(
        uri: str,
        db: str,
        collection: str,
        output_file: str,
        query: Optional[Dict] = None,
        fields: Optional[str] = None,
        export_format: str = "json"
) -> Tuple[bool, str]:
    """
    Export MongoDB data to file (compatible with mongoimport format)

    Parameters:
    uri: MongoDB connection string (e.g. "mongodb://user:pass@localhost:27017")
    db: Database name
    collection: Collection name
    output_file: Output file path
    query: Query conditions for exporting data (e.g. {"age": {"$gt": 25}})
    fields: Specify fields to export (e.g. "name,age,email")
    export_format: Export format ("json" or "csv")

    Returns:
    Tuple[bool, str]: Success status and message
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Build base command as list to avoid shell injection and quoting issues
    cmd = [
        "mongoexport",
        f"--uri={uri}",
        f"--db={db}",
        f"--collection={collection}",
        f"--out={output_file}"
    ]

    # Add format parameter
    if export_format.lower() == "csv":
        cmd.append("--type=csv")
        if not fields:
            return False, "Fields parameter must be specified for CSV export"

    # Add query condition (properly formatted as JSON string)
    if query:
        # Use proper JSON formatting without extra quotes
        query_str = json.dumps(query)
        cmd.extend(["--query", query_str])

    # Add field selection
    if fields:
        cmd.extend(["--fields", fields])

    # Execute export command
    try:
        # Use list format instead of shell string to avoid quoting issues
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=300  # Add timeout to prevent hanging
        )
        print("✅ Export successful!")
        print(f"📁 File path: {output_file}")
        print(f"📊 Export format: {export_format.upper()}")
        if query:
            print(f"🔍 Query condition: {json.dumps(query)}")
        return True, "Export successful"
    except subprocess.CalledProcessError as e:
        error_msg = f"Export failed: {e.stderr if e.stderr else 'Unknown error'}"
        print(f"❌ {error_msg}")
        return False, error_msg
    except FileNotFoundError:
        error_msg = "mongoexport tool not found, please install MongoDB database tools"
        print(f"❌ {error_msg}")
        return False, error_msg
    except subprocess.TimeoutExpired:
        error_msg = "Export timed out after 5 minutes"
        print(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


if __name__ == "__main__":
    # Command line argument parsing
    parser = argparse.ArgumentParser(description="MongoDB Data Export Tool")
    parser.add_argument("--uri", required=True, help="MongoDB connection URI")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--collection", required=True, help="Collection name")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--query", type=json.loads, help="Query conditions (JSON format)")
    parser.add_argument("--fields", help="Export fields (comma separated)")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")

    args = parser.parse_args()

    # Execute export
    success, message = export_mongodb_data(
        uri=args.uri,
        db=args.db,
        collection=args.collection,
        output_file=args.output,
        query=args.query,
        fields=args.fields,
        export_format=args.format
    )

    exit(0 if success else 1)
