import csv

# Open the CSV file
with open('C:/Users/jastw/Desktop/Labs/Capstone/iata-icao.csv', mode='r', encoding='utf-8') as csv_file:
    csv_reader = csv.reader(csv_file)

    # Skip the header row since the CSV has no headers
    next(csv_reader)

    # Prepare the SQL INSERT statement
    insert_statement = "INSERT INTO public.iata_to_icao (country_code, iata, icao, latitude, longitude) VALUES "

    # Iterate through each row in the CSV file
    for row in csv_reader:
        # Construct the VALUES part of the SQL statement for each row
        values_part = f"('{row[0]}', '{row[1]}', '{row[2]}', {row[3]}, {row[4]})"

        # Append the VALUES part to the INSERT statement
        insert_statement += values_part + ", "

    # Remove the trailing comma and space
    insert_statement = insert_statement.rstrip(", ")

    with open('iata-icao.sql', 'w', encoding='utf-8') as sql_file:
        sql_file.write(insert_statement)

