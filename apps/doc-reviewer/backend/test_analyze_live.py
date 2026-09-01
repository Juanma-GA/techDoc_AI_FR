import json
import httpx

doc_id = "85d0744ec7fb454f95d8eb033e0bb9e8"
url = f"http://127.0.0.1:8003/api/v1/documents/{doc_id}/analyze?checklist=true"

counts = {"suggestion": 0, "progress": 0, "quality": 0, "run_started": 0, "error": 0, "done": 0}
last_progress = None
error_msg = None
done_payload = None

with httpx.stream("POST", url, headers={"Accept": "text/event-stream"}, timeout=300.0) as r:
    print("HTTP status:", r.status_code)
    event = ""
    for line in r.iter_lines():
        if not line:
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
            if event in counts:
                counts[event] += 1
            if event == "progress":
                try:
                    last_progress = json.loads(data)
                except Exception:
                    pass
            if event == "error":
                error_msg = data
            if event == "done":
                done_payload = data

print("counts:", counts)
print("last_progress:", last_progress)
print("error_msg:", error_msg)
print("done_payload:", done_payload)
