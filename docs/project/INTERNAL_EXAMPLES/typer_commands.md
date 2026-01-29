# Пример вызова typer

```python
import typer
from typing import Annotated

app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, file_path: Annotated[str | None, typer.Argument()] = None):
    print(f'file path is {file_path}')
    print(f'command is: {ctx.invoked_subcommand} of type {type(ctx.invoked_subcommand)}') # none if no command is given

@app.command()
def command(command_param: str):
    print(f'command param is {command_param}')

if __name__ == '__main__':
    app()
```