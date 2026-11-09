import os
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional

class RequirementStatus(str, Enum):
    UNCOMPILED = "UNCOMPILED"
    QUESTIONNAIRE_READY = "QUESTIONNAIRE_READY"
    LOCKED = "LOCKED"

class RequirementQuestion(dict):
    """
    Represents a single open requirement question for the consolidated questionnaire.
    """
    def __init__(self, id: str, question: str, description: str, options: List[str], default_option: str):
        super().__init__(
            id=id,
            question=question,
            description=description,
            options=options,
            default_option=default_option
        )

class RequirementCompiler:
    """
    V0.3 Requirement Compiler Engine.
    Inspects the local workspace to resolve known parameters, compiles remaining unknowns
    into a single consolidated questionnaire, and locks requirements prior to task execution.
    """

    def __init__(self):
        self._status: RequirementStatus = RequirementStatus.UNCOMPILED
        self._goal: str = ""
        self._known_requirements: Dict[str, Any] = {}
        self._questions: List[RequirementQuestion] = []
        self._locked_requirements: Dict[str, Any] = {}

    @property
    def status(self) -> RequirementStatus:
        return self._status

    def compile_requirements(self, goal_prompt: str, workspace_path: str = ".") -> Dict[str, Any]:
        """
        Inspects workspace, infers environment parameters, and generates consolidated questionnaire.
        """
        self._goal = goal_prompt
        self._known_requirements = self._inspect_environment(workspace_path)
        self._questions = self._generate_questions(goal_prompt, self._known_requirements)
        self._status = RequirementStatus.QUESTIONNAIRE_READY

        return self.get_state()

    def lock_requirements(self, user_answers: Dict[str, str]) -> Dict[str, Any]:
        """
        Locks user choices into a locked requirement specification.
        """
        if self._status != RequirementStatus.QUESTIONNAIRE_READY and not self._questions:
            # Fallback if locking directly
            self._status = RequirementStatus.QUESTIONNAIRE_READY

        # Combine known auto-detected requirements with user locked answers
        self._locked_requirements = {**self._known_requirements}
        
        for q in self._questions:
            q_id = q["id"]
            selected = user_answers.get(q_id, q["default_option"])
            self._locked_requirements[q_id] = selected

        self._status = RequirementStatus.LOCKED
        return self.get_state()

    def reset(self):
        """Resets requirement compiler to UNCOMPILED state."""
        self._status = RequirementStatus.UNCOMPILED
        self._goal = ""
        self._known_requirements = {}
        self._questions = []
        self._locked_requirements = {}

    def get_state(self) -> Dict[str, Any]:
        """Returns current requirement compiler state."""
        return {
            "status": self._status.value,
            "goal": self._goal,
            "known_requirements": self._known_requirements,
            "questions": self._questions,
            "locked_requirements": self._locked_requirements
        }

    def _inspect_environment(self, workspace_path: str) -> Dict[str, Any]:
        """
        Inspects local workspace directory for project configuration files.
        """
        ws = Path(workspace_path).resolve()
        known = {
            "workspace_root": str(ws),
            "is_git_repository": (ws / ".git").exists(),
        }

        # Detect Python
        if (ws / "requirements.txt").exists() or (ws / "pyproject.toml").exists():
            known["primary_language"] = "Python"
            known["python_framework"] = "FastAPI" if (ws / "backend/main.py").exists() or (ws / "main.py").exists() else "Standard Python"

        # Detect Node/TypeScript/React
        if (ws / "package.json").exists() or (ws / "apps/desktop/package.json").exists():
            known["frontend_framework"] = "React (TypeScript)"
            known["desktop_wrapper"] = "Tauri 2"

        # Detect Rust
        if (ws / "Cargo.toml").exists() or (ws / "apps/desktop/src-tauri/Cargo.toml").exists():
            known["native_language"] = "Rust"

        # Detect Database
        known["database"] = "SQLite (Local)"

        return known

    def _generate_questions(self, goal: str, known: Dict[str, Any]) -> List[RequirementQuestion]:
        """
        Generates open question items tailored to the user's task goal.
        """
        questions = []
        goal_lower = goal.lower()

        # Architecture & Storage
        if "auth" in goal_lower or "user" in goal_lower or "login" in goal_lower:
            questions.append(RequirementQuestion(
                id="auth_method",
                question="Preferred Authentication Method?",
                description="Choose the primary authentication tokens or session strategy.",
                options=["JWT Bearer Tokens", "Session Cookies", "OAuth2 / OIDC"],
                default_option="JWT Bearer Tokens"
            ))

        if "db" in goal_lower or "database" in goal_lower or "store" in goal_lower or "data" in goal_lower:
            questions.append(RequirementQuestion(
                id="database_engine",
                question="Database Engine Selection?",
                description="Specify local vs relational database backend.",
                options=["SQLite (Local File)", "PostgreSQL", "In-Memory Dict"],
                default_option="SQLite (Local File)"
            ))

        # Default task configuration questions if no specific domain matched
        if not questions:
            questions.append(RequirementQuestion(
                id="execution_mode",
                question="Task Execution Autonomy Level?",
                description="Select whether Johnny executes changes automatically or requests confirmation per step.",
                options=["Autonomous (Lock & Run)", "Step-by-Step Confirmation", "Dry-Run Only"],
                default_option="Autonomous (Lock & Run)"
            ))
            questions.append(RequirementQuestion(
                id="verification_strategy",
                question="Automated Verification Strategy?",
                description="Choose how completed changes should be verified.",
                options=["Run Unit Test Suite (Pytest/NPM)", "Lint & Type Check Only", "Manual Inspection"],
                default_option="Run Unit Test Suite (Pytest/NPM)"
            ))

        return questions

# Global singleton compiler instance
requirement_compiler = RequirementCompiler()
