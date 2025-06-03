import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import datetime
import os
import sys
import time
import csv
import random
import pandas as pd
import folium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

# --- Setup correct path to chromedriver ---
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)
chromedriver_path = os.path.join(base_path, "chromedriver-mac")

# --- App Settings ---
DATE_OPTIONS = [
    "Yesterday", "Last 3 Days", "Last Week", "Last 2 Weeks", "Last 28 Days",
    "Last Month", "Last 3 Months", "Last 6 Months", "Last Year"
]

DROPDOWN_MAP = {
    "Yesterday": "Yesterday", "Last 3 Days": "3 days", "Last Week": "1 week",
    "Last 2 Weeks": "2 weeks", "Last 28 Days": "28 days", "Last Month": "1 month",
    "Last 3 Months": "3 months", "Last 6 Months": "6 months", "Last Year": "1 year"
}

ZIP_CENTER = (32.972, -96.737)  # Placeholder center

# --- GUI Setup ---
root = tk.Tk()
root.title("CrimeScout (Mac)")
root.geometry("740x520")

frame_input = tk.Frame(root)
frame_input.pack(pady=10)

tk.Label(frame_input, text="ZIP Code:").grid(row=0, column=0, padx=5)
zip_entry = tk.Entry(frame_input, width=10)
zip_entry.grid(row=0, column=1)

tk.Label(frame_input, text="Timeframe:").grid(row=0, column=2, padx=5)
timeframe_var = tk.StringVar()
timeframe_combo = ttk.Combobox(frame_input, textvariable=timeframe_var, values=DATE_OPTIONS, state='readonly')
timeframe_combo.grid(row=0, column=3)
timeframe_combo.current(0)

console = scrolledtext.ScrolledText(root, height=20, width=90, state='disabled', font=("Consolas", 10))
console.pack(padx=10, pady=10)

def log(message):
    console.config(state='normal')
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    console.insert(tk.END, f"[{timestamp}] {message}\n")
    console.see(tk.END)
    console.config(state='disabled')

# --- Main Worker Function ---
def run_scraper():
    zip_code = zip_entry.get().strip()
    timeframe = timeframe_var.get()
    if not zip_code or not timeframe:
        log("⚠️ Please enter a ZIP code and timeframe.")
        return

    log(f"🚀 Launching scraper with ZIP: {zip_code}, Timeframe: {timeframe}")
    mapped_timeframe = DROPDOWN_MAP[timeframe]

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")

    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        driver.get("https://communitycrimemap.com/")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Continue']]"))).click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter city, address or coordinates']"))).send_keys(zip_code + Keys.ENTER)

        log("⏳ Waiting for map pins to load...")
        time.sleep(20)

        try:
            address_label = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'location-label')]")))
            state_abbr = address_label.text.strip().split(",")[-1].strip().split(" ")[0]
        except:
            state_abbr = "UNK"

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.filter-options-btn"))).click()
        time.sleep(2)

        dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-select[contains(@class, 'quick-dates')]")))
        driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
        dropdown.click()
        wait.until(EC.element_to_be_clickable((By.XPATH, f"//mat-option//span[normalize-space(text())='{mapped_timeframe}']"))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@title='Apply Filters']"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@title='Data Grid']"))).click()
        time.sleep(5)

        data = []
        headers = []
        while True:
            table = wait.until(EC.presence_of_element_located((By.XPATH, "//table")))
            rows = table.find_elements(By.TAG_NAME, "tr")
            if not headers:
                headers = [th.text for th in rows[0].find_elements(By.TAG_NAME, "th")]
            for row in rows[1:]:
                cells = [td.text for td in row.find_elements(By.TAG_NAME, "td")]
                data.append(cells)
            next_btn = driver.find_element(By.XPATH, "//button[@aria-label='Next page']")
            if "disabled" in next_btn.get_attribute("class"):
                break
            next_btn.click()
            time.sleep(2)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        safe_tf = mapped_timeframe.replace(" ", "").lower()
        filename = f"crime_data_{zip_code}_{state_abbr}_{safe_tf}_{timestamp}.csv"
        csv_path = os.path.join(base_path, filename)

        with open(csv_path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)

        log(f"✅ Scraped {len(data)} rows. Saved to {csv_path}")

        # --- Map Generation ---
        df = pd.read_csv(csv_path)
        crimes = df['Class'].dropna().unique()
        color_list = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen', 'pink', 'gray', 'black']
        color_map = {crime: color_list[i % len(color_list)] for i, crime in enumerate(crimes)}
        crime_map = folium.Map(location=ZIP_CENTER, zoom_start=13, control_scale=True)

        feature_groups = {
            crime: folium.FeatureGroup(
                name=f'<span style="color:{color_map[crime]}; font-weight:bold;">&#11044;</span> {crime}',
                show=True
            ) for crime in crimes
        }

        for _, row in df.iterrows():
            crime_type = row['Class']
            if pd.isna(crime_type): continue
            label = f"<b>{row['Class']}</b><br>{row['Crime']}<br>{row['Date/Time']}<br>{row['Agency']}<br>{row['Address']}"
            lat = ZIP_CENTER[0] + random.uniform(-0.01, 0.01)
            lon = ZIP_CENTER[1] + random.uniform(-0.01, 0.01)
            folium.CircleMarker(
                location=(lat, lon),
                radius=8,
                popup=folium.Popup(label, max_width=300),
                fill=True,
                fill_color=color_map[crime_type],
                fill_opacity=0.85,
                stroke=False
            ).add_to(feature_groups[crime_type])

        for fg in feature_groups.values():
            fg.add_to(crime_map)

        folium.LayerControl(collapsed=False).add_to(crime_map)
        map_file = f"crime_map_{timestamp}.html"
        map_path = os.path.join(base_path, map_file)
        crime_map.save(map_path)

        log(f"🗺️ Map saved to {map_path}")
        os.system(f"open '{map_path}'")

    except TimeoutException:
        log("❌ Timeout waiting for page elements.")
    except Exception as e:
        log(f"❌ Error: {e}")
    finally:
        driver.quit()

# --- GUI Button ---
start_btn = tk.Button(
    root,
    text="Start Scraping",
    command=lambda: threading.Thread(target=run_scraper, daemon=True).start(),
    font=("Arial", 12, "bold"),
    bg="green",
    fg="white"
)
start_btn.pack(pady=10)

root.mainloop()
