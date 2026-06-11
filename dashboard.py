import threading
import logging
import io
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file

# ------------------------------------------------------------
# Logging setup for this module
# ------------------------------------------------------------
# Create a logger for the dashboard module
logger = logging.getLogger(__name__)
# Set default level to INFO (can be changed externally)
logger.setLevel(logging.INFO)
# If no handlers exist, add a console handler with a reasonable format
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

app = Flask(__name__)

# Global variable that holds the manager instance (set later by run_flask_dashboard)
session_manager = None

# Suppress verbose Flask/Werkzeug logs to keep output clean
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route('/')
def index():
    """Serve the main dashboard HTML page."""
    logger.info("Rendering main dashboard page (index)")
    return render_template('index.html')


@app.route('/api/boards')
def get_boards():
    """
    API endpoint that returns the status of all boards.
    Expects session_manager to be initialized.
    """
    logger.info("Received request for /api/boards")
    if session_manager is None:
        error_msg = "Manager not initialized"
        logger.error(error_msg)
        return jsonify({"error": error_msg})

    logger.debug("Fetching board status from session_manager")
    data = session_manager.get_all_boards_status()
    logger.debug(f"Returning board status with {len(data)} entries")
    return jsonify(data)


# New route to display the date selection page for export
@app.route('/export-page')
def export_page():
    """Serve the Excel export date selection page."""
    logger.info("Rendering export page (export.html)")
    return render_template('export.html')


# New route to generate and download an Excel file with data in the given date range
@app.route('/api/export-excel', methods=['GET'])
def export_excel():
    """
    API endpoint that exports data between start_date and end_date as an Excel file.
    Query parameters: start_date, end_date (format expected by session_manager).
    """
    logger.info("Received export request to Excel")
    if session_manager is None:
        logger.error("Export failed: session_manager not initialized")
        return "Manager not initialized", 500

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Validate that both dates are provided
    if not start_date or not end_date:
        logger.warning("Export request missing start_date or end_date")
        return "لطفا هر دو تاریخ را انتخاب کنید.", 400

    logger.info(f"Exporting data from {start_date} to {end_date}")

    try:
        # Attempt to fetch real data from the session manager
        raw_data = session_manager.get_data_between_dates(start_date, end_date)
        logger.debug(f"Retrieved {len(raw_data)} raw records from session_manager")
    except AttributeError:
        # Fallback: if the method does not exist on the manager, create dummy data
        logger.warning("session_manager has no get_data_between_dates method - using test data")
        raw_data = [
            {"id": 1, "date": start_date, "status": "test 1"},
            {"id": 2, "date": end_date, "status": "test 2"}
        ]
        logger.debug(f"Test data created: {len(raw_data)} records")

    # Convert the raw data into a pandas DataFrame
    df = pd.DataFrame(raw_data)
    logger.debug(f"DataFrame shape: {df.shape}")

    # If no data is found for the given range, return 404
    if df.empty:
        logger.warning(f"No data found between {start_date} and {end_date}")
        return "داده ای در این بازه زمانی یافت نشد.", 404

    # Create an Excel file in memory (without writing to disk)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Export')
    output.seek(0)  # Rewind the buffer to the beginning

    # Send the file to the client as an attachment
    filename = f"export_{start_date}_to_{end_date}.xlsx"
    logger.info(f"Export successful, sending file: {filename}")
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def run_flask_dashboard(manager_instance):
    """
    Initialize the global session_manager and start the Flask development server.
    This function is intended to be called from another thread.

    Args:
        manager_instance: The manager object that provides board status and data retrieval methods.
    """
    logger.info("Starting Flask dashboard with provided manager instance")
    global session_manager
    session_manager = manager_instance
    logger.debug("Global session_manager has been set")

    # Run Flask app on all available IPs, port 5000, without debug mode and without reloader
    logger.info("Launching Flask app on 0.0.0.0:5000 (debug=False, use_reloader=False)")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)