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
import platform
import re
import shutil
import string
import sys
from io import StringIO
from textwrap import wrap
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from pypdf import PdfReader
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm


class TerminalDisplay(object):

    def __init__(self):
        """
        This class provides methods for terminal output formatting and
        display.

        Attributes:
            term_width (int): Width of the terminal window.
            box_width (int): Width of the Unicode box for displaying sections.
        """
        self.term_width: int = self.get_terminal_width()
        self.box_width: int = max(min(self.term_width, 100), 40)

    def get_terminal_width(self, default: int = 80) -> int:
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

    def word_wrap(self, text: str, width: int) -> List[str]:
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

    def strip_ansi(self, text: str) -> str:
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
        self, title: str, lines: List[str], color_code: str = ""
    ) -> None:
        """
        Print a section in a Unicode box, wrapping lines and title.

        Args:
            title (str): The section title.
            lines (List[str]): The lines to print inside the box.
            color_code (str, optional): ANSI color code for the title. Defaults
                to "".
        """

        title_prefix: str = " " + title + " "
        max_title_width = self.box_width - 2
        title_lines = self.word_wrap(title_prefix, max_title_width)

        content_lines = []
        for line in lines:
            content_lines.extend(self.word_wrap(line, self.box_width - 2))

        print("╔" + "═" * (self.box_width - 2) + "╗")
        for tline in title_lines:
            tline = tline[: self.box_width - 2]
            if color_code:
                tline = f"{color_code}{tline}\033[0m"
            pad = self.box_width - 3 - len(self.strip_ansi(tline))
            print("║" + tline + " " * pad + "║")
        print("╟" + "─" * (self.box_width - 2) + "╢")
        for cline in content_lines:
            pad = self.box_width - 2 - len(self.strip_ansi(cline))
            print("║ " + cline + " " * (pad - 1) + "║")
        print("╚" + "═" * (self.box_width - 2) + "╝")

    def print_summary_tables(
        self, no_year: pd.DataFrame, not_found: pd.DataFrame
    ) -> None:
        """
        Print summary tables for references with no year and not found.

        Args:
            no_year (pd.DataFrame): DataFrame of references missing a year.
            not_found (pd.DataFrame): DataFrame of references not found.
        """
        if not no_year.empty:
            lines = [f"• {ref}" for ref in no_year["StudentRef"]]
            self.print_boxed_section(
                "🕑 References with no year featured", lines, "\033[1m"
            )

        if not not_found.empty:
            lines = [f"• {ref}" for ref in not_found["StudentRef"]]
            self.print_boxed_section(
                "🔍 References not found on DBLP or Scholar", lines, "\033[1m"
            )

    def print_flagged_references(
        self, flagged: pd.DataFrame, threshold: int
    ) -> None:
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
                self.print_boxed_section(
                    f"🚩 Reference flagged (edit distance > {threshold})",
                    lines,
                    "\033[1m",
                )
        else:
            self.print_boxed_section(
                "✅ All clear!",
                ["No references flagged for exceeding set edit distance."],
                "\033[1m",
            )


def report_results(
    df: pd.DataFrame, args: argparse.Namespace, term: TerminalDisplay
) -> None:
    """
    Print summary and flagged references from the results DataFrame.

    Args:
        df (pd.DataFrame): DataFrame with reference checking results.
        args (argparse.Namespace): Parsed command-line arguments.
        term (TerminalDisplay): Terminal display helper.
    """
    not_found = df[df["EditDistance"] == 999999]
    no_year = df[df["EditDistance"] == 999998]
    filtered = df[
        (df["EditDistance"] != 999999) & (df["EditDistance"] != 999998)
    ].sort_values(by="EditDistance", ascending=False)
    flagged = filtered[filtered["EditDistance"] > args.max_edit_distance]

    term.print_summary_tables(no_year, not_found)
    term.print_flagged_references(flagged, args.max_edit_distance)

    if getattr(args, "print_dataframe", False):
        term.print_boxed_section(
            "📋 \033[1mProcessed References Table:\033[0m", [filtered]
        )
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", None)
        pd.set_option("display.colheader_justify", "left")
        print(filtered)


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

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            not_found (pd.DataFrame): References not found in DBLP or Scholar.
            no_year (pd.DataFrame): References with no year found.
            filtered (pd.DataFrame): Filtered references with valid edit dist.
            flagged (pd.DataFrame): References flagged for high edit distance.
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
        (output["EditDistance"] != 999999) & (output["EditDistance"] != 999998)
    ].sort_values(by="EditDistance", ascending=False)
    flagged = filtered[filtered["EditDistance"] > args.max_edit_distance]

    return not_found, no_year, filtered, flagged


def extract_apa_title(reference: str) -> Optional[str]:
    """
    Extract the first author and title from an APA-style reference string.

    Args:
        reference (str): APA-style reference string.

    Returns:
        Optional[str]: Extracted author and title string, or None if not found.
    """
    query: str = ""
    match = re.search(r"^(.+?)\s*\(\d{4}\)", reference)
    if match:
        query += match.group(1).strip()
    match = re.search(r"\(\d{4}\)\.\s*(.+?)\.\s", reference)
    if match:
        query += " " + match.group(1).strip()
    return query


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


def check_dblp(reference: str) -> Optional[str]:
    """
    Check if a reference exists in DBLP and return the best matching citation.

    Args:
        reference (str): Reference string to search.

    Returns:
        Optional[str]: Formatted DBLP citation if found, else None.
    """
    url = "https://dblp.org/search/publ/api"
    params: Dict[str, str] = {"q": reference, "format": "json", "h": 1}
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
    elif browser == "edge":
        return webdriver.Edge()
    elif browser == "opera":
        return webdriver.Opera()
    elif browser == "brave" or browser == "vivaldi" or browser == "chromium":
        try:
            os_name = platform.system().lower()
            options = webdriver.ChromeOptions()
            if os_name == "linux":
                if browser == "brave":
                    options.binary_location = "/usr/bin/brave"
                elif browser == "vivaldi":
                    options.binary_location = "/usr/bin/vivaldi"
                elif browser == "chromium":
                    options.binary_location = "/usr/bin/chromium-browser"
            elif os_name == "darwin":  # macOS
                if browser == "brave":
                    options.binary_location = (
                        "/Applications/Brave Browser.app/Contents/"
                        "MacOS/Brave Browser"
                    )
                elif browser == "vivaldi":
                    options.binary_location = (
                        "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"
                    )
                elif browser == "chromium":
                    options.binary_location = (
                        "/Applications/Chromium.app/Contents/MacOS/Chromium"
                    )
            elif os_name == "windows":  # Windows
                if browser == "brave":
                    options.binary_location = (
                        "C:\\Program Files\\BraveSoftware\\Brave-Browser"
                        "\\Application\\brave.exe"
                    )
                elif browser == "vivaldi":
                    options.binary_location = (
                        "C:\\Program Files\\Vivaldi\\Application\\vivaldi.exe"
                    )
                elif browser == "chromium":
                    options.binary_location = (
                        "C:\\Program Files\\Chromium\\Application\\chrome.exe"
                    )
            return webdriver.Chrome(options=options)
        except Exception:
            raise ValueError("Seems like this browser option is not working.")
    else:
        raise ValueError(f"Unsupported browser: {browser}")


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
    reader: PdfReader = PdfReader(pdf_name)
    references: List[str] = []
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
    reader: PdfReader = PdfReader(pdf_name)
    num_pages: int = len(reader.pages)
    start_page: Optional[int] = None
    end_page: Optional[int] = None

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


def get_reference_page_range(
    args: argparse.Namespace, term: TerminalDisplay
) -> List[int]:
    """
    Determine the page range for references, either from args or by auto-
    detect.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        term (TerminalDisplay): Terminal display helper.

    Returns:
        List[int]: List of page numbers for the references section.

    Raises:
        SystemExit: If the references section cannot be detected.
    """
    if args.references_page_range is not None:
        return parse_page_range(args.references_page_range)
    else:
        page_range = find_references_section_by_text(args.pdf_name)
        if page_range is None:
            print(
                "Could not auto-detect the references section in the PDF "
                "using outline or text search."
            )
            sys.exit(1)
        term.print_boxed_section(
            "📄 Automatically detected reference pages",
            [f"{page_range}"],
            "\033[1m",
        )
        return page_range


def load_or_compute_results(
    args: argparse.Namespace, term: TerminalDisplay
) -> pd.DataFrame:
    """
    Load results from CSV if available and not overwriting, otherwise compute
    and save new results.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
        term (TerminalDisplay): Terminal display helper.

    Returns:
        pd.DataFrame: DataFrame with reference checking results.
    """
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(
        output_dir,
        os.path.splitext(os.path.basename(args.pdf_name))[0] + ".csv",
    )
    required_cols = {"StudentRef", "Source", "Citation", "EditDistance"}

    # Try to load CSV unless overwrite is requested
    if os.path.exists(csv_path) and not args.overwrite_csv:
        df = pd.read_csv(csv_path)
        if not required_cols.issubset(df.columns):
            print(
                f"CSV file {csv_path} is missing required columns. "
                "Recomputing..."
            )
            df = None
        else:
            term.print_boxed_section(
                "📦 Loaded cached results",
                [f"{csv_path} exists; invoke --overwrite_csv to recompute."],
                "\033[1m",
            )
    else:
        df = None

    if df is None:
        page_range = get_reference_page_range(args, term)
        references = extract_references(args.pdf_name, page_range)
        citations, sources, edit_distances = check_references(
            references, args.browser, args.captcha_time
        )
        df = pd.DataFrame(
            {
                "StudentRef": references,
                "Source": sources,
                "Citation": citations,
                "EditDistance": edit_distances,
            }
        )
        df.to_csv(csv_path, index=False)
        print(f"Results saved to {csv_path}")

    return df


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
        choices=[
            "firefox",
            "chrome",
            "safari",
            "edge",
            "opera",
            "brave",
            "vivaldi",
            "chromium",
        ],
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
    parser.add_argument(
        "--overwrite_csv",
        action="store_true",
        help="If set, overwrite the CSV file with the results for this"
        " thesis if it exists.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Main entry point for the script. Handles argument parsing, reference
    extraction, citation checking, result processing, and optional logging.
    """
    args = parse_args()
    term = TerminalDisplay()
    log_buffer: Optional[StringIO] = None

    orig_stdout = sys.stdout
    if args.log_output:
        log_buffer = StringIO()
        sys.stdout = log_buffer

    try:
        df = load_or_compute_results(args, term)
        report_results(df, args, term)
    finally:
        save_log_if_needed(args, log_buffer, orig_stdout)


if __name__ == "__main__":
    main()
