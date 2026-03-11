import asyncio
import json
from common_classes import MyDeps, ParameterResult
from secretKeys import SILICONFLOW_BASE_URL, SILICONFLOW_MODEL, SILICONFLOW_API_KEY, OPENROUTER_STRUCTURED_MODELS, OPENROUTER_API_KEY
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

class ParameterTuningAgent:
    def __init__(self, performance_to_tuning_queue: asyncio.Queue, tuning_to_performance_queue: asyncio.Queue):
        self.performance_to_tuning_queue = performance_to_tuning_queue
        self.tuning_to_performance_queue = tuning_to_performance_queue
        
        self.sys_prompt = (
            "You are a parameter tuning agent. Based on network conditions, previous analysis, and historical data, "
            "set optimal capture duration (30-40 seconds) and cycle interval (5-30 seconds). "
            "Guidelines: Increase duration and decrease interval if attacks are frequent or latency is high; "
            "otherwise, decrease duration and increase interval. "
            "Return only strict JSON: {\"duration\": int, \"interval\": int}."
        )
        self.client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)
        self.structured_models = OPENROUTER_STRUCTURED_MODELS

    def _clamp_int(self, value: int, low: int, high: int) -> int:
        return max(low, min(high, int(value)))

    def _fallback_tuning(self, avg_latency: float | None, avg_loss: float | None, previous_attack_detected: bool, num_attacks: int) -> MyDeps:
        """Local deterministic fallback when LLM tuning fails."""
        high_risk = (
            previous_attack_detected
            or num_attacks >= 2
            or (avg_latency is not None and avg_latency > 150)
            or (avg_loss is not None and avg_loss > 5)
        )

        if high_risk:
            duration = 35
            cycle_interval = 8
        else:
            duration = 20
            cycle_interval = 18

        return MyDeps(
            duration=self._clamp_int(duration, 30, 40),
            cycle_interval=self._clamp_int(cycle_interval, 5, 30),
        )

    def _llm_tune_once(self, prompt: str) -> ParameterResult:
        last_error = None
        for model_name in self.structured_models:
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": self.sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                content = (response.choices[0].message.content or "").strip()
                payload = json.loads(content)
                logger.info("[TUNE] Structured model succeeded: %s", model_name)
                return ParameterResult(duration=int(payload["duration"]), interval=int(payload["interval"]))
            except Exception as exc:
                last_error = exc
                logger.warning("[TUNE] Structured model failed (%s): %s", model_name, exc)
                continue

        raise RuntimeError(f"All structured tuning models failed: {last_error}")

    async def run(self) -> None:
        """Adjust monitoring parameters based on current and historical network conditions."""
        while True:
            data = await self.performance_to_tuning_queue.get()
            try:
                metrics = data["metrics"]
                previous_attack_detected = data["previous_attack_detected"]
                recent_history = data.get("recent_history", [])

                avg_latency_current = metrics.get("aggregates", {}).get("avg_latency")
                avg_loss_current = metrics.get("aggregates", {}).get("avg_loss")

                if recent_history:
                    latencies = [entry["avg_latency"] for entry in recent_history if entry["avg_latency"] is not None]
                    attacks = [entry["attack_detected"] for entry in recent_history if entry["attack_detected"] is not None]
                    avg_latency_history = sum(latencies) / len(latencies) if latencies else None
                    num_attacks = sum(1 for attack in attacks if attack)
                else:
                    avg_latency_history = None
                    num_attacks = 0

                prompt = (
                    f"Tune parameters based on current network conditions, previous analysis, and historical data. "
                    f"Current average latency: {avg_latency_current} ms, "
                    f"current packet loss: {avg_loss_current} %, "
                    f"previous attack detected: {previous_attack_detected}, "
                    f"number of attacks in last 10 cycles: {num_attacks}, "
                    f"average latency in last 10 cycles: {avg_latency_history or 'N/A'} ms."
                )

                try:
                    if not OPENROUTER_API_KEY:
                        raise ValueError("OPENROUTER_API_KEY is not set")

                    param_result = await asyncio.to_thread(self._llm_tune_once, prompt)
                    duration = self._clamp_int(param_result.duration, 30, 40)
                    cycle_interval = self._clamp_int(param_result.interval, 5, 30)
                    updated_deps = MyDeps(duration=duration, cycle_interval=cycle_interval)
                    logger.info(
                        "[TUNE] LLM tuning success: duration=%ss cycle_interval=%ss",
                        duration,
                        cycle_interval,
                    )
                except Exception as llm_error:
                    logger.warning(
                        "[TUNE] LLM tuning failed (%s). Falling back to local heuristic tuning.",
                        llm_error,
                    )
                    updated_deps = self._fallback_tuning(
                        avg_latency=avg_latency_current,
                        avg_loss=avg_loss_current,
                        previous_attack_detected=previous_attack_detected,
                        num_attacks=num_attacks,
                    )
                    logger.info(
                        "[TUNE] Fallback tuning result: duration=%ss cycle_interval=%ss",
                        updated_deps.duration,
                        updated_deps.cycle_interval,
                    )

                await self.tuning_to_performance_queue.put(updated_deps)
            except Exception as run_error:
                logger.error("[TUNE] Unexpected error in tuning loop: %s", run_error)
                # Keep pipeline moving with safe defaults instead of killing the task.
                await self.tuning_to_performance_queue.put(MyDeps(duration=30, cycle_interval=10))