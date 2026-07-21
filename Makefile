.PHONY: install test run ui docker-build docker-run start stop

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

run:
	python src/server.py

ui:
	streamlit run src/ui.py

docker-build:
	docker build -t secure-local-mcp .

docker-run:
	docker run -v ./my_notes:/app/my_notes -it secure-local-mcp

start:
	docker-compose up -d --build

stop:
	docker-compose down
