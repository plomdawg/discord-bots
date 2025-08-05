# discord-bots Makefile

.PHONY: help lint format format-check

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Check code style and type hints
	pylint --disable=fixme bot.py bots/ cogs/
	mypy bot.py bots/ cogs/

format: ## Format code with black
	black bot.py bots/ cogs/

format-check: ## Check if code needs formatting
	black --check bot.py bots/ cogs/
