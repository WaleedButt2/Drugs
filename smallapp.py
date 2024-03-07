import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import threading
import streamlit.components.v1 as components
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
import requests
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
drugbank_base_url = "https://go.drugbank.com/drugs/"
health_canada_base_url = "https://health-products.canada.ca/dpd-bdpp/index-eng.jsp"
# Function to set up a WebDriver
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install(),options=chrome_options))
def search_drugbank(query, results):
    driver = setup_driver()
    driver.get("https://go.drugbank.com/releases/latest")
    
    search_field = driver.find_element(By.ID, "query") 
    search_field.send_keys(query)
    button = driver.find_element(By.CLASS_NAME, "search-query-button")
    button.click()

    summary_element = driver.find_element(By.CSS_SELECTOR, "dd.col-xl-10.col-md-9.col-sm-8 p")
    summary_text = summary_element.text
    
    drugbank_number_element = driver.find_element(By.CSS_SELECTOR, "dd.col-xl-4.col-md-9.col-sm-8")
    drugbank_number = drugbank_number_element.text

    try:
        chemical_Formula_elements = driver.find_elements(By.CSS_SELECTOR, "dd.col-xl-8.col-md-9.col-sm-8")
        chemical_Formula = chemical_Formula_elements[1].text
    except IndexError:
        chemical_Formula = "N/A"

    driver.quit()

    results['DrugBank'] = {
        "Summary": summary_text,
        "DrugBank Number": drugbank_number,
        "Protein Chemical Formula": chemical_Formula
    }
def fetch_and_display_content(url):
    response = requests.get('https://health-products.canada.ca' + url)
    soup = BeautifulSoup(response.content, 'html.parser')
    labels = soup.find_all('p', class_='col-sm-4')

    # Skip the first one and display the rest
    for label in labels[1:]:
        # Find the next <p> element which contains the actual information
        value = label.find_next('p')

        # Check if the value element exists and display its content
        if value:
            st.write(f"{label.text.strip()}: {value.text.strip()}")

def search_dpd(product, din, results):
    driver = setup_driver()
    driver.get("https://health-products.canada.ca/dpd-bdpp/")

    driver.find_element(By.ID, "product").send_keys(product)
    if din:
        driver.find_element(By.ID, "din").send_keys(din)
    driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()

    time.sleep(3)  # Wait for the page to load

    # Fetch the page source and load it into BeautifulSoup
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    driver.quit()  # Close the driver

    # Find the table rows
    rows = soup.find_all('tr')

    data = []
    links = []  # To store the links separately

    for row in rows:
        cols = row.find_all('td')
        if len(cols) > 0:  # This checks to ensure it's not a header row
            row_data = []
            for i, col in enumerate(cols):
                row_data.append(col.text.strip())  # Add the text from each column to row_data
                if i == 1:  # If this is the DIN column (second column)
                    # Extract the link from the DIN field
                    link = col.find('a')['href'] if col.find('a') else None
                    links.append(link)  # Save the link
            data.append(row_data)

    # Ensure the number of columns in 'data' matches the columns you specify here
    results['DPD'] = {
        "data": pd.DataFrame(data, columns=["Status", "DIN", "Company", "Product", "Class", "PM", "Schedule", "#", "A.I. Name", "Strength"]),
        "links": links  # Save the links separately
    }
def handle_button_click(button_id):
    st.session_state.clicked_button_id = button_id

if 'clicked_button_id' not in st.session_state:
    st.session_state.clicked_button_id = None

# Streamlit UI
st.title("Drug Product Search")
product_name = st.text_input("Product Name")
din_number = st.text_input("DIN Number (optional)")

if st.button("Search"):
    results = {}
    threads = []

    with st.spinner('Searching... Please wait'):
        # Thread for DrugBank search
        drugbank_thread = threading.Thread(target=search_drugbank, args=(product_name, results))
        threads.append(drugbank_thread)

        # Thread for Health Canada DPD search
        dpd_thread = threading.Thread(target=search_dpd, args=(product_name, din_number, results))
        threads.append(dpd_thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    # For DrugBank results:
    if 'DrugBank' in results:
        drugbank_base_url = "https://go.drugbank.com/"
        st.markdown(f"<a href='{drugbank_base_url}' target='_blank'>DrugBank Results for {product_name}</a>", unsafe_allow_html=True)
        for key, value in results['DrugBank'].items():
            st.write(f"{key}: {value}")

    # For Health Canada DPD results:
    if 'DPD' in results:
        st.write("DPD results found.")
        dpd_results = results['DPD']['data']
        links = results['DPD']['links']
        
        st.write("Displaying DataFrame:")
        st.dataframe(dpd_results)
        
        # Render buttons for each row and assign direct content fetching on click
        for index, row in dpd_results.iterrows():
            link = links[index]
            st.button(f"Scrape Details for {row['Product']} (DIN: {row['DIN']})", 
                      on_click=fetch_and_display_content, args=(link,))

# Outside the loop, check if content should be fetched and displayed
if st.session_state.clicked_button_id is not None:
    button_index = next(index for index, link in enumerate(links) if st.session_state.clicked_button_id in link)
    fetch_and_display_content(links[button_index])
    st.session_state.clicked_button_id = None




