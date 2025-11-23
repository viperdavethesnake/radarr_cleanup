#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

import os
import re
import shutil

def process_movies(source_dir, target_dir):
    os.makedirs(target_dir, exist_ok=True)

    for folder in os.listdir(source_dir):
        folder_path = os.path.join(source_dir, folder)
        if os.path.isdir(folder_path):
            nfo_file = os.path.join(folder_path, 'movie.nfo')
            if os.path.isfile(nfo_file):
                with open(nfo_file, 'r') as file:
                    nfo_content = file.read()
                    title_match = re.search(r'<title>(.*?)</title>', nfo_content)
                    year_match = re.search(r'<year>(.*?)</year>', nfo_content)
                    imdb_match = re.search(r'<uniqueid type="imdb">(.*?)</uniqueid>', nfo_content)

                    if title_match and year_match and imdb_match:
                        title = title_match.group(1).replace(' ', '_')
                        year = year_match.group(1)
                        imdb_id = imdb_match.group(1)

                        mkv_file = next((f for f in os.listdir(folder_path) if f.endswith('.mkv')), None)
                        if mkv_file:
                            new_filename = f"{title}_{year}_[imdbid-{imdb_id}].mkv"
                            mkv_file_path = os.path.join(folder_path, mkv_file)
                            new_file_path = os.path.join(target_dir, new_filename)

                            # Move and rename the file
                            shutil.move(mkv_file_path, new_file_path)
                            print(f"Moved: {mkv_file_path} -> {new_file_path}")

                            # Delete the original folder and its contents
                            shutil.rmtree(folder_path)
                            print(f"Deleted folder: {folder_path}")
                        else:
                            print(f"No MKV file found in {folder_path}")
                    else:
                        print(f"Incomplete metadata in {nfo_file}")
            else:
                print(f"No movie.nfo found in {folder_path}")

if __name__ == "__main__":
    process_movies("./movies", "./movies_renamed")

