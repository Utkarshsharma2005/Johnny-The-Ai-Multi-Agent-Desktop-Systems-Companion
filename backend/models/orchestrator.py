import time
import asyncio
from collections import deque
from typing import List, Dict, Any, Optional, Deque
from backend.models.base import ModelProvider
from backend.models.router import router_instance
from backend.core.config import settings
from backend.core.evidence_merger import (
    EvidenceMerger, ModelOpinion, MergedEvidenceReport, calibrate_confidence
)

# Bounded history to prevent RAM growth in long sessions
_MAX_HISTORY = 100

class MultimodelOrchestrator:
    """
    Multimodel Orchestration Engine for ensemble, cascade, and multimodal fusion deliberation.
    """

    def __init__(self, provider: Optional[ModelProvider] = None):
        self.provider = provider or router_instance.get_provider()
        # Use a bounded deque to cap RAM usage in long-running sessions
        self.history: Deque[MergedEvidenceReport] = deque(maxlen=_MAX_HISTORY)

    async def deliberate(
        self,
        query: str,
        strategy: str = "ensemble",
        models: Optional[List[str]] = None,
        image_path: Optional[str] = None,
        history: Optional[List[dict]] = None,
    ) -> MergedEvidenceReport:
        """
        Executes multi-model deliberation using specified strategy ('ensemble', 'cascade', 'multimodal_fusion').
        """
        strategy_clean = strategy.lower().strip()

        if strategy_clean == "cascade":
            report = await self._deliberate_cascade(query, models, history=history)
        elif strategy_clean == "multimodal_fusion" or image_path is not None:
            report = await self._deliberate_multimodal_fusion(query, image_path, models, history=history)
        else:
            report = await self._deliberate_ensemble(query, models, history=history)

        self.history.append(report)
        return report

    async def _deliberate_ensemble(
        self,
        query: str,
        models: Optional[List[str]] = None,
        history: Optional[List[dict]] = None,
    ) -> MergedEvidenceReport:
        """
        Dispatches prompt concurrently across selected model ensemble using asyncio.gather.
        """
        target_models = models or [
            settings.LLAMA_MODEL_ID,
            settings.DEEPSEEK_MODEL_ID,
            settings.NEMOTRON_MODEL_ID
        ]

        async def query_model(model_id: str) -> ModelOpinion:
            start = time.perf_counter()
            try:
                raw_res = await self.provider.generate(query, model_id=model_id, history=history)
                elapsed = (time.perf_counter() - start) * 1000.0
                assertions = EvidenceMerger.parse_assertions(raw_res)
                return ModelOpinion(
                    model_id=model_id,
                    raw_output=raw_res,
                    confidence=calibrate_confidence(raw_res),
                    key_assertions=assertions,
                    execution_time_ms=round(elapsed, 2),
                )
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000.0
                return ModelOpinion(
                    model_id=model_id,
                    raw_output=f"[FAILED] {str(e)}",
                    confidence=0.0,
                    key_assertions=[],
                    execution_time_ms=round(elapsed, 2),
                )

        opinions = await asyncio.gather(*[query_model(m) for m in target_models])
        return EvidenceMerger.merge_opinions(query, "ensemble", list(opinions))

    async def _deliberate_cascade(
        self,
        query: str,
        models: Optional[List[str]] = None,
        history: Optional[List[dict]] = None,
    ) -> MergedEvidenceReport:
        """
        Evaluates primary model first; if confidence/verification criteria require, escalates to secondary model.
        """
        primary_model = (models and models[0]) or settings.LLAMA_MODEL_ID
        secondary_model = (models and len(models) > 1 and models[1]) or settings.DEEPSEEK_MODEL_ID

        opinions: List[ModelOpinion] = []

        start = time.perf_counter()
        primary_res = await self.provider.generate(query, model_id=primary_model, history=history)
        elapsed = (time.perf_counter() - start) * 1000.0
        primary_op = ModelOpinion(
            model_id=primary_model,
            raw_output=primary_res,
            confidence=calibrate_confidence(primary_res),
            key_assertions=EvidenceMerger.parse_assertions(primary_res),
            execution_time_ms=round(elapsed, 2),
        )
        opinions.append(primary_op)

        needs_escalation = any(k in query.lower() for k in ["code", "debug", "verify", "complex", "review", "fix", "error"])
        if needs_escalation:
            # BUGFIX (hardening): pass the full conversation history to the
            # escalation call so the secondary model has the same context.
            escalated_query = (
                f"Original query: '{query}'\n"
                f"Primary model ({primary_model}) response: '{primary_res}'\n"
                "Please review and provide specialized analysis."
            )
            start_sec = time.perf_counter()
            sec_res = await self.provider.generate(
                escalated_query, model_id=secondary_model, history=history
            )
            elapsed_sec = (time.perf_counter() - start_sec) * 1000.0
            sec_op = ModelOpinion(
                model_id=secondary_model,
                raw_output=sec_res,
                confidence=calibrate_confidence(sec_res),
                key_assertions=EvidenceMerger.parse_assertions(sec_res),
                execution_time_ms=round(elapsed_sec, 2),
            )
            opinions.append(sec_op)

        return EvidenceMerger.merge_opinions(query, "cascade", opinions)

    async def _deliberate_multimodal_fusion(
        self,
        query: str,
        image_path: Optional[str] = None,
        models: Optional[List[str]] = None,
        history: Optional[List[dict]] = None,
    ) -> MergedEvidenceReport:
        """
        Fuses visual perception evidence (MiniMax M3) with text reasoning models (Llama 3.3 / DeepSeek R1).
        """
        vision_model = settings.MINIMAX_MODEL_ID
        text_model = (models and models[0]) or settings.LLAMA_MODEL_ID

        opinions: List[ModelOpinion] = []

        # 1. Vision model execution
        if image_path:
            start_vis = time.perf_counter()
            try:
                vis_res = await self.provider.analyze_image(image_path, query, model_id=vision_model)
                elapsed_vis = (time.perf_counter() - start_vis) * 1000.0
                raw_text = vis_res.get("analysis_raw") or str(vis_res.get("analysis", vis_res))
                if isinstance(raw_text, dict):
                    raw_text = f"Summary: {raw_text.get('summary', '')} Objects: {', '.join(raw_text.get('objects_detected', []))}"
                
                opinions.append(ModelOpinion(
                    model_id=vision_model,
                    raw_output=str(raw_text),
                    confidence=0.90,
                    key_assertions=EvidenceMerger.parse_assertions(str(raw_text)),
                    execution_time_ms=round(elapsed_vis, 2)
                ))
            except Exception as e:
                opinions.append(ModelOpinion(
                    model_id=vision_model,
                    raw_output=f"Vision inspection failed: {str(e)}",
                    confidence=0.0,
                    key_assertions=[],
                    execution_time_ms=0.0
                ))

        # 2. Text reasoning model with conversation history
        start_txt = time.perf_counter()
        txt_res = await self.provider.generate(query, model_id=text_model, history=history)
        elapsed_txt = (time.perf_counter() - start_txt) * 1000.0
        opinions.append(ModelOpinion(
            model_id=text_model,
            raw_output=txt_res,
            confidence=calibrate_confidence(txt_res),
            key_assertions=EvidenceMerger.parse_assertions(txt_res),
            execution_time_ms=round(elapsed_txt, 2),
        ))

        return EvidenceMerger.merge_opinions(query, "multimodal_fusion", opinions)

    def get_history(self) -> List[MergedEvidenceReport]:
        """Returns deliberation history as a list (bounded by _MAX_HISTORY items)."""
        return list(self.history)

# Global orchestrator — lazy singleton pattern avoids import-time side effects
_orchestrator_instance: Optional[MultimodelOrchestrator] = None


def get_orchestrator() -> MultimodelOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = MultimodelOrchestrator()
    return _orchestrator_instance


# Backward-compat alias: always access via get_orchestrator() to ensure lazy init
# Direct attribute access kept for import compatibility but delegates to the lazy getter
class _OrchestratorProxy:
    """Thin proxy that defers MultimodelOrchestrator construction until first use."""
    def __getattr__(self, name: str):
        return getattr(get_orchestrator(), name)

multimodel_orchestrator = _OrchestratorProxy()
