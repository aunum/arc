import typer

app = typer.Typer(name="arc")


@app.command()
def run(path: str):
    print(f"Hello {path}")


if __name__ == "__main__":
    app()
