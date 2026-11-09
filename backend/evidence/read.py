def read(file_name):
    """
    Reads the content of a file and returns it as a string.

    Args:
        file_path (str): The path to the file to be read.
    """
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            content = file.read()
            lines=content.splitlines()
            snippet_num = 1
            snippets = []

            if len(lines) == 0:
                print(f"Warning: The file at {file_name} is empty.")
                return snippets

            for start in range(0, len(lines), 40):
                snippet = lines[start:start+40]

                start_line = start + 1
                end_line = start_line + len(snippet)-1

                snippet_record = {
                    "id": (snippet_num,file_name),
                    "path": file_name,
                    "content": (snippet),
                    "start_line": start_line,
                    "end_line": end_line
                }
                snippets.append(snippet_record)                

                
                snippet_num += 1    
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
