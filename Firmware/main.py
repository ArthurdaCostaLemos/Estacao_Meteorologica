# main.py
import uasyncio as asyncio
import ubinascii
import os
import time
import json
import socket
import struct
import network
import dht
from machine import Pin, I2C, ADC, RTC

import config
from bmp280 import BMP280
from mqtt_async import MQTTAsyncClient

BOOT_ID = ubinascii.hexlify(os.urandom(8)).decode()
EPOCH_OFFSET = 946684800  # Diferença entre 1970 (Unix) e 2000 (ESP32 MicroPython)

fila = []
sequencia = 0
amostras_descartadas = 0
rede_atual = None
bmp = None

dht_sensor = dht.DHT22(Pin(config.DHT22_PIN))
i2c = I2C(0, scl=Pin(config.I2C_SCL_PIN), sda=Pin(config.I2C_SDA_PIN), freq=100000)

adc_ldr = ADC(Pin(config.LDR_ADC_PIN))
adc_ldr.atten(ADC.ATTN_11DB)

adc_mq = ADC(Pin(config.MQ135_ADC_PIN))
if getattr(config, "MQ135_ADC_ATTENUATION_DB", 11) == 0:
    adc_mq.atten(ADC.ATTN_0DB)
else:
    adc_mq.atten(ADC.ATTN_11DB)

def init_bmp():
    global bmp
    try:
        bmp = BMP280(i2c)
        print("[HARDWARE] BMP280 inicializado")
    except Exception as e:
        bmp = None
        print("[HARDWARE] Falha BMP280:", e)
        
_lux_filtrado = None

def ler_luminosidade():
    global _lux_filtrado
    leituras = []
    for _ in range(16):
        leituras.append(adc_ldr.read())
        time.sleep_ms(2)
    leituras.sort()
    # Descarta os 4 menores e 4 maiores valores (ruídos) e usa a média dos 8 centrais
    raw = sum(leituras[4:12]) // 8

    if raw <= 15 or raw >= 4095:
        return None, "saturado"

    v_out = (raw / 4095.0) * 3.3
    r_ldr = (10.0 * v_out) / max(3.3 - v_out, 0.001)
    lux_bruto = 500.0 * (r_ldr ** -1.4)
    if lux_bruto > 5000.0:
        return None, "acima_faixa"

    # Suavização exponencial para evitar saltos bruscos
    if _lux_filtrado is None:
        _lux_filtrado = lux_bruto
    else:
        _lux_filtrado = (0.35 * lux_bruto) + (0.65 * _lux_filtrado)

    return round(_lux_filtrado, 2), "ok"


def ler_qualidade_ar():
    soma = 0
    for _ in range(8):
        soma += adc_mq.read()
    raw = soma // 8

    # Calcula as tensões antes das validações para sempre exibir no terminal
    v_adc = (raw / 4095.0) * 3.3
    v_ao = v_adc * 1.5  # Compensa divisor 10k / 20k

    print("[MQ135] Bruto: {} | V_pino34: {:.3f} V | V_sensor(AO): {:.3f} V".format(raw, v_adc, v_ao))

    if raw <= 30:
        return None, None, "sinal_baixo"
    if raw >= 4080:
        return None, None, "adc_saturado"
    if not config.MQ135_CALIBRATION_ENABLED or not config.MQ135_R0_KOHM:
        return None, None, "calibracao_pendente"

    if v_ao <= 0.01 or v_ao >= 4.95:
        return None, None, "fora_faixa_tensao"
    rs = ((5.0 - v_ao) / v_ao) * 10.0
    ratio = rs / config.MQ135_R0_KOHM
    ppm = round(config.MQ135_CURVE_A * (ratio ** config.MQ135_CURVE_B), 2)

    if ppm < config.MQ135_MIN_PPM:
        return None, None, "abaixo_faixa"
    if ppm > config.MQ135_MAX_PPM:
        return None, None, "acima_faixa"
    if config.MQ135_REFERENCE_IS_SIMULATION:
        return None, ppm, "simulado"
    return ppm, None, "ok"

def timestamp_iso_atual():
    ano = RTC().datetime()[0]
    if ano < 2024:
        return None
    tm = time.gmtime(time.time())
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(*tm[:6])

async def adquirir():
    global sequencia, amostras_descartadas
    while True:
        t0 = time.ticks_ms()
        sequencia += 1
        estados = {}
        temp = None
        umid = None
        press = None

        if bmp:
            try:
                t_bmp, p_bmp = bmp.read()
                if -40 <= t_bmp <= 80:
                    temp = t_bmp
                    estados["origem_temperatura"] = "bmp280"
                if p_bmp and 300 <= p_bmp <= 1200:
                    press = p_bmp
            except Exception:
                estados["bmp280"] = "erro"

        try:
            dht_sensor.measure()
            t_dht = dht_sensor.temperature()
            u_dht = dht_sensor.humidity()
            if -40 <= t_dht <= 80:
                temp = round(float(t_dht), 2)
                estados["origem_temperatura"] = "dht22"
            if 0 <= u_dht <= 100:
                umid = round(float(u_dht), 2)
        except Exception:
            estados["dht22"] = "erro"

        lux, st_ldr = ler_luminosidade()
        estados["ldr"] = st_ldr

        qar, qar_sim, st_mq = ler_qualidade_ar()
        estados["mq135"] = st_mq

        amostra = {
            "id_estacao": config.STATION_ID,
            "boot_id": BOOT_ID,
            "sequencia": sequencia,
            "uptime_ms": time.ticks_ms(),
            "enfileirado_ms": time.ticks_ms(),
            "coletado_em": timestamp_iso_atual(),
            "temperatura": temp,
            "umidade": umid,
            "pressao": press,
            "qualidade_ar": qar,
            "luminosidade": lux,
            "amostras_descartadas": amostras_descartadas,
            "estado_sensores": estados,
        }
        if qar_sim is not None:
            amostra["mq135_ppm_simulado"] = qar_sim

        if len(fila) >= config.MQTT_QUEUE_SIZE:
            fila.pop(0)
            amostras_descartadas += 1
        fila.append(amostra)

        gasto = time.ticks_diff(time.ticks_ms(), t0)
        await asyncio.sleep_ms(max(100, config.SAMPLE_INTERVAL_MS - gasto))

async def monitor_wifi():
    global rede_atual
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    await asyncio.sleep_ms(500)
    while True:
        if not wlan.isconnected():
            rede_atual = None
            for net in config.WIFI_NETWORKS:
                print("[WIFI] Conectando a", net["ssid"])
                try:
                    wlan.disconnect()
                except Exception:
                    pass
                await asyncio.sleep_ms(200)
                wlan.connect(net["ssid"], net["password"])
                for _ in range(20):
                    if wlan.isconnected():
                        rede_atual = net
                        print("[WIFI] Conectado:", wlan.ifconfig()[0])
                        break
                    await asyncio.sleep_ms(500)
                if wlan.isconnected():
                    break
        await asyncio.sleep(2)

async def publicar():
    cliente = None
    topico = "estacoes/{}/telemetria".format(config.STATION_ID)
    while True:
        if not rede_atual or not fila:
            await asyncio.sleep_ms(200)
            continue
        try:
            if cliente is None:
                cid = "esp32-{}-{}".format(config.STATION_ID, BOOT_ID[:6])
                cliente = MQTTAsyncClient(
                    cid,
                    rede_atual["mqtt_host"],
                    rede_atual.get("mqtt_port", 1883),
                    config.MQTT_USER,
                    config.MQTT_PASSWORD,
                )
                await cliente.connect()
                print("[MQTT] Conectado ao broker", rede_atual["mqtt_host"])

            item = dict(fila[0])
            enfileirado = item.pop("enfileirado_ms")
            item["atraso_envio_ms"] = max(0, time.ticks_diff(time.ticks_ms(), enfileirado))
            if item["coletado_em"] is None:
                del item["coletado_em"]

            await cliente.publish_qos1(topico, json.dumps(item))
            fila.pop(0)
            print("[MQTT] Publicacao confirmada seq=", item["sequencia"])
        except Exception as e:
            print("[MQTT] Erro:", e)
            if cliente:
                cliente.close()
                cliente = None
            await asyncio.sleep(2)

async def recuperar_sensores():
    while True:
        if bmp is None:
            init_bmp()
        await asyncio.sleep(10)

async def sincronizar_relogio():
    while True:
        if rede_atual:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setblocking(False)
                pkt = bytearray(48)
                pkt[0] = 0x1B
                s.sendto(pkt, (config.NTP_HOST, 123))
                for _ in range(20):
                    try:
                        data = s.recv(48)
                        if len(data) == 48:
                            val = struct.unpack("!I", data[40:44])[0]
                            ts_esp = val - 2208988800 - EPOCH_OFFSET
                            tm = time.gmtime(ts_esp)
                            RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
                            print("[NTP] Relogio sincronizado")
                            s.close()
                            await asyncio.sleep(21600)  # 6 horas
                            break
                    except OSError:
                        pass
                    await asyncio.sleep_ms(100)
                s.close()
            except Exception:
                pass
        await asyncio.sleep(60)

async def supervisionar(coro_fn):
    while True:
        try:
            await coro_fn()
        except Exception as e:
            print("[SUPERVISOR] Reiniciando tarefa:", e)
            await asyncio.sleep(1)

async def main():
    print("[BOOT] Iniciando tarefas...")
    init_bmp()
    print("[BOOT] Chamando asyncio.gather...")
    await asyncio.gather(
        supervisionar(monitor_wifi),
        supervisionar(publicar),
        supervisionar(adquirir),
        supervisionar(recuperar_sensores),
        supervisionar(sincronizar_relogio),
    )

print("[BOOT] Fim do carregamento do script")
asyncio.run(main())
