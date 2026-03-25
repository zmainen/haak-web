.PHONY: build deploy clean preview fetch bios all

build:
	python3 build.py

bios:
	python3 scripts/generate_bios.py

all: bios build

deploy:
	python3 build.py --deploy

preview:
	python3 -m http.server 18840

fetch:
	python3 -c "from build import *; fetch_s2_publications(load_people())"

clean:
	rm -f index.html .narrative-cache.json
	rm -rf people/
