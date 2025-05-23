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

import argparse
from typing import List, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from pypdf import PdfReader
import pandas as pd
import re


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for PDF name and reference page range."""
    parser = argparse.ArgumentParser(
        description="Check PDF references via Google Scholar."
    )
    parser.add_argument("pdf_name", type=str, help="Path to the PDF file.")
    parser.add_argument(
        "--references_page_range",
        type=str,
        required=True,
        help="Page range for references, e.g., '23-25' (inclusive).",
    )
    return parser.parse_args()


def parse_page_range(page_range_str: str) -> List[int]:
    """Parse a page range string like '23-25' into a list of integers."""
    start, end = map(int, page_range_str.split("-"))
    return list(range(start, end + 1))


def extract_references(
    pdf_name: str, references_page_range: List[int]
) -> List[str]:
    """
    Extract references from the specified pages of a PDF.
    Args:
        pdf_name: Path to the PDF file.
        references_page_range: List of page numbers to extract references from.
    Returns:
        List of extracted reference strings.
    """
    reader = PdfReader(pdf_name)
    references = []
    for p_num in references_page_range:
        page = reader.pages[p_num]
        text = page.extract_text(extraction_mode="layout")
        text_bits = text.split("\n\n")
        t = re.split(r"\n(?!\s{4,})", text_bits[-1])
        for ref in t:
            if (
                ref != ""
                and not ref.startswith("  ")
                and not ref.startswith("\n")
            ):
                references.append(ref)
    return references


def check_citations_via_scholar(
    references: List[str],
) -> Tuple[List[str], List[str]]:
    """
    For each reference, search Google Scholar and retrieve the APA citation.
    Args:
        references: List of reference strings.
    Returns:
        Tuple of (scholar_citations, ratings).
    """
    driver = webdriver.Firefox()
    driver.set_window_size(800, 800)
    scholar_citations = []
    ratings = []
    for ref in references:
        driver.get("https://scholar.google.com/")
        ActionChains(driver).send_keys(ref).perform()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        driver.implicitly_wait(1)
        citation_button = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "gs_or_cit"))
        )
        citation_button.click()
        citations = driver.find_elements(By.CLASS_NAME, "gs_citr")
        if len(citations) == 0:
            scholar_citations.append("")
            ratings.append("N")
            continue
        apa_cite = citations[1].text
        scholar_citations.append(apa_cite)
        print(f"\n----\nThis is the student's citation: \n{ref}\n")
        print(f"This is the top result on Google Scholar: \n{apa_cite}\n\n")
        rating = input(
            "Press enter to continue or 'N' if something seems off: "
        )
        ratings.append(rating)
    driver.close()
    return scholar_citations, ratings


def main():
    args = parse_args()
    page_range = parse_page_range(args.references_page_range)
    references = extract_references(args.pdf_name, page_range)
    scholar_citations, ratings = check_citations_via_scholar(references)
    output = pd.DataFrame(
        {
            "StudentRef": references,
            "ScholarRef": scholar_citations,
            "Rating": ratings,
        }
    )
    print(output)


if __name__ == "__main__":
    main()
