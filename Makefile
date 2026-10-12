PY ?= python3

.PHONY: video stills audio preview

video:
	$(PY) render/render.py

stills:
	$(PY) render/stills.py

audio:
	$(PY) render/audio.py

preview:
	$(PY) -m http.server 8000
