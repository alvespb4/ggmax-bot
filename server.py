"""
GGMAX BOT - Servidor Railway Completo
Anti-Cloudflare com espera longa
"""

import sys
import os
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import asyncio
import random
import string
import time
import re
import requests
import threading
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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US'] });
window.chrome = { runtime: {} };
"""


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
    nomes = ["miguel", "carlos", "gabriel", "lucas", "pedro", "joao", "andre",
             "rafael", "mateus", "felipe", "thiago", "rodrigo", "bruno", "victor"]
    sobrenomes = ["silva", "santos", "oliveira", "souza", "lima", "costa",
                  "ferreira", "alves", "pereira", "gomes", "martins"]
    return random.choice(nomes) + random.choice(sobrenomes) + str(random.randint(100, 9999))


def gerar_senha():
    nomes = ["Gabriel", "Carlos", "Miguel", "Lucas", "Pedro", "Andre", "Rafael"]
    return random.choice(nomes) + random.choice(["@", "#"]) + str(random.randint(10, 9999))


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


async def criar_pagina_stealth(browser):
    ua = random.choice(USER_AGENTS)
    context = await browser.new_context(
        viewport={"width": random.randint(1280, 1920), "height": random.randint(700, 900)},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        user_agent=ua,
        extra_http_headers={
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
    )
    await context.add_init_script(STEALTH_JS)
    page = await context.new_page()
    return context, page


async def aguardar_site_carregar(page, timeout=45):
    """Aguarda o Cloudflare passar e o site GGMAX carregar de verdade"""
    inicio = time.time()
    while time.time() - inicio < timeout:
        title = await page.title()
        url = page.url
        print(f"  CHECANDO: title='{title}'", flush=True)

        # Cloudflare ainda rodando
        if "momento" in title.lower() or "moment" in title.lower() or title.strip() == "":
            print("  CLOUDFLARE_ATIVO, aguardando 4s...", flush=True)
            await asyncio.sleep(4)
            continue

        # Site carregou!
        if title and "cloudflare" not in title.lower() and title != "":
            print(f"  SITE_CARREGADO: '{title}'", flush=True)
            return True

        await asyncio.sleep(2)

    print("  TIMEOUT_CLOUDFLARE", flush=True)
    return False


async def clicar_menu(page):
    print("  ABRINDO_MENU...", flush=True)

    # Debug botões
    try:
        info = await page.evaluate("""
            () => {
                const result = [];
                document.querySelectorAll('button, [role="button"]').forEach((el, i) => {
                    if (i < 10) result.push({
                        text: el.innerText.trim().substring(0, 30),
                        cls: (el.className || '').substring(0, 60),
                        aria: el.getAttribute('aria-label') || '',
                        id: el.id || ''
                    });
                });
                return result;
            }
        """)
        for item in info:
            print(f"  BTN: '{item['text']}' cls='{item['cls']}'", flush=True)
    except:
        pass

    # Estratégia 1: coordenada canto direito
    try:
        vp = page.viewport_size
        w = vp["width"] if vp else 1366
        await page.mouse.click(w - 40, 30)
        await asyncio.sleep(2)
        if await page.query_selector("text=Entrar"):
            print("  MENU_OK_COORDENADA", flush=True)
            return True
    except:
        pass

    # Estratégia 2: JS topo direito
    try:
        await page.evaluate("""
            () => {
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    const rect = el.getBoundingClientRect();
                    if (rect.top >= 0 && rect.top < 80 && rect.right > window.innerWidth * 0.7) {
                        el.click();
                        return;
                    }
                }
            }
        """)
        await asyncio.sleep(2)
        if await page.query_selector("text=Entrar"):
            print("  MENU_OK_JS", flush=True)
            return True
    except:
        pass

    print("  MENU_FALHOU", flush=True)
    return False


async def processar_conta(campanha_id, url_anuncio, titulo, tom, numero, total):
    usuario = gerar_usuario()
    senha   = gerar_senha()
    email   = None
    pergunta = None

    print(f"INICIANDO_CONTA [{numero}/{total}] user={usuario}", flush=True)

    mailtm = MailTM()
    try:
        email = mailtm.criar_conta()
    except Exception as e:
        print(f"ERRO_EMAIL: {e}", flush=True)
        registrar_conta(campanha_id, numero, usuario, "", "", "erro", str(e))
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--window-size=1366,768",
            ]
        )
        context, page = await criar_pagina_stealth(browser)

        try:
            registrar_conta(campanha_id, numero, usuario, email, "", "cadastrando")
            print(f"  ABRINDO_GGMAX...", flush=True)
            await page.goto(GGMAX_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            # Aguardar Cloudflare passar (até 45s)
            ok = await aguardar_site_carregar(page, timeout=45)
            if not ok:
                raise Exception("Cloudflare não passou em 45 segundos")

            await asyncio.sleep(2)
            await clicar_menu(page)
            await asyncio.sleep(2)

            await page.click("text=Entrar", timeout=10000)
            await asyncio.sleep(1.5)

            await page.click("text=Criar uma conta", timeout=10000)
            await asyncio.sleep(2)

            await page.fill("input[placeholder='Usuário']", usuario)
            await asyncio.sleep(0.5)
            await page.fill("input[placeholder='E-mail']", email)
            await asyncio.sleep(0.5)
            await page.fill("input[placeholder='Senha']", senha)
            await asyncio.sleep(0.5)
            await page.fill("input[placeholder='Confirmar senha']", senha)
            await asyncio.sleep(0.5)

            await page.click("button:has-text('CADASTRAR')")
            await asyncio.sleep(3)
            print(f"  CADASTRO_ENVIADO", flush=True)

            registrar_conta(campanha_id, numero, usuario, email, "", "verificando")
            link_confirmacao = mailtm.aguardar_link_confirmacao(timeout=120)

            await page.goto(link_confirmacao, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            print(f"  EMAIL_CONFIRMADO", flush=True)

            registrar_conta(campanha_id, numero, usuario, email, "", "logando")
            await page.goto(GGMAX_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            await aguardar_site_carregar(page, timeout=30)
            await asyncio.sleep(2)

            await clicar_menu(page)
            await asyncio.sleep(2)

            await page.click("text=Entrar", timeout=10000)
            await asyncio.sleep(1.5)

            await page.fill("input[placeholder='Usuário ou e-mail']", usuario)
            await asyncio.sleep(0.5)
            await page.fill("input[placeholder='Senha']", senha)
            await asyncio.sleep(0.5)

            await page.click("button:has-text('ENTRAR')")
            await asyncio.sleep(3)
            print(f"  LOGIN_REALIZADO", flush=True)

            pergunta = gerar_pergunta(titulo, tom)
            registrar_conta(campanha_id, numero, usuario, email, pergunta, "perguntando")
            print(f"  PERGUNTA: {pergunta}", flush=True)

            await page.goto(url_anuncio, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
            await asyncio.sleep(2)

            campo = await page.query_selector(
                "textarea[placeholder*='pergunta'], textarea[placeholder*='Pergunta'], textarea[placeholder*='Digite']"
            )
            if not campo:
                raise Exception("Campo de pergunta não encontrado")

            await campo.fill(pergunta)
            await asyncio.sleep(1.5)
            await page.click("button:has-text('Perguntar')")
            await asyncio.sleep(3)

            registrar_conta(campanha_id, numero, usuario, email, pergunta, "concluido")
            print(f"  CONCLUIDO [{numero}/{total}]", flush=True)

        except Exception as e:
            print(f"  ERRO [{numero}/{total}]: {e}", flush=True)
            registrar_conta(campanha_id, numero, usuario, email or "", pergunta or "", "erro", str(e))
        finally:
            await browser.close()

    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


async def executar_campanha_async(campanha_id, url_anuncio, titulo, quantidade, tom):
    atualizar_campanha(campanha_id, "ativa")
    for i in range(1, quantidade + 1):
        await processar_conta(campanha_id, url_anuncio, titulo, tom, i, quantidade)
    atualizar_campanha(campanha_id, "concluida")


def rodar_campanha(campanha_id, url_anuncio, titulo, quantidade, tom):
    asyncio.run(executar_campanha_async(campanha_id, url_anuncio, titulo, quantidade, tom))


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
