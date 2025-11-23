#!/usr/bin/python3

import os
import subprocess

def check_and_remove_attachments(source_dir):
    """Check for and remove attachments from MKV files using mkvpropedit with attachment indices."""
    for file in os.listdir(source_dir):
        if file.endswith(".mkv"):
            file_path = os.path.join(source_dir, file)
            print(f"Processing: {file}")

            try:
                # Run mkvinfo to check for attachments
                result = subprocess.run(
                    ["mkvinfo", file_path], capture_output=True, text=True, check=True
                )

                # Parse attachment indices from mkvinfo output
                lines = result.stdout.splitlines()
                attachment_indices = []
                index = 0

                for line in lines:
                    line = line.strip()
                    if "+ Attached" in line:
                        index += 1  # Increment for each detected attachment
                        attachment_indices.append(str(index))

                # If attachments are found, remove them by index
                if attachment_indices:
                    print(f"Attachments found: {attachment_indices}. Removing...")
                    for index in attachment_indices:
                        subprocess.run(
                            ["mkvpropedit", file_path, "--delete-attachment", index],
                            capture_output=True, text=True, check=True
                        )
                    print(f"✔ All attachments removed from: {file}\n")
                else:
                    print(f"No attachments found in {file}.\n")

            except subprocess.CalledProcessError as e:
                print(f"Error processing {file_path}: {e}")
            except Exception as ex:
                print(f"Unexpected error processing {file_path}: {ex}")

if __name__ == "__main__":
    check_and_remove_attachments("./")


