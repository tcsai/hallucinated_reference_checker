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
import difflib
import os
import re
import string
import sys
from io import StringIO
from typing import List, Optional, Tuple

import pandas as pd
from pypdf import PdfReader
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def print_summary_tables(
    no_year: pd.DataFrame, not_found: pd.DataFrame
) -> None:
    """
    Print summary tables for references with no year and not found references.

    Args:
        no_year (pd.DataFrame): DataFrame of references missing a year.
        not_found (pd.DataFrame): DataFrame of references not found on Google Scholar.
    """
    if not no_year.empty:
        print("\n🕑 \033[1mReferences with no year featured:\033[0m")
        for ref in no_year["StudentRef"]:
            print(f"  • {ref}")

    if not not_found.empty:
        print("\n🔍 \033[1mReferences not found on Google Scholar:\033[0m")
        for ref in not_found["StudentRef"]:
            print(f"  • {ref}")


def print_flagged_references(flagged: pd.DataFrame, threshold: int) -> None:
    """
    Print references whose edit distance exceeds the specified threshold.

    Args:
        flagged (pd.DataFrame): DataFrame of flagged references.
        threshold (int): Edit distance threshold.
    """
    if not flagged.empty:
        print(
            f"\n🚩 \033[1mReferences with edit distance > {threshold}:\033[0m"
        )
        for _, row in flagged.iterrows():
            print("╔" + "═" * 60)
            print("║ \033[94mStudentRef:\033[0m")
            print(f"║   {row['StudentRef']}")
            print("║ \033[92mScholarRef:\033[0m")
            print(f"║   {row['ScholarRef']}")
            print(f"║ \033[91mEditDistance:\033[0m {row['EditDistance']}")
            print("╚" + "═" * 60)


def save_log_if_needed(
    args: argparse.Namespace, log_buffer: StringIO, orig_stdout
) -> None:
    """
    Save the printed output to a log file if the log_output flag is set.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        log_buffer (StringIO): Buffer containing printed output.
        orig_stdout: Original sys.stdout to restore.
    """
    if args.log_output:
        sys.stdout = orig_stdout
        log_filename = os.path.basename(args.pdf_name) + ".log"
        with open(log_filename, "w", encoding="utf-8") as f:
            f.write(log_buffer.getvalue())
        print(f"\n📝 Log saved to {log_filename}")


def process_references(
    args: argparse.Namespace,
    references: list[str],
    scholar_citations: list[str],
    edit_distances: list[int],
) -> None:
    """
    Process and print the results of the reference checking.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        references (list[str]): List of student references.
        scholar_citations (list[str]): List of citations from Google Scholar.
        edit_distances (list[int]): List of edit distances between references.
    """
    output = pd.DataFrame(
        {
            "StudentRef": references,
            "ScholarRef": scholar_citations,
            "EditDistance": edit_distances,
        }
    )
    output["StudentRef"] = output["StudentRef"].str.strip()
    output["ScholarRef"] = output["ScholarRef"].str.strip()

    not_found = output[output["EditDistance"] == 999999]
    no_year = output[output["EditDistance"] == 999998]
    filtered = output[
        (output["EditDistance"] != 999999) & (output["EditDistance"] != 999998)
    ].sort_values(by="EditDistance", ascending=False)
    flagged = filtered[filtered["EditDistance"] > args.max_edit_distance]

    print_summary_tables(no_year, not_found)
    print_flagged_references(flagged, args.max_edit_distance)

    if getattr(args, "print_dataframe", False):
        print("\n📋 \033[1mProcessed References Table:\033[0m")
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", None)
        pd.set_option("display.colheader_justify", "left")
        print(filtered)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the script.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Check PDF references via Google Scholar."
    )
    parser.add_argument("pdf_name", type=str, help="Path to the PDF file.")
    parser.add_argument(
        "--references_page_range",
        type=str,
        help="Page range for references, e.g., '23-25' (inclusive). If not " \
             "given, will auto-detect.",
    )
    parser.add_argument(
        "--browser",
        type=str,
        choices=["firefox", "chrome", "safari"],
        default="firefox",
        help="Browser to use for Selenium (default: firefox).",
    )
    parser.add_argument(
        "--max_edit_distance",
        type=int,
        default=30,
        help="Maximum edit distance to consider a reference as matching " \
             "(default: 30).",
    )
    parser.add_argument(
        "--log_output",
        action="store_true",
        help="If set, also save the printed output to a log file named " \
             "after the input PDF.",
    )
    parser.add_argument(
        "--print_dataframe",
        action="store_true",
        help="If set, print the full processed DataFrame at the end.",
    )
    return parser.parse_args()


def parse_page_range(page_range_str: str) -> List[int]:
    """
    Parse a page range string like '23-25' into a list of integers.

    Args:
        page_range_str (str): Page range string in the format 'start-end'.

    Returns:
        List[int]: List of page numbers in the specified range (inclusive).
    """
    start, end = map(int, page_range_str.split("-"))
    return list(range(start, end + 1))


def extract_references(
    pdf_name: str, references_page_range: List[int]
) -> List[str]:
    """
    Extract references from the specified pages of a PDF.

    Args:
        pdf_name (str): Path to the PDF file.
        references_page_range (List[int]): List of page numbers to extract 
            references from.

    Returns:
        List[str]: List of extracted reference strings.
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
                references.append(re.sub(r"\s+", " ", ref))
    return references


def get_webdriver(browser: str):
    """
    Return a Selenium webdriver instance for the specified browser.

    Args:
        browser (str): Name of the browser ('firefox', 'chrome', etc.).

    Returns:
        selenium.webdriver: Selenium webdriver instance.

    Raises:
        ValueError: If the browser is not supported.
        NotImplementedError: If Internet Explorer is selected.
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
    """
    Normalize a reference string by lowercasing, removing punctuation, and 
    extra spaces.

    Args:
        ref (str): Reference string.

    Returns:
        str: Normalized reference string.
    """
    ref = ref.lower()
    ref = ref.translate(str.maketrans("", "", string.punctuation))
    ref = re.sub(r"\s+", " ", ref)
    return ref.strip()


def edit_distance(a: str, b: str) -> int:
    """
    Compute edit distance between two strings using SequenceMatcher.

    Args:
        a (str): First string.
        b (str): Second string.

    Returns:
        int: Edit distance between the two strings.
    """
    sm = difflib.SequenceMatcher(None, a, b)
    return int(max(len(a), len(b)) * (1 - sm.ratio()))


def check_citations_via_scholar(
    references: List[str], browser: str
) -> Tuple[List[str], List[int]]:
    """
    For each reference, search Google Scholar and retrieve the APA citation.
    Returns the scholar citations and their edit distances to the original.

    Args:
        references (List[str]): List of reference strings to check.
        browser (str): Browser to use for Selenium.

    Returns:
        Tuple[List[str], List[int]]: Scholar citations and their edit 
            distances.
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
            # sleep to avoid being blocked
            driver.implicitly_wait(3)
        except Exception as e:
            # Handle cases where Google Scholar fails to load or find results
            scholar_citations.append("Error")
            edit_distances.append(999999)  # Large edit distance
    driver.close()
    return scholar_citations, edit_distances


def find_references_section_by_text(pdf_name: str) -> Optional[List[int]]:
    """
    Find the 'References' section by scanning for a page that starts with
    'References' and ends before a page that starts with 'Appendix'.

    Args:
        pdf_name (str): Path to the PDF file.

    Returns:
        Optional[List[int]]: List of page numbers if found, else None.
    """
    reader = PdfReader(pdf_name)
    num_pages = len(reader.pages)
    start_page = None
    end_page = None

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        first_line = text.strip().split("\n", 1)[0].strip().lower()
        if first_line.startswith("references"):
            start_page = i
            break

    if start_page is None:
        return None

    # Find the first page after start_page that starts with 'Appendix'
    for i in range(start_page + 1, num_pages):
        text = reader.pages[i].extract_text() or ""
        first_line = text.strip().split("\n", 1)[0].strip().lower()
        if first_line.startswith("appendix"):
            end_page = i - 1
            break

    if end_page is None:
        end_page = num_pages - 1

    return list(range(start_page, end_page + 1))


def main() -> None:
    """
    Main entry point for the script. Handles argument parsing, reference 
    extraction, citation checking, result processing, and optional logging.
    """
    args = parse_args()
    log_buffer = None
    orig_stdout = sys.stdout
    if args.log_output:
        log_buffer = StringIO()
        sys.stdout = log_buffer

    try:
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
        process_references(args, references, scholar_citations, edit_distances)
    finally:
        save_log_if_needed(args, log_buffer, orig_stdout)


if __name__ == "__main__":
    main()
