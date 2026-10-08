"""
Flask dashboard: collects login + employee details from the browser,
triggers the Selenium flow in automation.py, and renders the result.

Nothing in this file hardcodes credentials — username/password come in on
every request via the submitted form (per the assignment requirement).
"""

from flask import Flask, render_template, request

from automation import run_orangehrm_flow

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", result=None)


@app.route("/run-automation", methods=["GET", "POST"])
def run_automation():

    if request.method == "GET":
        return render_template("index.html", result=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    employee_id = request.form.get("employee_id", "").strip()
    headless = request.form.get("headless") == "on"

    result = run_orangehrm_flow(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        employee_id=employee_id,
        headless=headless,
    )

    return render_template("index.html", result=result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
