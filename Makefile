.PHONY: build init-db discover backfill build-marts dq run-analysis notify test shell airflow-up airflow-down

build:
	docker compose build

airflow-up:
	docker compose --profile airflow up -d --build

airflow-down:
	docker compose --profile airflow down

init-db:
	docker compose run --rm etl python -m src.pipelines.init_db

discover:
	docker compose run --rm etl python -m src.pipelines.sync_dictionaries
	docker compose run --rm etl python -m src.pipelines.discover_metadata

backfill:
	docker compose run --rm etl python -m src.pipelines.extract_trade --backfill

build-marts:
	docker compose run --rm etl python -m src.pipelines.build_marts

dq:
	docker compose run --rm etl python -m src.quality.run_dq

run-analysis:
	docker compose run --rm etl python -m src.analytics.models_fx_granger
	docker compose run --rm etl python -m src.analytics.generate_report

notify:
	docker compose run --rm etl python -m src.alerting.notify_power_automate --dry-run

test:
	docker compose run --rm etl pytest -v

shell:
	docker compose run --rm etl bash
