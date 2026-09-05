.PHONY: init up down logs check test seed seed-dry migrations css

init:
	cp .env.example .env
	docker compose build
	docker compose run --rm assets npm run css:build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f web

check:
	docker compose run --rm web python manage.py check

test:
	docker compose run --rm -e LOAD_DEMO_DATA=false web python manage.py test

seed:
	docker compose run --rm -e LOAD_DEMO_DATA=false web python manage.py seed_demo

seed-dry:
	docker compose run --rm -e LOAD_DEMO_DATA=false web python manage.py seed_demo --dry-run

migrations:
	docker compose run --rm -e LOAD_DEMO_DATA=false web python manage.py makemigrations

css:
	docker compose run --rm assets npm run css:build
