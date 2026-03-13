import sys, os, random, string, time, re, requests, threading
os.environ["PYTHONUNBUFFERED"] = "1"
try:
    sys.stdout.reconfigure(line_buffering=True)
except: pass

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY    = "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"
BASE44_ENDPOINT = "https://preview-sandbox--69ab80547aecb9090ac003a1.base44.app/functions/webhook"
BASE44_API_KEY  = "5e03b0370d5f42d8a6e011517930bfe4"
CAPTCHA_KEY     = "0a0c73fdbddbe3001115bd157f04979a"
MAILTM_API      = "https://api.mail.tm"
GGMAX_API       = "https://ggmax.com.br/api"
GGMAX_URL       = "https://ggmax.com.br"
DELAY_MIN       = 3.0
DELAY_MAX       = 8.0

groq_client = Groq(api_key=GROQ_API_KEY)
campanhas_status = {}


def registrar_conta_local(cid, num, user, email, perg, status, erro=""):
    campanhas_status.setdefault(cid, {"contas": [], "campanha_status": "ativa"})
    contas = campanhas_status[cid]["contas"]
    obj = next((c for c in contas if c["numero"] == num), None)
    if obj:
        obj.update({"usuario": user, "email": email, "pergunta": perg, "status": status, "erro": erro})
    else:
        contas.append({"numero": num, "usuario": user, "email": email, "pergunta": perg, "status": status, "erro": erro})

def registrar_conta(cid, num, user, email, perg, status, erro=""):
    registrar_conta_local(cid, num, user, email, perg, status, erro)
    try:
        requests.post(BASE44_ENDPOINT, json={
            "api_key": BASE44_API_KEY, "campanha_id": cid, "numero": num,
            "usuario": user, "email": email, "pergunta": perg,
            "status": status, "erro": erro}, timeout=10)
    except Exception as e:
        print(f"Erro Base44: {e}", flush=True)

def atualizar_campanha(cid, status):
    campanhas_status.setdefault(cid, {})["campanha_status"] = status
    try:
        requests.post(BASE44_ENDPOINT, json={
            "api_key": BASE44_API_KEY, "campanha_id": cid,
            "tipo": "atualizar_campanha", "status": status}, timeout=10)
    except: pass

def gerar_usuario():
    nomes = ["miguel","carlos","gabriel","lucas","pedro","joao","andre","rafael"]
    return random.choice(nomes) + str(random.randint(10, 999))

def gerar_senha():
    nomes = ["Gabriel","Carlos","Miguel","Lucas","Pedro","Andre","Rafael"]
    return random.choice(nomes) + random.choice(["@","#"]) + str(random.randint(10,9999))

def gerar_pergunta(titulo, tom="variado"):
    try:
        tons = {"curioso":"curiosa e genuína","interessado":"interessada e positiva",
                "direto":"direta e curta","variado":random.choice(["curiosa","direta","simples"])}
        r = groq_client.chat.completions.create(
            model="llama3-8b-8192", max_tokens=60,
            messages=[{"role":"user","content":(
                f"Gere UMA pergunta {tons.get(tom,'curiosa')} para: '{titulo}'. "
                "Comprador brasileiro. APENAS a pergunta. Máximo 15 palavras.")}])
        return r.choices[0].message.content.strip()
    except:
        return random.choice([
            "Qual o prazo de entrega após o pagamento?",
            "Funciona em qualquer dispositivo?",
            "Tem suporte caso tenha algum problema?",
            "Como recebo após confirmar o pagamento?",
        ])

def extrair_slug(url):
    m = re.search(r'/anuncio/([^/?#]+)', url)
    return m.group(1) if m else None


def obter_cf_e_device(url_pagina):
    """Resolve Cloudflare via 2captcha e captura x-gg-device do storage/requests"""
    from playwright.sync_api import sync_playwright
    import json as json_lib

    print("  PLAYWRIGHT_START...", flush=True)

    # JS que intercepta o turnstile E captura o device token do storage
    inject_js = """
        // Intercepta XMLHttpRequest para capturar x-gg-device
        const _origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
        XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
            if (name && name.toLowerCase() === 'x-gg-device') {
                console.log('XHR_DEVICE:' + value);
                window.__gg_device = value;
            }
            return _origSetHeader.apply(this, arguments);
        };

        // Intercepta fetch para capturar x-gg-device
        const _origFetch = window.fetch;
        window.fetch = function(url, opts) {
            if (opts && opts.headers) {
                const h = opts.headers;
                const dev = (h instanceof Headers) ? h.get('x-gg-device') :
                            (typeof h === 'object' ? (h['x-gg-device'] || h['X-Gg-Device']) : null);
                if (dev) {
                    console.log('FETCH_DEVICE:' + dev);
                    window.__gg_device = dev;
                }
            }
            return _origFetch.apply(this, arguments);
        };
    """

    device_token = None
    cookies_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--window-size=1920,1080',
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        page = context.new_page()
        page.add_init_script(inject_js)

        # Captura via console (fetch/XHR interceptado no JS)
        captured = {}
        def on_console(msg):
            t = msg.text
            if t.startswith('CF_PARAMS:'):
                try:
                    captured['cf'] = json_lib.loads(t[10:])
                    print(f"  CF_PARAMS OK: sitekey={captured['cf'].get('sitekey','?')}", flush=True)
                except: pass
            elif t.startswith('FETCH_DEVICE:') or t.startswith('XHR_DEVICE:'):
                dev = t.split(':', 1)[1]
                if dev and not captured.get('device'):
                    captured['device'] = dev
                    print(f"  DEVICE_VIA_JS!", flush=True)
        page.on("console", on_console)

        # Também intercepta via Playwright (backup)
        def on_request(req):
            gg = req.headers.get("x-gg-device")
            if gg and not captured.get('device'):
                captured['device'] = gg
                print(f"  DEVICE_VIA_PW!", flush=True)
        context.on("request", on_request)

        # 1. Navega
        print("  NAVEGANDO...", flush=True)
        try:
            page.goto(url_pagina, timeout=30000, wait_until="domcontentloaded")
        except: pass
        page.wait_for_timeout(6000)

        # 2. Aguarda o CF resolver sozinho (stealth mode)
        # Verifica título e aguarda passar
        for tentativa in range(6):
            title = page.title()
            print(f"  TITLE[{tentativa}]: {title[:60]}", flush=True)
            if "cloudflare" not in title.lower() and "attention" not in title.lower() and "just a moment" not in title.lower():
                print("  CF_PASSOU!", flush=True)
                break
            print(f"  CF_AGUARDANDO... ({tentativa+1}/6)", flush=True)
            page.wait_for_timeout(5000)

        # 4. Tenta extrair device do storage JS
        if not captured.get('device'):
            try:
                dev = page.evaluate("window.__gg_device || localStorage.getItem('deviceToken') || localStorage.getItem('device') || sessionStorage.getItem('deviceToken') || null")
                if dev:
                    captured['device'] = dev
                    print(f"  DEVICE_VIA_STORAGE!", flush=True)
            except: pass

        # 5. Aguarda requisições naturais do site (home page faz várias)
        if not captured.get('device'):
            page.wait_for_timeout(8000)

        # 6. Tenta extrair novamente do storage
        if not captured.get('device'):
            try:
                dev = page.evaluate("window.__gg_device")
                if dev:
                    captured['device'] = dev
                    print(f"  DEVICE_VIA_WINDOW!", flush=True)
            except: pass

        # 7. Loga todas as keys do localStorage para debug
        if not captured.get('device'):
            try:
                keys = page.evaluate("Object.keys(localStorage)")
                print(f"  LOCALSTORAGE_KEYS: {keys}", flush=True)
            except: pass

        # Cookies finais
        for c in context.cookies():
            cookies_dict[c["name"]] = c["value"]
        device_token = captured.get('device')
        browser.close()

    if not device_token:
        raise Exception("Não conseguiu capturar x-gg-device")

    return device_token, cookies_dict


def headers_ggmax(device_token, auth_token=None):
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": GGMAX_URL,
        "Referer": GGMAX_URL + "/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "x-gg-device": device_token,
    }
    if auth_token:
        h["Authorization"] = f"Bearer {auth_token}"
    return h


class MailTM:
    def __init__(self):
        self.email = self.senha = self.token = None

    def criar_conta(self):
        resp = requests.get(f"{MAILTM_API}/domains")
        dom = resp.json().get("hydra:member", [{}])[0].get("domain","dollicons.com")
        u = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"{u}@{dom}"
        self.senha = gerar_senha()
        r = requests.post(f"{MAILTM_API}/accounts", json={"address":self.email,"password":self.senha})
        if r.status_code not in (200,201):
            raise Exception(f"Erro criar email: {r.text}")
        print(f"  EMAIL_CRIADO: {self.email}", flush=True)
        return self.email

    def autenticar(self):
        r = requests.post(f"{MAILTM_API}/token", json={"address":self.email,"password":self.senha})
        self.token = r.json().get("token")

    def aguardar_link(self, timeout=120):
        if not self.token: self.autenticar()
        headers = {"Authorization": f"Bearer {self.token}"}
        inicio = time.time()
        print("  AGUARDANDO_EMAIL...", flush=True)
        while time.time() - inicio < timeout:
            msgs = requests.get(f"{MAILTM_API}/messages", headers=headers).json().get("hydra:member",[])
            for msg in msgs:
                assunto = msg.get("subject","").lower()
                remetente = msg.get("from",{}).get("address","").lower()
                if "ggmax" in remetente or any(w in assunto for w in ["verific","confirm","ativ"]):
                    det = requests.get(f"{MAILTM_API}/messages/{msg['id']}", headers=headers).json()
                    conteudo = (det.get("html") or "") + (det.get("text") or "")
                    links = re.findall(r'https?://[^\s"<>]+ggmax[^\s"<>]+', conteudo)
                    if links:
                        print(f"  LINK: {links[0]}", flush=True)
                        return links[0].strip()
            time.sleep(5)
        raise Exception("Timeout: e-mail não chegou")


def processar_conta(cid, url_anuncio, titulo, tom, numero, total):
    usuario = gerar_usuario()
    senha   = gerar_senha()
    email   = None
    pergunta = None

    print(f"INICIANDO_CONTA [{numero}/{total}] user={usuario}", flush=True)

    mailtm = MailTM()
    try:
        email = mailtm.criar_conta()
    except Exception as e:
        registrar_conta(cid, numero, usuario, "", "", "erro", str(e))
        return

    try:
        registrar_conta(cid, numero, usuario, email, "", "resolvendo_cloudflare")
        device_token, cookies = obter_cf_e_device(GGMAX_URL)
        print(f"  DEVICE_OK!", flush=True)

        registrar_conta(cid, numero, usuario, email, "", "cadastrando")
        r = requests.post(f"{GGMAX_API}/register",
            json={"username":usuario,"email":email,"password":senha,"confirmPassword":senha},
            headers=headers_ggmax(device_token), cookies=cookies, timeout=30)
        print(f"  REGISTER: {r.status_code} | {r.text[:200]}", flush=True)
        if r.status_code not in (200,201):
            raise Exception(f"Registro: {r.status_code} {r.text[:100]}")

        registrar_conta(cid, numero, usuario, email, "", "verificando")
        link = mailtm.aguardar_link(120)
        requests.get(link, headers=headers_ggmax(device_token), allow_redirects=True, timeout=30)
        time.sleep(2)

        registrar_conta(cid, numero, usuario, email, "", "logando")
        r = requests.post(f"{GGMAX_API}/auth",
            json={"username":usuario,"password":senha,"googleAccessToken":"","code":None,"validation":None},
            headers=headers_ggmax(device_token), cookies=cookies, timeout=30)
        print(f"  LOGIN: {r.status_code} | {r.text[:200]}", flush=True)
        if r.status_code not in (200,201):
            raise Exception(f"Login: {r.status_code} {r.text[:100]}")

        login_data = r.json()
        auth_token = login_data.get("token") or login_data.get("access_token") or login_data.get("accessToken")
        if not auth_token:
            raise Exception(f"Token não encontrado: {str(login_data)[:200]}")
        print("  LOGIN_OK", flush=True)

        pergunta = gerar_pergunta(titulo, tom)
        registrar_conta(cid, numero, usuario, email, pergunta, "perguntando")
        slug = extrair_slug(url_anuncio)
        print(f"  PERGUNTA: {pergunta} | SLUG: {slug}", flush=True)

        r = requests.post(f"{GGMAX_API}/listings/{slug}/questions",
            json={"question": pergunta},
            headers=headers_ggmax(device_token, auth_token=auth_token),
            cookies=cookies, timeout=30)
        print(f"  PERGUNTA_STATUS: {r.status_code} | {r.text[:200]}", flush=True)

        if r.status_code in (200,201):
            registrar_conta(cid, numero, usuario, email, pergunta, "concluido")
            print(f"  CONCLUIDO [{numero}/{total}]", flush=True)
        else:
            raise Exception(f"Pergunta: {r.status_code} {r.text[:100]}")

    except Exception as e:
        print(f"  ERRO [{numero}/{total}]: {e}", flush=True)
        registrar_conta(cid, numero, usuario, email or "", pergunta or "", "erro", str(e))

    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def executar_campanha(cid, url_anuncio, titulo, quantidade, tom):
    try:
        print(f"CAMPANHA_START cid={cid} qtd={quantidade}", flush=True)
        atualizar_campanha(cid, "ativa")
        for i in range(1, quantidade + 1):
            processar_conta(cid, url_anuncio, titulo, tom, i, quantidade)
        atualizar_campanha(cid, "concluida")
        print(f"CAMPANHA_FIM cid={cid}", flush=True)
    except Exception as e:
        import traceback
        print(f"CAMPANHA_EXCEPTION: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        atualizar_campanha(cid, "erro")


@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/iniciar", methods=["POST","OPTIONS"])
def iniciar():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    if data.get("api_key") != BASE44_API_KEY:
        return jsonify({"erro": "API key inválida"}), 401
    cid         = data.get("campanha_id")
    url_anuncio = data.get("url_anuncio")
    titulo      = data.get("titulo", "Produto")
    quantidade  = int(data.get("quantidade", 5))
    tom         = data.get("tom", "variado")
    if not cid or not url_anuncio:
        return jsonify({"erro": "campanha_id e url_anuncio são obrigatórios"}), 400
    campanhas_status[cid] = {"contas": [], "campanha_status": "ativa"}
    print(f"INICIAR: cid={cid} url={url_anuncio} qtd={quantidade}", flush=True)
    t = threading.Thread(target=executar_campanha, args=(cid, url_anuncio, titulo, quantidade, tom))
    t.daemon = True
    t.start()
    print(f"THREAD_STARTED", flush=True)
    return jsonify({"status": "iniciado", "campanha_id": cid})

@app.route("/status", methods=["GET"])
def status():
    cid = request.args.get("campanha_id")
    if cid and cid in campanhas_status:
        return jsonify(campanhas_status[cid])
    if campanhas_status:
        return jsonify(list(campanhas_status.values())[-1])
    return jsonify({"contas": [], "campanha_status": "aguardando"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
