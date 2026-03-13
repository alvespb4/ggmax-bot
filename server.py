import sys, os, random, string, time, re, requests, threading
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)

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


# ─── helpers ────────────────────────────────────────────────────────────────

def registrar_conta_local(cid, num, user, email, perg, status, erro=""):
    campanhas_status.setdefault(cid, {"contas": [], "campanha_status": "ativa"})
    contas = campanhas_status[cid]["contas"]
    obj = next((c for c in contas if c["numero"] == num), None)
    if obj:
        obj.update({"usuario": user, "email": email, "pergunta": perg,
                    "status": status, "erro": erro})
    else:
        contas.append({"numero": num, "usuario": user, "email": email,
                       "pergunta": perg, "status": status, "erro": erro})

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


# ─── 2captcha Cloudflare Turnstile ──────────────────────────────────────────

def obter_cf_e_device(url_pagina):
    """Abre GGMAX uma única vez, resolve Cloudflare via 2captcha e intercepta x-gg-device"""
    from playwright.sync_api import sync_playwright
    import json as json_lib

    print(f"  PLAYWRIGHT_INICIANDO sessão unificada...", flush=True)

    inject_js = """
        const i = setInterval(() => {
            if (window.turnstile) {
                clearInterval(i);
                window.turnstile.render = (a, b) => {
                    let params = {
                        sitekey: b.sitekey,
                        pageurl: window.location.href,
                        data: b.cData,
                        pagedata: b.chlPageData,
                        action: b.action,
                        userAgent: navigator.userAgent,
                    };
                    console.log('intercepted-params:' + JSON.stringify(params));
                    window.cfCallback = b.callback;
                    return 'foo';
                };
            }
        }, 50);
    """

    device_token = None
    cookies_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script(inject_js)

        # Intercepta x-gg-device em qualquer requisição
        captured = {}
        def on_request(req):
            gg = req.headers.get("x-gg-device")
            if gg and not captured.get("device"):
                captured["device"] = gg
                print(f"  DEVICE_INTERCEPTADO!", flush=True)
        page.on("request", on_request)

        # Captura params do turnstile via console
        cf_params = {}
        def on_console(msg):
            if 'intercepted-params:' in msg.text:
                raw = msg.text.replace('intercepted-params:', '').strip()
                try:
                    cf_params.update(json_lib.loads(raw))
                    print(f"  CF_PARAMS: sitekey={cf_params.get('sitekey','?')}", flush=True)
                except: pass
        page.on("console", on_console)

        # 1. Navega para GGMAX
        print(f"  NAVEGANDO...", flush=True)
        try:
            page.goto(url_pagina, timeout=30000, wait_until="domcontentloaded")
        except: pass
        page.wait_for_timeout(5000)

        # 2. Se interceptou params do CF, resolve via 2captcha
        if cf_params.get("sitekey"):
            print(f"  ENVIANDO_2CAPTCHA...", flush=True)
            r = requests.post("https://2captcha.com/in.php", data={
                "key": CAPTCHA_KEY,
                "method": "turnstile",
                "sitekey": cf_params.get("sitekey", ""),
                "pageurl": url_pagina,
                "data": cf_params.get("data", ""),
                "pagedata": cf_params.get("pagedata", ""),
                "action": cf_params.get("action", "managed"),
                "userAgent": cf_params.get("userAgent", ""),
                "json": 1,
            }, timeout=30)
            resp_data = r.json()
            print(f"  CAPTCHA_TASK: {resp_data}", flush=True)

            if resp_data.get("status") == 1:
                task_id = resp_data["request"]
                # Aguarda token
                cf_token = None
                for _ in range(36):
                    time.sleep(5)
                    r2 = requests.get(f"https://2captcha.com/res.php?key={CAPTCHA_KEY}&action=get&id={task_id}&json=1", timeout=30)
                    result = r2.json()
                    status_msg = result.get("request", "")
                    print(f"  CAPTCHA_STATUS: {str(status_msg)[:40]}", flush=True)
                    if result.get("status") == 1:
                        cf_token = result["request"]
                        break
                    if status_msg not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
                        break

                if cf_token:
                    print(f"  CAPTCHA_OK! Injetando token...", flush=True)
                    # Injeta o token via JS para completar o challenge
                    page.evaluate(f"if(window.cfCallback) window.cfCallback('{cf_token}')")
                    page.wait_for_timeout(5000)

        # 3. Tenta navegar para o site principal (após challenge)
        if not captured.get("device"):
            try:
                page.goto(url_pagina, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
            except: pass

        # 4. Tenta abrir cadastro para forçar requisição com x-gg-device
        if not captured.get("device"):
            try:
                # Clica nas 3 barras
                page.click("button[aria-label*='menu'], .hamburger, [class*='menu'], [class*='burger']", timeout=3000)
                page.wait_for_timeout(1000)
                page.click("text=Entrar", timeout=3000)
                page.wait_for_timeout(1000)
                page.click("text=Criar uma conta", timeout=3000)
                page.wait_for_timeout(2000)
            except: pass

        # 5. Tenta fazer uma requisição direta à API para forçar o device token
        if not captured.get("device"):
            try:
                page.evaluate("""
                    fetch('/api/announcements?limit=1', {
                        headers: {'Accept': 'application/json'}
                    })
                """)
                page.wait_for_timeout(3000)
            except: pass

        # Captura cookies finais
        for c in context.cookies():
            cookies_dict[c["name"]] = c["value"]
        device_token = captured.get("device")
        browser.close()

    if not device_token:
        raise Exception("Não conseguiu interceptar x-gg-device")

    return device_token, cookies_dict


def resolver_cloudflare_challenge(url_pagina):
    """Wrapper — chama obter_cf_e_device"""
    return obter_cf_e_device(url_pagina)


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


# ─── Mail.tm ─────────────────────────────────────────────────────────────────

class MailTM:
    def __init__(self):
        self.email = self.senha = self.token = None

    def criar_conta(self):
        resp = requests.get(f"{MAILTM_API}/domains")
        dom = resp.json().get("hydra:member", [{}])[0].get("domain","dollicons.com")
        u = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"{u}@{dom}"
        self.senha = gerar_senha()
        r = requests.post(f"{MAILTM_API}/accounts",
                          json={"address":self.email,"password":self.senha})
        if r.status_code not in (200,201):
            raise Exception(f"Erro criar email: {r.text}")
        print(f"  EMAIL_CRIADO: {self.email}", flush=True)
        return self.email

    def autenticar(self):
        r = requests.post(f"{MAILTM_API}/token",
                          json={"address":self.email,"password":self.senha})
        self.token = r.json().get("token")

    def aguardar_link(self, timeout=120):
        if not self.token: self.autenticar()
        headers = {"Authorization": f"Bearer {self.token}"}
        inicio = time.time()
        print("  AGUARDANDO_EMAIL...", flush=True)
        while time.time() - inicio < timeout:
            msgs = requests.get(f"{MAILTM_API}/messages",
                                headers=headers).json().get("hydra:member",[])
            for msg in msgs:
                assunto = msg.get("subject","").lower()
                remetente = msg.get("from",{}).get("address","").lower()
                if "ggmax" in remetente or any(w in assunto for w in ["verific","confirm","ativ"]):
                    det = requests.get(f"{MAILTM_API}/messages/{msg['id']}",
                                       headers=headers).json()
                    conteudo = (det.get("html") or "") + (det.get("text") or "")
                    links = re.findall(r'https?://[^\s"<>]+ggmax[^\s"<>]+', conteudo)
                    if links: 
                        print(f"  LINK: {links[0]}", flush=True)
                        return links[0].strip()
            time.sleep(5)
        raise Exception("Timeout: e-mail não chegou")


# ─── Fluxo principal ─────────────────────────────────────────────────────────

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
        registrar_conta(cid, numero, usuario, email, "", "resolvendo_captcha")

        # 1. Resolver Cloudflare + interceptar device token (sessão unificada)
        registrar_conta(cid, numero, usuario, email, "", "resolvendo_cloudflare")
        device_token, cookies = obter_cf_e_device(GGMAX_URL)
        print(f"  DEVICE_OK: {device_token[:30]}...", flush=True)

        # 3. Registrar conta
        registrar_conta(cid, numero, usuario, email, "", "cadastrando")
        print(f"  REGISTRANDO...", flush=True)
        r = requests.post(f"{GGMAX_API}/register",
            json={"username":usuario,"email":email,
                  "password":senha,"confirmPassword":senha},
            headers=headers_ggmax(device_token),
            cookies=cookies,
            timeout=30)
        print(f"  REGISTER: {r.status_code} | {r.text[:200]}", flush=True)
        if r.status_code not in (200,201):
            raise Exception(f"Registro: {r.status_code} {r.text[:100]}")

        # 4. Confirmação de e-mail
        registrar_conta(cid, numero, usuario, email, "", "verificando")
        link = mailtm.aguardar_link(120)
        requests.get(link, headers=headers_ggmax(device_token),
                     allow_redirects=True, timeout=30)
        time.sleep(2)

        # 5. Login
        registrar_conta(cid, numero, usuario, email, "", "logando")
        r = requests.post(f"{GGMAX_API}/auth",
            json={"username":usuario,"password":senha,
                  "googleAccessToken":"","code":None,"validation":None},
            headers=headers_ggmax(device_token),
            cookies=cookies,
            timeout=30)
        print(f"  LOGIN: {r.status_code} | {r.text[:200]}", flush=True)
        if r.status_code not in (200,201):
            raise Exception(f"Login: {r.status_code} {r.text[:100]}")

        login_data = r.json()
        auth_token = (login_data.get("token") or
                      login_data.get("access_token") or
                      login_data.get("accessToken"))
        if not auth_token:
            raise Exception(f"Token não encontrado: {str(login_data)[:200]}")
        print(f"  LOGIN_OK", flush=True)

        # 6. Pergunta
        pergunta = gerar_pergunta(titulo, tom)
        registrar_conta(cid, numero, usuario, email, pergunta, "perguntando")
        slug = extrair_slug(url_anuncio)
        print(f"  PERGUNTA: {pergunta} | SLUG: {slug}", flush=True)

        r = requests.post(f"{GGMAX_API}/listings/{slug}/questions",
            json={"question": pergunta},
            headers=headers_ggmax(device_token, auth_token=auth_token),
            cookies=cookies,
            timeout=30)
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
    atualizar_campanha(cid, "ativa")
    for i in range(1, quantidade + 1):
        processar_conta(cid, url_anuncio, titulo, tom, i, quantidade)
    atualizar_campanha(cid, "concluida")


# ─── Rotas Flask ─────────────────────────────────────────────────────────────

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
    t = threading.Thread(target=executar_campanha,
                         args=(cid, url_anuncio, titulo, quantidade, tom))
    t.daemon = True
    t.start()
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
