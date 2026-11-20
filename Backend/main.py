import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import mysql.connector
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Carrega as variáveis do arquivo .env
load_dotenv()

# --- CONFIGURAÇÕES CARREGADAS DO AMBIENTE ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "172.20.10.6")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "estacoes/1/telemetria")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Estacao2026@"),
    "database": os.getenv("DB_NAME", "estacao_meteorologica"),
}

ARQUIVO_LOCALIZACAO = Path(__file__).parent / "localizacao_estacao.json"

# --- SEGURANÇA ADMINISTRATIVA (PASSO 5) ---
security = HTTPBearer()
ADMIN_KEY = os.environ["ESTACAO_ADMIN_KEY"]


def validar_admin(credenciais: HTTPAuthorizationCredentials = Depends(security)):
    if not secrets.compare_digest(credenciais.credentials, ADMIN_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave administrativa inválida.",
        )


# Estado em memória para leitura rápida e controle de atividade da ESP32
ultima_leitura_valida: Optional[dict] = None
ultimo_recebimento_dt: Optional[datetime] = None


# --- FUNÇÕES AUXILIARES DE LOCALIZAÇÃO ---
def carregar_localizacao() -> Optional[dict]:
    if ARQUIVO_LOCALIZACAO.exists():
        try:
            return json.loads(ARQUIVO_LOCALIZACAO.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def salvar_localizacao(latitude: float, longitude: float) -> dict:
    dados = {"latitude": latitude, "longitude": longitude}
    ARQUIVO_LOCALIZACAO.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    return dados


# --- 1. MODELO DE VALIDAÇÃO (Pydantic) ---
class PacoteSensores(BaseModel):
    temperatura: Optional[float] = Field(default=None, ge=-40.0, le=80.0)
    umidade: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    pressao: Optional[float] = Field(default=None, ge=300.0, le=1100.0)
    qualidade_ar: Optional[float] = Field(default=None, ge=0, le=100000)
    luminosidade: Optional[float] = Field(default=None, ge=0, le=100000)


def classificar_ar(ppm: Optional[float]) -> str:
    if ppm is None:
        return "Sinal baixo"
    if ppm <= 400:
        return "Excelente"
    if ppm <= 800:
        return "Boa"
    if ppm <= 1200:
        return "Moderada"
    return "Ruim"


def salvar_no_mysql(dados: PacoteSensores, status_ar: str):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    sql = """
        INSERT INTO leituras_sensores
        (temperatura, umidade, pressao, qualidade_ar, luminosidade, alerta_ar)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    valores = (
        dados.temperatura,
        dados.umidade,
        dados.pressao,
        dados.qualidade_ar,
        dados.luminosidade,
        status_ar,
    )
    try:
        cursor.execute(sql, valores)
    except mysql.connector.Error as err:
        if err.errno == 1048:
            valores_fallback = (
                dados.temperatura or 0.0,
                dados.umidade or 0.0,
                dados.pressao or 0.0,
                dados.qualidade_ar or 0.0,
                dados.luminosidade or 0.0,
                status_ar,
            )
            cursor.execute(sql, valores_fallback)
        else:
            raise
    conn.commit()
    cursor.close()
    conn.close()

# --- 2. PERSISTÊNCIA NO MYSQL ---
def salvar_no_mysql(dados: PacoteSensores, status_ar: str):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        sql = """
            INSERT INTO leituras_sensores 
            (temperatura, umidade, pressao, qualidade_ar, luminosidade, alerta_ar)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        valores = (
            dados.temperatura,
            dados.umidade,
            dados.pressao,
            dados.qualidade_ar,
            dados.luminosidade,
            status_ar,
        )
        cursor.execute(sql, valores)
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"[ERRO MYSQL] Falha ao gravar: {err}")


def formatar_registro_mysql(row: dict, fallback_dt: datetime) -> dict:
    # Detecta automaticamente qual coluna de data/hora sua tabela MySQL usa
    bruto_dt = (
        row.get("data_hora")
        or row.get("criado_em")
        or row.get("created_at")
        or row.get("timestamp")
    )
    if isinstance(bruto_dt, datetime):
        dt = bruto_dt
    elif isinstance(bruto_dt, str):
        try:
            dt = datetime.fromisoformat(bruto_dt)
        except ValueError:
            dt = fallback_dt
    else:
        dt = fallback_dt

    return {
        "id_leitura": row.get("id", 0),
        "temperatura": float(row["temperatura"]) if row.get("temperatura") is not None else None,
        "umidade": float(row["umidade"]) if row.get("umidade") is not None else None,
        "pressao": float(row["pressao"]) if row.get("pressao") is not None else None,
        "qualidade_ar": float(row["qualidade_ar"]) if row.get("qualidade_ar") is not None else None,
        "luminosidade": float(row["luminosidade"]) if row.get("luminosidade") is not None else None,
        "data_hora": dt.isoformat(),
        "coletado_em": dt.timestamp(),
        "estado_sensores": {},
        "qualidade": {},
    }


# --- 3. CALLBACKS DO CLIENTE MQTT ---
def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Conectado ao Mosquitto em {MQTT_BROKER}:{MQTT_PORT} (Código: {reason_code})", flush=True)
    client.subscribe("#")
    print("[MQTT] Escutando todos os tópicos (#)...", flush=True)


def on_message(client, userdata, msg):
    global ultima_leitura_valida, ultimo_recebimento_dt
    bruto = msg.payload.decode("utf-8", errors="replace")
    print(f"[MQTT RECEBIDO] Tópico: {msg.topic} | Dados: {bruto}", flush=True)

    try:
        payload_bruto = json.loads(bruto)
        dados_confirmados = PacoteSensores(**payload_bruto)
        status_ar = classificar_ar(dados_confirmados.qualidade_ar)

        salvar_no_mysql(dados_confirmados, status_ar)

        agora = datetime.now()
        ultimo_recebimento_dt = agora
        ultima_leitura_valida = {
            **dados_confirmados.model_dump(),
            "alerta_ar": status_ar,
            "data_hora": agora.isoformat(),
            "coletado_em": agora.timestamp(),
        }
        print("[OK] Pacote validado e salvo no MySQL!", flush=True)

    except json.JSONDecodeError:
        print("[DESCARTADO] O texto recebido não é um JSON válido.", flush=True)
    except ValidationError as e:
        print(f"[DESCARTADO] Nome de campo ou limite inválido: {e}", flush=True)
    except Exception as e:
        print(f"[ERRO] Falha ao processar mensagem: {e}", flush=True)

# --- 4. CICLO DE VIDA DA APLICAÇÃO ---
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    yield
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


app = FastAPI(title="API Estação Meteorológica", lifespan=lifespan)


# --- CONTROLE DE LIMITE DE REQUISIÇÕES (PASSO 6) ---
def pegar_ip(request: Request):
    return request.headers.get("CF-Connecting-IP") or get_remote_address(request)


limiter = Limiter(key_func=pegar_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS (PASSO 4) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://estacao-b1874.web.app",
        "https://estacao-b1874.firebaseapp.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 5. ENDPOINTS PARA O DASHBOARD (FIREBASE) ---
@app.get("/api/leituras/ultimas-24h")
@limiter.limit("120/minute")
def obter_leituras_24h(request: Request, id_estacao: int = 1):
    agora = datetime.now()
    historico = []

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM leituras_sensores ORDER BY id DESC LIMIT 60")
        registros = cursor.fetchall()
        cursor.close()
        conn.close()

        historico = [formatar_registro_mysql(r, agora) for r in registros]
    except mysql.connector.Error as err:
        print(f"[ERRO MYSQL] Falha ao ler histórico: {err}")

    # Se o banco ainda estiver vazio mas acabou de chegar leitura na RAM, usa ela
    if not historico and ultima_leitura_valida:
        historico = [{
            "id_leitura": 1,
            **ultima_leitura_valida,
            "estado_sensores": {},
            "qualidade": {},
        }]

    # Se chegou uma leitura ao vivo agora, garante que o topo tenha o timestamp mais recente
    if historico and ultima_leitura_valida and ultimo_recebimento_dt:
        historico[0]["data_hora"] = ultimo_recebimento_dt.isoformat()
        historico[0]["coletado_em"] = ultimo_recebimento_dt.timestamp()

    # Calcula estatísticas para os cards de resumo
    temps = [r["temperatura"] for r in historico if r["temperatura"] is not None]
    umids = [r["umidade"] for r in historico if r["umidade"] is not None]
    airs = [r["qualidade_ar"] for r in historico if r["qualidade_ar"] is not None]
    press = [r["pressao"] for r in historico if r["pressao"] is not None]

    estatisticas_24h = {
        "temp_max": max(temps) if temps else None,
        "temp_min": min(temps) if temps else None,
        "umid_media": (sum(umids) / len(umids)) if umids else None,
        "air_max": max(airs) if airs else None,
        "press_media": (sum(press) / len(press)) if press else None,
    }

    # Verifica se a ESP32 mandou dados nos últimos 15 segundos
    esp32_ativo = False
    if ultimo_recebimento_dt and (agora - ultimo_recebimento_dt).total_seconds() <= 15:
        esp32_ativo = True
    elif historico:
        try:
            ultima_dt = datetime.fromisoformat(historico[0]["data_hora"])
            if (agora - ultima_dt).total_seconds() <= 15:
                esp32_ativo = True
        except ValueError:
            pass

    return {
        "id_estacao": id_estacao,
        "esp32_ativo": esp32_ativo,
        "estacao": carregar_localizacao(),
        "historico": historico,
        "historico_24h": list(reversed(historico[:25])),
        "estatisticas_24h": estatisticas_24h,
    }


@app.put("/api/estacoes/{id_estacao}/localizacao", dependencies=[Depends(validar_admin)])
@limiter.limit("10/minute")
def atualizar_localizacao(request: Request, id_estacao: int, payload: dict):
    lat = payload.get("latitude")
    lng = payload.get("longitude")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Latitude e longitude são obrigatórias.")

    salva = salvar_localizacao(float(lat), float(lng))
    return {
        "status": "ok",
        "id_estacao": id_estacao,
        "latitude": salva["latitude"],
        "longitude": salva["longitude"],
    }
