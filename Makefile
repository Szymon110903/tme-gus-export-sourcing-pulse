.PHONY: init-db backfill run-analysis test dq

init-db:
	python -m src.db_init

backfill:
	python -m src.extract_trade --backfill

run-analysis:
	python -m src.models_fx_granger
	python -m src.generate_report

dq:
	python -m src.run_dq

test:
	pytest -v
