"""
GGMAX BOT - Versão Final
- undetected-chromedriver (passa CF automaticamente)
- Proxy residencial rotativo (IP diferente por conta)
- Mail.tm para email temporário
- Groq AI para gerar perguntas
- Múltiplas contas em sequência
"""
import random
import string
import json
import re
import time
import os
import zipfile
import tempfile
import threading
import requests

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc

# ==================== CONFIGURAÇÕES ====================
GROQ_KEY = "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"

PROXY = {
    "host": "res.proxy-seller.com",
    "port": 10000,
    "user": "apic150d39d45b4473b",
    "pass": "3V7cpy5K",
}

CF_WORDS = ["um momento", "just a moment", "un instant", "один момент",
            "performing security", "verification en cours", "einen moment"]

INJECT_JS = """
window.__dev = null;
window.__auth_token = null;
const oF = window.fetch;
window.fetch = async function(url, opts) {
    const resp = await oF.apply(this, arguments);
    if (url && url.includes('/api/auth')) {
        try {
            const clone = resp.clone();
            const data = await clone.json();
            if (data.token) window.__auth_token = data.token;
        } catch(e) {}
    }
    if (opts && opts.headers) {
        const h = opts.headers;
        const dev = (h instanceof Headers) ? h.get('x-gg-device') :
                    (h && typeof h === 'object' ? (h['x-gg-device'] || h['X-Gg-Device']) : null);
        if (dev) window.__dev = dev;
    }
    return resp;
};
"""
# =======================================================

def is_cf(title):
    return any(w in title.lower() for w in CF_WORDS)

def gerar_usuario():
    nomes = ["joao","pedro","lucas","mateus","gabriel","felipe","andre","bruno","carlos","diego"]
    return random.choice(nomes) + ''.join(random.choices(string.digits, k=4))

def gerar_senha():
    return "Gabriel@" + ''.join(random.choices(string.digits, k=4))

def fechar_popups(driver):
    for xpath in [
        "//button[contains(text(),'Aceitar tudo')]",
        "//button[contains(text(),'Aceitar')]",
        "//button[contains(text(),'Bloquear')]",
        "//button[contains(text(),'Nunca')]",
        "//button[contains(text(),'Não salvar')]",
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
    manifest = """{
  "version": "1.0.0",
  "manifest_version": 2,
  "name": "Proxy Auth",
  "permissions": ["proxy","tabs","unlimitedStorage","storage","<all_urls>","webRequest","webRequestBlocking"],
  "background": {"scripts": ["background.js"]},
  "minimum_chrome_version": "22.0.0"
}"""
    background = f"""
var config = {{mode:"fixed_servers",rules:{{singleProxy:{{scheme:"http",host:"{PROXY['host']}",port:{PROXY['port']}}},bypassList:["localhost"]}}}};
chrome.proxy.settings.set({{value:config,scope:"regular"}},function(){{}});
function callbackFn(details){{return{{authCredentials:{{username:"{PROXY['user']}",password:"{PROXY['pass']}"}}}};}}
chrome.webRequest.onAuthRequired.addListener(callbackFn,{{urls:["<all_urls>"]}},["blocking"]);
"""
    ext_path = os.path.join(tempfile.gettempdir(), "proxy_auth_ext.zip")
    with zipfile.ZipFile(ext_path, 'w') as zp:
        zp.writestr("manifest.json", manifest)
        zp.writestr("background.js", background)
    return ext_path

def criar_driver():
    ext_path = criar_extensao_proxy()
    options = uc.ChromeOptions()
    options.add_extension(ext_path)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=pt-BR")
    options.add_argument("--disable-notifications")
    options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
    })
    driver = uc.Chrome(headless=False, version_main=145, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT_JS})
    return driver

def criar_email():
    try:
        r = requests.get("https://api.mail.tm/domains", timeout=10)
        domains = r.json().get("hydra:member", [])
        if not domains:
            return None
        domain = domains[0]["domain"]
        usuario = gerar_usuario()
        email = f"{usuario}@{domain}"
        senha = gerar_senha()
        r = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": senha}, timeout=10)
        if r.status_code not in [200, 201]:
            return None
        r = requests.post("https://api.mail.tm/token", json={"address": email, "password": senha}, timeout=10)
        token = r.json().get("token")
        return {"email": email, "senha": senha, "token": token, "usuario": usuario}
    except Exception as e:
        print(f"  Erro email: {e}")
        return None

def aguardar_confirmacao(mail_token, timeout=300):
    headers = {"Authorization": f"Bearer {mail_token}"}
    for i in range(timeout // 5):
        time.sleep(5)
        try:
            r = requests.get("https://api.mail.tm/messages", headers=headers, timeout=10)
            msgs = r.json().get("hydra:member", [])
            if msgs:
                r2 = requests.get(f"https://api.mail.tm/messages/{msgs[0]['id']}", headers=headers, timeout=10)
                data = r2.json()
                html = str(data.get("html", ""))
                text = str(data.get("text", ""))
                for body in [html, text]:
                    links = re.findall(r'https://ggmax\.com\.br/register/confirm/[a-f0-9]+', body)
                    if links:
                        return links[0]
        except:
            pass
        if i % 4 == 0:
            print(f"  [{i*5}s] aguardando email...")
    return None

def gerar_pergunta(titulo):
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": f"Crie UMA pergunta curta (máx 15 palavras) sobre: {titulo}. Só a pergunta."}],
                "max_tokens": 50
            },
            timeout=15
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return random.choice(["Qual o prazo de entrega?", "Ainda disponível?", "Aceita negociação?", "Como funciona?"])

def aguardar_cf(driver, timeout=40):
    for i in range(timeout // 2):
        time.sleep(2)
        try:
            if not is_cf(driver.title):
                print(f"  ✓ CF passou em {i*2}s")
                return True
        except:
            pass
        if i % 5 == 0:
            print(f"  [{i*2}s] aguardando CF...")
    return False

def executar_conta(url_anuncio, titulo, num_conta, callback=None):
    """Executa fluxo completo para uma conta"""
    resultado = {
        "numero": num_conta,
        "status": "erro",
        "usuario": "",
        "email": "",
        "pergunta": "",
        "erro": ""
    }

    def atualizar(status, **kwargs):
        resultado.update({"status": status, **kwargs})
        if callback:
            callback(resultado.copy())

    # Extrai slug
    slug_match = re.search(r'ggmax\.com\.br/(?:anuncio/)?([^/?]+)', url_anuncio)
    slug = slug_match.group(1) if slug_match else url_anuncio.split('/')[-1]

    # Cria email
    print(f"\n[{num_conta}] Criando email...")
    mail = criar_email()
    if not mail:
        atualizar("erro", erro="Falha criar email")
        return resultado

    resultado["email"] = mail["email"]
    resultado["usuario"] = mail["usuario"]
    senha = mail["senha"]
    print(f"[{num_conta}] Email: {mail['email']} | Usuario: {mail['usuario']}")

    for tentativa in range(1, 4):
        print(f"\n[{num_conta}] Tentativa {tentativa}/3...")
        driver = None
        parar = threading.Event()

        try:
            driver = criar_driver()
            popup_thread = threading.Thread(target=monitorar_popups, args=(driver, parar), daemon=True)
            popup_thread.start()
            driver.execute_cdp_cmd("Network.enable", {})

            # 1. Home
            print(f"[{num_conta}] Abrindo home...")
            driver.get("https://ggmax.com.br")
            time.sleep(3)
            if is_cf(driver.title):
                if not aguardar_cf(driver):
                    driver.quit()
                    continue
            print(f"  ✓ {driver.title}")

            wait = WebDriverWait(driver, 15)

            # 2. Abre modal de cadastro
            driver.execute_script("document.querySelector('.header__account a').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
            time.sleep(2)
            driver.execute_script("document.querySelectorAll('.account-menu a').forEach(a=>{if(a.textContent.trim()==='Entrar')a.dispatchEvent(new MouseEvent('click',{bubbles:true}))})")
            time.sleep(2)
            driver.execute_script("document.querySelectorAll('a,button,span').forEach(el=>{if(el.textContent.includes('Criar uma conta'))el.click()})")
            time.sleep(2)

            # 3. Preenche cadastro
            print(f"[{num_conta}] Preenchendo cadastro...")
            try:
                usuario_f = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Usuário']")))
                usuario_f.send_keys(mail["usuario"])
                driver.find_element(By.XPATH, "//input[@placeholder='E-mail']").send_keys(mail["email"])
                for f in driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
                    f.send_keys(senha)
                time.sleep(1)
                driver.execute_script("document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim().toUpperCase()==='CADASTRAR')b.click()})")
                print(f"  ✓ Cadastro enviado")
                time.sleep(5)
            except Exception as e:
                print(f"  Erro cadastro: {e}")

            # 4. Aguarda email
            print(f"[{num_conta}] Aguardando email...")
            link = aguardar_confirmacao(mail["token"])
            if link:
                print(f"  ✓ Link: {link[:50]}")
                driver.get(link)
                time.sleep(3)
                if is_cf(driver.title):
                    aguardar_cf(driver)
            else:
                print("  Email não chegou — continuando...")

            # 5. Login
            print(f"[{num_conta}] Fazendo login...")
            driver.execute_script("document.querySelector('.header__account a').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
            time.sleep(2)
            driver.execute_script("document.querySelectorAll('.account-menu a').forEach(a=>{if(a.textContent.trim()==='Entrar')a.dispatchEvent(new MouseEvent('click',{bubbles:true}))})")
            time.sleep(2)

            try:
                campo = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Usuário ou e-mail']")))
                campo.send_keys(mail["usuario"])
                driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(senha)
                driver.execute_script("document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim().toUpperCase()==='ENTRAR')b.click()})")
                print(f"  ✓ Login enviado")
                time.sleep(5)
            except Exception as e:
                print(f"  Erro login: {e}")

            # 6. Captura token
            auth_token = None
            for i in range(15):
                try:
                    auth_token = driver.execute_script("return window.__auth_token")
                    if auth_token:
                        print(f"  ✓ Token capturado!")
                        break
                    token_ls = driver.execute_script("""
                        for(let k of Object.keys(localStorage)){
                            let v=localStorage.getItem(k);
                            if(v&&v.length>50&&k.toLowerCase().includes('token'))return v;
                        }return null;
                    """)
                    if token_ls:
                        auth_token = token_ls
                        print(f"  ✓ Token via localStorage!")
                        break
                except:
                    pass
                time.sleep(1)

            if not auth_token:
                print("  Token não capturado")
                parar.set()
                driver.quit()
                continue

            # 7. Pergunta
            print(f"[{num_conta}] Abrindo anúncio...")
            driver.get(url_anuncio)
            time.sleep(5)
            if is_cf(driver.title):
                aguardar_cf(driver)

            pergunta = gerar_pergunta(titulo)
            resultado["pergunta"] = pergunta
            print(f"[{num_conta}] Pergunta: {pergunta}")

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
                print(f"  ✓ Clicou Perguntar!")
                time.sleep(5)

                body = driver.find_element(By.TAG_NAME, "body").text
                if pergunta in body:
                    print(f"  ✓ Pergunta confirmada!")
                    atualizar("concluido")
                else:
                    atualizar("concluido")

            except Exception as e:
                print(f"  Erro pergunta: {e}")
                atualizar("erro", erro=str(e))

            parar.set()
            driver.quit()
            if resultado["status"] == "concluido":
                break

        except Exception as e:
            print(f"  Erro geral: {e}")
            try:
                parar.set()
                driver.quit()
            except:
                pass
            continue

    return resultado

def rodar_campanha(url_anuncio, titulo, quantidade, callback=None):
    """Roda campanha com N contas em sequência"""
    resultados = []
    concluidos = 0
    erros = 0

    print(f"\n{'='*50}")
    print(f"GGMAX BOT - Campanha: {quantidade} contas")
    print(f"Anúncio: {url_anuncio}")
    print(f"{'='*50}")

    for i in range(1, quantidade + 1):
        resultado = executar_conta(url_anuncio, titulo, i, callback)
        resultados.append(resultado)

        if resultado["status"] == "concluido":
            concluidos += 1
        else:
            erros += 1

        print(f"\n[{i}/{quantidade}] Status: {resultado['status']} | Concluídos: {concluidos} | Erros: {erros}")

        # Delay entre contas
        if i < quantidade:
            delay = random.randint(5, 10)
            print(f"Aguardando {delay}s antes da próxima conta...")
            time.sleep(delay)

    print(f"\n{'='*50}")
    print(f"CAMPANHA CONCLUÍDA: {concluidos}/{quantidade} contas com sucesso")
    print(f"{'='*50}")
    return resultados

if __name__ == "__main__":
    # CONFIGURAÇÃO DA CAMPANHA
    URL_ANUNCIO = "https://ggmax.com.br/anuncio/fallout-76-caps"
    TITULO = "Fallout 76 Caps"
    QUANTIDADE = 1  # Mude para quantas contas quiser

    resultados = rodar_campanha(URL_ANUNCIO, TITULO, QUANTIDADE)

    print("\n========== RESULTADOS ==========")
    for r in resultados:
        print(json.dumps(r, ensure_ascii=False))
    print("================================")
