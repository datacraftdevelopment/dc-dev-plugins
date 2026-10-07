#!/usr/bin/env bash
# Offline end-to-end test of Runway's Linear adapter against fake_linear.py.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RUNWAY="$HERE/../../../plugin/runway/runway.py"
PORT=${PORT:-$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')}
python3 "$HERE/fake_linear.py" $PORT & SRV=$!
trap 'kill $SRV' EXIT
sleep 1
F="http://127.0.0.1:$PORT"
REPO="$(mktemp -d)/linear-demo"; mkdir -p "$REPO"; cd "$REPO"
git init -q -b main; git config user.email runway@example.com; git config user.name runway
echo "# demo" > README.md; printf '_pm/\nrunway.json\n' > .gitignore; git add -A; git commit -qm init
cat > runway.json <<JSON
{"tracker": "linear",
 "linear": {"team": "SF", "project": "Practice", "api_url": "$F/graphql"},
 "agent_cmd": "python3 $HERE/fake_agent.py", "prep_cmd": "python3 $HERE/fake_prep.py",
 "check_cmd": "true", "finish": "off"}
JSON
export LINEAR_API_KEY=test-key
# 1 auto; 2 auto after 1; 3 gated after 2; 4 auto after 3; 5 a wayfinder ticket (ignored); 6 auto blocked by 5
curl -s -XPOST $F/seed -d '[
 {"title":"Greeting module","labels":["ready-for-agent"]},
 {"title":"Greeting tests","labels":["ready-for-agent"],"blocked_by":[1]},
 {"title":"Public API name","labels":["ready-for-human"],"blocked_by":[2]},
 {"title":"Export API","labels":["ready-for-agent"],"blocked_by":[3]},
 {"title":"Which locale first?","labels":["wayfinder:grilling"]},
 {"title":"Locale strings","labels":["ready-for-agent"],"blocked_by":[5]}]' >/dev/null
echo "== setup"; python3 "$RUNWAY" setup
echo; echo "== loop 1: expect SF-1, SF-2 done, SF-3 packet, SF-4 and SF-6 blocked, SF-5 ignored"
python3 "$RUNWAY" loop
echo; echo "== Joe comments 'go greet()' on SF-3 in Linear"
curl -s -XPOST $F/comment -d '{"id":"i3","body":"go greet() please"}' >/dev/null
echo; echo "== loop 2: expect sync to approve SF-3, then SF-3 and SF-4 done"
python3 "$RUNWAY" loop
echo; echo "== integration branch"; git log --oneline runway/integration
echo; echo "== SF-3 got Joe's note:"; git show runway/integration:sf-3-public-api-name 2>/dev/null || git show runway/integration:public-api-name.txt
echo; echo "== final Linear state"
curl -s $F/dump | python3 -c "import json,sys; d=json.load(sys.stdin); [print(v['identifier'], v['state'], v['labels'], len(v['comments']),'comments') for v in d.values()]"
