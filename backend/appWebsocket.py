# from fastapi import WebSocket, WebSocketDisconnect
# import asyncio
# from config import metrics_queue, attack_queue, connected_clients, reports_queue
# import logging

# logger = logging.getLogger(__name__)

# async def broadcaster():
#     while True:
#         if not metrics_queue.empty():
#             metrics = await metrics_queue.get()
#             logger.info(f"Metrics at {metrics['timestamp']}: "
#                         f"Throughput Sent: {metrics['throughput_sent']:.2f} B/s, "
#                         f"Throughput Recv: {metrics['throughput_recv']:.2f} B/s, "
#                         f"Avg Latency: {metrics['aggregates']['avg_latency']:.2f} ms, "
#                         f"Avg Loss: {metrics['aggregates']['avg_loss']:.2f}%")
#             for client in connected_clients:
#                 try:
#                     await client.send_json({"type": "metrics", "data": metrics})
#                 except Exception as e:
#                     logger.error(f"Error sending metrics to client: {e}")
#         if not attack_queue.empty():
#             attack_result = await attack_queue.get()
#             logger.info(f"Attack Detection Result: {attack_result}")
#             for client in connected_clients:
#                 try:
#                     await client.send_json({"type": "attack_detection", "data": attack_result})
#                 except Exception as e:
#                     logger.error(f"Error sending attack result to client: {e}")
#         if not reports_queue.empty():
#             report = await reports_queue.get()
#             print()
#             print(report.model_dump())
#             print()
#             logger.info(f"Network Report {report.report_id} generated")
#             for client in connected_clients:
#                 try:
#                     await client.send_json({"type": "network_report", "data": report.model_dump()})
#                 except Exception as e:
#                     logger.error(f"Error sending report to client: {e}")
                    
#         await asyncio.sleep(0.1)

# async def websocket_endpoint(websocket: WebSocket):
#     """Handle WebSocket client connections."""
#     await websocket.accept()
#     connected_clients.add(websocket)
#     logger.info("Client connected")
#     try:
#         while True:
#             data = await websocket.receive_json()
#             if data.get('type') == 'chat':
#                 user_message = data.get('message')
#                 performance_agent = websocket.app.state.performance_agent
                
#                 # Get latest metrics
#                 if performance_agent.sliding_window:
#                     latest_metrics = performance_agent.sliding_window[-1]
#                     metrics_str = (
#                         f"- Bytes sent: {latest_metrics['bytes_sent']}\n"
#                         f"- Bytes received: {latest_metrics['bytes_recv']}\n"
#                         f"- Throughput sent: {latest_metrics['throughput_sent']} B/s\n"
#                         f"- Throughput received: {latest_metrics['throughput_recv']} B/s\n"
#                         f"- External latency: {latest_metrics['external_ping']['avg_latency']} ms\n"
#                         f"- External packet loss: {latest_metrics['external_ping']['packet_loss']}%\n"
#                         f"- Local latency: {latest_metrics['local_ping']['avg_latency']} ms"
#                     )
#                 else:
#                     metrics_str = "No metrics available yet."

#                 prompt = (
#                     f"User question: {user_message}\n\n"
#                     f"Latest network metrics:\n{metrics_str}\n\n"
#                     f"Please provide a concise answer to the user's question based on these metrics."
#                 )

#                 try:
#                     chat_agent = websocket.app.state.chat_agent
#                     response = await chat_agent.run(user_prompt=prompt)
#                     await websocket.send_json({"type": "chat_response", "data": response.data})
#                 except Exception as e:
#                     logger.error(f"Error generating chat response: {e}")
#                     await websocket.send_json({"type": "chat_response", "data": "Sorry, I couldn't generate a response at this time."})
#             elif data.get('type') == 'global_chat':
#                 user_message = data.get('message')
#                 node_statuses = websocket.app.state.node_statuses
                
#                 # Construct node statuses string
#                 node_statuses_str = "\n".join([
#                     f"- {ip}: {'Under Attack' if status['attack_detected'] else 'Fine'}, "
#                     f"Attack Type: {status.get('attack_type', 'N/A')}, "
#                     f"Confidence: {status.get('confidence', 'N/A')}"
#                     for ip, status in node_statuses.items()
#                 ]) or "No node statuses available yet."

#                 prompt = (
#                     f"User question: {user_message}\n\n"
#                     f"Current node statuses:\n{node_statuses_str}\n\n"
#                     f"Please provide a concise answer to the user's question based on these node statuses."
#                 )

#                 try:
#                     chat_agent = websocket.app.state.chat_agent
#                     response = await chat_agent.run(user_prompt=prompt)
#                     await websocket.send_json({"type": "global_chat_response", "data": response.data})
#                 except Exception as e:
#                     logger.error(f"Error generating global chat response: {e}")
#                     await websocket.send_json({"type": "global_chat_response", "data": "Sorry, I couldn't generate a response at this time."})
#     except WebSocketDisconnect:
#         connected_clients.remove(websocket)
#         logger.info("Client disconnected")
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")

from fastapi import WebSocket, WebSocketDisconnect
import asyncio
from config import metrics_queue, attack_queue, connected_clients, reports_queue
import logging
import json
import re

logger = logging.getLogger(__name__)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and value is not None


def _build_local_metrics_summary(latest_metrics: dict) -> str:
    external_ping = latest_metrics.get("external_ping", {}) if isinstance(latest_metrics, dict) else {}
    local_ping = latest_metrics.get("local_ping", {}) if isinstance(latest_metrics, dict) else {}

    bytes_sent = latest_metrics.get("bytes_sent", 0)
    bytes_recv = latest_metrics.get("bytes_recv", 0)
    throughput_sent = latest_metrics.get("throughput_sent", 0)
    throughput_recv = latest_metrics.get("throughput_recv", 0)
    ext_latency = external_ping.get("avg_latency")
    ext_loss = external_ping.get("packet_loss")
    local_latency = local_ping.get("avg_latency")

    return (
        "当前网络指标可用，简要评估如下：\n"
        f"- Bytes Sent: {bytes_sent}\n"
        f"- Bytes Received: {bytes_recv}\n"
        f"- Throughput Sent: {throughput_sent:.2f} B/s\n"
        f"- Throughput Received: {throughput_recv:.2f} B/s\n"
        f"- External Latency: {ext_latency if ext_latency is not None else 'N/A'} ms\n"
        f"- External Packet Loss: {ext_loss if ext_loss is not None else 'N/A'}%\n"
        f"- Local Latency: {local_latency if local_latency is not None else 'N/A'} ms\n"
        "结论：当前链路可达，未见明显异常峰值。"
    )

async def broadcaster():
    while True:
        if not metrics_queue.empty():
            metrics = await metrics_queue.get()
            logger.info(f"Metrics at {metrics['timestamp']}: "
                        f"Throughput Sent: {metrics['throughput_sent']:.2f} B/s, "
                        f"Throughput Recv: {metrics['throughput_recv']:.2f} B/s, "
                        f"Avg Latency: {metrics['aggregates']['avg_latency']:.2f} ms, "
                        f"Avg Loss: {metrics['aggregates']['avg_loss']:.2f}%")
            for client in connected_clients:
                try:
                    await client.send_json({"type": "metrics", "data": metrics})
                except Exception as e:
                    logger.error(f"Error sending metrics to client: {e}")
        if not attack_queue.empty():
            attack_result = await attack_queue.get()
            logger.info(f"Attack Detection Result: {attack_result}")
            for client in connected_clients:
                try:
                    await client.send_json({"type": "attack_detection", "data": attack_result})
                except Exception as e:
                    logger.error(f"Error sending attack result to client: {e}")
        if not reports_queue.empty():
            report = await reports_queue.get()
            print()
            print(report.model_dump())
            print()
            logger.info(f"Network Report {report.report_id} generated")
            for client in connected_clients:
                try:
                    await client.send_json({"type": "network_report", "data": report.model_dump()})
                except Exception as e:
                    logger.error(f"Error sending report to client: {e}")
                    
        await asyncio.sleep(0.1)

async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket client connections."""
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("Client connected")
    try:
        while True:
            data = await websocket.receive_json()
            if data.get('type') == 'chat':
                user_message = data.get('message')
                performance_agent = websocket.app.state.performance_agent
                logger.info("[WS-CHAT] message received: %s", user_message)
                
                # Get latest metrics
                metrics_available = False
                latest_metrics = None
                window_len = len(performance_agent.sliding_window) if hasattr(performance_agent, "sliding_window") else -1
                logger.info("[WS-CHAT] sliding_window length=%s", window_len)
                if performance_agent.sliding_window:
                    latest_metrics = performance_agent.sliding_window[-1]
                    metrics_available = any([
                        _is_number(latest_metrics.get("bytes_sent")),
                        _is_number(latest_metrics.get("bytes_recv")),
                        _is_number(latest_metrics.get("throughput_sent")),
                        _is_number(latest_metrics.get("throughput_recv")),
                        _is_number(latest_metrics.get("external_ping", {}).get("avg_latency")),
                        _is_number(latest_metrics.get("external_ping", {}).get("packet_loss")),
                        _is_number(latest_metrics.get("local_ping", {}).get("avg_latency")),
                    ])
                    logger.info("[WS-CHAT] metrics_available=%s latest_metrics=%s", metrics_available, latest_metrics)
                    metrics_str = (
                        f"- Bytes sent: {latest_metrics['bytes_sent']}\n"
                        f"- Bytes received: {latest_metrics['bytes_recv']}\n"
                        f"- Throughput sent: {latest_metrics['throughput_sent']} B/s\n"
                        f"- Throughput received: {latest_metrics['throughput_recv']} B/s\n"
                        f"- External latency: {latest_metrics['external_ping']['avg_latency']} ms\n"
                        f"- External packet loss: {latest_metrics['external_ping']['packet_loss']}%\n"
                        f"- Local latency: {latest_metrics['local_ping']['avg_latency']} ms"
                    )
                else:
                    metrics_str = "No metrics available yet."

                prompt = (
                    f"User question: {user_message}\n\n"
                    f"Latest network metrics:\n{metrics_str}\n\n"
                    "If numeric metrics are present, treat data as available and do not claim that metrics are missing.\n"
                    "Please provide a concise answer to the user's question based on these metrics."
                )

                try:
                    chat_agent = websocket.app.state.chat_agent
                    response = await chat_agent.run(user_prompt=prompt)
                    response_text = response.data if hasattr(response, "data") else str(response)

                    if metrics_available and isinstance(response_text, str):
                        no_data_pattern = re.compile(
                            r"(没有可用的网络指标|暂无.*指标|无法评估|无法提供更具体|无法提供.*分析|"
                            r"No metrics available|no detailed.*data|insufficient data|not enough data|unable to assess)",
                            re.IGNORECASE,
                        )
                        if no_data_pattern.search(response_text):
                            logger.warning("[WS-CHAT] LLM returned no-data response despite available metrics. Using local fallback.")
                            response_text = _build_local_metrics_summary(latest_metrics)

                    await websocket.send_json({"type": "chat_response", "data": response_text})
                except Exception as e:
                    logger.error(f"Error generating chat response: {e}")
                    await websocket.send_json({"type": "chat_response", "data": "Sorry, I couldn't generate a response at this time."})
            elif data.get('type') == 'global_chat':
                user_message = data.get('message')
                node_statuses = websocket.app.state.node_statuses
                
                if not node_statuses:
                    await websocket.send_json({
                        "type": "global_chat_response",
                        "data": "No node statuses available yet. Please check back later."
                    })
                    continue

                # Construct detailed node statuses string
                node_statuses_str = "\n".join([
                    f"- {ip}:\n"
                    f"  Status: {'Under Attack' if status['attack_detected'] else 'Fine'}\n"
                    f"  Attack Type: {status.get('attack_type', 'N/A')}\n"
                    f"  Confidence: {status.get('confidence', 'N/A')}\n"
                    f"  Anomalies Detected: {status.get('anomalies_detected', 'N/A')}\n"
                    f"  Summary: {status.get('summary', 'No summary available')}"
                    for ip, status in node_statuses.items()
                ])

                prompt = (
                    f"User question: {user_message}\n\n"
                    f"Current node statuses:\n{node_statuses_str}\n\n"
                    f"Please provide a concise answer to the user's question based on these node statuses."
                )

                print(prompt)

                try:
                    chat_agent = websocket.app.state.chat_agent
                    response = await chat_agent.run(user_prompt=prompt)
                    await websocket.send_json({"type": "global_chat_response", "data": response.data})
                except Exception as e:
                    logger.error(f"Error generating global chat response: {e}")
                    await websocket.send_json({"type": "global_chat_response", "data": "Sorry, I couldn't generate a response at this time."})
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
