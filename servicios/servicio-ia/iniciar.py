"""Materializa ADC desde un secreto de entorno en plataformas sin secret volumes."""

import json
import os
import sys
import tempfile


def main() -> None:
    credencial = os.environ.pop("GOOGLE_CREDENTIALS_JSON", None)
    if credencial:
        json.loads(credencial)  # Fallar antes del arranque si el secreto no es JSON válido.
        descriptor, ruta = tempfile.mkstemp(prefix="agro-gcp-", suffix=".json")
        with os.fdopen(descriptor, "w") as archivo:
            archivo.write(credencial)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ruta
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
