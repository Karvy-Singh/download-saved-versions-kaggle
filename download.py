import os
import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

NOTEBOOK_URL = "https://www.kaggle.com/code/YOUR_USERNAME/NOTEBOOK_NAME"

DOWNLOAD_DIR = os.path.expanduser("~/Downloads/kaggle_versions")

MAX_ATTEMPTS_PER_VERSION = 3

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

options = Options()

# We need to use an already running session of chromium with kaggle logged in,
# coz sometimes it otherwise gives error on logging in on selenium browser session coz it is not authorized

options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

driver = webdriver.Chrome(options=options)

wait = WebDriverWait(driver, 20)

print("Connected to existing Chromium.")
print("Current page:", driver.current_url)


# Because we are attaching to an ALREADY RUNNING browser,
# ChromeOptions download preferences won't work.
#
# Instead, tell Chromium through DevTools where downloads
# should be stored.

try:
    driver.execute_cdp_cmd(
        "Browser.setDownloadBehavior",
        {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_DIR,
            "eventsEnabled": True,
        },
    )

except Exception:
    # Fallback for some Chromium versions
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_DIR,
        },
    )


VERSION_ROWS = "ul.MuiList-root > div[role='button']"
HISTORY_BUTTON = (
    "//button[.//span[normalize-space()='history'] "
    "and .//*[contains(normalize-space(), 'Version')]]"
)
VIEW_FULL_VERSION_LINK = (
    "//a[contains(@href, 'scriptVersionId=')]"
    "[.//*[normalize-space()='View full version']]"
)


# HELPER funcs


def js_click(element):
    """
    Scroll to element and click using JS.
    More reliable on React/Kaggle UI.
    """

    driver.execute_script(
        """
        arguments[0].scrollIntoView({
            block: 'center',
            inline: 'center'
        });
        """,
        element,
    )

    time.sleep(0.4)

    driver.execute_script(
        "arguments[0].click();",
        element,
    )


def wait_for_download(previous_files=None, timeout=120):
    """
    Wait for a file to be created or overwritten and for .crdownload
    temporary files to disappear.
    """

    if previous_files is None:
        previous_files = {}

    start = time.time()

    while time.time() - start < timeout:

        current_files = get_download_snapshot()
        changed_files = [
            name
            for name, details in current_files.items()
            if previous_files.get(name) != details
        ]
        partial_files = [name for name in current_files if name.endswith(".crdownload")]

        if changed_files and not partial_files:
            time.sleep(1)
            final_files = get_download_snapshot()
            return [
                name
                for name, details in final_files.items()
                if previous_files.get(name) != details
                and not name.endswith(".crdownload")
            ]

        time.sleep(0.5)

    raise TimeoutException("Download did not finish within timeout.")


def get_download_snapshot():
    """Return size and modification time for every file in the directory."""

    snapshot = {}

    for name in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, name)

        try:
            stat = os.stat(path)
        except FileNotFoundError:
            continue

        if os.path.isfile(path):
            snapshot[name] = (stat.st_size, stat.st_mtime_ns)

    return snapshot


def add_version_to_filenames(filenames, version_name):
    """Add the Kaggle version name to each downloaded filename."""

    version_tag = re.sub(r"[^A-Za-z0-9._-]+", "_", version_name).strip("._-")
    version_tag = version_tag or "version"
    renamed_files = []

    for filename in filenames:
        source = os.path.join(DOWNLOAD_DIR, filename)
        stem, extension = os.path.splitext(filename)
        destination_name = f"{stem}_{version_tag}{extension}"
        destination = os.path.join(DOWNLOAD_DIR, destination_name)

        suffix = 2
        while os.path.exists(destination):
            destination_name = f"{stem}_{version_tag}_{suffix}{extension}"
            destination = os.path.join(DOWNLOAD_DIR, destination_name)
            suffix += 1

        os.rename(source, destination)
        renamed_files.append(destination_name)

    return renamed_files


def get_version_rows():
    """
    Find version rows inside Kaggle Version History.
    """

    return wait.until(
        EC.presence_of_all_elements_located(
            (
                By.CSS_SELECTOR,
                VERSION_ROWS,
            )
        )
    )


def version_history_is_open():
    """Return whether the history drawer intersects the browser viewport."""

    rows = driver.find_elements(By.CSS_SELECTOR, VERSION_ROWS)

    if not rows:
        return False

    return driver.execute_script(
        """
        const rect = arguments[0].getBoundingClientRect();
        return rect.left < window.innerWidth && rect.right > 0;
        """,
        rows[0],
    )


def open_version_history():
    """
    Click Kaggle's Version history control.
    """

    wait.until(EC.presence_of_element_located((By.XPATH, HISTORY_BUTTON)))

    if not version_history_is_open():
        history = driver.find_element(By.XPATH, HISTORY_BUTTON)
        js_click(history)

        wait.until(lambda _driver: version_history_is_open())

    rows = get_version_rows()

    print(f"Version history opened. " f"Found {len(rows)} rows.")


def open_version(index):
    """
    Open the options menu for one version-history entry.
    """

    rows = get_version_rows()

    if index >= len(rows):
        raise IndexError(f"Requested row {index}, " f"but only {len(rows)} rows exist.")

    row = rows[index]
    version_name = row.get_attribute("innerText").splitlines()[0]
    more_options = row.find_element(
        By.CSS_SELECTOR,
        "button[aria-label='More options for this version']",
    )

    js_click(more_options)

    # Wait specifically for View full version
    wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                VIEW_FULL_VERSION_LINK,
            )
        )
    )

    print("Selected:", version_name)


def click_view_full_version():
    """
    Click View full version.
    """

    link = wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                VIEW_FULL_VERSION_LINK,
            )
        )
    )

    version_url = link.get_attribute("href")

    js_click(link)

    wait.until(lambda current_driver: current_driver.current_url == version_url)


def click_download():
    """
    Click the Kaggle Download control and select the .ipynb format.
    """

    button = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[.//span[normalize-space()='file_download'] "
                "and .//span[normalize-space()='Download']]",
            )
        )
    )

    js_click(button)

    ipynb_item = wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//li[@role='menuitem']"
                "[.//span[normalize-space()='folder_zip'] "
                "and .//*[normalize-space()='Download .ipynb']]",
            )
        )
    )

    js_click(ipynb_item)


def return_to_history():
    """
    Go backwards until version-history rows are available.
    """

    for _ in range(3):
        driver.back()
        try:
            WebDriverWait(driver, 20).until(
                lambda current_driver: "scriptVersionId="
                not in current_driver.current_url
            )
            open_version_history()
            return
        except TimeoutException:
            continue

    raise RuntimeError("Could not return to Version History.")


def download_version(index, total_versions):
    print("=" * 60)
    print(f"VERSION {index + 1}/{total_versions}")
    print("=" * 60)

    rows = get_version_rows()
    row_text = rows[index].get_attribute("innerText").strip()
    version_name = row_text.splitlines()[0]
    print("History row:", repr(row_text))

    print("Opening version options...")
    open_version(index)

    print("Clicking View full version...")
    click_view_full_version()

    before_download = get_download_snapshot()

    print("Clicking Download...")
    click_download()

    print("Waiting for download to finish...")
    downloaded = wait_for_download(
        previous_files=before_download,
        timeout=180,
    )
    downloaded = add_version_to_filenames(downloaded, version_name)
    print("Downloaded:", downloaded)

    print("Returning to version history...")
    return_to_history()
    print("Ready for next version.")


# OPEN notebook

driver.get(NOTEBOOK_URL)

wait.until(
    EC.presence_of_element_located(
        (
            By.TAG_NAME,
            "body",
        )
    )
)

print("Notebook loaded.")

time.sleep(2)


open_version_history()

rows = get_version_rows()

total_versions = len(rows)

print()
print(f"Will process {total_versions} versions.")
print()


failed_versions = []

for index in range(total_versions):
    for attempt in range(1, MAX_ATTEMPTS_PER_VERSION + 1):
        try:
            download_version(index, total_versions)
            break
        except Exception as error:
            print()
            print(
                f"ERROR on history row {index + 1} "
                f"(attempt {attempt}/{MAX_ATTEMPTS_PER_VERSION}):"
            )
            print(error)

            if attempt == MAX_ATTEMPTS_PER_VERSION:
                failed_versions.append(index + 1)
                break

            print("Reloading the notebook before retrying...")
            driver.get(NOTEBOOK_URL)
            time.sleep(2)
            open_version_history()


print()
print("=" * 60)
print("FINISHED")
print("=" * 60)

print(
    "Downloads:",
    DOWNLOAD_DIR,
)

if failed_versions:
    print("Failed history rows:", failed_versions)
