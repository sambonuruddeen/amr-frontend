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


# --- BILLING & MANAGEMENT MODULES ---

@app.route("/tariffs", methods=['GET', 'POST'])
def tariffs():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name')
        band = request.form.get('band')
        rate = request.form.get('rate')
        effective_date = request.form.get('effective_date')

        cur.execute('''
            INSERT INTO tariffs (name, band, rate_per_kwh, effective_date)
            VALUES (%s, %s, %s, %s)
        ''', (name, band, rate, effective_date))
        conn.commit()
        flash("Tariff created successfully.", "success")
        return redirect(url_for('tariffs'))

    cur.execute("SELECT * FROM tariffs ORDER BY effective_date DESC")
    tariffs_data = cur.fetchall()
    
    # Get distinct bands from feeder_details to populate dropdown
    cur.execute("SELECT DISTINCT band FROM feeder_details WHERE band IS NOT NULL")
    bands = [row['band'] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    return render_template('tariffs.html', tariffs=tariffs_data, bands=bands)

@app.route("/customers", methods=['GET', 'POST'])
def customers():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            name = request.form.get('name')
            account_number = request.form.get('account_number')
            email = request.form.get('email')
            phone = request.form.get('phone')
            address = request.form.get('address')
            
            try:
                cur.execute('''
                    INSERT INTO customers (name, account_number, email, phone, address)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (name, account_number, email, phone, address))
                conn.commit()
                flash("Customer added successfully.", "success")
            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
                
        elif action == 'assign_meter':
            customer_id = request.form.get('customer_id')
            meter_number = request.form.get('meter_number')
            
            cur.execute('''
                UPDATE feeder_details SET customer_id = %s WHERE meter_number = %s
            ''', (customer_id, meter_number))
            conn.commit()
            flash(f"Meter {meter_number} assigned to customer.", "success")

        return redirect(url_for('customers'))

    # Fetch Customers
    cur.execute("SELECT * FROM customers ORDER BY created_at DESC")
    customers_data = cur.fetchall()

    # Fetch Meters for assignment (optionally filter those without customers)
    cur.execute("SELECT meter_number, feeder_name, customer_id FROM feeder_details")
    meters = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('customers.html', customers=customers_data, meters=meters)

@app.route("/billing", methods=['GET'])
def billing():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    # Fetch recent bills with customer and tariff info
    cur.execute('''
        SELECT b.*, c.name as customer_name, c.account_number, t.name as tariff_name
        FROM bills b
        JOIN customers c ON b.customer_id = c.id
        LEFT JOIN tariffs t ON b.tariff_id = t.id
        ORDER BY b.created_at DESC
        LIMIT 50
    ''')
    bills = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('billing.html', bills=bills)

@app.route("/billing/generate", methods=['POST'])
def generate_bills():
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    try:
        # 1. Get all meters that are assigned to a customer
        cur.execute('''
            SELECT meter_number, customer_id, band 
            FROM feeder_details 
            WHERE customer_id IS NOT NULL
        ''')
        meters_to_bill = cur.fetchall()
        
        generated_count = 0
        
        for meter in meters_to_bill:
            meter_id = meter['meter_number']
            customer_id = meter['customer_id']
            band = meter['band']
            
            # 2. Calculate Usage: Max Reading - Min Reading in the period
            cur.execute('''
                SELECT MIN(active_energy_import) as start_read, MAX(active_energy_import) as end_read
                FROM meter_readings
                WHERE meter_serial_number = %s AND timestamp BETWEEN %s AND %s
            ''', (meter_id, start_date, end_date))
            readings = cur.fetchone()
            
            if not readings or readings['start_read'] is None or readings['end_read'] is None:
                continue # Skip if no data
                
            start_read = float(readings['start_read'])
            end_read = float(readings['end_read'])
            usage = end_read - start_read
            
            if usage < 0: usage = 0 # Should not happen usually
            
            # 3. Find Tariff
            # Logic: Find most recent tariff for this Band or General
            cur.execute('''
                SELECT * FROM tariffs 
                WHERE (band = %s OR band = 'GENERAL') AND effective_date <= %s
                ORDER BY effective_date DESC LIMIT 1
            ''', (band, end_date))
            tariff = cur.fetchone()
            
            tariff_id = tariff['id'] if tariff else None
            rate = float(tariff['rate_per_kwh']) if tariff else 0.0
            
            # 4. Calculate Amount
            amount = usage * rate
            
            # 5. Insert Bill
            cur.execute('''
                INSERT INTO bills (meter_serial_number, customer_id, tariff_id, billing_period_start, billing_period_end, total_kwh, tariff_rate_applied, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (meter_id, customer_id, tariff_id, start_date, end_date, usage, rate, amount))
            generated_count += 1
            
        conn.commit()
        if generated_count > 0:
            flash(f"Successfully generated {generated_count} bills.", "success")
        else:
            flash("No bills generated. Check if meters have readings and assigned customers.", "warning")
            
    except Exception as e:
        conn.rollback()
        logging.error(f"Billing Error: {e}")
        flash(f"Error generating bills: {e}", "danger")
        
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('billing'))

if __name__ == "__main__":
    threading.Thread(target=fetch_data, daemon=True).start()
    app.run(host='0.0.0.0', port=8000)