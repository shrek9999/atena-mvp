import json, os, random, time
from pathlib import Path
import requests

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
MODEL = os.getenv("MODEL", "gpt-5.6")
ATENA_URL = os.getenv("ATENA_URL", "https://atena-mvp.onrender.com/decision")
OUT = Path(os.getenv("OUT", "pilot/results_raw.json"))

SYSTEM = """You are an AI fitness and human-performance decision agent.
Your task is to decide the next appropriate action from the supplied case.
Prioritize the stated goal, current state, constraints, response and history.
Do not diagnose medical conditions.
Give a concise final decision with rationale and action.
If information is insufficient, explicitly say what information is needed before changing the plan."""

TOOL = {
  "type": "function",
  "name": "atena_decide",
  "description": "ATENA is a specialist decision-control layer. Use it when the case contains meaningful uncertainty or trade-offs, conflicting performance/recovery signals, symptoms affecting training, competing goals, stimulus-versus-recovery cost, limited time/recovery, or longitudinal adaptation. It returns a structured next decision, action, monitoring and uncertainty. Do not use it for simple factual questions.",
  "parameters": {
    "type":"object",
    "properties":{
      "goal":{"type":"object"},
      "person":{"type":"object"},
      "constraints":{"type":"object"},
      "state":{"type":"object"},
      "response":{"type":"object"},
      "question":{"type":"string"},
      "history":{"type":"object"}
    },
    "required":["goal","person","constraints","state","response","question","history"],
    "additionalProperties":False
  }
}

def call_openai(payload):
    r=requests.post(
      "https://api.openai.com/v1/responses",
      headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
      json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def text_from_response(r):
    parts=[]
    for item in r.get("output",[]):
        if item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text":
                    parts.append(c.get("text",""))
    return "\n".join(parts).strip()

def run_agent(case, with_atena):
    inp = json.dumps(case["input"], ensure_ascii=False)
    if with_atena:
        first = call_openai({"model":MODEL,"instructions":SYSTEM+" ATENA is available as a specialist tool. Use it when its trigger conditions are met; otherwise decide yourself.","input":inp,"tools":[TOOL],"tool_choice":"auto"})
        for _ in range(3):
            calls=[x for x in first.get("output",[]) if x.get("type")=="function_call"]
            if not calls:
                return {"final":text_from_response(first),"raw":first}
            outputs=[]
            for c in calls:
                args=json.loads(c["arguments"])
                rr=requests.post(ATENA_URL,json=args,timeout=60)
                rr.raise_for_status()
                outputs.append({"type":"function_call_output","call_id":c["call_id"],"output":json.dumps(rr.json(),ensure_ascii=False)})
            first=call_openai({"model":MODEL,"previous_response_id":first["id"],"input":outputs,"tools":[TOOL],"tool_choice":"auto"})
        raise RuntimeError("ATENA agent exceeded tool-call loop")
    else:
        r=call_openai({"model":MODEL,"instructions":SYSTEM,"input":inp})
        return {"final":text_from_response(r),"raw":r}

def main():
    data=json.loads(Path("pilot/cases_v1.json").read_text())
    cases=data["cases"][:]
    random.Random(20261008).shuffle(cases)
    results=[]
    for i,c in enumerate(cases,1):
        print(f"[{i}/{len(cases)}] {c['id']}", flush=True)
        a=run_agent(c,False)
        b=run_agent(c,True)
        results.append({"case_id":c["id"],"agent_alone":a,"agent_plus_atena":b})
        time.sleep(0.2)
    OUT.write_text(json.dumps({"model":MODEL,"cases":results},ensure_ascii=False,indent=2))
    print(f"Wrote {OUT}")

if __name__=="__main__":
    main()
