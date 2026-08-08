from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from .database import connect_database, initialize_database
from .domain import CreateTicket
from .ai_client import AIConfig, OpenAICompatibleClient
from .analysis import AnalysisService
from .errors import AIUnavailableError, TicketSystemError
from .evaluation import evaluate_cases, load_cases, write_report
from .repository import TicketRepository
from .review import ReviewService
from .service import TicketService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ticket-system")
    parser.add_argument("--db", default="data/tickets.db", help="SQLite 数据库路径")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init")
    commands.add_parser("seed")

    create = commands.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--submitter", required=True)
    create.add_argument("--priority", default="P2", choices=("P0", "P1", "P2", "P3"))

    list_command = commands.add_parser("list")
    list_command.add_argument("--status", choices=("new", "triaged", "in_progress", "resolved", "closed"))
    list_command.add_argument(
        "--category",
        choices=("unclassified", "account_access", "software", "network", "hardware", "facilities", "other"),
    )
    list_command.add_argument("--priority", choices=("P0", "P1", "P2", "P3"))
    list_command.add_argument("--submitter")

    show = commands.add_parser("show")
    show.add_argument("public_id")
    show.add_argument("--history", action="store_true")

    status = commands.add_parser("status")
    status.add_argument("public_id")
    status.add_argument("target", choices=("new", "triaged", "in_progress", "resolved", "closed"))
    status.add_argument("--actor", required=True)
    status.add_argument("--version", required=True, type=int)

    analyze = commands.add_parser("analyze")
    analyze.add_argument("public_id")
    analyze.add_argument("--prompt-version", choices=("baseline", "hardened"), default="hardened")

    review = commands.add_parser("review")
    review.add_argument("suggestion_id", type=int)
    review.add_argument("action", choices=("confirm", "modify", "reject"))
    review.add_argument("--reviewer", required=True)
    review.add_argument("--category", choices=("account_access", "software", "network", "hardware", "facilities", "other"))
    review.add_argument("--priority", choices=("P0", "P1", "P2", "P3"))

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--prompt-version", choices=("baseline", "hardened"), required=True)
    evaluate.add_argument("--cases", required=True)
    evaluate.add_argument("--output-dir", required=True)
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    connection = connect_database(arguments.db)
    try:
        initialize_database(connection)
        service = TicketService(TicketRepository(connection))
        if arguments.command == "init":
            result = {"database": arguments.db, "initialized": True}
        elif arguments.command == "seed":
            result = service.seed()
        elif arguments.command == "create":
            result = service.create(
                CreateTicket(
                    arguments.title,
                    arguments.description,
                    arguments.submitter,
                    arguments.priority,
                )
            )
        elif arguments.command == "list":
            filters = {
                name: value
                for name, value in {
                    "status": arguments.status,
                    "category": arguments.category,
                    "priority": arguments.priority,
                    "submitter": arguments.submitter,
                }.items()
                if value is not None
            }
            result = service.list(filters)
        elif arguments.command == "show":
            result = service.show(arguments.public_id)
            if arguments.history:
                result = {"ticket": result, "history": service.history(arguments.public_id)}
        elif arguments.command == "analyze":
            analysis = AnalysisService(TicketRepository(connection), OpenAICompatibleClient(AIConfig.from_environment()))
            result = analysis.analyze(arguments.public_id, arguments.prompt_version)
        elif arguments.command == "review":
            suggestion, ticket = ReviewService(TicketRepository(connection)).review(
                arguments.suggestion_id,
                arguments.action,
                arguments.reviewer,
                arguments.category,
                arguments.priority,
            )
            result = {"suggestion": suggestion, "ticket": ticket}
        elif arguments.command == "evaluate":
            config = AIConfig.from_environment()
            report = evaluate_cases(
                load_cases(arguments.cases),
                OpenAICompatibleClient(config),
                arguments.prompt_version,
            )
            result = {"report": str(write_report(report, arguments.output_dir)), "aggregate": report.aggregate}
        else:
            result = service.change_status(
                arguments.public_id,
                arguments.target,
                arguments.actor,
                expected_version=arguments.version,
            )
        print(json.dumps(_json_value(result), ensure_ascii=False))
        return 0
    except TicketSystemError as error:
        print(str(error), file=sys.stderr)
        if isinstance(error, AIUnavailableError):
            print("工单未改变", file=sys.stderr)
        return error.exit_code
    finally:
        connection.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(run())


def _json_value(value):
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
