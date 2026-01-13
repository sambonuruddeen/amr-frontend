from flask import Flask, render_template, jsonify, Response, send_file, flash, redirect, url_for
from flask import request, session
import csv
import threading
import time
import mysql.connector
import logging
import random
from datetime import datetime
import io

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_very_secret_key' # It's important to set a secret key for flashing

data = []


logging.basicConfig(level=logging.INFO)

# MySQL Database Settings
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "jed_data"
DB_USER = "root"
DB_PASSWORD = ""


def get_db_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return conn

@app.route('/stream_meters', methods=['GET'])
def generate_dummy_data():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('''
            SELECT 
                fr.*,
                fd.feeder_name, fd.band, fd.transformer_rating, fd.location
            FROM 
                meter_readings fr
            INNER JOIN (
                SELECT 
                    meter_serial_number, MAX(timestamp) AS max_timestamp
                FROM 
                    meter_readings
                GROUP BY 
                    meter_serial_number
            ) latest
            ON 
                fr.meter_serial_number = latest.meter_serial_number 
                AND fr.timestamp = latest.max_timestamp
            INNER JOIN feeder_details fd
                ON fr.meter_serial_number = fd.meter_number
        ''')

    # cur.execute('''
    #     SELECT 
    #         fr.*
    #     FROM 
    #         meter_readings fr
    #     INNER JOIN (
    #         SELECT 
    #             meter_serial_number, MAX(timestamp) AS max_timestamp
    #         FROM 
    #             meter_readings
    #         GROUP BY 
    #             meter_serial_number
    #     ) latest
    #     ON 
    #         fr.meter_serial_number = latest.meter_serial_number AND fr.timestamp = latest.max_timestamp
    # ''')
    # cur.execute('''
    #         SELECT
    #             DISTINCT ON (meter_id) meter_id, real_power, apparent_power, power_factor, supply_voltage, lrms1_1, acc_power, acc_mins, acc_sec, timestamp
    #         FROM 
    #             meter_readings
    #         ORDER BY  
    #             meter_id, timestamp DESC;

    # ''')
    feeders = cur.fetchall()
    cur.close()
    conn.close()
    return feeders

def fetch_data():
    global data
    while True:
        try:
            # Generate dummy data
            dummy_data = generate_dummy_data()
            data = dummy_data

            # Log the generated data
            logging.info(f"Generated data: {dummy_data}")

        except Exception as e:
            logging.error(f"Error generating data: {e}")
        time.sleep(3)


@app.route('/data')
def get_data():
    global data
    try:
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error in /data route: {e}")
        return jsonify({"error": "Internal server error"}), 500
        

# PAGES
@app.route("/",  methods=['GET'])
def dashboard():
    return render_template('dashboard.html')

@app.route("/meter_reading",  methods=['GET', 'POST'])
def reports():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT 
            meter_number, feeder_name
        FROM 
            feeder_details
    ''')
    feeders = cur.fetchall()
    cur.close()
    conn.close()
    if request.method == 'GET':
        feeder_name = None
        start = None
        end = None
        report = []
    else:
        feeder_name = request.form.get('feeder_name')
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT
                mr.*, fd.feeder_name
            FROM
                meter_readings mr
            JOIN
                feeder_details fd ON mr.meter_serial_number = fd.meter_number
            WHERE
                mr.meter_serial_number = %s AND mr.timestamp BETWEEN %s AND %s
           
            ORDER BY
                mr.timestamp DESC
            ''', (feeder_name, start, end)
        )
        report = cur.fetchall()
        cur.close()
        conn.close()
    return render_template('meter_reading.html', feeders=feeders, report=report, feeder_name=feeder_name, start=start, end=end)

@app.route("/report",  methods=['GET', 'POST'])
def meter_readings():

    if request.method == 'GET':
        start = None
        end = None
        report = []
    else:
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute('''
            SELECT 
                    mr.*, fd.* 
            FROM 
                    meter_readings mr
            JOIN 
                    feeder_details fd ON mr.meter_serial_number = fd.meter_number
            WHERE 
                    mr.timestamp BETWEEN %s AND %s
            ORDER BY 
                    mr.meter_serial_number, mr.timestamp DESC;
        ''', (start, end)
        )
        report = cur.fetchall()
        cur.close()
        conn.close()
    return render_template('report.html', report=report, start=start, end=end)


@app.route("/new_meter",  methods=['GET', 'POST'])
def new_meter():
    if request.method == 'POST':
        # Get Form Data
        meter_number = request.form.get('meter_number')
        feeder_name = request.form.get('feeder_name')
        sim_card_number = request.form.get('sim_card_number')
        location = request.form.get('location')
        distribution_substation = request.form.get('distribution_substation')
        service_center = request.form.get('service_center')
        business_unit = request.form.get('business_unit')
        region = request.form.get('region')
        transformer_rating = request.form.get('transformer_rating')
        band = request.form.get('band')

        conn = get_db_connection()
        cur = conn.cursor()
        feeder_name = request.form.get('feeder_name')
        # Add other fields as needed, e.g. location, description, etc.
        cur.execute('''
            INSERT INTO feeder_details (meter_number, feeder_name, sim_card_number, location, distribution_substation, service_center, business_unit, region, transformer_rating, band)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (meter_number, feeder_name, sim_card_number, location, distribution_substation, service_center, business_unit, region, transformer_rating, band))
        conn.commit()
        cur.close()
        conn.close()
        flash("New feeder added successfully.", "success")
        return redirect(url_for('meters'))

    return render_template('new_meter.html')

@app.route("/meters", methods=['GET'])
def meters():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('''
        SELECT 
            *
        FROM 
            feeder_details
    ''')
    feeders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('meters.html', feeders=feeders)


@app.route("/download_csv")
def download_csv():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('''
        SELECT 
            mr.*, fd.* 
        FROM meter_readings mr
        JOIN feeder_details fd ON mr.meter_serial_number = fd.meter_number
        WHERE mr.timestamp BETWEEN %s AND %s
        ORDER BY mr.meter_serial_number, mr.timestamp DESC;
    ''', (start_date, end_date)
    )
    meters = cur.fetchall()
    cur.close()
    conn.close()

    if not meters:
        flash("No data found for the selected date range.", "warning")
        return redirect(url_for('meter_readings'))

    # Use io.StringIO for in-memory CSV generation
    output = io.StringIO()
    writer = csv.writer(output)

    # Define the header and the order of columns
    header = [
        'region', 'business_unit', 'service_center', 'distribution_substation', 
        'meter_number', 'feeder_name', 'sim_card_number', 'location', 
        'transformer_rating', 'band', 'clock', 'voltage_l1', 'voltage_l2', 
        'voltage_l3', 'current_l1', 'current_l2', 'current_l3', 
        'active_power_plus', 'active_power_minus', 'reactive_power_plus', 
        'reactive_power_minus', 'active_energy_import', 'active_energy_export', 
        'reactive_energy_import', 'reactive_energy_export', 'power_factor', 
        'frequency', 'timestamp'
    ]
    writer.writerow(header)

    for meter in meters:
        # Create a row with values in the correct order
        row = [meter.get(col, '') for col in header]
        writer.writerow(row)
 
    # Create a direct download response with the CSV data and appropriate headers
    response = Response(output.getvalue(), content_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=profile_data.csv"
 
    return response




# @app.route('/get_readings')
# def get_readings():
#     try:
#         response = requests.get("http://localhost:5000/stream_meters")
#         response.raise_for_status()  # Check if the request was successful
#         readings = response.json()  # Parse the JSON data from the response
#     except requests.RequestException as e:
#         return jsonify({"error": f"Error fetching data: {e}"}), 500

#     return jsonify(readings)


#@app.route("/meter/<int:id>")
# def meter(id: int):
#     readings = requests.get(
#             "http://localhost:5000/meter/{id}",
#     )
#     #return render_template('meter_readings.html', readings=readings)
#     return jsonify(readings)


if __name__ == "__main__":
#     #app.run(debug=True)
    threading.Thread(target=fetch_data, daemon=True).start()
    app.run(host='0.0.0.0', port=8000)