from pathlib import Path
import sys
import zlib
import urllib.request


PLANTUML_SERVER = "https://www.plantuml.com/plantuml"


def encode64(data: bytes) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"

    def append3bytes(b1, b2, b3):
        c1 = b1 >> 2
        c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
        c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
        c4 = b3 & 0x3F
        return alphabet[c1] + alphabet[c2] + alphabet[c3] + alphabet[c4]

    result = ""
    i = 0

    while i < len(data):
        b1 = data[i]
        b2 = data[i + 1] if i + 1 < len(data) else 0
        b3 = data[i + 2] if i + 2 < len(data) else 0
        result += append3bytes(b1, b2, b3)
        i += 3

    return result


def plantuml_encode(text: str) -> str:
    compressed = zlib.compress(text.encode("utf-8"))[2:-4]
    return encode64(compressed)


def render_puml(input_path: Path, fmt: str = "svg") -> None:
    source = input_path.read_text(encoding="utf-8")
    encoded = plantuml_encode(source)

    url = f"{PLANTUML_SERVER}/{fmt}/{encoded}"
    output_path = input_path.with_suffix(f".{fmt}")

    request = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "image/svg+xml,image/png,*/*"
    }
)

    with urllib.request.urlopen(request, timeout=30) as response:
        output_path.write_bytes(response.read())

    print(f"Rendered: {output_path}")


def main():
    if len(sys.argv) > 1:
        files = [Path(arg) for arg in sys.argv[1:]]
    else:
        files = list(Path(".").glob("*.puml"))

    if not files:
        print("No .puml files found in current folder.")
        return

    for file in files:
        if not file.exists():
            print(f"Not found: {file}")
            continue

        render_puml(file, fmt="svg")


if __name__ == "__main__":
    main()