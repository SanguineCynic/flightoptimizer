# Generic python packages
import os, requests, psycopg2, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Flask imports
from app import app, db, login_manager
from flask import render_template, request, redirect, url_for, flash, jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app.models import UserProfile, Icao, Airport
from app.forms import LoginForm, FuelPredictionForm, EmissionForm
from werkzeug.security import check_password_hash, generate_password_hash

# Amadeus for live flight data
from amadeus import Client, ResponseError

# AI model for fuel emissions predictions
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

###
# Routing for your application.
###

@app.route('/')
@login_required
def home():
    """Render website's home page."""
    conn, cur = get_db_connection()
    
    # Queries the Icao model from models.py to check for table population. If empty, populate.
    if Icao.query.first() is None:
        with open(os.getcwd()+"\\app\\static\\sql\\icao_query.sql", "r", encoding="utf-8") as file:
            cur.execute(file.read())
            conn.commit()
    
    # Query to get all ICAO codes
    cur.execute("SELECT * FROM icao_codes")
    rows = cur.fetchall()

    region_names = [row[0] for row in rows]
    icao_codes = [row[1] for row in rows]
    airports = [row[2] for row in rows]

    return render_template('home.html', icao_codes=icao_codes, region_names=region_names, airports=airports)


@app.route('/about/')
def about():
    """Render the website's about page."""
    return render_template('about.html', name="Mary Jane")

# This needs to be here. Without it, the endpoint /weather/<icao> cannot exist
@app.route('/weather/')
def weather():
    return redirect(url_for('home'))

@app.route('/weather/<icao>', methods=['GET'])
@login_required
def airport_weather(icao):
    api_key = os.environ.get('CX_WEATHER_API_KEY') 
    url = f'https://api.checkwx.com/metar/{icao}/nearest/decoded'
    headers = {'X-API-Key': api_key}

    taf_data = fetch_taf_data(icao)
    sigmet_data = fetch_sigmet_data(icao)
    taf_impacts = analyze_taf_fuel_impact(taf_data)
    sigmet_impacts = analyze_sigmet_fuel_impact(sigmet_data)

    response = requests.request("GET", url, headers={'X-API-Key': api_key})
    try:
        data = response.json()["data"][0]
    except IndexError:
        flash('Incorrect ICAO code', 'warning')
        return redirect(url_for('home'))

    temperature_data = data["temperature"]
    degsC = temperature_data["celsius"]
    degsF = temperature_data["fahrenheit"]

    try:
        wind_data=data["wind"]
        speedKPH = wind_data["speed_kph"]
        speedMPH = wind_data["speed_mph"]
    except KeyError:
        speedKPH = "Not Reported "
        speedMPH = "Not Reported "

    conditions = data["clouds"][0]
    forecast_desc = conditions["text"]
    
    humidity = data["humidity"]["percent"]

    return render_template('weather.html', degsC=degsC, degsF=degsF, speedKPH=speedKPH, speedMPH=speedMPH, icao=icao, humidity=humidity,
                           forecast_desc=forecast_desc, taf_impacts=taf_impacts, sigmet_impacts=sigmet_impacts)

@app.route('/flights/')
@login_required
def flights():
    conn, cur = get_db_connection()

    # Queries the Airport model from models.py to check for table population. If empty, populate.
    if Airport.query.first() is None:
        print("Populating table...")
        with open(os.getcwd()+"\\app\\static\\sql\\load_airports.sql", "r", encoding="utf-8") as file:
            print("SQL file found.")
            cur.execute(file.read())
            conn.commit()
            print("Table populated.")
    
    cur.execute("SELECT * FROM airports")
    rows = cur.fetchall()

    cities = [row[0] for row in rows]
    countries = [row[1] for row in rows]
    iata = [row[2] for row in rows]
    continent = [row[3] for row in rows]
    print(len(cities))

    return render_template('flights.html', cities=cities, countries=countries,iata=iata,continent=continent)

from flask import request

@app.route('/flights/<src>/<dest>/<date>', methods=['GET'])
@login_required
def flights_to_dest(src, dest, date):
    rockMe = Client(
        client_id="tT7RKPlYmqow0doAYBPEi0Emi9N78wWX",
        client_secret="UFSIgv5qhZxFLAog"
    )
    
    try:
        # Format the date as 'YYYY-MM-DD'
        formatted_date = date

        response = rockMe.shopping.flight_offers_search.get(
                    originLocationCode=src, 
                    destinationLocationCode=dest, 
                    departureDate=formatted_date,
                    adults=1)
        
        flights_info=[]
        for itinerary in response.data:
            flights_info.append(itinerary)
            
        # Parse the JSON data
        data = flights_info

        # Initialize a dictionary to store the extracted information
        itinerary_info = {}

        # Iterate through each itinerary
        for itinerary in data['itineraries']:
            # Extract the number of segments
            num_segments = len(itinerary['segments'])

            # Initialize lists to store departure and arrival IATA codes, and aircraft codes
            dep_iata_codes = []
            arr_iata_codes = []
            aircraft_codes = []

            # Iterate through each segment to extract the required information
            for segment in itinerary['segments']:
                dep_iata_codes.append(segment['departure']['iataCode'])
                arr_iata_codes.append(segment['arrival']['iataCode'])
                aircraft_codes.append(segment['aircraft']['code'])

            # Store the extracted information in the dictionary
            itinerary_info[itinerary['id']] = {
                'num_segments': num_segments,
                'dep_iata_codes': dep_iata_codes,
                'arr_iata_codes': arr_iata_codes,
                'aircraft_codes': aircraft_codes
            }

        # Print the extracted information
        for itinerary_id, info in itinerary_info.items():
            print(f"Itinerary ID: {itinerary_id}")
            print(f"Number of Segments: {info['num_segments']}")
            print("Departure IATA Codes:", info['dep_iata_codes'])
            print("Arrival IATA Codes:", info['arr_iata_codes'])
            print("Aircraft Codes:", info['aircraft_codes'])
            print("\n")
        return jsonify(flights_info)
    except ResponseError as error:
        return jsonify({"error": str(error)})
    
# @app.route("/flights/", methods=['GET'])
# def flights():
#     con, cursor = get_db_connection()
#     cursor.execute("SELECT planemodel, source, destination, source_icao, destination_icao FROM flights")
#     flights = cursor.fetchall()
#     print(flights)
#     return render_template("flights.html", flights=flights)


@app.route('/prediction/', methods=['GET', 'POST'])
def fuelPrediction():
    # Load your model and scaler
    fuel_Pred_Model = pickle.load(open(os.getcwd()+"\\fuel_Pred_Model.pkl", "rb"))
    scaler = pickle.load(open(os.getcwd()+"\\scaler.pkl", "rb")) 

    # Load the LabelEncoder for categorical columns
    label_encoder = LabelEncoder()
    form = FuelPredictionForm()

    if form.validate_on_submit():
        # Collect features from the form
        features_input = [
            form.airline_iata.data.upper(),
            form.acft_icao.data.upper(),
            form.acft_class.data.upper(),
            form.seymour_proxy.data.upper(),
            float(form.seats.data),
            float(form.n_flights.data),
            form.iata_departure.data.upper(),
            form.iata_arrival.data.upper(),
            float(form.distance_km.data),
            float(form.rpk.data),
            float(form.fuel_burn_seymour.data),
            float(form.fuel_burn.data)
        ]

        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame([features_input], columns=['airline_iata', 'acft_icao', 'acft_class', 'seymour_proxy', 'seats', 'n_flights', 'iata_departure', 'iata_arrival', 'distance_km', 'rpk', 'fuel_burn_seymour', 'fuel_burn'])

        # Handle missing values (if any)
        # Assuming you've handled missing values in your training data, you might want to do the same here
        # For example, fill missing values with the mean or median
        # test_df.fillna(test_df.mean(), inplace=True)

        # Encode categorical columns
        categorical_columns = ['airline_iata', 'acft_icao', 'acft_class', 'seymour_proxy', 'iata_departure', 'iata_arrival']
        for column in categorical_columns:
            df[column] = label_encoder.fit_transform(df[column])

        # Convert to numpy array and scale
        features = df.values
        features = scaler.transform(features)

        # Make prediction
        prediction = fuel_Pred_Model.predict(features)

        return render_template('fuelPrediction.html', form=form, prediction=prediction[0])
    return render_template('fuelPrediction.html', form=form, prediction=0)

@app.route('/emissions-report/', methods=['GET', 'POST'])
def generateReport():
    form = EmissionForm()
    if form.validate_on_submit():
        country_name = get_country_name_by_code(form.country.data)
        raw_data = get_emissions(
            country=form.country.data,
            timeframe=form.timeframe.data,
            start_year=form.start_year.data,
            month=form.month.data if form.month.data else None,
            quarter=form.quarter.data if form.quarter.data else None,
            end_year=form.end_year.data,
            end_month=form.end_month.data if form.end_month.data else None,
            end_quarter=form.end_quarter.data if form.end_quarter.data else None
        )

        if raw_data == "NoRecordsFound":
            flash('No data available for the selected parameters.', 'warning')
            return redirect(url_for('generateReport'))
        elif raw_data == "ErrorParsingXML" or raw_data == "Failed to retrieve data":
            flash('There was an error processing your request. Please try again later.', 'error')
            return redirect(url_for('generateReport'))

        data_summary = {}
        total_emissions = 0
        for item in raw_data:
            time_key = item['time_period']
            emissions = float(item['emissions'])
            total_emissions += emissions
            data_summary.setdefault(time_key, 0)
            data_summary[time_key] += emissions

        return render_template('report.html', data_summary=data_summary, total_emissions=total_emissions, country=country_name, timeframe=form.timeframe.data, start_year=form.start_year.data, end_year=form.end_year.data)
    else:
            # If there is a validation error, the form will be rendered with error messages
            for fieldName, errorMessages in form.errors.items():
                for err in errorMessages:
                    flash(f'Error in {fieldName}: {err}', 'error')
            redirect(url_for('generateReport'))
    return render_template('reportform.html', form=form)

@login_required
@app.route('/chat/')
def load_chatbot():
    return render_template('chatbot.html')

@app.route('/api/chat/', methods=['POST'])
def chat():
    try:
        data = request.json
        icao_code = data.get('icao_code', '').strip()
        flight_distance_str = data.get('flight_distance', '0').strip()

        if not icao_code:
            return jsonify({'error': 'Missing ICAO code'}), 400
        try:
            flight_distance = float(flight_distance_str)
        except ValueError:
            return jsonify({'error': 'Invalid flight distance format'}), 400

        # Fetch weather data
        weather_data = get_weather(os.getenv('CX_WEATHER_API_KEY'), icao_code)
        wind_speed = extract_wind_speed(weather_data)
        temperature = extract_temperature(weather_data)
        is_rainfall, is_thunderstorms = check_weather_conditions(weather_data)

        # Calculate emissions
        emissions = calculate_emissions(flight_distance, wind_speed)
        recommendations = generate_recommendations(emissions)

        # Compose response message
        weather_info = []
        if temperature is not None:
            weather_info.append(f"Temperature: {temperature} °C")
        if wind_speed is not None:
            weather_info.append(f"Wind Speed: {wind_speed} kt")
        weather_info.append(f"Rainfall: {'Yes' if is_rainfall else 'No'}")
        weather_info.append(f"Thunderstorms: {'Yes' if is_thunderstorms else 'No'}")

        message = f"Current Weather Conditions:\n" + '\n'.join(weather_info) + \
                  f"\n\nEmissions: {emissions:.2f} kg CO2. {recommendations}"

        return jsonify({'message': message})
    except Exception as e:
        return jsonify({'error': f"Error processing request: {str(e)}"}), 500

# Works and retruns  a dictionary
def get_emissions(country, timeframe, start_year, month, quarter, end_year, end_month, end_quarter):
    base_url = "https://sdmx.oecd.org/public/rest/data"
    dataflow = "OECD.SDD.NAD.SEEA,DSD_AIR_TRANSPORT@DF_AIR_TRANSPORT,1.0"
    
    # Determine time suffix and period based on the timeframe
    if timeframe == 'annual':
        start_period = f"{start_year}"
        end_period = f"{end_year}"
        time_suffix = ".A......."
    elif timeframe == 'monthly':
        start_period = f"{start_year}-{month.zfill(2)}"
        end_period = f"{end_year}-{end_month.zfill(2)}"
        time_suffix = ".M......."
    elif timeframe == 'quarterly':
        start_period = f"{start_year}-Q{quarter}"
        end_period = f"{end_year}-Q{end_quarter}"
        time_suffix = ".Q......."
    
    url = f"{base_url}/{dataflow}/{country}{time_suffix}?startPeriod={start_period}&endPeriod={end_period}&dimensionAtObservation=AllDimensions"
    print("Requesting URL:", url)  # For debugging purposes
    response = requests.get(url)
    print("response: ", response)
    
    if response.status_code == 404:
        return "NoRecordsFound"
    elif response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            emissions_data = []
            for obs in root.findall('.//generic:Obs', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}):
                data_point = {
                    'time_period': obs.find('.//generic:Value[@id="TIME_PERIOD"]', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value'],
                    'emissions': float(obs.find('.//generic:ObsValue', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value']),
                    'unit': obs.find('.//generic:Value[@id="UNIT_MEASURE"]', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value']
                }
                emissions_data.append(data_point)
            return emissions_data
        except ET.ParseError:
            return "ErrorParsingXML"
    return "Failed to retrieve data"  # Handles other unexpected status codes


@app.route('/login', methods=['POST', 'GET'])
def login():
    
    if UserProfile.query.count() == 0:
        # If the table is empty, add a new user profile
        user = UserProfile(first_name="Crypto",
                           last_name="Ciphers Unltd.",
                            username="admin",
                            password="admin")
        db.session.add(user)
        db.session.commit()
        print("Admin user created")

    form = LoginForm()

    if form.validate_on_submit():
        # Get the username and password values from the form.
        res = request.form
        formUsername = res['username']
        formPassword = res['password']

        user =  UserProfile.query.filter_by(username = formUsername)

        #Try catch in the event of incorrect username
        try:
            if check_password_hash(user[0].password, formPassword):
                # Gets user id, load into session
                login_user(user[0])
                # Remember to flash a message to the user
                return redirect(url_for("home"))  
            else:
                flash("Incorrect password","error")
        except IndexError:
            flash("User not found", "error")
            return redirect(url_for('login'))

    return render_template("login.html", form=form)

# user_loader callback. This callback is used to reload the user object from
# the user ID stored in the session
@login_manager.user_loader
def load_user(id):
    return db.session.execute(db.select(UserProfile).filter_by(id=id)).scalar()

###
# The functions below should be applicable to all Flask apps.
###

# Flash errors from the form if validation fails
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
), 'danger')

@app.route('/<file_name>.txt')
def send_text_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.txt'
    return app.send_static_file(file_dot_text)


@app.after_request
def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404

@app.route('/logout')
def logout():
    logout_user()
    flash("You are now logged out")
    return redirect(url_for('home'))

# Database connection setup
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="flightoptimizer",
        user=os.environ.get('DATABASE_USERNAME', 'postgres'),
        password= os.environ.get('DATABASE_PASSWORD')
    )    
    cur = conn.cursor()    
    return conn, cur

# Helper functions for SIGMET and TAF weather advisories
def fetch_data(url, headers):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data: {response.status_code} {response.text}")
        return None

def fetch_taf_data(icao):
    taf_base_url = 'https://api.checkwx.com/taf/'
    url = f"{taf_base_url}{icao}/decoded"
    api_key = os.environ.get('CX_WEATHER_API_KEY') 
    headers = {'X-API-Key': api_key}
    return fetch_data(url, headers)

def fetch_sigmet_data(icao):
    sigmet_base_url = 'https://api.checkwx.com/sigmet/'
    url = f"{sigmet_base_url}{icao}/decoded"
    api_key = os.environ.get('CX_WEATHER_API_KEY')
    headers = {'X-API-Key': api_key}
    return fetch_data(url, headers)

def analyze_taf_fuel_impact(taf_data):
    impacts = []
    if taf_data and 'data' in taf_data:
        for report in taf_data['data']:
            icao = report.get('icao', 'Unknown')
            for forecast in report.get('forecast', []):
                period = f"From {forecast['timestamp']['from']} to {forecast['timestamp']['to']}"
                conditions_described = ', '.join(c['text'] for c in forecast.get('conditions', []))
                wind_speed = forecast.get('wind', {}).get('speed_kts', 0)
                impact_desc = f"{conditions_described}. High winds might increase fuel if wind speed > 20 kts ({wind_speed} kts)."

                # Include visibility and significant weather conditions like snow, ice, or fog
                if 'visibility' in forecast and forecast['visibility']['miles_float'] < 1:
                    impact_desc += " Low visibility could lead to delays and increased fuel usage."
                if any('snow' in c['text'].lower() or 'ice' in c['text'].lower() or 'fog' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Conditions like snow, ice, or fog may require de-icing and can cause delays, increasing fuel usage."

                # Check for rain and its operational implications
                if any('rain' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Rain may lead to increased braking distances and reduced runway friction, potentially affecting fuel usage due to longer taxi and rollout times."

                # Check for thunderstorms and turbulence for additional flight considerations
                if any('thunderstorm' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Thunderstorms may necessitate significant rerouting."
                if any('turbulence' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Turbulence could lead to operational adjustments and potential fuel inefficiencies."

                # Append the formatted string to impacts list
                impacts.append({
                    'icao': icao,
                    'period': period,
                    'description': impact_desc
                })
    return impacts

def analyze_sigmet_fuel_impact(sigmet_data):
    impacts = []
    if sigmet_data and 'data' in sigmet_data:
        for entry in sigmet_data['data']:
            icao = entry.get('icao', 'Unknown')
            hazard_type = entry.get('hazard', {}).get('type', {}).get('text', 'Unknown')
            description = f"Hazard type: {hazard_type}. "
            if 'Thunderstorm' in hazard_type:
                description += "Potential rerouting increases fuel."
            elif 'Volcanic ash' in hazard_type:
                description += "Avoidance increases fuel usage."
            # ... more conditions if necessary

            impacts.append({
                'icao': icao,
                'description': description
            })
        if not impacts:
            impacts.append({
            'icao': 'N/A',
            'period': 'N/A',
            'description': 'No significant SIGMET advisories affecting fuel emissions.'
        })
    return impacts

def fetch_country_codes():
    url = 'https://restcountries.com/v3.1/all'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        countries = {country['cca3']: country['name']['common'] for country in data}
        # Sorting countries by their common name
        sorted_countries = dict(sorted(countries.items(), key=lambda item: item[1]))
        return sorted_countries
    else:
        print("Failed to fetch data")
        return {}
    
def get_country_name_by_code(country_code):
    # Fetch the dictionary of country codes
    countries = fetch_country_codes()
    # Return the country name matching the country code
    return countries.get(country_code, "Unknown country code")

def extract_wind_speed(weather_data):
    try:
        return weather_data['data'][0]['wind']['speed_kts']
    except (IndexError, KeyError):
        return None

def extract_temperature(weather_data):
    try:
        return weather_data['data'][0]['temperature']['value']
    except (IndexError, KeyError):
        return None

def check_weather_conditions(weather_data):
    try:
        weather_conditions = weather_data['data'][0]['weather']
        is_rainfall = any(condition['value'] in ['RA', 'TSRA'] for condition in weather_conditions)
        is_thunderstorms = any(condition['value'] == 'TS' for condition in weather_conditions)
        return is_rainfall, is_thunderstorms
    except (IndexError, KeyError):
        return False, False

def calculate_emissions(flight_distance, wind_speed):
    baseline_emissions = flight_distance * 0.1
    if wind_speed is not None and wind_speed > 10:
        adjusted_emissions = baseline_emissions * 0.9
    else:
        adjusted_emissions = baseline_emissions
    return adjusted_emissions

def generate_recommendations(emissions):
    if emissions < 100:
        return "Your flight emissions are relatively low. Consider offsetting them with a carbon offset program."
    elif emissions >= 100 and emissions < 200:
        return "Your flight emissions are moderate. You may want to choose a more fuel-efficient airline for future flights."
    else:
        return "Your flight emissions are high. Consider alternative transportation options or carbon offset programs."
    
# Function to fetch weather data from CheckWX API
def get_weather(api_key, icao_code):
    url = f'https://api.checkwx.com/metar/{icao_code}/decoded'
    headers = {'X-API-Key': api_key}
    response = requests.get(url, headers=headers)
    return response.json()