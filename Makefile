.PHONY: build init-db discover backfill run-analysis test dq shell

build:
	docker compose build

init-db:
	docker compose run --rm etl python -m src.db_init

discover:
	docker compose run --rm etl python -m src.sync_dictionaries
	docker compose run --rm etl python -m src.discover_metadata

backfill:
	docker compose run --rm etl python -m src.extract_trade --backfill

run-analysis:
	docker compose run --rm etl python -m src.models_fx_granger
	docker compose run --rm etl python -m src.generate_report

dq:
	docker compose run --rm etl python -m src.run_dq

test:
	docker compose run --rm etl pytest -v

shell:
	docker compose run --rm etl bash
