import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from enhancement_core.codex.options import CodexOptions
from enhancement_core.config import HostBridgeSettings

logger = logging.getLogger(__name__)


class CodexRunnerError(RuntimeError):
    def __init__(
        self,
        message: str,
        run_id: str | None = None,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        log_path: str | None = None,
    ):
        super().__init__(message)
        self.run_id = run_id
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.log_path = log_path


class CodexRunner:
    def __init__(self, settings: HostBridgeSettings | None = None):
        base_dir = Path(__file__).resolve().parents[3]
        self.settings = settings or HostBridgeSettings()
        self.repo_path = self.settings.next_path
        self.prompt_prefix = self.settings.prompt_prefix.strip()
        self.codex_bin = self.settings.codex_bin
        logs_root = self.settings.logs_root
        self.logs_root = logs_root if logs_root.is_absolute() else base_dir / logs_root
        self.exec_timeout = float(self.settings.codex_timeout_seconds)
        try:
            self.logs_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CodexRunnerError("Unable to prepare codex log directory") from exc

    def ensure_repo(self) -> Path:
        if not self.repo_path.exists():
            raise CodexRunnerError("Target repository path does not exist")
        if not self.repo_path.is_dir():
            raise CodexRunnerError("Target repository path is not a directory")
        return self.repo_path

    def resolve_binary(self) -> str:
        candidate = shutil.which(self.codex_bin)
        if not candidate:
            raise CodexRunnerError("Codex binary not found on PATH")
        return candidate

    def build_prompt(self, feedback: str) -> str:
        body = feedback.strip()
        if not body:
            raise CodexRunnerError("Feedback is empty")
        return f"{self.prompt_prefix}\n\nFeedback:\n{body}"

    def run(self, feedback: str, *, codex_options: CodexOptions | None = None) -> dict[str, str | int]:
        repo = self.ensure_repo()
        binary = self.resolve_binary()
        prompt = self.build_prompt(feedback)
        run_id = str(uuid.uuid4())
        log_dir, created_at = self._prepare_log_dir(run_id)
        command = [binary, "exec", "--skip-git-repo-check", "--cd", str(repo)]
        if codex_options:
            command.extend(codex_options.as_command_args())
        command.append(prompt)
        print("🔧 Running Codex to apply changes...")

        # Use Popen instead of run for better process control
        process = None
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid  # Create new process group for better signal handling
            )

            try:
                # Wait for process to complete with timeout to allow for interrupts
                stdout, stderr = process.communicate(timeout=self.exec_timeout)
            except subprocess.TimeoutExpired:
                print("\n⏰ Codex process timed out, terminating...")
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                raise CodexRunnerError("Codex process timed out")

        except KeyboardInterrupt:
            # If user interrupts with Ctrl+C, kill the entire process group
            print("\n🛑 Received interrupt signal, terminating Codex process...")
            if process and process.poll() is None:  # Process is still running
                try:
                    # Kill the process group to ensure all child processes are terminated
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    # Give it a moment to terminate gracefully, then force kill if needed
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass  # Process already exited
            raise
        except FileNotFoundError as exc:
            raise CodexRunnerError("Codex executable missing") from exc
        self._persist_logs(
            log_dir=log_dir,
            command=command,
            prompt=prompt,
            stdout=stdout,
            stderr=stderr,
            exit_code=process.returncode,
            created_at=created_at,
            run_id=run_id,
            codex_options=codex_options,
        )
        if process.returncode != 0:
            print(f"❌ Codex run failed with exit code {process.returncode}")
            raise CodexRunnerError(
                "Codex run failed",
                run_id=run_id,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                log_path=str(log_dir),
            )
        print("✨ Codex completed successfully!")
        return {
            "run_id": run_id,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": process.returncode,
            "log_path": str(log_dir),
        }

    def _prepare_log_dir(self, run_id: str) -> tuple[Path, str]:
        timestamp = datetime.now(timezone.utc)
        folder = timestamp.strftime("%Y%m%d-%H%M%S-%f")
        path = self.logs_root / f"{folder}-{run_id}"
        try:
            path.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise CodexRunnerError("Unable to create codex log directory", log_path=str(path)) from exc
        return path, timestamp.isoformat()

    def _persist_logs(
        self,
        *,
        log_dir: Path,
        command: list[str],
        prompt: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        created_at: str,
        run_id: str,
        codex_options: CodexOptions | None = None,
    ) -> None:
        try:
            (log_dir / "prompt.txt").write_text(prompt)
            (log_dir / "command.txt").write_text(shlex.join(command))
            (log_dir / "stdout.log").write_text(stdout or "")
            (log_dir / "stderr.log").write_text(stderr or "")
            metadata = {
                "run_id": run_id,
                "created_at": created_at,
                "exit_code": exit_code,
                "command": command,
            }
            if codex_options:
                metadata["codex_options"] = codex_options.model_dump(exclude_none=True)
            (log_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        except OSError as exc:
            raise CodexRunnerError("Unable to persist codex logs", log_path=str(log_dir)) from exc


__all__ = ["CodexRunner", "CodexRunnerError"]
