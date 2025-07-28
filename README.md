# Chrome Bookmark Cleaner: Smart Merge & Reorganizer

This Python script is designed to help you clean up, deduplicate, and reorganize your Google Chrome bookmarks into a logical, consolidated structure. It intelligently merges bookmarks from various locations into canonical (meaningful) paths, reducing clutter and making your bookmarks easier to navigate.

## 🌟 Features

* **Intelligent Deduplication:** Identifies and consolidates bookmarks with the same URL, placing them in a single, defined location.
* **Path Canonicalization:** Determines a "meaningful" path for each bookmark by:
    * Ignoring default Chrome root folders (e.g., "Bookmarks Bar", "Other Bookmarks", "Mobile Bookmarks").
    * Applying internal path deduplication (e.g., `FolderA > FolderB > FolderA > Link` becomes `FolderB > FolderA > Link`).
* **Selective Folder Flattening:** Allows you to define specific top-level parent folders (e.g., "More") that, if encountered, will cause all bookmarks within them to be flattened to just their deepest folder name. This is crucial for merging content from temporary or generic import folders.
* **Hierarchical Reconstruction:** Rebuilds your bookmark structure based on the determined canonical paths, creating new folders as needed.
* **Safety First:** Automatically creates a timestamped backup of your original Chrome Bookmarks file before making any changes.

## 💡 How it Works (Under the Hood)

The script works by:

1.  **Locating the Chrome Bookmarks file:** It finds the `Bookmarks` JSON file used by Chrome on your operating system.
2.  **Parsing the JSON:** It reads the entire bookmark tree from the file.
3.  **Collecting & Canonicalizing Bookmarks:**
    * It recursively traverses every bookmark and folder.
    * For each bookmark, it constructs its full path.
    * It then applies a `get_canonical_path_segments` function which implements the core logic:
        * It removes Chrome's default root names (e.g., "Bookmarks Bar").
        * It checks if the first *user-defined* parent folder is in the `FLATTENING_INITIATOR_PARENTS` list. If so, the canonical path is just the deepest folder name (e.g., `Bookmarks > More > Bread` becomes just `Bread`).
        * Otherwise, it applies an internal path deduplication logic (e.g., `Work > Projects > Work > MyDoc` becomes `Projects > Work > MyDoc`) to create the canonical path.
    * It stores bookmarks under these canonical paths in an internal, consolidated dictionary, using the URL as a key for deduplication.
4.  **Rebuilding the Structure:**
    * It completely clears the existing children from your primary Chrome bookmark roots (like "Bookmarks Bar").
    * It then converts the consolidated internal dictionary back into Chrome's JSON format, creating folders for each segment of the canonical paths.
    * All reorganized bookmarks are placed under the `bookmark_bar` root (which corresponds to your visible "Bookmarks Bar" in Chrome).
5.  **Saving Changes:** The modified bookmark data is saved back to the Chrome Bookmarks file.

## 🚀 Usage

### Prerequisites

* Python 3 installed on your system.
* Git (if you're cloning this repository).
* **IMPORTANT:** Ensure Google Chrome is **completely closed** before running the script.

### Steps

1.  **Download the script:**
    * Clone this repository: `git clone https://github.com/anovul/chrome-bookmark-cleaner.git`
    * Navigate into the project directory: `cd chrome-bookmark-cleaner`
    * Or, simply download the `bookmark_cleaner.py` file directly.

2.  **Configure (Optional, but Recommended):**
    Open `bookmark_cleaner.py` in a text editor and review the `CONFIGURATION` section near the top.

    * `DESTINATION_ROOT_NAME`: This is typically `bookmark_bar` for your main bookmarks bar.
    * `CHROME_ROOT_NAMES`: Standard Chrome root folders; usually fine as is.
    * `FLATTENING_INITIATOR_PARENTS`: **This is key!** Add any folder names here (e.g., `"More"`, `"Imported HTML"`, `"Unsorted Bookmarks"`) that you want to be treated as "disposable" top-level containers, causing their contents to flatten to just the deepest folder name.

3.  **Run the script:**
    Open your Command Prompt (CMD on Windows) or Terminal (macOS/Linux), navigate to the directory where you saved `bookmark_cleaner.py`, and run:

    ```bash
    python bookmark_cleaner.py
    ```

4.  **Follow the prompts:** The script will guide you through the process, prompting you to close Chrome and confirming steps.

## ⚙️ Configuration Details

The script's behavior can be customized via constants at the top of the `bookmark_cleaner.py` file:

* **`DESTINATION_ROOT_NAME = "bookmark_bar"`**:
    This defines the Chrome root folder where all your reorganized bookmarks will be placed. `bookmark_bar` corresponds to your main Chrome Bookmarks Bar.

* **`FLATTENING_INITIATOR_PARENTS = {"More"}`**:
    This set contains names of parent folders that, if they are the *first user-defined segment* in a bookmark's path, will cause the bookmark's canonical path to be flattened to only its deepest folder.
    * Example: A bookmark at `Bookmarks Bar > More > My Articles > Interesting Article` will be canonicalized to `My Articles > Interesting Article`. If `More` is in this set, it will be `Interesting Article`.
    * This is ideal for consolidating bookmarks from generic import folders (`Imported Chrome`, `More`, `Unsorted Bookmarks`).

## ⚠️ Important Notes & Warnings

* **CLOSE CHROME:** It is absolutely critical that Google Chrome is completely closed before running the script. Chrome writes to the `Bookmarks` file constantly, and running the script while Chrome is open can lead to file corruption or lost changes.
* **BACKUP:** The script automatically creates a timestamped backup of your `Bookmarks` file. However, it's always a good idea to make an additional manual backup if you have critical bookmarks.
* **USE AT YOUR OWN RISK:** While tested, this script modifies system files. By using it, you accept any potential risks. Review the code if you have concerns.

---