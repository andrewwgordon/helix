"""Custom ``flask`` CLI commands."""

import click
from flask.cli import with_appcontext


@click.command("seed")
@with_appcontext
def seed_command():
    """Seed reference data and roles (idempotent)."""
    from flask import current_app

    from app import db
    from app.seed import seed_all

    seed_all(db.session, current_app.appbuilder.sm)
    click.echo("Reference data and roles seeded.")


@click.command("seed-uav")
@with_appcontext
def seed_uav_command():
    """Seed the HoverX-4 UAV demonstration dataset (idempotent)."""
    from flask import current_app

    from app import db
    from app.uav_seed import seed_uav

    summary = seed_uav(db.session, current_app.appbuilder.sm)
    if not summary.get("created"):
        click.echo(
            f"HoverX-4 dataset already present ({summary['product']}) - no-op."
        )
        return
    click.echo(
        "Seeded HoverX-4: "
        f"{summary['requirements']} requirements, "
        f"{summary['parts']} parts, "
        f"{summary['documents']} documents, "
        f"{summary['relationships']} relationships, "
        f"baseline {summary['baseline']} "
        f"({summary['baseline_members']} members)."
    )


@click.command("teardown-uav")
@with_appcontext
def teardown_uav_command():
    """Remove the HoverX-4 UAV demonstration dataset."""
    from flask import current_app

    from app import db
    from app.uav_seed import teardown_uav

    summary = teardown_uav(
        db.session, current_app.config.get("UPLOAD_FOLDER")
    )
    if summary.get("removed"):
        click.echo(f"Removed HoverX-4 dataset ({summary['items']} items).")
    else:
        click.echo("Nothing to remove - HoverX-4 dataset not present.")


def register_cli(app):
    app.cli.add_command(seed_command)
    app.cli.add_command(seed_uav_command)
    app.cli.add_command(teardown_uav_command)
