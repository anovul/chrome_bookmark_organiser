import os
import json
import shutil
from pathlib import Path
import uuid
import sys

# --- CONFIGURATION ---
# Define the name of the root where we will place the new, organized folders.
# This will usually be "bookmark_bar" to place them directly visible in Chrome.
DESTINATION_ROOT_NAME = "bookmark_bar"

# Standard Chrome root folder names that should be ignored when determining the "canonical" path.
# Bookmarks directly under these will be grouped under the root name itself.
CHROME_ROOT_NAMES = {"Bookmarks Bar", "Other Bookmarks", "Mobile Bookmarks", "Managed Bookmarks", "Reading list"}

# Set a safety limit for recursion to prevent crashes on malformed files.
MAX_RECURSION_DEPTH = 100

# --- Helper Functions ---

def _wait_for_exit():
    """Helper function to wait for user input before exiting, handling potential stdin issues."""
    try:
        input("Press Enter to exit.")
    except (RuntimeError, EOFError):
        print("Exiting. (Could not read 'Press Enter to exit' due to console input issues.)")
    except Exception as e:
        print(f"An unexpected error occurred during exit prompt: {e}")

def get_chrome_bookmark_path():
    """
    Locates the Chrome Bookmarks file for the current user in a platform-independent way.
    """
    home = Path.home()
    possible_paths = [
        home / "AppData/Local/Google/Chrome/User Data/Default/Bookmarks",  # Windows
        home / "Library/Application Support/Google/Chrome/Default/Bookmarks",  # macOS
        home / ".config/google-chrome/Default/Bookmarks"  # Linux
    ]
    for path in possible_paths:
        if path.exists():
            print(f"✅ Found Chrome Bookmarks file at: {path}")
            return path
    print("❌ Error: Could not find Chrome Bookmarks file. Please ensure Chrome is installed and used.")
    return None

def load_bookmarks(path):
    """Loads the bookmarks JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        print(f"❌ Error decoding JSON from bookmarks file: {e}")
        print("This might indicate a corrupted bookmarks file. Please check your backup.")
        return None
    except IOError as e:
        print(f"❌ Error reading bookmarks file: {e}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred while loading bookmarks: {e}")
        return None

def save_bookmarks(data, path):
    """Saves the modified bookmarks data back to the file."""
    try:
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"❌ Error saving bookmarks file: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred while saving bookmarks: {e}")

def get_canonical_path_segments(original_full_path_parts):
    """
    Determines the canonical (meaningful and non-redundant) path for a bookmark.
    Applies internal path deduplication (e.g., A > B > A becomes B > A).

    Args:
        original_full_path_parts (list): List of folder names from Chrome root down to immediate parent.
                                       e.g., ["Bookmarks Bar", "Work", "Projects", "Design"]
    Returns:
        list: The canonical path segments. e.g., ["Work", "Projects", "Design"] or ["Bookmarks Bar"]
    """
    # Step 1: Filter out Chrome Root Names
    user_defined_path_parts = []
    for part in original_full_path_parts:
        if part not in CHROME_ROOT_NAMES:
            user_defined_path_parts.append(part)
        elif not user_defined_path_parts: # If we're still at the beginning and it's a Chrome root
            continue # Skip this initial Chrome root, will be handled by special case if no user parts
        else:
            # If a Chrome root name appears *after* user-defined folders (unlikely but possible),
            # it's treated as a normal folder name and included.
            user_defined_path_parts.append(part)

    # Step 2: Handle Bookmarks Directly Under Chrome Roots (or if only Chrome roots were in path)
    if not user_defined_path_parts and original_full_path_parts:
        # If no user-defined folders were found, but the bookmark was under a Chrome root,
        # use the specific Chrome root name as the canonical path segment.
        return [original_full_path_parts[0]] # e.g., ["Bookmarks Bar"]

    # Step 3: Internal Path Deduplication (for user-defined paths)
    final_canonical_path_segments = []
    seen_names_in_new_path = set()

    # Iterate backwards from the immediate parent towards the root
    for i in range(len(user_defined_path_parts) - 1, -1, -1):
        current_folder_name = user_defined_path_parts[i]

        if current_folder_name not in seen_names_in_new_path:
            # Add to the front to maintain correct path order in the new hierarchy
            final_canonical_path_segments.insert(0, current_folder_name)
            seen_names_in_new_path.add(current_folder_name)
        else:
            # If the name is already an ancestor in the *new* path, stop.
            # This flattens the redundant segment as per your requirement (e.g., A > B > A becomes B > A).
            break

    return final_canonical_path_segments

def collect_bookmarks_recursively(node, current_path_parts, collected_bookmarks, seen_urls, depth=0):
    """
    Recursively traverses the bookmark tree, determines canonical paths, and collects bookmarks.
    """
    if depth > MAX_RECURSION_DEPTH:
        print(f"⚠️ Warning: Reached maximum folder depth at path: {' > '.join(current_path_parts)}. Skipping deeper items.")
        return

    node_type = node.get("type")

    if node_type == "url":
        url = node.get("url")
        if not url or url.startswith("javascript:"):
            return # Skip invalid or javascript bookmarks

        # Use the URL itself as the key for deduplication
        if url in seen_urls:
            return # Skip if this URL has already been collected

        seen_urls.add(url)
        
        # Create a new GUID for the bookmark when it's moved/reorganized
        bookmark_item = {
            "type": "url",
            "name": node.get("name", "No Name"),
            "url": url,
            "guid": str(uuid.uuid4()),
            "date_added": node.get("date_added", "0") # Preserve original date_added
        }

        canonical_path = get_canonical_path_segments(current_path_parts)
        
        # Navigate the `collected_bookmarks` dictionary to the correct leaf based on canonical path
        current_level = collected_bookmarks
        for segment in canonical_path:
            if segment not in current_level:
                current_level[segment] = {}
            current_level = current_level[segment]
        
        # At the final destination (leaf of the canonical path), append the bookmark.
        # Use a special key '_bookmarks' to store a list of URLs directly under this folder.
        if '_bookmarks' not in current_level:
            current_level['_bookmarks'] = []
        current_level['_bookmarks'].append(bookmark_item)


    elif node_type == "folder":
        folder_name = node.get("name")
        # Ensure 'name' exists before appending to path. Otherwise, skip this folder's name in path.
        if folder_name:
            next_path_parts = current_path_parts + [folder_name]
        else: # Handle folders with no name (rare, but possible in corrupted files)
            print(f"⚠️ Warning: Skipping unnamed folder at path: {' > '.join(current_path_parts)}")
            next_path_parts = current_path_parts # Don't add to path, but continue recursion with same path
        
        for child in node.get("children", []):
            collect_bookmarks_recursively(child, next_path_parts, collected_bookmarks, seen_urls, depth + 1)

def build_chrome_json_structure(collected_node_dict):
    """
    Recursively converts the `collected_bookmarks` dictionary (our custom nested structure)
    into Chrome's standard JSON format for children lists.
    """
    children_list = []

    # Separate folders from direct bookmarks at this level
    folder_keys = []
    direct_bookmarks = []

    if '_bookmarks' in collected_node_dict:
        direct_bookmarks = collected_node_dict['_bookmarks']
        # Create a temporary dictionary for folder keys only
        temp_dict_for_folders = {k: v for k, v in collected_node_dict.items() if k != '_bookmarks'}
    else:
        temp_dict_for_folders = collected_node_dict
    
    folder_keys = sorted(temp_dict_for_folders.keys(), key=lambda x: x.lower()) # Sort folders alphabetically by name

    # Add folders first (recursively build their content)
    for folder_name in folder_keys:
        folder_content = temp_dict_for_folders[folder_name]
        folder_children = build_chrome_json_structure(folder_content)
        
        children_list.append({
            "type": "folder",
            "name": folder_name,
            "children": folder_children,
            "guid": str(uuid.uuid4()), # New GUID for the new folder
            "date_added": "0", # Can set to current timestamp or preserve original if available
            "date_modified": "0" # Can set to current timestamp
        })
    
    # Add direct bookmarks after folders, sorted by name
    if direct_bookmarks:
        children_list.extend(sorted(direct_bookmarks, key=lambda x: x['name'].lower()))

    return children_list

def main():
    """Main function to execute the bookmark reorganization process."""
    # Increase recursion limit to handle potentially deep bookmark trees safely
    sys.setrecursionlimit(MAX_RECURSION_DEPTH + 50) 
    
    print("--- Chrome Bookmark Reorganizer (Deep Merge by Canonical Path) ---")
    print("This tool will consolidate bookmarks based on their full, unique folder paths.")
    print("It aims to restore a clean, intended folder structure by merging duplicates.")
    print("It handles internal path redundancies (e.g., 'A > B > A' becomes 'B > A').")
    
    try:
        input("\n🔴 IMPORTANT: Please ensure Google Chrome is COMPLETELY CLOSED, then press Enter to continue...")
    except (RuntimeError, EOFError) as e:
        print(f"\n❌ Error: Failed to read input from the console ({type(e).__name__}: {e}).")
        print("This often happens when running the script in an environment where standard input (sys.stdin) is not available.")
        print("Please try running the script directly from a standard command prompt or terminal (e.g., cmd.exe on Windows, Terminal.app on macOS/Linux).")
        return
    except Exception as e:
        print(f"\n❌ An unexpected error occurred while waiting for user input: {e}")
        print("Please try running the script directly from a standard command prompt or terminal.")
        return

    bookmark_path = get_chrome_bookmark_path()
    if not bookmark_path:
        _wait_for_exit()
        return

    # Create a timestamped backup for extra safety.
    backup_path = bookmark_path.with_suffix(f".{int(Path(bookmark_path).stat().st_mtime)}.backup")
    try:
        shutil.copy2(bookmark_path, backup_path)
        print(f"✅ Successfully created backup: {backup_path.name}")
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        print("Please ensure you have write permissions to the directory where Chrome stores bookmarks.")
        _wait_for_exit()
        return

    bookmark_data = load_bookmarks(bookmark_path)
    if not bookmark_data:
        _wait_for_exit()
        return

    print("\n🔎 Reading and organizing all bookmarks...")
    # `collected_bookmarks` will hold the final, deeply merged structure.
    # It's a nested dictionary where leaf nodes are lists of bookmark dicts.
    collected_bookmarks = {} 
    seen_urls = set() # To track and deduplicate bookmarks by URL

    roots = bookmark_data.get("roots", {})
    if not roots:
        print("❌ Error: Bookmarks file does not contain a 'roots' section. It might be corrupted.")
        _wait_for_exit()
        return

    for root_name, root_node in roots.items():
        if root_name in CHROME_ROOT_NAMES: # Process only standard Chrome roots
            print(f"   - Scanning '{root_name}'...")
            # Start recursion with the Chrome root name as the initial path part
            collect_bookmarks_recursively(root_node, [root_name], collected_bookmarks, seen_urls)
        # Else: If there are non-standard root names, they will be ignored by this process.
        # All reorganized bookmarks will go under DESTINATION_ROOT_NAME.

    total_unique_bookmarks = len(seen_urls)
    print(f"\n📊 Analysis Complete: Found {total_unique_bookmarks} unique bookmarks.")
    
    if not collected_bookmarks:
        print("No bookmarks found or collected after analysis. Nothing to reorganize.")
        _wait_for_exit()
        return

    print("🗑️ Clearing old bookmark structure completely...")
    # Clear all existing children under all standard roots to prepare for the new structure
    for root_name in roots.keys():
        if root_name in CHROME_ROOT_NAMES and 'children' in bookmark_data['roots'][root_name]:
            bookmark_data['roots'][root_name]['children'] = []

    print(f"🏗️ Building new, clean, and merged structure under '{DESTINATION_ROOT_NAME}'...")
    
    # Convert our collected_bookmarks dictionary into Chrome's standard JSON format
    new_root_children = build_chrome_json_structure(collected_bookmarks)

    # Place the new structure under the DESTINATION_ROOT_NAME (e.g., "bookmark_bar")
    if DESTINATION_ROOT_NAME in bookmark_data["roots"]:
        bookmark_data["roots"][DESTINATION_ROOT_NAME]["children"] = new_root_children
    else:
        # If the destination root itself doesn't exist (very rare for "bookmark_bar"),
        # we'd need to create it or place it under the first available root.
        # For simplicity, we assume DESTINATION_ROOT_NAME always exists as a base root.
        print(f"❌ Error: The destination root '{DESTINATION_ROOT_NAME}' was not found in the bookmarks file.")
        print("Cannot place reorganized bookmarks. Please ensure your bookmarks file is valid.")
        _wait_for_exit()
        return

    print("💾 Saving changes to bookmarks file...")
    save_bookmarks(bookmark_data, bookmark_path)

    print("\n✅✅✅ Success! Your bookmarks have been reorganized and cleaned.")
    print(f"Your original bookmarks file was saved as '{backup_path.name}'.")
    _wait_for_exit()

if __name__ == "__main__":
    main()