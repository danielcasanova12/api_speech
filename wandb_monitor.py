import time
import requests
import wandb
from datetime import datetime

# ================= CONFIG =================
CHECK_INTERVAL = 15       # segundos entre verificações (1 minuto)
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1456985530246889596/xZdAllsKqUUl4vWHD-TCmpb6f-AXFllNQEXNTvaKxiJV8k5oFbl7OasWoAfASub4iqWn"
API_KEY = "9e2b02aadec54f5820352e4124937fb9c55df9ea"
ENTITY = "snaxofc10-utfpr-medianeira"
DISCORD_TAG = "@here"
# =========================================

# Login no W&B
wandb.login(key=API_KEY)
api = wandb.Api()

monitoring = True
active_runs = {}  # {run_id: {"project": str, "name": str, "started_at": datetime}}

def send_notification(message: str, mention: bool = False):
    try:
        if mention:
            payload = {"content": f"{DISCORD_TAG} {message}"}
        else:
            payload = {"content": message}
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Alerta enviado para Discord")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ERRO Discord: {e}")

def format_duration(seconds):
    """Formata duração em formato legível"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}min"
    else:
        hours = int(seconds/3600)
        mins = int((seconds % 3600)/60)
        return f"{hours}h {mins}min"

def monitor_projects():
    global monitoring
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Monitoramento iniciado")
    print(f"[INFO] Verificando a cada {CHECK_INTERVAL} segundos")
    print(f"[INFO] Entity: {ENTITY}\n")

    while monitoring:
        try:
            current_active = set()
            
            for project in api.projects(ENTITY):
                project_name = project.name
                
                for run in api.runs(f"{ENTITY}/{project_name}"):
                    state = run.state
                    
                    # Se a run está rodando
                    if state == "running":
                        current_active.add(run.id)
                        
                        # Se é uma run nova que começou a rodar
                        if run.id not in active_runs:
                            active_runs[run.id] = {
                                "project": project_name,
                                "name": run.name,
                                "started_at": datetime.now()
                            }
                            
                            msg = (
                                f"✅ **NOVA RUN INICIADA**\n"
                                f"📦 Projeto: `{ENTITY}/{project_name}`\n"
                                f"🏃 Run: `{run.name}`\n"
                                f"⏰ Horário: `{datetime.now().strftime('%H:%M:%S')}`"
                            )
                            send_notification(msg, mention=False)  # Sem menção
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Nova run: {run.name} ({project_name})")
            
            # Verificar runs que pararam de rodar
            stopped_runs = set(active_runs.keys()) - current_active
            
            for run_id in stopped_runs:
                data = active_runs[run_id]
                
                # Buscar estado final da run
                try:
                    run = api.run(f"{ENTITY}/{data['project']}/{run_id}")
                    final_state = run.state
                    duration = (datetime.now() - data['started_at']).total_seconds()
                    
                    # Emoji e menção baseado no estado final
                    if final_state == "finished":
                        emoji = "✅"
                        status_text = "CONCLUÍDA COM SUCESSO"
                        mention = False  # Sem menção para sucesso
                    elif final_state in ["crashed", "failed"]:
                        emoji = "❌"
                        status_text = "FALHOU"
                        mention = True  # COM MENÇÃO para erros
                    else:
                        emoji = "⚠️"
                        status_text = f"PAROU ({final_state})"
                        mention = True  # COM MENÇÃO para estados inesperados
                    
                    msg = (
                        f"{emoji} **RUN {status_text}**\n"
                        f"📦 Projeto: `{ENTITY}/{data['project']}`\n"
                        f"🏃 Run: `{data['name']}`\n"
                        f"🛑 Estado final: `{final_state}`\n"
                        f"⏱️ Duração: `{format_duration(duration)}`\n"
                        f"⏰ Finalizada: `{datetime.now().strftime('%H:%M:%S')}`"
                    )
                    send_notification(msg, mention=mention)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {emoji} Run parou: {data['name']} - {final_state}")
                    
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ERRO ao buscar estado final: {e}")
                
                # Remove da lista de runs ativas
                del active_runs[run_id]
            
            # Status atual
            if active_runs:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 {len(active_runs)} run(s) ativa(s) sendo monitorada(s)")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Nenhuma run ativa no momento")

        except Exception as e:
            error_msg = f"🚨 ERRO no monitoramento: {e}"
            send_notification(error_msg, mention=True)  # COM MENÇÃO para erros do sistema
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ERRO: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        monitor_projects()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⛔ Monitoramento encerrado pelo usuário")
        monitoring = False