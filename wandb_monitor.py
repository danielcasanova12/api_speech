from dataclasses import dataclass
from datetime import datetime
import os
import time
from typing import Any


@dataclass(frozen=True)
class MonitorConfig:
    api_key: str
    entity: str
    discord_webhook_url: str
    check_interval_seconds: int = 15
    discord_tag: str = "@here"


def load_config_from_environment() -> MonitorConfig:
    """Load monitor settings without authenticating or performing network I/O."""
    required_variables = {
        "WANDB_API_KEY": os.getenv("WANDB_API_KEY", "").strip(),
        "WANDB_ENTITY": os.getenv("WANDB_ENTITY", "").strip(),
        "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
    }
    missing = [name for name, value in required_variables.items() if not value]
    if missing:
        raise ValueError(
            "Missing required monitor environment variables: "
            + ", ".join(sorted(missing))
        )

    interval_value = os.getenv("WANDB_MONITOR_INTERVAL_SECONDS", "15")
    try:
        check_interval_seconds = int(interval_value)
    except ValueError as exc:
        raise ValueError(
            "WANDB_MONITOR_INTERVAL_SECONDS must be an integer."
        ) from exc
    if check_interval_seconds <= 0:
        raise ValueError("WANDB_MONITOR_INTERVAL_SECONDS must be greater than zero.")

    return MonitorConfig(
        api_key=required_variables["WANDB_API_KEY"],
        entity=required_variables["WANDB_ENTITY"],
        discord_webhook_url=required_variables["DISCORD_WEBHOOK_URL"],
        check_interval_seconds=check_interval_seconds,
        discord_tag=os.getenv("DISCORD_TAG", "@here"),
    )


def create_wandb_api(config: MonitorConfig) -> Any:
    """Authenticate only when the monitor is explicitly started."""
    try:
        import wandb
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Monitor dependencies are missing. Install requirements-monitor.txt."
        ) from exc

    wandb.login(key=config.api_key)
    return wandb.Api()


def send_notification(
    config: MonitorConfig,
    message: str,
    mention: bool = False,
) -> None:
    try:
        import requests

        content = f"{config.discord_tag} {message}" if mention else message
        response = requests.post(
            config.discord_webhook_url,
            json={"content": content},
            timeout=10,
        )
        response.raise_for_status()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Alerta enviado para Discord")
    except Exception as exc:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ERRO Discord: {exc}")


def format_duration(seconds: float) -> str:
    """Format a duration in a compact human-readable form."""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}min"

    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    return f"{hours}h {minutes}min"


def monitor_projects(api: Any, config: MonitorConfig) -> None:
    active_runs: dict[str, dict[str, Any]] = {}

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoramento iniciado")
    print(f"[INFO] Verificando a cada {config.check_interval_seconds} segundos")
    print(f"[INFO] Entity: {config.entity}\n")

    while True:
        try:
            current_active: set[str] = set()

            for project in api.projects(config.entity):
                project_name = project.name
                for run in api.runs(f"{config.entity}/{project_name}"):
                    if run.state != "running":
                        continue

                    current_active.add(run.id)
                    if run.id in active_runs:
                        continue

                    active_runs[run.id] = {
                        "project": project_name,
                        "name": run.name,
                        "started_at": datetime.now(),
                    }
                    message = (
                        "**NOVA RUN INICIADA**\n"
                        f"Projeto: `{config.entity}/{project_name}`\n"
                        f"Run: `{run.name}`\n"
                        f"Horário: `{datetime.now().strftime('%H:%M:%S')}`"
                    )
                    send_notification(config, message)
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Nova run: {run.name} ({project_name})"
                    )

            stopped_runs = set(active_runs) - current_active
            for run_id in stopped_runs:
                data = active_runs[run_id]
                try:
                    run = api.run(
                        f"{config.entity}/{data['project']}/{run_id}"
                    )
                    final_state = run.state
                    duration = (
                        datetime.now() - data["started_at"]
                    ).total_seconds()

                    if final_state == "finished":
                        status_text = "CONCLUÍDA COM SUCESSO"
                        mention = False
                    elif final_state in {"crashed", "failed"}:
                        status_text = "FALHOU"
                        mention = True
                    else:
                        status_text = f"PAROU ({final_state})"
                        mention = True

                    message = (
                        f"**RUN {status_text}**\n"
                        f"Projeto: `{config.entity}/{data['project']}`\n"
                        f"Run: `{data['name']}`\n"
                        f"Estado final: `{final_state}`\n"
                        f"Duração: `{format_duration(duration)}`\n"
                        f"Finalizada: `{datetime.now().strftime('%H:%M:%S')}`"
                    )
                    send_notification(config, message, mention=mention)
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Run parou: {data['name']} - {final_state}"
                    )
                except Exception as exc:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"ERRO ao buscar estado final: {exc}"
                    )
                finally:
                    del active_runs[run_id]

            if active_runs:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"{len(active_runs)} run(s) ativa(s) sendo monitorada(s)"
                )
            else:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    "Nenhuma run ativa no momento"
                )
        except Exception as exc:
            error_message = f"ERRO no monitoramento: {exc}"
            send_notification(config, error_message, mention=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {error_message}")

        time.sleep(config.check_interval_seconds)


def main() -> None:
    config = load_config_from_environment()
    api = create_wandb_api(config)
    monitor_projects(api, config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Monitoramento encerrado")
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(f"Erro de configuração: {exc}") from exc
