"""
GGMAX BOT - API Direta (sem Playwright, sem Cloudflare)
"""

import sys
import os
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import random
import string
import time
import re
import requests
import threading
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY    = "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"
BASE44_ENDPOINT = "https://preview-sandbox--69ab80547aecb9090ac003a1.base44.app/functions/webhook"
BASE44_API_KEY  = "5e03b0370d5f42d8a6e011517930bfe4"
MAILTM_API      = "https://api.mail.tm"
GGMAX_API       = "https://ggmax.com.br/api"
DELAY_MIN       = 3.0
DELAY_MAX       = 8.0

groq_client = Groq(api_key=GROQ_API_KEY)
campanhas_status = {}


def registrar_conta_local(campanha_id, numero, usuario, email, pergunta, status, erro=""):
    if campanha_id not in campanhas_status:
        campanhas_status[campanha_id] = {"contas": [], "campanha_status": "ativa"}
    contas = campanhas_status[campanha_id]["contas"]
    existente = next((c for c in contas if c["numero"] == numero), None)
    if existente:
        existente.update({"usuario": usuario, "email": email, "pergunta": pergunta, "status": status, "erro": erro})
    else:
        contas.append({"numero": numero, "usuario": usuario, "email": email, "pergunta": pergunta, "status": status, "erro": erro})


def registrar_conta(campanha_id, numero, usuario, email, pergunta, status, erro=""):
    registrar_conta_local(campanha_id, numero, usuario, email, pergunta, status, erro)
    try:
        requests.post(BASE44_ENDPOINT, json={
            "api_key": BASE44_API_KEY,
            "campanha_id": campanha_id,
            "numero": numero,
            "usuario": usuario,
            "email": email,
            "pergunta": pergunta,
            "status": status,
            "erro": erro,
        }, timeout=10)
    except Exception as e:
        print(f"Erro Base44: {e}", flush=True)


def atualizar_campanha(campanha_id, status):
    if campanha_id in campanhas_status:
        campanhas_status[campanha_id]["campanha_status"] = status
    try:
        requests.post(BASE44_ENDPOINT, json={
            "api_key": BASE44_API_KEY,
            "campanha_id": campanha_id,
            "tipo": "atualizar_campanha",
            "status": status,
        }, timeout=10)
    except Exception as e:
        print(f"Erro Base44: {e}", flush=True)


def gerar_usuario():
    nomes = ["miguel", "carlos", "gabriel", "lucas", "pedro",
             "joao", "andre", "rafael", "mateus", "felipe"]
    sufixo = str(random.randint(10, 999))
    nome = random.choice(nomes) + sufixo
    return nome  # máximo 12 caracteres


def gerar_senha():
    nomes = ["Gabriel", "Carlos", "Miguel", "Lucas", "Pedro", "Andre", "Rafael"]
    return random.choice(nomes) + random.choice(["@", "#"]) + str(random.randint(10, 9999))


def headers_ggmax(token=None):
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://ggmax.com.br",
        "Referer": "https://ggmax.com.br/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


class MailTM:
    def __init__(self):
        self.email = None
        self.senha = None
        self.token = None

    def criar_conta(self):
        resp = requests.get(f"{MAILTM_API}/domains")
        dominios = resp.json().get("hydra:member", [])
        if not dominios:
            raise Exception("Nenhum domínio disponível")
        dominio = dominios[0]["domain"]
        usuario = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"{usuario}@{dominio}"
        self.senha = gerar_senha()
        resp = requests.post(f"{MAILTM_API}/accounts", json={
            "address": self.email, "password": self.senha
        })
        if resp.status_code not in (200, 201):
            raise Exception(f"Erro criar email: {resp.text}")
        print(f"  EMAIL_CRIADO: {self.email}", flush=True)
        return self.email

    def autenticar(self):
        resp = requests.post(f"{MAILTM_API}/token", json={
            "address": self.email, "password": self.senha
        })
        self.token = resp.json().get("token")

    def aguardar_link_confirmacao(self, timeout=120):
        if not self.token:
            self.autenticar()
        headers = {"Authorization": f"Bearer {self.token}"}
        inicio = time.time()
        print("  AGUARDANDO_EMAIL...", flush=True)
        while time.time() - inicio < timeout:
            resp = requests.get(f"{MAILTM_API}/messages", headers=headers)
            for msg in resp.json().get("hydra:member", []):
                assunto   = msg.get("subject", "").lower()
                remetente = msg.get("from", {}).get("address", "").lower()
                if "ggmax" in remetente or "verific" in assunto or "confirm" in assunto or "ativ" in assunto:
                    detalhe = requests.get(
                        f"{MAILTM_API}/messages/{msg['id']}", headers=headers
                    ).json()
                    html  = detalhe.get("html", "") or ""
                    texto = detalhe.get("text", "") or ""
                    conteudo = html + texto
                    links = re.findall(r'https?://[^\s"<>]+ggmax[^\s"<>]+', conteudo)
                    if links:
                        print(f"  LINK_CONFIRMACAO: {links[0]}", flush=True)
                        return links[0].strip()
                    links2 = re.findall(r'https?://[^\s"<>]*(confirm|verif|activ|ativ)[^\s"<>]*', conteudo, re.IGNORECASE)
                    if links2:
                        print(f"  LINK_ENCONTRADO: {links2[0]}", flush=True)
                        return links2[0].strip()
            time.sleep(5)
        raise Exception("Timeout: e-mail não chegou em 2 minutos")


def gerar_pergunta(titulo, tom="variado"):
    try:
        tons = {
            "curioso": "curiosa e genuína",
            "interessado": "interessada e positiva",
            "direto": "direta e curta",
            "variado": random.choice(["curiosa", "direta", "simples"]),
        }
        resposta = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            max_tokens=60,
            messages=[{"role": "user", "content": (
                f"Gere UMA pergunta {tons.get(tom, 'curiosa')} para: '{titulo}'. "
                "Comprador brasileiro. APENAS a pergunta. Máximo 15 palavras."
            )}]
        )
        return resposta.choices[0].message.content.strip()
    except:
        return random.choice([
            "Qual o prazo de entrega após o pagamento?",
            "Funciona em qualquer dispositivo?",
            "Tem suporte caso tenha algum problema?",
            "Como recebo após confirmar o pagamento?",
            "Funciona no celular Android?",
        ])


def extrair_id_anuncio(url_anuncio):
    """Extrai o ID ou slug do anúncio da URL"""
    # URL formato: https://ggmax.com.br/anuncio/SLUG--ID
    match = re.search(r'/anuncio/([^/?#]+)', url_anuncio)
    if match:
        return match.group(1)
    return None


def processar_conta(campanha_id, url_anuncio, titulo, tom, numero, total):
    usuario = gerar_usuario()
    senha   = gerar_senha()
    email   = None
    pergunta = None

    print(f"INICIANDO_CONTA [{numero}/{total}] user={usuario}", flush=True)

    # 1. Criar e-mail temporário
    mailtm = MailTM()
    try:
        email = mailtm.criar_conta()
    except Exception as e:
        print(f"ERRO_EMAIL: {e}", flush=True)
        registrar_conta(campanha_id, numero, usuario, "", "", "erro", str(e))
        return

    try:
        registrar_conta(campanha_id, numero, usuario, email, "", "cadastrando")

        # 2. Registrar conta na GGMAX via API
        print(f"  REGISTRANDO_API...", flush=True)
        resp = requests.post(f"{GGMAX_API}/register",
            json={
                "username": usuario,
                "email": email,
                "password": senha,
                "confirmPassword": senha,
            },
            headers=headers_ggmax(),
            timeout=30
        )
        print(f"  REGISTER_STATUS: {resp.status_code} | {resp.text[:200]}", flush=True)

        if resp.status_code not in (200, 201):
            raise Exception(f"Erro registro: {resp.status_code} - {resp.text[:100]}")

        # 3. Aguardar e-mail de confirmação
        registrar_conta(campanha_id, numero, usuario, email, "", "verificando")
        link_confirmacao = mailtm.aguardar_link_confirmacao(timeout=120)

        # 4. Clicar no link de confirmação
        print(f"  CONFIRMANDO_EMAIL...", flush=True)
        resp_confirm = requests.get(link_confirmacao,
            headers=headers_ggmax(),
            allow_redirects=True,
            timeout=30
        )
        print(f"  CONFIRM_STATUS: {resp_confirm.status_code}", flush=True)
        time.sleep(2)

        # 5. Login via API
        registrar_conta(campanha_id, numero, usuario, email, "", "logando")
        print(f"  FAZENDO_LOGIN...", flush=True)
        resp_login = requests.post(f"{GGMAX_API}/auth",
            json={
                "username": usuario,
                "password": senha,
                "googleAccessToken": "",
                "code": None,
                "validation": None,
            },
            headers=headers_ggmax(),
            timeout=30
        )
        print(f"  LOGIN_STATUS: {resp_login.status_code} | {resp_login.text[:200]}", flush=True)

        if resp_login.status_code not in (200, 201):
            raise Exception(f"Erro login: {resp_login.status_code} - {resp_login.text[:100]}")

        login_data = resp_login.json()
        token = login_data.get("token") or login_data.get("access_token") or login_data.get("accessToken")
        if not token:
            # Tentar encontrar token no objeto retornado
            print(f"  LOGIN_DATA: {str(login_data)[:300]}", flush=True)
            raise Exception("Token não encontrado na resposta de login")

        print(f"  LOGIN_OK: token={token[:20]}...", flush=True)

        # 6. Fazer pergunta no anúncio
        pergunta = gerar_pergunta(titulo, tom)
        registrar_conta(campanha_id, numero, usuario, email, pergunta, "perguntando")
        print(f"  PERGUNTA: {pergunta}", flush=True)

        # Extrair slug/id do anúncio
        slug = extrair_id_anuncio(url_anuncio)
        print(f"  SLUG_ANUNCIO: {slug}", flush=True)

        # Tentar endpoint de perguntas
        resp_pergunta = requests.post(f"{GGMAX_API}/listings/{slug}/questions",
            json={"question": pergunta},
            headers=headers_ggmax(token=token),
            timeout=30
        )
        print(f"  PERGUNTA_STATUS: {resp_pergunta.status_code} | {resp_pergunta.text[:200]}", flush=True)

        if resp_pergunta.status_code in (200, 201):
            registrar_conta(campanha_id, numero, usuario, email, pergunta, "concluido")
            print(f"  CONCLUIDO [{numero}/{total}]", flush=True)
        else:
            raise Exception(f"Erro pergunta: {resp_pergunta.status_code} - {resp_pergunta.text[:100]}")

    except Exception as e:
        print(f"  ERRO [{numero}/{total}]: {e}", flush=True)
        registrar_conta(campanha_id, numero, usuario, email or "", pergunta or "", "erro", str(e))

    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def executar_campanha(campanha_id, url_anuncio, titulo, quantidade, tom):
    atualizar_campanha(campanha_id, "ativa")
    for i in range(1, quantidade + 1):
        processar_conta(campanha_id, url_anuncio, titulo, tom, i, quantidade)
    atualizar_campanha(campanha_id, "concluida")


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/iniciar", methods=["POST", "OPTIONS"])
def iniciar():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    if data.get("api_key") != BASE44_API_KEY:
        return jsonify({"erro": "API key inválida"}), 401
    campanha_id = data.get("campanha_id")
    url_anuncio = data.get("url_anuncio")
    titulo      = data.get("titulo", "Produto")
    quantidade  = int(data.get("quantidade", 5))
    tom         = data.get("tom", "variado")
    if not campanha_id or not url_anuncio:
        return jsonify({"erro": "campanha_id e url_anuncio são obrigatórios"}), 400
    campanhas_status[campanha_id] = {"contas": [], "campanha_status": "ativa"}
    thread = threading.Thread(
        target=executar_campanha,
        args=(campanha_id, url_anuncio, titulo, quantidade, tom)
    )
    thread.daemon = True
    thread.start()
    return jsonify({"status": "iniciado", "campanha_id": campanha_id, "mensagem": "Campanha iniciada!"})


@app.route("/status", methods=["GET"])
def status():
    campanha_id = request.args.get("campanha_id")
    if campanha_id and campanha_id in campanhas_status:
        return jsonify(campanhas_status[campanha_id])
    if campanhas_status:
        ultima = list(campanhas_status.values())[-1]
        return jsonify(ultima)
    return jsonify({"contas": [], "campanha_status": "aguardando"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
