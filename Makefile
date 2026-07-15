.PHONY: install test run docker-build docker-run

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

run:
	python src/server.py

docker-build:
	docker build -t secure-local-mcp .

docker-run:
	docker run -v ./my_notes:/app/my_notes -it secure-local-mcp
