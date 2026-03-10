"""
GGMAX BOT - Servidor Railway Completo
Fluxo correto baseado no site real da GGMAX
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import asyncio
import random
import string
import time
import re
import requests
import threading
import os
from playwright.async_api import async_playwright
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY    = "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"
BASE44_ENDPOINT = "https://preview-sandbox--69ab80547aecb9090ac003a1.base44.app/functions/webhook"
BASE44_API_KEY  = "5e03b0370d5f42d8a6e011517930bfe4"
MAILTM_API      = "https://api.mail.tm"
GGMAX_URL       = "https://ggmax.com.br"
DELAY_MIN       = 3.0
DELAY_MAX       = 8.0

groq_client = Groq(api_key=GROQ_API_KEY)
campanhas_status = {}


# ──────────────────────────────────────────────
# BASE44 — Reportar progresso
# ──────────────────────────────────────────────
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
        print(f"Erro Base44: {e}")


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
        print(f"Erro Base44: {e}")


# ──────────────────────────────────────────────
# GERADORES
# ──────────────────────────────────────────────
def gerar_usuario():
    """
    Gera usuário no formato: nome + números (tudo minúsculo)
    Ex: miguelsilva1544, carlosferreira892
    """
    nomes = ["miguel", "carlos", "gabriel", "lucas", "pedro", "joao", "andre",
             "rafael", "mateus", "felipe", "thiago", "rodrigo", "bruno", "victor"]
    sobrenomes = ["silva", "santos", "oliveira", "souza", "lima", "costa",
                  "ferreira", "alves", "pereira", "gomes", "martins"]
    nome = random.choice(nomes) + random.choice(sobrenomes)
    numero = str(random.randint(100, 9999))
    return nome + numero


def gerar_senha():
    """
    Gera senha válida para GGMAX:
    - 8 a 20 caracteres
    - letras maiúsculas e minúsculas
    - pelo menos um número
    - pelo menos um caractere especial (#@)
    Ex: Gabriel@2024
    """
    nomes = ["Gabriel", "Carlos", "Miguel", "Lucas", "Pedro", "Andre", "Rafael"]
    especiais = ["@", "#"]
    nome = random.choice(nomes)
    numero = str(random.randint(10, 9999))
    especial = random.choice(especiais)
    return nome + especial + numero


# ──────────────────────────────────────────────
# E-MAIL TEMPORÁRIO — Mail.tm
# ──────────────────────────────────────────────
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
        print(f"  ✓ E-mail criado: {self.email}")
        return self.email

    def autenticar(self):
        resp = requests.post(f"{MAILTM_API}/token", json={
            "address": self.email, "password": self.senha
        })
        self.token = resp.json().get("token")

    def aguardar_link_confirmacao(self, timeout=120):
        """Aguarda e-mail da GGMAX e extrai o link de confirmação."""
        if not self.token:
            self.autenticar()
        headers = {"Authorization": f"Bearer {self.token}"}
        inicio = time.time()
        print("  ⏳ Aguardando e-mail de confirmação...")
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
                    # Extrair link de confirmação da GGMAX
                    links = re.findall(r'https?://[^\s"<>]+ggmax[^\s"<>]+', conteudo)
                    if links:
                        link = links[0].strip()
                        print(f"  ✓ Link de confirmação: {link}")
                        return link
                    # Fallback: qualquer link de confirmação/verify
                    links2 = re.findall(r'https?://[^\s"<>]*(confirm|verif|activ|ativ)[^\s"<>]*', conteudo, re.IGNORECASE)
                    if links2:
                        link = links2[0].strip()
                        print(f"  ✓ Link encontrado: {link}")
                        return link
            time.sleep(5)
        raise Exception("Timeout: e-mail de confirmação não chegou em 2 minutos")


# ──────────────────────────────────────────────
# GERAÇÃO DE PERGUNTAS COM IA
# ──────────────────────────────────────────────
def gerar_pergunta(titulo, tom="variado"):
    tons = {
        "curioso":     "curiosa e genuína de alguém querendo saber mais antes de comprar",
        "interessado": "interessada e positiva demonstrando interesse no produto",
        "direto":      "direta e curta máximo 8 palavras",
        "variado":     random.choice(["curiosa", "direta", "simples", "bem curta"]),
    }
    try:
        resposta = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            max_tokens=60,
            messages=[{"role": "user", "content": (
                f"Gere UMA pergunta {tons.get(tom, 'curiosa')} para este produto: '{titulo}'. "
                "Deve parecer natural de um comprador real no Brasil. "
                "Retorne APENAS a pergunta sem aspas sem explicações. Máximo 15 palavras."
            )}]
        )
        return resposta.choices[0].message.content.strip()
    except:
        fallback = [
            "Qual o prazo de entrega após o pagamento?",
            "Funciona em qualquer dispositivo?",
            "Tem suporte caso tenha algum problema?",
            "Posso usar em mais de um aparelho?",
            "Como recebo após confirmar o pagamento?",
            "Existe garantia inclusa?",
            "É possível renovar quando vencer?",
            "Funciona no celular Android?",
            "Quanto tempo leva para ativar?",
            "Tem alguma restrição de uso?",
        ]
        return random.choice(fallback)


# ──────────────────────────────────────────────
# AUTOMAÇÃO DO NAVEGADOR — Fluxo correto GGMAX
# ──────────────────────────────────────────────
async def processar_conta(campanha_id, url_anuncio, titulo, tom, numero, total):
    usuario = gerar_usuario()
    senha   = gerar_senha()
    email   = None
    pergunta = None

    print(f"\n{'─'*50}")
    print(f"  [{numero}/{total}] Usuário: {usuario} | Senha: {senha}")

    # 1. Criar e-mail temporário
    mailtm = MailTM()
    try:
        email = mailtm.criar_conta()
    except Exception as e:
        registrar_conta(campanha_id, numero, usuario, "", "", "erro", str(e))
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(110,125)}.0.0.0 Safari/537.36"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()

        try:
            # ── PASSO 1: Abrir GGMAX ──
            registrar_conta(campanha_id, numero, usuario, email, "", "cadastrando")
            await page.goto(GGMAX_URL, wait_until="networkidle")
            await asyncio.sleep(random.uniform(1.5, 2.5))

            # ── PASSO 2: Clicar nas 3 barras (menu hamburguer) ──
            await page.locator("header").get_by_role("button").last.click(timeout=8000)
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # ── PASSO 3: Clicar em "Entrar" no menu ──
            await page.click("text=Entrar", timeout=5000)
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # ── PASSO 4: Clicar em "Criar uma conta" ──
            await page.click("text=Criar uma conta", timeout=5000)
            await asyncio.sleep(random.uniform(1, 2))

            # ── PASSO 5: Preencher formulário de cadastro ──
            # Campo Usuário (letras minúsculas + números)
            await page.click("input[placeholder='Usuário']")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            for char in usuario:
                await page.type("input[placeholder='Usuário']", char, delay=random.randint(60, 140))
            await asyncio.sleep(random.uniform(0.4, 0.8))

            # Campo E-mail
            await page.click("input[placeholder='E-mail']")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            for char in email:
                await page.type("input[placeholder='E-mail']", char, delay=random.randint(60, 140))
            await asyncio.sleep(random.uniform(0.4, 0.8))

            # Campo Senha
            await page.click("input[placeholder='Senha']")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            for char in senha:
                await page.type("input[placeholder='Senha']", char, delay=random.randint(60, 140))
            await asyncio.sleep(random.uniform(0.3, 0.6))

            # Campo Confirmar senha
            await page.click("input[placeholder='Confirmar senha']")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            for char in senha:
                await page.type("input[placeholder='Confirmar senha']", char, delay=random.randint(60, 140))
            await asyncio.sleep(random.uniform(0.5, 1.0))

            # ── PASSO 6: Clicar em CADASTRAR ──
            await page.click("button:has-text('CADASTRAR')")
            await asyncio.sleep(random.uniform(2, 3))
            print(f"  ✓ Cadastro enviado: {usuario} / {email} / {senha}")

            # ── PASSO 7: Aguardar link de confirmação no e-mail ──
            registrar_conta(campanha_id, numero, usuario, email, "", "verificando")
            link_confirmacao = mailtm.aguardar_link_confirmacao(timeout=120)

            # ── PASSO 8: Clicar no link de confirmação ──
            await page.goto(link_confirmacao, wait_until="networkidle")
            await asyncio.sleep(random.uniform(2, 3))
            print(f"  ✓ E-mail confirmado!")

            # ── PASSO 9: Fazer login ──
            registrar_conta(campanha_id, numero, usuario, email, "", "logando")
            await page.goto(GGMAX_URL, wait_until="networkidle")
            await asyncio.sleep(random.uniform(1.5, 2.5))

            # Clicar nas 3 barras
            await page.click("button.hamburger, button[aria-label*='menu'], .menu-icon, button:has(svg), header button:last-child", timeout=5000)
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # Clicar em Entrar
            await page.click("text=Entrar", timeout=5000)
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # Preencher login — campo aceita "Usuário ou e-mail"
            await page.click("input[placeholder='Usuário ou e-mail']")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            for char in usuario:
                await page.type("input[placeholder='Usuário ou e-mail']", char, delay=random.randint(60, 140))
            await asyncio.sleep(random.uniform(0.4, 0.8))

            await page.click("input[placeholder='Senha']")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            for char in senha:
                await page.type("input[placeholder='Senha']", char, delay=random.randint(60, 140))
            await asyncio.sleep(random.uniform(0.5, 1.0))

            # Clicar no botão azul ENTRAR
            await page.click("button:has-text('ENTRAR')")
            await asyncio.sleep(random.uniform(2, 3))
            print(f"  ✓ Login realizado: {usuario}")

            # ── PASSO 10: Navegar para o anúncio e fazer pergunta ──
            pergunta = gerar_pergunta(titulo, tom)
            registrar_conta(campanha_id, numero, usuario, email, pergunta, "perguntando")

            await page.goto(url_anuncio, wait_until="networkidle")
            await asyncio.sleep(random.uniform(2, 4))

            # Scroll até a seção de perguntas
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
            await asyncio.sleep(random.uniform(1, 2))

            # Encontrar campo de pergunta
            campo = await page.query_selector(
                "textarea[placeholder*='pergunta'], textarea[placeholder*='Pergunta'], textarea[placeholder*='Digite']"
            )
            if not campo:
                raise Exception("Campo de pergunta não encontrado")

            await campo.click()
            await asyncio.sleep(random.uniform(0.5, 1.0))
            for char in pergunta:
                await campo.type(char, delay=random.randint(40, 100))
            await asyncio.sleep(random.uniform(1, 2))

            # Clicar em Perguntar
            await page.click("button:has-text('Perguntar')")
            await asyncio.sleep(random.uniform(2, 3))

            # ── SUCESSO ──
            registrar_conta(campanha_id, numero, usuario, email, pergunta, "concluido")
            print(f"  ✓ [{numero}/{total}] CONCLUÍDO! Pergunta: \"{pergunta}\"")

        except Exception as e:
            print(f"  ✗ [{numero}/{total}] ERRO: {e}")
            registrar_conta(campanha_id, numero, usuario, email or "", pergunta or "", "erro", str(e))
        finally:
            await browser.close()

    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


# ──────────────────────────────────────────────
# ORQUESTRADOR
# ──────────────────────────────────────────────
async def executar_campanha_async(campanha_id, url_anuncio, titulo, quantidade, tom):
    atualizar_campanha(campanha_id, "ativa")
    for i in range(1, quantidade + 1):
        await processar_conta(campanha_id, url_anuncio, titulo, tom, i, quantidade)
    atualizar_campanha(campanha_id, "concluida")


def rodar_campanha(campanha_id, url_anuncio, titulo, quantidade, tom):
    asyncio.run(executar_campanha_async(campanha_id, url_anuncio, titulo, quantidade, tom))


# ──────────────────────────────────────────────
# ENDPOINTS FLASK
# ──────────────────────────────────────────────
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
        target=rodar_campanha,
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
