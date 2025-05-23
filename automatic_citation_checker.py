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
from typing import List, Tuple, Optional
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
    """Parse command-line arguments for PDF name, reference page range, and
    browser."""
    parser = argparse.ArgumentParser(
        description="Check PDF references via Google Scholar."
    )
    parser.add_argument("pdf_name", type=str, help="Path to the PDF file.")
    parser.add_argument(
        "--references_page_range",
        type=str,
        help=("Page range for references, e.g., '23-25' (inclusive). If not"
              "given, will auto-detect using PDF outline."),
    )
    parser.add_argument(
        "--browser",
        type=str,
        choices=["firefox", "chrome", "safari"],
        default="firefox",
        help="Browser to use for Selenium (default: firefox).",
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


def get_webdriver(browser: str):
    """
    Return a Selenium webdriver instance for the specified browser.
    Args:
        browser: Name of the browser ('firefox', 'chrome', 'safari').
    Returns:
        Selenium webdriver instance.
    """
    if browser == "firefox":
        return webdriver.Firefox()
    elif browser == "chrome":
        return webdriver.Chrome()
    elif browser == "safari":
        return webdriver.Safari()
    elif browser == "edge":
        return webdriver.Edge()
    elif browser == "opera":
        return webdriver.Opera()
    elif browser == "brave":
        return webdriver.Brave()
    elif browser == "internet_explorer":
        raise NotImplementedError(
            "Really? Internet Explorer? Good luck with that."
        )
    else:
        raise ValueError(f"Unsupported browser: {browser}")


def check_citations_via_scholar(
    references: List[str], browser: str
) -> Tuple[List[str], List[str]]:
    """
    For each reference, search Google Scholar and retrieve the APA citation.
    Args:
        references: List of reference strings.
        browser: Browser to use for Selenium.
    Returns:
        Tuple of (scholar_citations, ratings).
    """
    driver = get_webdriver(browser)
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


def find_references_section_by_outline(pdf_name: str) -> Optional[List[int]]:
    """
    Find the 'References' section using PDF outlines/bookmarks.
    Returns a list of page numbers if found, else None.
    """
    reader = PdfReader(pdf_name)
    if not hasattr(reader, "outlines") or not reader.outlines:
        return None

    outlines = reader.outlines
    num_pages = len(reader.pages)
    start_page = None
    end_page = None

    def flatten(outlines):
        for item in outlines:
            if isinstance(item, list):
                yield from flatten(item)
            else:
                yield item

    # Find the 'References' outline
    for outline in flatten(outlines):
        title = getattr(outline, "title", str(outline))
        if title.strip().lower() == "references":
            start_page = reader.get_destination_page_number(outline)
            break

    if start_page is None:
        return None

    # Find the next outline after 'References'
    next_pages = []
    found = False
    for outline in flatten(outlines):
        title = getattr(outline, "title", str(outline))
        page_num = reader.get_destination_page_number(outline)
        if found and page_num > start_page:
            next_pages.append(page_num)
        if page_num == start_page:
            found = True
    if next_pages:
        end_page = min(next_pages) - 1
    else:
        end_page = num_pages - 1

    return list(range(start_page, end_page + 1))


def main():
    args = parse_args()
    if args.references_page_range is not None:
        page_range = parse_page_range(args.references_page_range)
    else:
        page_range = find_references_section_by_outline(args.pdf_name)
        if page_range is None:
            print("Could not auto-detect the references section in the PDF"
                  " outline/bookmarks.")
            return
        print(f"Automatically detected reference pages: {page_range}")
    references = extract_references(args.pdf_name, page_range)
    scholar_citations, ratings = check_citations_via_scholar(
        references, args.browser
    )
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
