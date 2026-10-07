
import csv
import logging
import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://opensource-demo.orangehrmlive.com"
LOGIN_URL = f"{BASE_URL}/web/index.php/auth/login"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

WAIT_TIMEOUT = 15  


def _build_logger(run_id):
    """One log file per automation run, so each dashboard submission is traceable."""
    logger = logging.getLogger(f"orangehrm_run_{run_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear() 

    log_path = os.path.join(LOG_DIR, f"run_{run_id}.log")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    return logger, log_path


def _get_driver(headless=False):
    """
    Create the Chrome WebDriver instance.

    webdriver-manager downloads/caches the correct chromedriver binary for the
    Chrome version installed on this machine, so we don't have to manually
    download and manage chromedriver ourselves.
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    
    driver.implicitly_wait(3)
    return driver


def _screenshot(driver, name, logger):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    try:
        driver.save_screenshot(path)
        logger.info(f"Screenshot saved: {path}")
    except Exception as exc:
        logger.warning(f"Could not save screenshot '{name}': {exc}")
    return path


def login(driver, wait, username, password, logger):
    logger.info("Opening login page")
    driver.get(LOGIN_URL)

    username_field = driver.find_element(By.NAME, "username")
    password_field = driver.find_element(By.NAME, "password")

    username_field.clear()
    username_field.send_keys(username)
    password_field.clear()
    password_field.send_keys(password)

    login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    login_button.click()
    logger.info("Submitted login form")


    try:
        wait.until(EC.url_contains("/dashboard"))
    except TimeoutException:
        try:
            error_el = driver.find_element(By.CSS_SELECTOR, ".oxd-alert-content-text")
            raise RuntimeError(f"Login failed: {error_el.text}")
        except NoSuchElementException:
            raise RuntimeError("Login failed: dashboard did not load and no error message was found")

    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".oxd-topbar-header")))
    logger.info("Login successful, dashboard loaded")


def navigate_to_add_employee(driver, wait, logger):
    logger.info("Navigating to PIM > Add Employee")

    driver.get(f"{BASE_URL}/web/index.php/pim/addEmployee")


    wait.until(EC.presence_of_element_located((By.NAME, "firstName")))
    logger.info("Add Employee form loaded")


def add_employee(driver, wait, first_name, last_name, employee_id, logger):
    logger.info(f"Filling employee form: {first_name} {last_name} (ID {employee_id})")

    first_name_field = driver.find_element(By.NAME, "firstName")
    last_name_field = driver.find_element(By.NAME, "lastName")

    first_name_field.clear()
    first_name_field.send_keys(first_name)
    last_name_field.clear()
    last_name_field.send_keys(last_name)


    if employee_id:
        try:
            employee_id_field = driver.find_element(
                By.XPATH, "//label[text()='Employee Id']/../following-sibling::div//input"
            )
            employee_id_field.clear()
            employee_id_field.send_keys(employee_id)
        except NoSuchElementException:
            logger.warning("Employee Id field not found by label — leaving auto-generated ID as-is")


    try:
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".oxd-form-loader")))
    except TimeoutException:
        pass  
    save_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Save']"))
    )
    save_button.click()
    logger.info("Submitted Add Employee form")

    wait.until(EC.url_contains("viewPersonalDetails"))
    logger.info("Employee saved — redirected to Personal Details page")


def verify_employee_created(driver, wait, first_name, last_name, logger):
    logger.info("Verifying employee name appears on the Personal Details page")

    locator = (By.CSS_SELECTOR, ".orangehrm-edit-employee-name h6")
    wait.until(lambda d: d.find_element(*locator).text.strip() != "")
    full_name = driver.find_element(*locator).text.strip()
    expected = f"{first_name} {last_name}".strip()

    if expected.lower() not in full_name.lower():
        raise RuntimeError(f"Verification failed: expected '{expected}', page shows '{full_name}'")

    logger.info(f"Verified: '{full_name}' is shown on the employee page")
    return full_name


def extract_employee_list(driver, wait, logger, max_rows=20):
    logger.info("Navigating to Employee List to extract data")
    driver.get(f"{BASE_URL}/web/index.php/pim/viewEmployeeList")

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".oxd-table-body")))
    time.sleep(1)  

    rows = driver.find_elements(By.CSS_SELECTOR, ".oxd-table-body .oxd-table-card")
    logger.info(f"Found {len(rows)} employee rows")

    data = []
    for row in rows[:max_rows]:
        cells = row.find_elements(By.CSS_SELECTOR, ".oxd-table-cell")
        texts = [c.text.strip() for c in cells]
        if len(texts) >= 5:
            data.append({
                "employee_id": texts[1],
                "first_name": texts[2],
                "middle_name": texts[3],
                "last_name": texts[4],
            })

    return data


def export_to_csv(data, run_id, logger):
    if not data:
        return None
    csv_path = os.path.join(EXPORT_DIR, f"employees_{run_id}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["employee_id", "first_name", "middle_name", "last_name"])
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"Exported {len(data)} rows to {csv_path}")
    return csv_path


def logout(wait, logger):
    logger.info("Logging out")
    user_dropdown = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".oxd-userdropdown-tab")))
    user_dropdown.click()

    logout_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[text()='Logout']")))
    logout_link.click()

    wait.until(EC.url_contains("/auth/login"))
    logger.info("Logged out successfully")


def run_orangehrm_flow(username, password, first_name, last_name, employee_id, headless=False):
    """
    Orchestrates the full flow and returns a result dict for the dashboard to render.
    This is the only function app.py needs to call.
    """
    run_id = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    logger, log_path = _build_logger(run_id)

    result = {
        "run_id": run_id,
        "status": "failed",
        "message": "",
        "employee": {
            "first_name": first_name,
            "last_name": last_name,
            "employee_id": employee_id,
        },
        "verified_name": None,
        "table_data": [],
        "csv_path": None,
        "screenshots": {},
        "log_path": log_path,
    }

    driver = None
    try:
        driver = _get_driver(headless=headless)
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        login(driver, wait, username, password, logger)
        time.sleep(3)
        result["screenshots"]["after_login"] = _screenshot(driver, f"{run_id}_after_login", logger)

        navigate_to_add_employee(driver, wait, logger)
        time.sleep(3)
        result["screenshots"]["before_add"] = _screenshot(driver, f"{run_id}_before_add", logger)

        add_employee(driver, wait, first_name, last_name, employee_id, logger)

        verified_name = verify_employee_created(driver, wait, first_name, last_name, logger)
        result["verified_name"] = verified_name
        time.sleep(3)
        result["screenshots"]["after_add"] = _screenshot(driver, f"{run_id}_after_add", logger)

        table_data = extract_employee_list(driver, wait, logger)
        result["table_data"] = table_data
        result["csv_path"] = export_to_csv(table_data, run_id, logger)

        logout(wait, logger)

        result["status"] = "success"
        result["message"] = f"Employee '{verified_name}' created and verified successfully."

    except Exception as exc:
        logger.error(f"Automation failed: {exc}")
        result["message"] = str(exc)
        if driver:
            result["screenshots"]["error"] = _screenshot(driver, f"{run_id}_error", logger)

    finally:
        if driver:
            driver.quit()  
            logger.info("Browser closed")

    return result
