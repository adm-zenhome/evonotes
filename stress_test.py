import asyncio
import time
import json
import httpx

BASE_URL = "http://127.0.0.1:8765"
CONCURRENT_AGENTS = 100

async def agent_worker(agent_id: int, client: httpx.AsyncClient):
    start_time = time.time()
    results = {}
    
    try:
        # 1. Health & Home HTML Check
        res_home = await client.get(f"{BASE_URL}/")
        results["home_status"] = res_home.status_code
        
        # 2. API Meetings List
        res_meetings = await client.get(f"{BASE_URL}/api/meetings")
        results["meetings_status"] = res_meetings.status_code
        meetings = res_meetings.json()
        results["meetings_count"] = len(meetings)
        
        # 3. Deep Detail Inspection
        if meetings:
            first_id = meetings[0]["file_id"]
            res_detail = await client.get(f"{BASE_URL}/api/meeting/{first_id}")
            results["detail_status"] = res_detail.status_code
            
            # 4. Interactive Todo State Test
            res_toggle = await client.post(f"{BASE_URL}/api/toggle-todo/{first_id}/0")
            results["toggle_status"] = res_toggle.status_code
            
        elapsed = time.time() - start_time
        return {"agent_id": agent_id, "success": True, "elapsed_ms": round(elapsed * 1000, 2), "data": results}
    except Exception as e:
        elapsed = time.time() - start_time
        return {"agent_id": agent_id, "success": False, "elapsed_ms": round(elapsed * 1000, 2), "error": str(e)}

async def run_100_agents_stress_test():
    print(f"🚀 Disparando frota de {CONCURRENT_AGENTS} agentes simultâneos...")
    start_all = time.time()
    
    limits = httpx.Limits(max_keepalive_connections=150, max_connections=200)
    async with httpx.AsyncClient(limits=limits, timeout=15.0) as client:
        tasks = [agent_worker(i, client) for i in range(1, CONCURRENT_AGENTS + 1)]
        results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_all
    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]
    latencies = [r["elapsed_ms"] for r in successes]
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    min_latency = min(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    
    report = {
        "total_agents": CONCURRENT_AGENTS,
        "successful_agents": len(successes),
        "failed_agents": len(failures),
        "total_wall_clock_time_sec": round(total_time, 3),
        "avg_latency_ms": round(avg_latency, 2),
        "min_latency_ms": min_latency,
        "p95_latency_ms": p95_latency,
        "max_latency_ms": max_latency,
        "throughput_req_per_sec": round((CONCURRENT_AGENTS * 4) / total_time, 2)
    }
    
    print("\n📊 RESULTADO DA HOMOLOGAÇÃO DE 100 AGENTES:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    with open("/Users/felipe/Jarvis/modules/executive_voice_os/data/homologation_report.json", "w", encoding="utf-8") as f:
        json.dump({"report": report, "agent_details": results}, f, indent=2, ensure_ascii=False)
        
    return report

if __name__ == "__main__":
    asyncio.run(run_100_agents_stress_test())
