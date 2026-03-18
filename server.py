"""
GGMAX BOT - Server Flask
Integra com o painel web e roda o bot
"""
import sys, os, random, string, time, re, threading, json
os.environ["PYTHONUNBUFFERED"] = "1"
try:
    sys.stdout.reconfigure(line_buffering=True)
except: pass

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==================== CONFIGURAÇÕES ====================
GROQ_KEY = "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"
API_KEY  = "5e03b0370d5f42d8a6e011517930bfe4"

PROXY = {
    "host": "res.proxy-seller.com",
    "port": 10000,
    "user": "apic150d39d45b4473b",
    "pass": "3V7cpy5K",
}
# =======================================================

campanhas_status = {}

# ── helpers ──────────────────────────────────────────────────────────────────

def registrar_conta(cid, num, user, email, perg, status, erro=""):
    campanhas_status.setdefault(cid, {"contas": [], "campanha_status": "ativa"})
    contas = campanhas_status[cid]["contas"]
    obj = next((c for c in contas if c["numero"] == num), None)
    if obj:
        obj.update({"usuario": user, "email": email, "pergunta": perg, "status": status, "erro": erro})
    else:
        contas.append({"numero": num, "usuario": user, "email": email, "pergunta": perg, "status": status, "erro": erro})

def atualizar_campanha(cid, status):
    campanhas_status.setdefault(cid, {})["campanha_status"] = status

# ── bot functions ─────────────────────────────────────────────────────────────

import requests as req
import zipfile, tempfile

CF_WORDS = ["um momento", "just a moment", "un instant", "один момент",
            "performing security", "verification en cours", "einen moment"]

INJECT_JS = """
window.__dev = null;
window.__auth_token = null;
const oF = window.fetch;
window.fetch = async function(url, opts) {
    const resp = await oF.apply(this, arguments);
    if (url && url.includes('/api/auth')) {
        try { const d = await resp.clone().json(); if(d.token) window.__auth_token=d.token; } catch(e) {}
    }
    return resp;
};
"""

def is_cf(title):
    return any(w in title.lower() for w in CF_WORDS)

def gerar_usuario():
    nomes = ["joao","pedro","lucas","mateus","gabriel","felipe","andre","bruno","carlos","diego"]
    return random.choice(nomes) + ''.join(random.choices(string.digits, k=4))

def gerar_senha():
    return "Gabriel@" + ''.join(random.choices(string.digits, k=4))

def fechar_popups(driver):
    from selenium.webdriver.common.by import By
    for xpath in [
        "//button[contains(text(),'Aceitar tudo')]",
        "//button[contains(text(),'Aceitar')]",
        "//button[contains(text(),'Bloquear')]",
        "//button[contains(text(),'Nunca')]",
    ]:
        try:
            for btn in driver.find_elements(By.XPATH, xpath):
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.3)
        except:
            pass

def monitorar_popups(driver, parar):
    while not parar.is_set():
        try:
            fechar_popups(driver)
        except:
            pass
        time.sleep(1)

def criar_extensao_proxy():
    manifest = '{"version":"1.0.0","manifest_version":2,"name":"Proxy Auth","permissions":["proxy","tabs","unlimitedStorage","storage","<all_urls>","webRequest","webRequestBlocking"],"background":{"scripts":["background.js"]},"minimum_chrome_version":"22.0.0"}'
    background = f'var config={{mode:"fixed_servers",rules:{{singleProxy:{{scheme:"http",host:"{PROXY["host"]}",port:{PROXY["port"]}}},bypassList:["localhost"]}}}};chrome.proxy.settings.set({{value:config,scope:"regular"}},function(){{}});function callbackFn(d){{return{{authCredentials:{{username:"{PROXY["user"]}",password:"{PROXY["pass"]}"}}}};}}chrome.webRequest.onAuthRequired.addListener(callbackFn,{{urls:["<all_urls>"]}},["blocking"]);'
    ext_path = os.path.join(tempfile.gettempdir(), "proxy_auth_ext.zip")
    with zipfile.ZipFile(ext_path, 'w') as zp:
        zp.writestr("manifest.json", manifest)
        zp.writestr("background.js", background)
    return ext_path

def criar_driver():
    import undetected_chromedriver as uc

    # Detecta se está no Railway/Linux ou Windows local
    is_linux = os.name != 'nt'

    ext_path = criar_extensao_proxy()
    options = uc.ChromeOptions()
    options.add_extension(ext_path)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=pt-BR")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    if is_linux:
        # Railway/Linux — headless com Xvfb
        options.add_argument("--headless=new")
        options.add_argument("--display=:99")
        chrome_path = "/usr/bin/google-chrome"
        if os.path.exists(chrome_path):
            options.binary_location = chrome_path

    options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
    })

    headless = is_linux
    driver = uc.Chrome(headless=headless, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT_JS})
    return driver

def criar_email():
    try:
        r = req.get("https://api.mail.tm/domains", timeout=10)
        domain = r.json()["hydra:member"][0]["domain"]
        usuario = gerar_usuario()
        email = f"{usuario}@{domain}"
        senha = gerar_senha()
        r = req.post("https://api.mail.tm/accounts", json={"address": email, "password": senha}, timeout=10)
        if r.status_code not in [200, 201]:
            return None
        r = req.post("https://api.mail.tm/token", json={"address": email, "password": senha}, timeout=10)
        return {"email": email, "senha": senha, "token": r.json().get("token"), "usuario": usuario}
    except:
        return None

def aguardar_confirmacao(mail_token, timeout=300):
    headers = {"Authorization": f"Bearer {mail_token}"}
    for i in range(timeout // 5):
        time.sleep(5)
        try:
            r = req.get("https://api.mail.tm/messages", headers=headers, timeout=10)
            msgs = r.json().get("hydra:member", [])
            if msgs:
                r2 = req.get(f"https://api.mail.tm/messages/{msgs[0]['id']}", headers=headers, timeout=10)
                data = r2.json()
                for body in [str(data.get("html","")), str(data.get("text",""))]:
                    links = re.findall(r'https://ggmax\.com\.br/register/confirm/[a-f0-9]+', body)
                    if links:
                        return links[0]
        except:
            pass
    return None

def gerar_pergunta(titulo, tom="variado"):
    try:
        prompts = {
            "variado": f"Crie UMA pergunta curta (máx 15 palavras) sobre: {titulo}. Só a pergunta.",
            "curioso": f"Crie UMA pergunta curiosa e interessada (máx 15 palavras) sobre: {titulo}. Só a pergunta.",
            "direto": f"Crie UMA pergunta direta e objetiva (máx 10 palavras) sobre: {titulo}. Só a pergunta.",
        }
        r = req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompts.get(tom, prompts["variado"])}], "max_tokens": 50},
            timeout=15
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return random.choice(["Qual o prazo de entrega?", "Ainda disponível?", "Aceita negociação?"])

def aguardar_cf(driver, timeout=40):
    for i in range(timeout // 2):
        time.sleep(2)
        try:
            if not is_cf(driver.title):
                return True
        except:
            pass
    return False

def executar_conta(cid, url_anuncio, titulo, num_conta, tom="variado", delay=5):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    slug_match = re.search(r'ggmax\.com\.br/(?:anuncio/)?([^/?]+)', url_anuncio)
    slug = slug_match.group(1) if slug_match else url_anuncio.split('/')[-1]

    registrar_conta(cid, num_conta, "", "", "", "iniciando")

    mail = criar_email()
    if not mail:
        registrar_conta(cid, num_conta, "", "", "", "erro", "Falha criar email")
        return

    registrar_conta(cid, num_conta, mail["usuario"], mail["email"], "", "cadastrando")
    senha = mail["senha"]

    for tentativa in range(1, 4):
        driver = None
        parar = threading.Event()
        try:
            driver = criar_driver()
            popup_thread = threading.Thread(target=monitorar_popups, args=(driver, parar), daemon=True)
            popup_thread.start()
            driver.execute_cdp_cmd("Network.enable", {})

            driver.get("https://ggmax.com.br")
            time.sleep(3)
            if is_cf(driver.title):
                if not aguardar_cf(driver):
                    driver.quit()
                    continue

            wait = WebDriverWait(driver, 15)

            # Abre modal cadastro
            driver.execute_script("document.querySelector('.header__account a').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
            time.sleep(2)
            driver.execute_script("document.querySelectorAll('.account-menu a').forEach(a=>{if(a.textContent.trim()==='Entrar')a.dispatchEvent(new MouseEvent('click',{bubbles:true}))})")
            time.sleep(2)
            driver.execute_script("document.querySelectorAll('a,button,span').forEach(el=>{if(el.textContent.includes('Criar uma conta'))el.click()})")
            time.sleep(2)

            # Preenche cadastro
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Usuário']"))).send_keys(mail["usuario"])
                driver.find_element(By.XPATH, "//input[@placeholder='E-mail']").send_keys(mail["email"])
                for f in driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
                    f.send_keys(senha)
                time.sleep(1)
                driver.execute_script("document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim().toUpperCase()==='CADASTRAR')b.click()})")
                time.sleep(5)
            except Exception as e:
                print(f"  Erro cadastro: {e}")

            # Email
            registrar_conta(cid, num_conta, mail["usuario"], mail["email"], "", "verificando")
            link = aguardar_confirmacao(mail["token"])
            if link:
                driver.get(link)
                time.sleep(3)
                if is_cf(driver.title):
                    aguardar_cf(driver)

            # Login
            registrar_conta(cid, num_conta, mail["usuario"], mail["email"], "", "logando")
            driver.execute_script("document.querySelector('.header__account a').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
            time.sleep(2)
            driver.execute_script("document.querySelectorAll('.account-menu a').forEach(a=>{if(a.textContent.trim()==='Entrar')a.dispatchEvent(new MouseEvent('click',{bubbles:true}))})")
            time.sleep(2)

            try:
                wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Usuário ou e-mail']"))).send_keys(mail["usuario"])
                driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(senha)
                driver.execute_script("document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim().toUpperCase()==='ENTRAR')b.click()})")
                time.sleep(5)
            except Exception as e:
                print(f"  Erro login: {e}")

            # Token
            auth_token = None
            for i in range(15):
                try:
                    t = driver.execute_script("return window.__auth_token")
                    if t:
                        auth_token = t
                        break
                    t = driver.execute_script("for(let k of Object.keys(localStorage)){let v=localStorage.getItem(k);if(v&&v.length>50&&k.toLowerCase().includes('token'))return v;}return null;")
                    if t:
                        auth_token = t
                        break
                except:
                    pass
                time.sleep(1)

            if not auth_token:
                parar.set()
                driver.quit()
                continue

            # Pergunta
            registrar_conta(cid, num_conta, mail["usuario"], mail["email"], "", "perguntando")
            driver.get(url_anuncio)
            time.sleep(5)
            if is_cf(driver.title):
                aguardar_cf(driver)

            pergunta = gerar_pergunta(titulo, tom)

            try:
                textarea = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", textarea)
                time.sleep(1)
                textarea.click()
                for char in pergunta:
                    textarea.send_keys(char)
                    time.sleep(0.05)
                time.sleep(3)

                btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(@class,'btn-primary') and contains(text(),'Perguntar')]")
                ))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click()", btn)
                time.sleep(5)

                registrar_conta(cid, num_conta, mail["usuario"], mail["email"], pergunta, "concluido")
                parar.set()
                driver.quit()
                return

            except Exception as e:
                registrar_conta(cid, num_conta, mail["usuario"], mail["email"], "", "erro", str(e))

            parar.set()
            driver.quit()
            return

        except Exception as e:
            print(f"  Erro geral tentativa {tentativa}: {e}")
            try:
                parar.set()
                driver.quit()
            except:
                pass

    registrar_conta(cid, num_conta, mail["usuario"], mail["email"], "", "erro", "Todas tentativas falharam")

def rodar_campanha(cid, url_anuncio, titulo, quantidade, tom, delay_config):
    delays = {"rapido": (3,5), "normal": (5,10), "lento": (10,20)}
    d_min, d_max = delays.get(delay_config, (5,10))

    for i in range(1, quantidade + 1):
        executar_conta(cid, url_anuncio, titulo, i, tom)
        if i < quantidade:
            time.sleep(random.randint(d_min, d_max))

    total = len(campanhas_status.get(cid, {}).get("contas", []))
    concluidos = sum(1 for c in campanhas_status.get(cid, {}).get("contas", []) if c["status"] == "concluido")
    atualizar_campanha(cid, "concluida" if concluidos > 0 else "erro")

# ── rotas Flask ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/iniciar", methods=["POST"])
def iniciar():
    data = request.json
    if data.get("api_key") != API_KEY:
        return jsonify({"erro": "API key inválida"}), 401

    cid = data.get("campanha_id", f"camp_{int(time.time())}")
    url = data.get("url_anuncio", "")
    titulo = data.get("titulo", "Produto")
    quantidade = int(data.get("quantidade", 1))
    tom = data.get("tom", "variado")
    delay = data.get("delay", "normal")

    if not url:
        return jsonify({"erro": "URL do anúncio obrigatória"}), 400

    campanhas_status[cid] = {"contas": [], "campanha_status": "ativa"}

    t = threading.Thread(target=rodar_campanha, args=(cid, url, titulo, quantidade, tom, delay), daemon=True)
    t.start()

    return jsonify({"ok": True, "campanha_id": cid, "quantidade": quantidade})

@app.route("/status")
def status():
    cid = request.args.get("campanha_id")
    if cid and cid in campanhas_status:
        return jsonify(campanhas_status[cid])
    return jsonify({"contas": [], "campanha_status": "nao_encontrada"})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": "ggmax-bot"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"GGMAX BOT rodando na porta {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
