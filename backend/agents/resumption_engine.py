from typing import List, Dict, Any, Optional
from backend.core.task_store import task_store, TaskPersistenceStore
from backend.agents.task_engine import task_engine, AutonomousTaskEngine

class CrashResumptionEngine:
    """
    V0.7 Crash Resumption Engine.
    Scans for interrupted or uncompleted task checkpoints on system startup or on-demand,
    re-hydrates Task Engine state, and resumes execution seamlessly.
    """

    def __init__(
        self,
        store: Optional[TaskPersistenceStore] = None,
        engine: Optional[AutonomousTaskEngine] = None
    ):
        self.store = store or task_store
        self.engine = engine or task_engine

    def detect_interrupted_tasks(self) -> List[Dict[str, Any]]:
        """
        Scans disk store for interrupted task state checkpoints.
        """
        return self.store.list_interrupted_tasks()

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """
        Loads saved checkpoint for task_id, restores task in task_engine, and resumes execution.
        """
        checkpoint = self.store.load_checkpoint(task_id)
        if not checkpoint:
            raise ValueError(f"No checkpoint file found for task ID '{task_id}'.")

        task = self.engine.restore_task(checkpoint)
        task.add_log(f"⚡ CrashResumptionEngine: Resuming task '{task_id}' from disk checkpoint.")
        self.store.save_checkpoint(task.id, task.to_dict())

        # Continue execution
        return self.engine.execute_task(task.id)

# Global Crash Resumption Engine instance
resumption_engine = CrashResumptionEngine()
