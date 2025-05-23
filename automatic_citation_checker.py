# -*- coding: utf-8 -*-
"""

README:

This is a quick and dirty script for checking the references of a student
paper for potential hallucinated examples. It extracts all references from a
.PDF file, opens a Firefox window and searches for that exact citation on
Google Scholar. It gets the APA format, and lets you evaluate if it looks 
suspicious or not.

Future implementations can probably do a simple text distance check to
determine without manual control if the student's reference and the top result
are similar enough.

NOTE: it currently needs your input for which page range the references are on!
NOTE: You will probably have to fill in some captchas yourself :/

PACKAGES:
    selenium:    '4.32.0'
    pypdf:       '5.5.0'
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from pypdf import PdfReader
import pandas as pd
import re

# =============================================================================
#                         FILL THIS IN BEFORE RUNNING
# =============================================================================

pdf_name = r"some_thesis_here.pdf"
references_page_range = list(range(23, 26))

# =============================================================================
#                         GET REFERENCES WITH CITATIONS
# =============================================================================

reader = PdfReader(pdf_name)

references = []
for p_num in list(references_page_range):
    page = reader.pages[p_num]  # 23, 24
    # extract text but with layout preserved!
    text = page.extract_text(extraction_mode="layout")
    text_bits = text.split("\n\n")
    # split on newline if newline is NOT surrounded by spaces
    t = re.split(r"\n(?!\s{4,})", text_bits[-1])
    for ref in t:
        # if ref empty or starts with spaces or newline, ignore (because
        # probably continuation of reference from previous page)
        if ref != "" and not ref.startswith("  ") and not ref.startswith("\n"):
            references.append(ref)

# =============================================================================
#                    CHECK CITATIONS VIA GOOGLE SCHOLAR
# =============================================================================


# Open Firefox
driver = webdriver.Firefox()
driver.set_window_size(800, 800)

scholar_citations = []
ratings = []
# get citations from google scholar per reference:
for ref in references:
    driver.get("https://scholar.google.com/")
    ActionChains(driver).send_keys(ref).perform()
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    driver.implicitly_wait(1)
    # get citation button
    citation_button = WebDriverWait(driver, 60).until(
        EC.visibility_of_element_located((By.CLASS_NAME, "gs_or_cit"))
    )
    # citation_button = driver.find_elements(By.CLASS_NAME, "gs_or_cit")
    citation_button.click()
    citations = driver.find_elements(By.CLASS_NAME, "gs_citr")
    # print APA citation
    if len(citations) == 0:
        break
    apa_cite = citations[1].text
    scholar_citations.append(apa_cite)
    print(f"\n----\nThis is the student's citation: \n{ref}\n")
    print(f"This is the top result on Google Scholar: \n{apa_cite}\n\n")
    # wait until user presses enter
    rating = input("Press enter to continue or 'N' if something seems off: ")
    ratings.append(rating)

print("DONE! Exiting now...")
# end driver
driver.close()

# =============================================================================
#                   MAKE OUTPUT DATAFRAME
# =============================================================================

output = pd.DataFrame(
    {
        "StudentRef": references,
        "ScholarRef": scholar_citations,
        "Rating": ratings,
    }
)


print(output)
