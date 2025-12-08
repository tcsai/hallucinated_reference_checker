# hallucinated_reference_checker

A script for checking if a PDF's references can also be found via Google Scholar or DBLP, or if they have been hallucinated.

The script detects the references section in the PDF, extracts all references, and searches for each citation on DBLP and Google Scholar via DOI, DBLP API, or Selenium-based browser automation. It compares the student's reference title to the found citation title using edit distance and prints an overview of flagged references.

## 📋 Requirements

You need the following installed to run the script:
- **Python 3.8+**
- **Selenium** (`4.32.0` or higher)
- **pypdf** (`5.5.0` or higher)
- **pandas** and **requests**
- A browser (Firefox, Chrome, Safari, Edge, Opera, Brave, Vivaldi, or Chromium) and its corresponding WebDriver.

## 🛠️ How does it work?

1. Place the script in a folder with the PDF(s) you want to check.
2. Run the script with the name of the PDF as an argument.
3. The script will:
   - Automatically detect the references section (optimized for LaTeX-generated PDFs; use `--references_page_range` if detection fails).
   - Extract references from the detected section.
   - For each reference:
     - Check if a valid DOI is present (using Selenium to validate).
     - Search DBLP API if no DOI found.
     - Fall back to Google Scholar (via Selenium) if DBLP match is poor or not found.
   - Compare extracted reference titles with found citation titles using edit distance.
   - Print flagged references and a summary table.

## 💻 Usage

Run the script from the command line:

```bash
python automatic_citation_checker.py <pdf_name> [options]
```

### Required Argument:
- `pdf_name`: Path to the PDF file to check.

### Optional Arguments:
- `--references_page_range`: Manually specify the page range for the references section (e.g., `23-25`). If not provided, the script will attempt to auto-detect using the PDF structure.
- `--browser`: Specify the browser to use for Selenium (`firefox`, `chrome`, `safari`, `edge`, `opera`, `brave`, `vivaldi`, or `chromium`). Default is `firefox`.
- `--max_edit_distance`: Maximum edit distance threshold to flag a reference (default: `30`).
- `--log_output`: If set, save the printed output to a log file.
- `--print_dataframe`: If set, print the full processed DataFrame at the end.
- `--captcha_time`: Time (in seconds) to wait for solving captchas on Google Scholar (default: `60`).
- `--overwrite_csv`: If set, overwrite the cached CSV file and recompute all results.

### Example Commands:

1. Automatically detect the references section:
   ```bash
   python automatic_citation_checker.py myfile.pdf
   ```

2. Specify the references page range manually:
   ```bash
   python automatic_citation_checker.py myfile.pdf --references_page_range 23-25
   ```

3. Use Chrome as the browser (default is Firefox):
   ```bash
   python automatic_citation_checker.py myfile.pdf --browser chrome
   ```

4. Save the output to a log file:
   ```bash
   python automatic_citation_checker.py myfile.pdf --log_output
   ```

5. Give yourself more time to solve captchas:
   ```bash
   python automatic_citation_checker.py myfile.pdf --captcha_time 120
   ```

6. Tune the edit distance threshold for flagging references:
   ```bash
   python automatic_citation_checker.py myfile.pdf --max_edit_distance 15
   ```

7. Recompute results and overwrite cached CSV:
   ```bash
   python automatic_citation_checker.py myfile.pdf --overwrite_csv
   ```

## 📊 Output

### Summary:
- **References with no year featured**: References that do not contain a year (e.g., `2020`) are skipped and listed separately with edit distance `999998`.
- **References not found**: References that could not be found on DBLP or Google Scholar are listed separately with edit distance `999999`.
- **Flagged references**: References with an edit distance greater than the specified threshold (`--max_edit_distance`) are flagged and displayed in detail.

### Full Table:
The script prints a full table of processed references, including:
- `StudentRef`: The original reference from the PDF.
- `Source`: The source of the citation (`DOI`, `DBLP`, `Scholar`, or `Error`).
- `Citation`: The citation retrieved from DOI validation, DBLP, or Google Scholar.
- `EditDistance`: The edit distance between the student reference title and the retrieved citation title.

## 📝 Notes

- The script uses **edit distance** to compare reference titles (extracted from the APA format `(YYYY). TITLE.`). A lower edit distance indicates a closer match.
- If a reference does not contain a year, it is skipped with edit distance `999998`.
- If a reference cannot be found on DBLP or Google Scholar, it is marked with edit distance `999999`.
- References with valid DOIs are considered perfect matches (edit distance `0`).
- Keep an eye out for captchas when using Google Scholar (usually at the start only). The script will wait for you to solve them.
- The script caches results in a `.csv` file in the `output/` directory. Use `--overwrite_csv` to force recomputation.

## ⚠️ Limitations

- The script relies on Google Scholar and DBLP for citation data. If these services block requests or fail to return results, the script may not work as expected.
- Automatic detection of the references section assumes the section starts with "References" and ends before "Appendix" (if present). This works well for LaTeX-generated PDFs but may not work for all document types.
- DOI validation is performed via Selenium navigation; some DOI services may block automated requests.
- Title extraction assumes APA citation format with the pattern `(YYYY). TITLE.`; references not in this format may not extract titles correctly.

## 🚀 Future Improvements

- Add support for more robust reference detection.
- Improve handling of captchas.
- Add support for additional citation databases.

Feel free to contribute or suggest improvements (via [Issues](https://github.com/tcsai/hallucinated_reference_checker/issues))!