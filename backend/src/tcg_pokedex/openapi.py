"""Print the API's OpenAPI schema as JSON: `python -m tcg_pokedex.openapi`.

The frontend generates its typed client from this output. Building the schema
needs no running server and is unaffected by prod hiding the /openapi.json route.
"""

import json

from tcg_pokedex.app import create_app


def main() -> None:
    print(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
