from flask import Flask, jsonify, render_template, request, flash
from forms import FuelPredictionForm
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Load your model and scaler
fuel_Pred_Model = pickle.load(open("fuel_Pred_Model.pkl", "rb"))
scaler = pickle.load(open("scaler.pkl", "rb")) 

# Load the LabelEncoder for categorical columns
label_encoder = LabelEncoder()


@app.route('/', methods=['GET', 'POST'])
def fuelPrediction():
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

        return render_template('results.html', prediction=prediction[0])
    return render_template('fuelPrediction.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)
