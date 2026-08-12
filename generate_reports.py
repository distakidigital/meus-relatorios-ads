import os
import json
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# Carregar clientes
CLIENTES_FILE = "clients.json"
OUTPUT_DIR = "docs"

def load_clients():
    if not os.path.exists(CLIENTES_FILE):
        return []
    with open(CLIENTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_metrics(text):
    metrics = {}
    # Investimento
    m = re.search(r'Investimento[\s\S]{0,80}?R\$\s*([\d.,]+)', text, re.I) or re.search(r'R\$\s*([\d.,]+)[\s\S]{0,30}?Investimento', text, re.I)
    if m: metrics['investimento'] = m.group(1)

    # Conversões / Mensagens
    m = re.search(r'Convers[õo]es\s*(\d+)', text, re.I) or re.search(r'Mensagens\s*(\d+)', text, re.I)
    if m: metrics['mensagens'] = m.group(1)

    # Custo por Conversão
    m = re.search(r'Custo[/\s]+conv\.?\s*R\$\s*([\d.,]+)', text, re.I) or re.search(r'Custo[/\s]+msg\s*R\$\s*([\d.,]+)', text, re.I)
    if m: metrics['custo_mensagem'] = m.group(1)

    # Cliques
    m = re.search(r'Cliques\s*(\d+)', text, re.I)
    if m: metrics['cliques'] = m.group(1)

    # Custo por Clique
    m = re.search(r'Custo\s*p\/\s*Cl?iq?ues?\s*R\$\s*([\d.,]+)', text, re.I) or re.search(r'CPC\s*R\$\s*([\d.,]+)', text, re.I)
    if m: metrics['custo_clique'] = m.group(1)

    # Impressões
    m = re.search(r'Impress[õo]es\s*([\d.,]+)', text, re.I)
    if m: metrics['impressoes'] = m.group(1)

    return metrics

def run():
    clients = load_clients()
    os.makedirs(os.path.join(OUTPUT_DIR, "assets"), exist_ok=True)
    
    today = datetime.now() - timedelta(hours=3) # Fuso Brasília
    periodo_str = f"01/{today.strftime('%m/%Y')} a {(today - timedelta(days=1)).strftime('%d/%m/%Y')}"

    reports_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        
        for client in clients:
            if not client.get("active", True):
                continue
            
            client_id = client["id"]
            client_name = client["name"]
            
            client_result = {
                "id": client_id,
                "name": client_name,
                "recipient": client.get("recipient", ""),
                "period": periodo_str,
                "google": None,
                "meta": None
            }

            for media_key, media_name in [("google", "Google"), ("meta", "Meta Ads")]:
                link = client.get(f"link_{media_key}")
                if not link or "COLOQUE" in link:
                    continue

                print(f"Processando {client_name} - {media_name}...")
                page = context.new_page()
                try:
                    clean_url = link.replace("/edit", "/view")
                    page.goto(clean_url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000) # Aguarda renderizar gráficos

                    # Tirar print
                    img_filename = f"{client_id}_{media_key}.jpg"
                    img_path = os.path.join(OUTPUT_DIR, "assets", img_filename)
                    page.screenshot(path=img_path, type="jpeg", quality=75)

                    # Extrair texto para métricas
                    page_text = page.inner_text("body")
                    metrics = parse_metrics(page_text)

                    client_result[media_key] = {
                        "metrics": metrics,
                        "image": f"assets/{img_filename}",
                        "link": link
                    }
                except Exception as e:
                    print(f"Erro ao processar {client_name} ({media_name}): {e}")
                finally:
                    page.close()

            reports_data.append(client_result)

        browser.close()

    # Salvar dados JSON para o site estático
    with open(os.path.join(OUTPUT_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(reports_data, f, ensure_ascii=False, indent=2)

    print("Relatórios gerados com sucesso!")

if __name__ == "__main__":
    run()
