import os
import sys

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_result_dir = os.path.join(repo_root, "tests", "test_result")
    output_file = os.path.join(repo_root, "tests", "test_result_merged.md")

    if not os.path.exists(test_result_dir):
        print(f"Error: Directory {test_result_dir} does not exist.")
        sys.exit(1)

    print(f"Tracing markdown files in {test_result_dir}...")
    
    merged_content = []
    
    for root, dirs, files in os.walk(test_result_dir):
        # Sort files and directories for consistent output
        dirs.sort()
        files.sort()
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, test_result_dir)
                
                print(f"Found: {rel_path}")
                
                merged_content.append(f"# {rel_path}\n")
                with open(file_path, "r", encoding="utf-8") as f:
                    merged_content.append(f.read().strip())
                merged_content.append("\n\n---\n\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("".join(merged_content).strip())

    print(f"Merged markdown saved to {output_file}")

if __name__ == "__main__":
    main()
