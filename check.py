import os
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

URL = "https://www.pensanoevento.com.br/sitev2/eventos/95297/imprevisto-sertanejo?promoter=50135"

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def send_discord(title, description, color=15158332):
    if not DISCORD_WEBHOOK:
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color
            }
        ]
    }

    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code >= 400:
        print("Erro ao enviar Discord:", r.text)


def fetch_lotes():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    lotes = soup.select(".lotes")

    current = {}

    for lote in lotes:
        name_el = lote.select_one("b")
        if not name_el:
            continue

        name = " ".join(name_el.get_text().split())
        esgotado = lote.select_one(".badge.bg-danger")
        status = "esgotado" if esgotado else "disponivel"

        current[name] = status

    return current


def main():
    state = load_json("state.json", {"lotes": {}, "last_change": None})
    stats = load_json("stats.json", {"runs": 0, "errors": 0, "last_report": None})

    stats["runs"] += 1
    now = datetime.now(timezone.utc).isoformat()

    try:
        current = fetch_lotes()
        previous = state["lotes"]

        changes = []

        for name in current:
            if name not in previous:
                changes.append(f"🆕 Novo lote: {name} ({current[name]})")

        for name in previous:
            if name not in current:
                changes.append(f"❌ Lote removido: {name}")

        for name in current:
            if name in previous and current[name] != previous[name]:
                changes.append(
                    f"🔄 Status mudou: {name} ({previous[name]} → {current[name]})"
                )

        if changes:
            send_discord(
                "🚨 Mudança detectada",
                "\n".join(changes),
                16711680
            )
            state["last_change"] = now

        state["lotes"] = current
        save_json("state.json", state)

        # relatório a cada 2h
        last_report = stats.get("last_report")
        send_report = False

        if not last_report:
            send_report = True
        else:
            last_dt = datetime.fromisoformat(last_report)
            diff = datetime.now(timezone.utc) - last_dt
            if diff.total_seconds() >= 7200:
                send_report = True

        if send_report:
            total = len(current)
            disponiveis = sum(1 for s in current.values() if s == "disponivel")
            esgotados = sum(1 for s in current.values() if s == "esgotado")

            report = (
                f"Execuções: {stats['runs']}\n"
                f"Erros: {stats['errors']}\n"
                f"Total lotes: {total}\n"
                f"Disponíveis: {disponiveis}\n"
                f"Esgotados: {esgotados}\n"
                f"Última mudança: {state.get('last_change')}"
            )

            send_discord("📊 Relatório 2h", report, 3447003)
            stats["last_report"] = now

        save_json("stats.json", stats)

    except Exception as e:
        stats["errors"] += 1
        save_json("stats.json", stats)
        send_discord("⚠️ Erro na execução", str(e), 15105570)


if __name__ == "__main__":
    time.sleep(random.randint(5, 20))  # anti padrão fixo
    main()
