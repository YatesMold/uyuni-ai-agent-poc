.PHONY: test run build

test:
	.venv/bin/pytest tests/ -v

run:
	.venv/bin/python main.py

build:
	docker build -t uyuni-ai-agent .
