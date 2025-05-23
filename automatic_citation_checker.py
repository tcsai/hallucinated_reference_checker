# -*- coding: utf-8 -*-
"""

README:

This is a less quick and dirty script for checking the references of a student
paper for potential hallucinated examples. It extracts tries to detect where
the references section starts, then extracts all references from the
.PDF file, opens a (specified) browser window and searches for that exact
citation on Google Scholar. It gets the APA format, and automatically
evaluates the edit distance between the student's reference and the
Google Scholar result. The script will then print a table with the
references, the Google Scholar result, and the edit distance.
The script is not perfect, and it will not work for all PDFs. It is
recommended to manually verify the results.

FIXME: if the reference is not found, the script will crash. It should
probably just return an empty string or None.
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
import difflib
import string


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
        help=(
            "Page range for references, e.g., '23-25' (inclusive). If not"
            "given, will auto-detect using PDF outline."
        ),
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


def normalize_reference(ref: str) -> str:
    """Lowercase, remove punctuation, and extra spaces."""
    ref = ref.lower()
    ref = ref.translate(str.maketrans("", "", string.punctuation))
    ref = re.sub(r"\s+", " ", ref)
    return ref.strip()


def edit_distance(a: str, b: str) -> int:
    """Compute edit distance using SequenceMatcher."""
    # difflib returns a ratio; convert to distance
    sm = difflib.SequenceMatcher(None, a, b)
    return int(max(len(a), len(b)) * (1 - sm.ratio()))


def check_citations_via_scholar(
    references: List[str], browser: str
) -> Tuple[List[str], List[int]]:
    """
    For each reference, search Google Scholar and retrieve the APA citation.
    Returns the scholar citations and their edit distances to the original.
    """
    driver = get_webdriver(browser)
    driver.set_window_size(800, 800)
    scholar_citations = []
    edit_distances = []
    for ref in references:
        # Check if the reference contains a year (4-digit number)
        if not re.search(r"\b\d{4}\b", ref):
            scholar_citations.append("No Year Found")
            edit_distances.append(999998)  # Large edit distance
            continue

        try:
            driver.get("https://scholar.google.com/")
            ActionChains(driver).send_keys(ref).perform()
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            driver.implicitly_wait(1)
            citation_button = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "gs_or_cit"))
            )
            citation_button.click()
            citations = driver.find_elements(By.CLASS_NAME, "gs_citr")
            if len(citations) == 0:
                # No citations found
                scholar_citations.append("Not Found")
                edit_distances.append(999999)  # Large edit distance
                continue
            apa_cite = citations[1].text
            scholar_citations.append(apa_cite)
            # Compute edit distance
            norm_ref = normalize_reference(ref)
            norm_apa = normalize_reference(apa_cite)
            dist = edit_distance(norm_ref, norm_apa)
            edit_distances.append(dist)
        except Exception as e:
            # Handle cases where Google Scholar fails to load or find results
            print(f"Error processing reference: {ref}. Error: {e}")
            scholar_citations.append("Error")
            edit_distances.append(999999)  # Large edit distance
    driver.close()
    return scholar_citations, edit_distances


def find_references_section_by_text(pdf_name: str) -> Optional[List[int]]:
    """
    Find the 'References' section by scanning for a page that starts with 
    'References' and ends before a page that starts with 'Appendix'.
    Returns a list of page numbers if found, else None.
    """
    reader = PdfReader(pdf_name)
    num_pages = len(reader.pages)
    start_page = None
    end_page = None

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        first_line = text.strip().split('\n', 1)[0].strip().lower()
        if first_line.startswith("references"):
            start_page = i
            break

    if start_page is None:
        return None

    # Find the first page after start_page that starts with 'Appendix'
    for i in range(start_page + 1, num_pages):
        text = reader.pages[i].extract_text() or ""
        first_line = text.strip().split('\n', 1)[0].strip().lower()
        if first_line.startswith("appendix"):
            end_page = i - 1
            break

    if end_page is None:
        end_page = num_pages - 1

    return list(range(start_page, end_page + 1))


def main():
    args = parse_args()
    if args.references_page_range is not None:
        page_range = parse_page_range(args.references_page_range)
    else:
        page_range = find_references_section_by_text(args.pdf_name)
        if page_range is None:
            print(
                "Could not auto-detect the references section in the PDF "
                "using outline or text search."
            )
            return
        print(f"Automatically detected reference pages: {page_range}")
    
    references = extract_references(args.pdf_name, page_range)
    scholar_citations, edit_distances = check_citations_via_scholar(
        references, args.browser
    )
    
    # Create the DataFrame
    output = pd.DataFrame(
        {
            "StudentRef": references,
            "ScholarRef": scholar_citations,
            "EditDistance": edit_distances,
        }
    )
    
    # Clean up whitespace in titles
    output["StudentRef"] = output["StudentRef"].str.strip()
    output["ScholarRef"] = output["ScholarRef"].str.strip()
    
    # Separate references with high edit distances
    not_found = output[output["EditDistance"] == 999999]
    no_year = output[output["EditDistance"] == 999998]
    
    # Filter out these rows from the main table
    output = output[(output["EditDistance"] != 999999) & (output["EditDistance"] != 999998)]
    
    # Sort the remaining rows by EditDistance in descending order
    output = output.sort_values(by="EditDistance", ascending=False)
    
    # Print the separated references
    if not no_year.empty:
        print("\nReferences with no year featured:")
        for ref in no_year["StudentRef"]:
            print(f"- {ref}")
    
    if not not_found.empty:
        print("\nReferences not found on Google Scholar:")
        for ref in not_found["StudentRef"]:
            print(f"- {ref}")
    
    # Print the full DataFrame
    print("\nProcessed References Table:")
    pd.set_option("display.max_rows", None)  # Show all rows
    pd.set_option("display.max_columns", None)  # Show all columns
    pd.set_option("display.width", None)  # No truncation of columns
    pd.set_option("display.colheader_justify", "left")  # Align headers to the left
    print(output)


if __name__ == "__main__":
    main()
