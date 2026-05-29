from .cli import cli
from .registry import registry

if __name__ == "__main__":

    registry.load_plugins()
    cli()
