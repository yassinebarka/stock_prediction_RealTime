from collections import deque
from kafka import KafkaConsumer
import psycopg2
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define Kafka broker address and topic name
KAFKA_BROKER = os.getenv("KAFKA_HOST") + ':9092'
KAFKA_TOPIC = 'stock'
FLASK_HOST = os.getenv("FLASK_SERVER_HOST")

# Define PostgreSQL database connection parameters
db_params = {
    "host": "postgres",
    "database": "Stockhist",
    "user": "postgres",
    "password": "zerouk1234"
}

# Create a KafkaConsumer instance
consumer = KafkaConsumer(
    KAFKA_TOPIC, bootstrap_servers=KAFKA_BROKER, group_id='my-group')

# Establish a database connection
conn = psycopg2.connect(**db_params)
cursor = conn.cursor()

# Define window sizes for short and long moving averages
short_window = 3
long_window = 4

# Create lists to store previous close values for short and long moving averages
short_ma_values = []
long_ma_values = []

# Function to calculate the short moving average
def calculate_short_ma(close_value):
    short_ma_values.append(close_value)
    if len(short_ma_values) > short_window:
        short_ma_values.pop(0)
    return sum(short_ma_values) / len(short_ma_values)

# Function to calculate the long moving average
def calculate_long_ma(close_value):
    long_ma_values.append(close_value)
    if len(long_ma_values) > long_window:
        long_ma_values.pop(0)
    return sum(long_ma_values) / len(long_ma_values)

# Function to consume and process messages from Kafka and insert into PostgreSQL
def consume_messages_from_kafka_and_insert():
    for message in consumer:
        try:
            # Process the message value (assuming it's in the format 'timestamp,open,high,low,close,volume')
            message_value = message.value.decode('utf-8')
            print(f"Message reçu : {message_value}")  # Debugging: display the consumed message

            values = message_value.split(',')
            if len(values) == 6:
                timestamp, open_val, high, low, close, volume = values  
                short_MA = calculate_short_ma(float(close))
                long_MA = calculate_long_ma(float(close))

                data = {'features': [float(open_val), float(high), float(low), float(close), float(volume), short_MA, long_MA]}
                
                response = requests.post(url=f'http://{FLASK_HOST}:5000/predict', json=data)
                print(f"Réponse de prédiction : {response.text}")  # Debugging: display the prediction response
                prediction = response.json().get('prediction', None)
                
                if prediction is not None:
                    print(f"Prédiction : {prediction}")  # Debugging: display the prediction

                    # Define the INSERT statement
                    insert_query = """INSERT INTO stock (timestamp, open, high, low, close, volume, prediction) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                    cursor.execute(insert_query, (timestamp, open_val, high, low, close, volume, prediction))
                    conn.commit()
                    print(f"Inséré dans PostgreSQL : {message_value}")  # Debugging: display the inserted data
                else:
                    print(f"Prédiction non trouvée pour le message : {message_value}")
        except psycopg2.Error as e:
            print(f"Erreur de base de données : {e}")
        except ValueError as ve:
            print(f"Erreur de valeur : {ve}")
        except Exception as e:
            print(f"Erreur de traitement du message : {str(e)}")

def main():
    try:
        print("Démarrage du consommateur...")
        consume_messages_from_kafka_and_insert()
        print("Données sauvegardées.")
    except KeyboardInterrupt:
        print("Consommateur interrompu.")
    finally:
        consumer.close()
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
