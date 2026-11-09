def chunk_text(content, file_name):
    """Split text into cited chunks without executing it or trimming its lines."""
    lines = content.splitlines()
    snippets = []
    for start in range(0, len(lines), 40):
        snippet = lines[start:start + 40]
        snippets.append({
            "id": (len(snippets) + 1, file_name),
            "path": file_name,
            "content": snippet,
            "start_line": start + 1,
            "end_line": start + len(snippet),
        })
    return snippets


def read(file_name):
    """
    Reads a UTF-8 file and returns line-cited snippet records.

    Args:
        file_path (str): The path to the file to be read.
    """
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            content = file.read()
            snippets = chunk_text(content, file_name)
            if not snippets:
                print(f"Warning: The file at {file_name} is empty.")
            return snippets    

    except FileNotFoundError:
        print(f"Error: The file at {file_name} was not found.")
        return []
    except IOError:
        print(f"Error: An I/O error occurred while reading the file at {file_name}.")
        return []

if __name__ == "__main__":
    records = read("samples/read.py")

    for record in records:
        print(f"\nPath: {record['path']}")
        print(f"Lines: {record['start_line']} - {record['end_line']}")

        for i, line in enumerate(
            record["content"],
            start=record["start_line"]
        ):
            print(f"Line {i}: {line}")
