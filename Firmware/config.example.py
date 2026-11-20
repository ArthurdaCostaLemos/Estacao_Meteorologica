STATION_ID = 1
SAMPLE_INTERVAL_MS = 2500
MQTT_QUEUE_SIZE = 24

# Lista de redes Wi-Fi em ordem de prioridade
WIFI_NETWORKS = [
    {
        "ssid": "SUA_REDE",
        "password": "SUA_SENHA",
        "mqtt_host": "IP_DO_COMPUTADOR_CONECTADO_NA_REDE",  # <-- TROQUE PELO IPV4 DO SEU PC
        "mqtt_port": 1883,
    }
]

MQTT_USER = ""
MQTT_PASSWORD = ""
NTP_HOST = "162.159.200.1"  # IP fixo da Cloudflare (evita DNS bloqueante)

# Pinos dos sensores
DHT22_PIN = 4
I2C_SDA_PIN = 21
I2C_SCL_PIN = 22
LDR_ADC_PIN = 35
MQ135_ADC_PIN = 34

# Calibração do LDR e MQ-135
LDR_DARK_REFERENCE_ADC = None
MQ135_ADC_ATTENUATION_DB = 0  # Permite ler até ~3.3V (após divisor 10k/20k)
MQ135_CALIBRATION_ENABLED = True
MQ135_R0_KOHM = 10.0
MQ135_CURVE_A = 77.255
MQ135_CURVE_B = -3.18
MQ135_MIN_PPM = 0.0
MQ135_MAX_PPM = 300.0
MQ135_REFERENCE_IS_SIMULATION = False
