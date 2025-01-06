import os
import sys
import io
import time
import gc
import json
import network
import M5
from M5 import *
from hardware import *
from umqtt.simple import MQTTClient

wlan = None
mqtt_client = None
#SSID = 'WIFI-DCI'
#PASSWORD = 'DComInf_2K24'
#SSID = 'Los Panas'
#PASSWORD = 'Jorge.Claudia@'
SSID = 'MARCO 2.4'
PASSWORD = 'QWERTY6114'
THINGSBOARD_SERVER = 'demo.thingsboard.io'
THINGSBOARD_PORT = 1883 
ACCESS_TOKEN = 'mVgsGYpgCiSMlf5iDKRB'

MOVEMENT_THRESHOLD = 0.2
QUIET_CONFIDENCE = 3
# mosquitto_pub -d -q 1 -h demo.thingsboard.io -p 1883 -t v1/devices/me/telemetry -u "thXLMcdrn8SXViFX2Y2E" -m "{temperature:25}"
# mosquitto_pub -d -q 1 -h demo.thingsboard.io -p 1883 -t v1/devices/me/telemetry -u "mVgsGYpgCiSMlf5iDKRB" -m "{temperature:25}"
quiet_counter = 0 

def btnA_wasReleased_event(state):
    global wlan, mqtt_client
    pass

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()
    
    print('Conectando a la red...')
    wlan.connect(ssid, password)
    
    retry_count = 0
    while not wlan.isconnected() and retry_count < 10:
        print('Intentando conectar...')
        time.sleep(1)
        retry_count += 1
    
    if wlan.isconnected():
        print('Conectado a la red')
        return wlan
    else:
        print('No se pudo conectar a la red')
        return None

def connect_mqtt():
    global mqtt_client
    mqtt_client = MQTTClient(client_id="",
                             server=THINGSBOARD_SERVER,
                             port=THINGSBOARD_PORT,
                             user=ACCESS_TOKEN,
                             password="",
                             keepalive=60)
    if mqtt_client is None:
      print("Error: No se pudo conectar al servidor MQTT.")
      return None
    
    mqtt_client.connect()
    print('Conectado al servidor MQTT de ThingsBoard')
    return mqtt_client

def send_data(data):
    global mqtt_client
    topic = 'v1/devices/me/telemetry'
    payload = json.dumps(data)
    try:
        mqtt_client.publish(topic, payload)
    except Exception as e:
        print("Error al enviar datos, intentando reconectar...", e)
        mqtt_client = connect_mqtt()  # Reintentar conexión
        try:
            mqtt_client.publish(topic, payload)  # Intentar nuevamente
        except Exception as e:
            print("Error crítico, no se pudo reconectar:", e)

def is_moving(accel_data, prev_accel_data=None):
    global quiet_counter

    x, y, z = accel_data
    magnitude = (x**2 + y**2 + z**2)**0.5

    # New thresholds for stationary detection
    stationary_range = (0.6, 1.4)

    # Check rate of change if previous data is available
    if prev_accel_data:
        dx = x - prev_accel_data[0]
        dy = y - prev_accel_data[1]
        dz = z - prev_accel_data[2]
        rate_of_change = (dx**2 + dy**2 + dz**2)**0.5
    else:
        rate_of_change = 0

    # Determine if moving
    moving = magnitude < stationary_range[0] or magnitude > stationary_range[1] or rate_of_change > 0.1

    if not moving:
        quiet_counter += 1
        if quiet_counter >= QUIET_CONFIDENCE:
            return False
        else:
            return True
    else:
        quiet_counter = 0
        return True

def setup():
    global wlan, mqtt_client

    M5.begin()
    BtnA.setCallback(type=BtnA.CB_TYPE.WAS_RELEASED, cb=btnA_wasReleased_event)

    wlan = connect_wifi(SSID, PASSWORD)

    if wlan:
        mqtt_client = connect_mqtt()
    else:
        print("Error: No se pudo conectar a la red WiFi.")

def loop():
    global wlan, mqtt_client

    if wlan and wlan.isconnected():
        if mqtt_client is None:
            mqtt_client = connect_mqtt()
        
        try:
            gyro_data = Imu.getGyro()
            accel_data = Imu.getAccel()
            moving = is_moving(accel_data)
            data = {
                "gyroscope-x": gyro_data[0],
                "gyroscope-y": gyro_data[1],
                "gyroscope-z": gyro_data[2],
                "accelerometer-x": accel_data[0],
                "accelerometer-y": accel_data[1],
                "accelerometer-z": accel_data[2],
                "moving": moving
            }
            send_data(data)
        except Exception as e:
            print("Error al enviar datos:", e)
            mqtt_client = connect_mqtt()  # Reintentar conexión
    else:
        print("Error: No hay conexión WiFi.")
        wlan = connect_wifi(SSID, PASSWORD)

    gc.collect()

if __name__ == '__main__':
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        print("Error o interrupción:", e)
        sys.exit(1)