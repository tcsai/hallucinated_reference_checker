# -*- coding: utf-8 -*-
"""
README:

This script checks the references of a student paper for hallucinated
examples. It detects the references section, extracts all references from
the PDF, and searches for each citation on DBLP and Google Scholar. It
compares the student's reference to the found citation using edit distance,
and prints an overview of flagged references.

PACKAGES:
    selenium:    '4.32.0'
    pypdf:       '5.5.0'
"""

import argparse
import difflib
import os
import re
import shutil
import string
import sys
from io import StringIO
from textwrap import wrap
from typing import List, Optional, Tuple

import pandas as pd
import requests
from pypdf import PdfReader
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm


def get_terminal_width(default: int = 80) -> int:
    """
    Get the width of the terminal window.

    Args:
        default (int): Default width to return if detection fails.

    Returns:
        int: Width of the terminal window in characters.
    """
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default


def word_wrap(text: str, width: int) -> List[str]:
    """
    Wrap text to the specified width at word boundaries.

    Args:
        text (str): The text to wrap.
        width (int): The maximum line width.

    Returns:
        List[str]: List of wrapped lines.
    """
    return wrap(
        text, width=width, break_long_words=False, break_on_hyphens=False
    )


def strip_ansi(text: str) -> str:
    """
    Remove ANSI escape sequences from a string.

    Args:
        text (str): The string to clean.

    Returns:
        str: The cleaned string.
    """
    ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def print_boxed_section(
    title: str, lines: List[str], color_code: str = ""
) -> None:
    """
    Print a section in a Unicode box, wrapping lines and title.

    Args:
        title (str): The section title.
        lines (List[str]): The lines to print inside the box.
        color_code (str, optional): ANSI color code for the title. Defaults
            to "".
    """
    term_width = get_terminal_width()
    box_width = max(min(term_width, 100), 40)

    title_prefix = " " + title + " "
    max_title_width = box_width - 2
    title_lines = word_wrap(title_prefix, max_title_width)

    content_lines = []
    for line in lines:
        content_lines.extend(word_wrap(line, box_width - 2))

    print("╔" + "═" * (box_width - 2) + "╗")
    for tline in title_lines:
        tline = tline[: box_width - 2]
        if color_code:
            tline = f"{color_code}{tline}\033[0m"
        pad = box_width - 3 - len(strip_ansi(tline))
        print("║" + tline + " " * pad + "║")
    print("╟" + "─" * (box_width - 2) + "╢")
    for cline in content_lines:
        pad = box_width - 2 - len(strip_ansi(cline))
        print("║" + cline + " " * pad + "║")
    print("╚" + "═" * (box_width - 2) + "╝")


def print_summary_tables(
    no_year: pd.DataFrame, not_found: pd.DataFrame
) -> None:
    """
    Print summary tables for references with no year and not found.

    Args:
        no_year (pd.DataFrame): DataFrame of references missing a year.
        not_found (pd.DataFrame): DataFrame of references not found.
    """
    if not no_year.empty:
        lines = [f"• {ref}" for ref in no_year["StudentRef"]]
        print_boxed_section(
            "🕑 References with no year featured", lines, "\033[1m"
        )

    if not not_found.empty:
        lines = [f"• {ref}" for ref in not_found["StudentRef"]]
        print_boxed_section(
            "🔍 References not found on DBLP or Scholar", lines, "\033[1m"
        )


def print_flagged_references(flagged: pd.DataFrame, threshold: int) -> None:
    """
    Print references whose edit distance exceeds the threshold.

    Args:
        flagged (pd.DataFrame): DataFrame of flagged references.
        threshold (int): Edit distance threshold for flagging.
    """
    if not flagged.empty:
        for _, row in flagged.iterrows():
            lines = [
                "",
                "  \033[94mStudent:\033[0m",
                f"    {row['StudentRef']}",
                "",
                "  \033[96mSource:\033[0m",
                f"    {row['Source']}",
                "",
                "  \033[92mCitation:\033[0m",
                f"    {row['Citation']}",
                "",
                "  \033[91mTitle Edit Distance:\033[0m",
                f"    {row['EditDistance']}",
            ]
            print_boxed_section(
                f"🚩 Reference flagged (edit distance > {threshold})",
                lines,
                "\033[1m",
            )
    else:
        print_boxed_section(
            "✅ All clear!",
            ["No references flagged for exceeding specified edit distance."],
            "\033[1m",
        )


def save_log_if_needed(
    args: argparse.Namespace, log_buffer: Optional[StringIO], orig_stdout
) -> None:
    """
    Save the printed output to a log file if the log_output flag is set.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        log_buffer (Optional[StringIO]): Buffer containing log output.
        orig_stdout: Original sys.stdout to restore.
    """
    if args.log_output and log_buffer is not None:
        sys.stdout = orig_stdout
        log_filename = os.path.basename(args.pdf_name) + ".log"
        with open(log_filename, "w", encoding="utf-8") as f:
            f.write(log_buffer.getvalue())
        print(f"\n📝 Log saved to {log_filename}")


def process_references(
    args: argparse.Namespace,
    references: List[str],
    citations: List[str],
    sources: List[str],
    edit_distances: List[int],
) -> None:
    """
    Process and print the results of the reference checking.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        references (List[str]): List of student references.
        citations (List[str]): List of citations from DBLP or Scholar.
        sources (List[str]): List of sources ("DBLP" or "Scholar").
        edit_distances (List[int]): List of edit distances between references.
    """
    output = pd.DataFrame(
        {
            "StudentRef": references,
            "Source": sources,
            "Citation": citations,
            "EditDistance": edit_distances,
        }
    )
    output["StudentRef"] = output["StudentRef"].str.strip()
    output["Citation"] = output["Citation"].str.strip()

    not_found = output[output["EditDistance"] == 999999]
    no_year = output[output["EditDistance"] == 999998]
    filtered = output[
        (output["EditDistance"] != 999999)
        & (output["EditDistance"] != 999998)
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
        help="Page range for references, e.g., '23-25' (inclusive).",
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
        help="Maximum edit distance to consider a reference as matching.",
    )
    parser.add_argument(
        "--log_output",
        action="store_true",
        help="If set, also save the printed output to a log file.",
    )
    parser.add_argument(
        "--print_dataframe",
        action="store_true",
        help="If set, print the full processed DataFrame at the end.",
    )
    parser.add_argument(
        "--captcha_time",
        type=int,
        default=10,
        help="Time to wait for captcha solving (default: 10 seconds).",
    )
    return parser.parse_args()


def parse_page_range(page_range_str: str) -> List[int]:
    """
    Parse a page range string like '23-25' into a list of integers.

    Args:
        page_range_str (str): Page range string, e.g., '23-25'.

    Returns:
        List[int]: List of page numbers (inclusive).
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
        references_page_range (List[int]): List of page numbers to extract.

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
        browser (str): Name of the browser ("firefox", "chrome", "safari").

    Returns:
        selenium.webdriver: Selenium WebDriver instance.

    Raises:
        ValueError: If the browser is not supported.
    """
    if browser == "firefox":
        return webdriver.Firefox()
    elif browser == "chrome":
        return webdriver.Chrome()
    elif browser == "safari":
        return webdriver.Safari()
    else:
        raise ValueError(f"Unsupported browser: {browser}")


def normalize_reference(ref: str) -> str:
    """
    Normalize a reference string for comparison.

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
    sm = difflib.SequenceMatcher(
        None, extract_apa_title(a), extract_apa_title(b)
    )
    return int(max(len(a), len(b)) * (1 - sm.ratio()))


def check_dblp(reference: str) -> Optional[str]:
    """
    Check if a reference exists in DBLP and return the best matching citation.

    Args:
        reference (str): Reference string to search.

    Returns:
        Optional[str]: Formatted DBLP citation if found, else None.
    """
    url = "https://dblp.org/search/publ/api"
    params = {"q": reference, "format": "json", "h": 1}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("result", {}).get("hits", {}).get("hit", [])
        if hits:
            info = hits[0].get("info", {})
            try:
                authors = [
                    author.get("text", "")
                    for author in info.get("authors", {}).get("author", [])
                ]
            except Exception:
                authors = []
            author_str = (
                ", ".join([a for a in authors if a])
                if isinstance(authors, list)
                else authors
            )
            title = info.get("title", "")
            year = info.get("year", "")
            venue = info.get("venue", "")
            dblp_citation = f"{author_str} ({year}). {title}. {venue}."
            return dblp_citation
    except Exception:
        pass
    return None


def extract_apa_title(reference: str) -> Optional[str]:
    """
    Extract the first author and title from an APA-style reference string.

    Args:
        reference (str): APA-style reference string.

    Returns:
        Optional[str]: Extracted author and title string, or None if not found.
    """
    query = ""
    match = re.search(r"^(.+?)\s*\(\d{4}\)", reference)
    if match:
        query += match.group(1).strip()
    match = re.search(r"\(\d{4}\)\.\s*(.+?)\.\s", reference)
    if match:
        query += " " + match.group(1).strip()
    return query


def get_citation_from_scholar(
    driver, ref: str, captcha_time: int
) -> Tuple[str, str, int]:
    """
    Search Google Scholar for a reference and return the citation, source,
    and edit distance.

    Args:
        driver: Selenium WebDriver instance.
        ref (str): Reference string to search.
        captcha_time (int): Time to wait for captcha solving.

    Returns:
        Tuple[str, str, int]: (citation, source, edit_distance)
    """
    try:
        driver.get("https://scholar.google.com/")
        ActionChains(driver).send_keys(ref).perform()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        driver.implicitly_wait(1)
        try:
            WebDriverWait(driver, 1).until(
                lambda d: d.find_elements(By.CLASS_NAME, "gs_or_cit")
                or d.find_elements(By.ID, "gs_captcha_ccl")
            )
        except TimeoutException:
            return "Not Found", "Error", 999999

        try:
            if driver.find_element(By.ID, "gs_captcha_ccl"):
                WebDriverWait(driver, captcha_time).until(
                    lambda d: d.find_elements(By.CLASS_NAME, "gs_or_cit")
                )
                citation_button = driver.find_element(
                    By.CLASS_NAME, "gs_or_cit"
                )
                citation_button.click()
        except NoSuchElementException:
            citation_button = driver.find_element(By.CLASS_NAME, "gs_or_cit")
            citation_button.click()

        citations_list = driver.find_elements(By.CLASS_NAME, "gs_citr")
        if len(citations_list) == 0:
            return "Not Found", "Error", 999999
        apa_cite = citations_list[1].text
        norm_ref = normalize_reference(ref)
        norm_apa = normalize_reference(apa_cite)
        dist = edit_distance(norm_ref, norm_apa)
        return apa_cite, "Scholar", dist
    except Exception:
        return "Error", "Error", 999999


def check_references(
    references: List[str], browser: str, captcha_time: int
) -> Tuple[List[str], List[str], List[int]]:
    """
    For each reference, check DBLP first, then Google Scholar if not found.
    Returns lists of citations, their sources, and edit distances.

    Args:
        references (List[str]): List of reference strings.
        browser (str): Browser to use for Selenium.
        captcha_time (int): Time to wait for captcha solving.

    Returns:
        Tuple[List[str], List[str], List[int]]:
            citations (List[str]): Citations found or error messages.
            sources (List[str]): Source of each citation ("DBLP", "Scholar", 
                or "Error").
            edit_distances (List[int]): Edit distances for each reference.
    """
    citations: List[str] = []
    sources: List[str] = []
    edit_distances: List[int] = []
    driver = get_webdriver(browser)
    driver.set_window_size(800, 800)
    for ref in tqdm(references):
        if not re.search(r"\b\d{4}\b", ref):
            citations.append("No Year Found")
            sources.append("Error")
            edit_distances.append(999998)
            continue

        title = extract_apa_title(ref)
        dblp_query = title if title else ref
        dblp_citation = check_dblp(dblp_query)
        if dblp_citation:
            citations.append(dblp_citation)
            sources.append("DBLP")
            norm_ref = normalize_reference(ref)
            norm_dblp = normalize_reference(dblp_citation)
            dist = edit_distance(norm_ref, norm_dblp)
            edit_distances.append(dist)
            continue

        scholar_cite, scholar_source, scholar_dist = get_citation_from_scholar(
            driver, ref, captcha_time
        )
        citations.append(scholar_cite)
        sources.append(scholar_source)
        edit_distances.append(scholar_dist)
    driver.close()
    return citations, sources, edit_distances


def find_references_section_by_text(
    pdf_name: str,
) -> Optional[List[int]]:
    """
    Find the 'References' section by scanning for a page that starts with
    'References' and ends before a page that starts with 'Appendix'.

    Args:
        pdf_name (str): Path to the PDF file.

    Returns:
        Optional[List[int]]: List of reference page numbers, or None if not
            found.
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

    Returns:
        None
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
            print_boxed_section(
                "📄 Automatically detected reference pages",
                [f"{page_range}"],
                "\033[1m",
            )

        references = extract_references(args.pdf_name, page_range)
        citations, sources, edit_distances = check_references(
            references, args.browser, args.captcha_time
        )
        process_references(
            args, references, citations, sources, edit_distances
        )
    finally:
        save_log_if_needed(args, log_buffer, orig_stdout)


if __name__ == "__main__":
    main()
