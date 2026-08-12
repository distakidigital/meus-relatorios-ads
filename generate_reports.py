import os
import json
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

CLIENTES_FILE = "clients.json"
OUTPUT_DIR = "docs"

def load_clients():
    if not os.path.exists(CLIENTES_FILE):
        return []
    with open(CLIENTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_metrics(text):
    metrics = {}
    m = re.search(r'Investimento[\s\S]{0,80}?R\$\s*([\d.,]+)', text, re.I) or re.search(r'R\$\s*([\d.,]+)[\s\S]{0,30}?Investimento', text, re.I)
    if m: metrics['investimento'] = m.group(1)

    m = re.search(r'Convers[õo]es\s*(\d+)', text, re.I) or re.search(r'Mensagens\s*(\d+)', text, re.I)
    if m: metrics['mensagens'] = m.group(1)

    m = re.search(r'Custo[/\s]+conv\.?\s*R\$\s*([\d.,]+)', text, re.I) or re.search(r'Custo[/\s]+msg\s*R\$\s*([\d.,]+)', text, re.I)
    if m: metrics['custo_mensagem'] = m.group(1)

    m = re.search(r'Cliques\s*(\d+)', text, re.I)
    if m: metrics['cliques'] = m.group(1)

    m = re.search(r'Custo\s*p\/\s*Cl?iq?ues?\s*R\$\s*([\d.,]+)', text, re.I) or re.search(r'CPC\s*R\$\s*([\d.,]+)', text, re.I)
    if m: metrics['custo_clique'] = m.group(1)

    m = re.search(r'Impress[õo]es\s*([\d.,]+)', text, re.I)
    if m: metrics['impressoes'] = m.group(1)

    return metrics

def run():
    clients = load_clients()
    os.makedirs(os.path.join(OUTPUT_DIR, "assets"), exist_ok=True)
    
    today = datetime.now() - timedelta(hours=3)
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    
    mes_anterior = (today.replace(day=1) - timedelta(days=1))
    fechamento_periodo_str = f"Mês de {meses[mes_anterior.month - 1]} de {mes_anterior.year}"
    
    ontem = today - timedelta(days=1)
    resumo_periodo_str = f"01/{str(today.month).zfill(2)} a {str(ontem.day).zfill(2)}/{str(ontem.month).zfill(2)}"

    reports_data = []

    # Os 4 tipos possíveis de relatórios
    targets = [
        {"key": "google_summary", "name": "Google Ads (Resumo Mensal)", "tipo": "Resumo", "period": resumo_periodo_str},
        {"key": "google_closure", "name": "Google Ads (Fechamento Mês Anterior)", "tipo": "Fechamento", "period": fechamento_periodo_str},
        {"key": "meta_summary", "name": "Meta Ads (Resumo Mensal)", "tipo": "Resumo", "period": resumo_periodo_str},
        {"key": "meta_closure", "name": "Meta Ads (Fechamento Mês Anterior)", "tipo": "Fechamento", "period": fechamento_periodo_str},
    ]

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
                "reports": []
            }

            for target in targets:
                link = client.get(target["key"])
                if not link or "COLOQUE" in link or link.strip() == "":
                    continue

                print(f"Processando {client_name} - {target['name']}...")
                page = context.new_page()
                try:
                    clean_url = link.replace("/edit", "/view")
                    page.goto(clean_url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000)

                    img_filename = f"{client_id}_{target['key']}.jpg"
                    img_path = os.path.join(OUTPUT_DIR, "assets", img_filename)
                    page.screenshot(path=img_path, type="jpeg", quality=75)

                    page_text = page.inner_text("body")
                    metrics = parse_metrics(page_text)

                    client_result["reports"].append({
                        "key": target["key"],
                        "name": target["name"],
                        "tipo": target["tipo"],
                        "period": target["period"],
                        "metrics": metrics,
                        "image": f"assets/{img_filename}",
                        "link": link
                    })
                except Exception as e:
                    print(f"Erro ao processar {client_name} ({target['name']}): {e}")
                finally:
                    page.close()

            if len(client_result["reports"]) > 0:
                reports_data.append(client_result)

        browser.close()

    with open(os.path.join(OUTPUT_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(reports_data, f, ensure_ascii=False, indent=2)

    print("Relatórios atualizados com sucesso!")

if __name__ == "__main__":
    run()
