

.PHONY: test
test:
	poetry run python -m pytest arc -s --log-cli-level INFO