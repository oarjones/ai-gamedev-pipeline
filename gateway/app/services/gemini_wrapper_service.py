"""Service for interacting with the Gemini CLI wrapper that maintains context.

This service provides a stateful alternative to one-shot requests by using
the Node.js wrapper that can maintain conversation context across requests.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, AsyncGenerator
from uuid import uuid4

logger = logging.getLogger(__name__)


# Adapter class to make subprocess.Popen compatible with asyncio.subprocess.Process
class _PopenAdapter:
    def __init__(self, pop: subprocess.Popen):
        self._p = pop

    @property
    def stdin(self):
        return self._p.stdin

    @property
    def stdout(self):
        return self._p.stdout

    @property
    def stderr(self):
        return self._p.stderr

    @property
    def returncode(self) -> Optional[int]:
        return self._p.poll()

    def terminate(self) -> None:
        try:
            self._p.terminate()
        except Exception:
            pass

    async def wait(self) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._p.wait)


class GeminiWrapperService:
    def __init__(self):
        self._sessions: dict[str, asyncio.subprocess.Process | _PopenAdapter] = {}
        self._wrapper_path = Path("gateway/wrapper/gemini-wrapper.js")
        self._session_histories: dict[str, list[str]] = {}

    def _get_wrapper_path(self) -> Path:
        """
        Obtiene la ruta absoluta al archivo gemini-wrapper.js.
        """
        script_dir = Path(__file__).parent.parent
        project_root = script_dir.parent
        wrapper_path = project_root / "wrapper" / "gemini-wrapper.js"
    
        if not wrapper_path.is_file():
            raise FileNotFoundError(
                f"No se encontró gemini-wrapper.js. Se buscó en: {wrapper_path.resolve()}"
            )
    
        return wrapper_path

    async def send_message(self, project_id: str, message: str) -> AsyncGenerator[str, None]:
        """Sends a message to the Gemini wrapper and yields response chunks."""
        try:
            if project_id not in self._sessions:
                logger.info(f"Starting new Gemini wrapper session for project {project_id}")
                wrapper_path = self._get_wrapper_path()
                try:
                    process = await asyncio.create_subprocess_exec(
                        "node",
                        str(wrapper_path),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                except NotImplementedError:
                    # Fallback for Windows environments where the default event loop doesn't support subprocesses.
                    logger.warning("asyncio.create_subprocess_exec not implemented, falling back to subprocess.Popen")
                    p = subprocess.Popen(
                        ["node", str(wrapper_path)],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    process = _PopenAdapter(p)

                self._sessions[project_id] = process
                self._session_histories.setdefault(project_id, [])

            process = self._sessions[project_id]

            if process.returncode is not None:
                logger.error(f"Gemini wrapper for {project_id} has terminated. Restarting.")
                self.cleanup_session(project_id)
                yield "Error: Conversation session terminated. Please try sending your message again."
                return

            if not process.stdin:
                raise RuntimeError("Process stdin is not available.")

            logger.info(f"Sending message to wrapper for project {project_id}: {message[:80]}...")
            process.stdin.write(message.encode('utf-8') + b'\n')
            # Handle stream flushing differently for Popen vs asyncio process
            if isinstance(process, _PopenAdapter):
                process.stdin.flush() # Sync flush
            else:
                await process.stdin.drain() # Async drain

            self._session_histories[project_id].append(f"user: {message}")

            response_parts = []

            # Concurrently drain stderr to prevent deadlocks
            async def log_stderr():
                if not process.stderr:
                    return
                while True:
                    try:
                        # For Popen, readline is sync, so we need to be careful
                        if isinstance(process, _PopenAdapter):
                            await asyncio.sleep(0.1) # Prevent tight loop
                            line = process.stderr.readline()
                        else:
                            line = await process.stderr.readline()
                        
                        if not line:
                            break
                        logger.warning(f"[gemini-wrapper.js] {line.decode('utf-8', 'replace').strip()}")
                    except (asyncio.CancelledError, ValueError, AttributeError):
                        break

            stderr_task = asyncio.create_task(log_stderr())

            # Read from stdout and yield response chunks
            if not process.stdout:
                raise RuntimeError("Process stdout is not available.")
            while True:
                try:
                    # For Popen, readline is sync
                    if isinstance(process, _PopenAdapter):
                        await asyncio.sleep(0.1) # Prevent tight loop
                        line_bytes = process.stdout.readline()
                    else:
                        line_bytes = await process.stdout.readline()

                    if not line_bytes:
                        break

                    line = line_bytes.decode('utf-8', 'replace').strip()

                    if line == '[END_RESPONSE]':
                        break

                    if line and not line.startswith(('[DEBUG]', '[GEMINI_STDERR]', '=== PROMPT', '[INPUT]', '[RESPONSE]')):
                        response_parts.append(line)
                        yield line
                except (asyncio.CancelledError, ValueError, AttributeError):
                    break
            
            stderr_task.cancel()
            try:
                await stderr_task
            except asyncio.CancelledError:
                pass

            if process.returncode is not None:
                 logger.error(f"Wrapper process for {project_id} terminated unexpectedly with code {process.returncode}.")
                 self.cleanup_session(project_id)

            full_response = "\n".join(response_parts)
            if full_response:
                self._session_histories[project_id].append(f"assistant: {full_response}")
                logger.info(f"Received response for project {project_id}: {full_response[:100]}...")

        except BrokenPipeError:
            logger.error(f"Broken pipe for project {project_id}. The wrapper process may have crashed.")
            self.cleanup_session(project_id)
            yield "Error: The connection to the conversation service was lost. Please try again."
        except Exception as e:
            logger.error(f"Error in send_message for project {project_id}: {e}", exc_info=True)
            yield f"Error: An unexpected error occurred: {e}"

    async def send_message_complete(self, project_id: str, message: str) -> str:
        """Send a message and return the complete response as a single string."""
        response_parts = []
        async for chunk in self.send_message(project_id, message):
            response_parts.append(chunk)
        return "\n".join(response_parts)

    def cleanup_session(self, project_id: str):
        """Clean up any resources for a project session."""
        if project_id in self._sessions:
            try:
                process = self._sessions[project_id]
                if hasattr(process, 'terminate'):
                    process.terminate()
                del self._sessions[project_id]
            except Exception as e:
                logger.error(f"Error cleaning up session {project_id}: {e}")

        if project_id in self._session_histories:
            del self._session_histories[project_id]

    def clear_conversation_history(self, project_id: str):
        """Clear the conversation history for a project."""
        if project_id in self._session_histories:
            del self._session_histories[project_id]
            logger.info(f"Cleared conversation history for project {project_id}")

    def get_conversation_history(self, project_id: str) -> list[str]:
        """Get the conversation history for a project."""
        return self._session_histories.get(project_id, []).copy()


# Singleton instance
gemini_wrapper_service = GeminiWrapperService()