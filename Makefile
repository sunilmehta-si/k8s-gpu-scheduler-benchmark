# Everyday commands. Python 3.10+ with the package installed (pip install -e .).
PY ?= python3
# STACK: default, kueue, volcano, kai, or a tuned variant: default-binpack, kueue-binpack, volcano-binpack
STACK ?= kai
SPEEDUP ?= 300

.PHONY: test results cluster clean

test:  ## run the unit tests (also checks committed traces, results, reports and charts)
	$(PY) -W error::SyntaxWarning -m unittest discover -s tests -t .

results:  ## regenerate every committed result, report and chart
	$(PY) -m gpu_sched_bench simulate --fleet fleets/mixed-256.yaml --trace traces/mixed-256-8h.jsonl -o results/mixed-256.json
	$(PY) -m gpu_sched_bench simulate --fleet fleets/lab-32.yaml --trace traces/lab-32-8h.jsonl -o results/lab-32.json
	$(PY) -m gpu_sched_bench simulate --fleet fleets/dc-1024.yaml --trace traces/dc-1024-8h.jsonl -o results/dc-1024.json
	$(PY) -m gpu_sched_bench report results/mixed-256.json results/lab-32.json results/dc-1024.json -o results/README.md
	$(PY) -m gpu_sched_bench sweep --fleet fleets/mixed-256.yaml --seeds 1-10 --rate 16 --hours 8 -o results/sweep-mixed-256.json
	$(PY) -m gpu_sched_bench report results/sweep-mixed-256.json -o results/sweep-mixed-256.md
	$(PY) -m gpu_sched_bench sweep --fleet fleets/mixed-256.yaml --seeds 1-10 --rate 16 --hours 8 --stacks default,default-binpack,kueue,kueue-binpack,volcano,volcano-binpack,kai -o results/sweep-mixed-256-tuned.json
	$(PY) -m gpu_sched_bench report results/sweep-mixed-256-tuned.json -o results/sweep-mixed-256-tuned.md
	$(PY) -m gpu_sched_bench chart results/mixed-256.json -o results/mixed-256.svg --title "256-GPU fleet, 131 jobs (reference simulation)"
	$(PY) -m gpu_sched_bench chart results/lab-32.json -o results/lab-32.svg --title "32-GPU lab, 26 jobs (reference simulation)"
	$(PY) -m gpu_sched_bench chart results/dc-1024.json -o results/dc-1024.svg --title "1,024-GPU data centre, 611 jobs (reference simulation)"

cluster:  ## run the smoke trace on a local kind + kwok cluster with STACK installed (fresh cluster per stack)
	scripts/cluster-up.sh
	if [ "$(STACK)" != "default" ]; then GSB="$(PY) -m gpu_sched_bench" scripts/install-$(STACK).sh; fi
	$(PY) -m gpu_sched_bench cluster run --stack $(STACK) --fleet fleets/lab-32.yaml --trace traces/lab-32-smoke.jsonl --speedup $(SPEEDUP) --strict -o cluster-$(STACK).json
	$(PY) -m gpu_sched_bench simulate --stacks $(STACK) --fleet fleets/lab-32.yaml --trace traces/lab-32-smoke.jsonl --placements -o model-$(STACK).json
	$(PY) -m gpu_sched_bench compare model-$(STACK).json cluster-$(STACK).json

clean:
	rm -rf build dist *.egg-info cluster-*.json model-*.json
