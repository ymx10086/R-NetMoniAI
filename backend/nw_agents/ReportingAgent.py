import logging
import asyncio
import json
from collections import deque
logger = logging.getLogger(__name__)

from openai import OpenAI
from common_classes import NetworkReport, MyDeps, AnalysisResult
from secretKeys import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_STRUCTURED_MODELS
import time

sys_prompt = """
You are a network analysis reporting agent. Generate comprehensive reports on network anomalies 
and security incidents using attack detection data and raw BERT model output. For each report:

1. Analyze attack data, raw BERT model output (attack type counts), and network metrics to identify patterns and anomalies
2. Determine the type and severity of any detected attacks based on BERT classifications
3. Recommend specific mitigation actions with clear priorities, tailored to identified attack types
4. Suggest further investigation steps when appropriate
5. Create concise but thorough summaries suitable for both technical and non-technical readers

Be specific and actionable in your recommendations. Include command suggestions when appropriate.
Include a confidence level based on the clarity of the evidence and the volume of attack traffic in the BERT output.
Return only JSON using these keys:
report_id, timestamp, summary, attack_detected, attack_type, confidence,
metrics_summary, anomalies_detected, potential_causes, recommended_actions, further_investigation
"""

report_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
report_models = OPENROUTER_STRUCTURED_MODELS


def _normalize_confidence(value, default: float = 0.5) -> float:
    """Normalize confidence values from LLM output into a float in [0.0, 1.0]."""
    if value is None:
        return default

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1.0:
            numeric /= 100.0
        return max(0.0, min(1.0, numeric))

    if isinstance(value, str):
        normalized = value.strip().lower()
        label_map = {
            "very high": 0.95,
            "high": 0.85,
            "medium": 0.65,
            "moderate": 0.65,
            "low": 0.35,
            "very low": 0.15,
        }
        if normalized in label_map:
            return label_map[normalized]

        if normalized.endswith("%"):
            normalized = normalized[:-1].strip()

        try:
            numeric = float(normalized)
            if numeric > 1.0:
                numeric /= 100.0
            return max(0.0, min(1.0, numeric))
        except ValueError:
            return default

    return default


def _normalize_bool(value, default: bool = False) -> bool:
    """Normalize flexible boolean values from LLM output."""
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "detected"}:
            return True
        if normalized in {"false", "0", "no", "n", "none", "normal"}:
            return False

    return default


def _build_fallback_report(analysis_result: AnalysisResult, avg_latency: float = None, avg_loss: float = None, cause: str = None) -> NetworkReport:
    """Create a local deterministic report when LLM report generation is unavailable."""
    is_dict = isinstance(analysis_result, dict)
    attack_detected = analysis_result.get("attack_detected", False) if is_dict else analysis_result.attack_detected
    details = analysis_result.get("details", "") if is_dict else (analysis_result.details or "")
    raw_bert_output = analysis_result.get("raw_bert_output", {}) if is_dict else getattr(analysis_result, "raw_bert_output", {})

    top_attack = None
    top_count = 0
    for label, count in raw_bert_output.items() if isinstance(raw_bert_output, dict) else []:
        if label != "Normal" and isinstance(count, (int, float)) and count > top_count:
            top_attack = label
            top_count = count

    latency_val = avg_latency if avg_latency is not None else 0.0
    loss_val = avg_loss if avg_loss is not None else 0.0
    confidence = 0.8 if attack_detected else 0.6

    summary = "Potential malicious activity detected." if attack_detected else "No clear attack signal was detected in the latest capture window."
    if cause:
        summary += f" (LLM fallback mode: {cause})"

    return NetworkReport(
        report_id=f"NR-LOCAL-{int(time.time())}",
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        summary=summary,
        attack_detected=attack_detected,
        attack_type=top_attack,
        confidence=confidence,
        metrics_summary=f"Latency: {latency_val}ms, Loss: {loss_val}%",
        anomalies_detected=details or "No explicit anomaly details available.",
        potential_causes="Traffic pattern drift and/or transient network instability.",
        recommended_actions=(
            "Validate source/destination hot spots, inspect top talkers, and compare with baseline traffic. "
            "If recurrence continues, isolate suspicious hosts and apply rate limiting."
        ),
        further_investigation="Correlate with endpoint and firewall logs; run deeper PCAP protocol breakdown."
    )

async def generate_network_report(analysis_result: AnalysisResult, pcap_path: str, 
                                 duration: int, cycle_interval: int, 
                                 avg_latency: float = None, avg_loss: float = None) -> NetworkReport:
    try:
        raw_bert_output = analysis_result.get('raw_bert_output', {}) if isinstance(analysis_result, dict) else getattr(analysis_result, 'raw_bert_output', {})
        logger.info(
            "[REPORT] Generating report from analysis: pcap=%s attack_detected=%s",
            pcap_path,
            analysis_result['attack_detected'] if isinstance(analysis_result, dict) else analysis_result.attack_detected,
        )
        prompt = (
            f"Generate a comprehensive report based on the following data:\n"
            f"- Attack detection result: {analysis_result['attack_detected'] if isinstance(analysis_result, dict) else analysis_result.attack_detected}\n"
            f"- Detection details: {analysis_result['details'] if isinstance(analysis_result, dict) else analysis_result.details}\n"
            f"- Raw BERT model output (attack type counts): {raw_bert_output}\n"
            f"- Network metrics: Latency={avg_latency}ms, Loss={avg_loss}%, Duration={duration}s, Interval={cycle_interval}s\n"
            f"Use the raw BERT output to identify specific attack types and their severity."
        )

        response = None
        last_error = None
        for model_name in report_models:
            try:
                response = await asyncio.to_thread(
                    report_client.chat.completions.create,
                    model=model_name,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                logger.info("[REPORT] Structured model succeeded: %s", model_name)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("[REPORT] Structured model failed (%s): %s", model_name, exc)

        if response is None:
            raise RuntimeError(f"All structured reporting models failed: {last_error}")

        payload = json.loads((response.choices[0].message.content or "{}").strip())
        report = NetworkReport(
            report_id=str(payload.get("report_id") or f"NR-{int(time.time())}"),
            timestamp=str(payload.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S")),
            summary=str(payload.get("summary") or "No summary provided."),
            attack_detected=_normalize_bool(payload.get("attack_detected", False)),
            attack_type=payload.get("attack_type"),
            confidence=_normalize_confidence(payload.get("confidence", 0.5)),
            metrics_summary=str(payload.get("metrics_summary") or f"Latency: {avg_latency}ms, Loss: {avg_loss}%"),
            anomalies_detected=str(payload.get("anomalies_detected") or "N/A"),
            potential_causes=str(payload.get("potential_causes") or "N/A"),
            recommended_actions=str(payload.get("recommended_actions") or "N/A"),
            further_investigation=str(payload.get("further_investigation") or "N/A"),
        )

        logger.info("[REPORT] Report model inference complete for pcap=%s", pcap_path)
        return report
    except Exception as e:
        logger.warning("[REPORT] LLM report generation failed for pcap=%s, using local fallback: %s", pcap_path, e)
        return _build_fallback_report(
            analysis_result=analysis_result,
            avg_latency=avg_latency,
            avg_loss=avg_loss,
            cause=str(e),
        )

class ReportingAgent:
    def __init__(self, security_to_reporting_queue: asyncio.Queue, reports_queue: asyncio.Queue):
        self.security_to_reporting_queue = security_to_reporting_queue
        self.reports_queue = reports_queue
        self.metrics_history = deque(maxlen=50)

    async def generate_report(self, attack_data, metrics_data, pcap_path):
        """Generate comprehensive report about detected anomalies and recommended actions."""
        logger.info(
            "[REPORT] Report request received: pcap=%s attack_detected=%s",
            pcap_path,
            attack_data.get("attack_detected") if isinstance(attack_data, dict) else None,
        )
        await asyncio.sleep(15)
        try:
            report_result = await generate_network_report(
                analysis_result=attack_data,  # Now includes raw_bert_output
                pcap_path=pcap_path,
                duration=metrics_data.get("duration", 5),
                cycle_interval=metrics_data.get("interval", 2),
                avg_latency=metrics_data.get("latency"),
                avg_loss=metrics_data.get("packet_loss")
            )
            await self.reports_queue.put(report_result)
            logger.info(
                "[REPORT] Report generated and queued: id=%s attack_type=%s confidence=%s",
                report_result.report_id,
                report_result.attack_type,
                report_result.confidence,
            )
            return report_result
        except Exception as e:
            logger.error("[REPORT] Error generating report for pcap=%s: %s", pcap_path, e)
            return None

    async def update_metrics_history(self, metrics):
        """Store metrics history for trend analysis in reports."""
        self.metrics_history.append(metrics)

    async def run(self):
        """Process security analysis results and generate reports."""
        while True:
            data = await self.security_to_reporting_queue.get()
            logger.info("[REPORT] Dequeued security payload for report generation")
            attack_data = data["attack_data"]
            metrics_data = data["metrics_data"]
            pcap_path = data["pcap_path"]
            await self.generate_report(attack_data, metrics_data, pcap_path)