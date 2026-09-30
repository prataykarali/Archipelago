.PHONY: ui test lint serve-inference serve-chat serve-graph

ui:
	npx esbuild books_showcase_src.tsx --bundle --outfile=ui/chat/library_showcase_3d.js --external:three

test:
	pytest tests/unit/ -k "not test_heavy_gpu" -v

lint:
	ruff check archipelago/ src/ okf/ tests/

serve-inference:
	python -m archipelago.apps.inference_app

serve-chat:
	python chat_server.py

serve-graph:
	python graph_server.py

serve-all:
	@echo "Starting all Archipelago servers..."
	python -m archipelago.apps.inference_app &
	python chat_server.py &
	python graph_server.py &
	@echo "Servers started: inference(5151) chat(5152) graph(5150)"
