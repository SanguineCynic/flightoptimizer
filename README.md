# CryptoCiphers Unltd. Capstone Project

### Authors

- [Jonathan Astwood](https://github.com/SanguineCynic)
- [Gabrielle Scott](https://github.com/gabriellecdjscott)
- [Brittany Thomas](https://github.com/BrittanyThomas162)
- [Jevaughn Mayne](https://example.com)

### About the Project

This project aims to address the challenges faced by current air traffic control (ATC) management systems through the integration of predictive analytics and advanced technological solutions. By leveraging tools such as Aviationstack for real-time and historical flight data, Google Colab for machine learning model development, and Keras with TensorFlow for neural network training, we seek to enhance the predictability of potential disruptions and optimize flight routes. Moreover, we prioritize environmental sustainability by incorporating Open Access Geospatial Data in Europe (OAG) to assess the environmental impact of air traffic and optimize flight paths accordingly. Through collaborative efforts and innovative approaches, this project endeavors to revolutionize air traffic control management for a more efficient and sustainable future.

### Setup

***Prerequisites: Python3, PostgreSQL***

1. git  clone https://github.com/SanguineCynic/flightoptimizer.git
2. Open a terminal window in the clone location
    - .\venv\Scripts\Activate
    - python -m pip install -r requirements.txt
3. Open a psql shell
    - Login to designated postgres database, e.g. localhost > postgres:5432
    - create database FlightOptimizer;
    - \c flightoptimizer or use flightoptimizer
4. Return to the original terminal 
    - python -m flask db migrate
    - python -m flask db upgrade
    - python -m flask --app app --debug run
