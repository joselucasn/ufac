"""
seed.py — Busca todas as tasks UFAC, incluindo as fechadas,
que não são retornadas pelo endpoint /tasks padrão.
"""
import requests
import json
import time
import sys

BASE = "https://secure.runrun.it/api/v1.0"
TOKEN = "oIbVXFCmN_JuACEi2R8MOGn-odhJ3uvt8-2XI7tcpUM"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# IDs de tarefas CONCLUÍDAS que sabemos que existem
# (descobertas via search_tasks e verificação manual)
TASKS_CONCLUIDAS = [
    9513, 8571, 8231, 11903, 8569, 17727, 9151, 11867,
    10958, 17891, 17733, 10900, 9016, 17889, 7275, 19250,
    18075, 18353, 20673, 21069, 21545, 21543, 21487,
]


def fetch_one(task_id: int) -> dict | None:
    url = f"{BASE}/tasks/{task_id}"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
            time.sleep(1)
        except Exception:
            time.sleep(2 ** attempt)
    return None


def fetch_all_concluidas() -> list[dict]:
    results = []
    for tid in TASKS_CONCLUIDAS:
        task = fetch_one(tid)
        if task:
            results.append(task)
            sys.stdout.write(f"#{tid} OK\n")
        else:
            sys.stdout.write(f"#{tid} FAIL\n")
        sys.stdout.flush()
        time.sleep(0.3)
    return results


if __name__ == "__main__":
    tasks = fetch_all_concluidas()
    # Salva como JSON
    with open("seed_concluidas.json", "w") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    print(f"\nSalvas: {len(tasks)} tarefas concluídas em seed_concluidas.json")
