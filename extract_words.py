import os
import glob
import json
import re
import subprocess
import tempfile
import concurrent.futures
from collections import Counter

ASEPRITE_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\aseprite.exe"
TARGET_DIR = r"G:\공유 드라이브\C2_SOUTHPAW\C2_Public\Storage"
DICT_FILE_PATH = "custom_dictionary.json"

def get_tags_from_file(file_path):
    json_fd, json_path = tempfile.mkstemp(suffix=".json")
    os.close(json_fd)
    
    lua_script = f"""
local sprite = app.sprite
if not sprite then return end
local file = io.open(app.params["out_json"], "w")
file:write("[")
for i, tag in ipairs(sprite.tags) do
    local name = string.gsub(tag.name, '"', '\\\\"')
    file:write('{{"name":"' .. name .. '"}}')
    if i < #sprite.tags then file:write(",") end
end
file:write("]")
file:close()
"""
    lua_fd, lua_path = tempfile.mkstemp(suffix=".lua")
    with os.fdopen(lua_fd, 'w', encoding='utf-8') as f:
        f.write(lua_script)

    cmd = [
        ASEPRITE_PATH, "-b", file_path,
        "--script-param", f"out_json={json_path}",
        "--script", lua_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        tags = []
        if result.returncode == 0:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = f.read()
                if data:
                    tags = json.loads(data)
    except Exception as e:
        tags = []
    finally:
        try:
            os.remove(json_path)
            os.remove(lua_path)
        except:
            pass
            
    return [t['name'] for t in tags]

def process_file(file_path):
    tags = get_tags_from_file(file_path)
    words = []
    for tag in tags:
        # Remove (Loop)
        clean_tag = tag.replace("_(Loop)", "").replace("(Loop)", "")
        parts = clean_tag.split('_')
        for part in parts:
            if not part: continue
            # Split by CamelCase
            sub_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', part)
            if not sub_words:
                sub_words = [part]
            for sw in sub_words:
                if len(sw) > 2 and not sw.isdigit():
                    words.append(sw.capitalize())
    return words

def main():
    print(f"Scanning directory: {TARGET_DIR}")
    files = []
    for ext in ('*.ase', '*.aseprite'):
        files.extend(glob.glob(os.path.join(TARGET_DIR, '**', ext), recursive=True))
    
    print(f"Found {len(files)} files. Extracting tags... (This may take a minute)")
    
    all_words = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in concurrent.futures.as_completed(futures):
            try:
                words = future.result()
                all_words.extend(words)
            except Exception as e:
                print(f"Error processing a file: {e}")

    counter = Counter(all_words)
    print("\n--- Most Common Words Extracted ---")
    for word, count in counter.most_common(50):
        print(f"{word}: {count}")

    # Load existing dictionary
    if os.path.exists(DICT_FILE_PATH):
        with open(DICT_FILE_PATH, 'r', encoding='utf-8') as f:
            custom_dict = json.load(f)
    else:
        custom_dict = []

    # Add words that appear at least 2 times (to filter out random typos)
    added_count = 0
    for word, count in counter.items():
        if count >= 2 and word not in custom_dict:
            custom_dict.append(word)
            added_count += 1
            
    if added_count > 0:
        with open(DICT_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(custom_dict, f, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully added {added_count} new words to the custom dictionary!")
    else:
        print("\nNo new words were added to the dictionary.")

if __name__ == '__main__':
    main()
