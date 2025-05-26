# hallucinated_reference_checker

A script for checking if a PDF's references can also be found via Google Scholar or DBLP, or if they have been hallucinated.

The script detects the references section in the PDF, extracts all references, and searches for each citation on DBLP and Google Scholar. It compares the student's reference to the found citation using edit distance and prints an overview of flagged references.

## 📋 Requirements

You need the following installed to run the script:
- **Python 3.8+**
- **Selenium** (`4.32.0` or higher)
- **pypdf** (`5.5.0` or higher)
- A browser (e.g., Firefox, Chrome, Safari, Edge, Opera, and (all untested) Brave, Vivaldi, Chromium) and its corresponding WebDriver.

## 🛠️ How does it work?

1. Place the script in a folder with the PDF(s) you want to check.
2. Run the script with the name of the PDF as an argument.
3. The script will:
   - Try to find the references section (should work for our LaTeX templates; if not, use a manually provided page range).
   - Extract references from the detected section.
   - Search for each reference on DBLP and Google Scholar.
   - Compare the extracted reference with the top result using edit distance.
   - Print flagged references and a summary table.

## 💻 Usage

Run the script from the command line:

```bash
python [automatic_citation_checker.py](http://_vscodecontentref_/1) <pdf_name> [options]
```

### Required Argument:
- `pdf_name`: Path to the PDF file to check.

### Optional Arguments:
- `--references_page_range`: Manually specify the page range for the references section (e.g., `23-25`). If not provided, the script will attempt to detect the references section automatically.
- `--browser`: Specify the browser to use for Selenium (`firefox`, `chrome`, or `safari`). Default is `firefox`.
- `--max_edit_distance`: Maximum edit distance to consider a reference as matching. Default is `30`.
- `--log_output`: Save the printed output to a log file.
- `--print_dataframe`: Print the full processed DataFrame at the end.
- `--captcha_time`: Time (in seconds) to wait for solving captchas. Default is `10`.

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

5. Give yourself more time to solve the captchas:
   ```bash
   python automatic_citation_checker.py myfile.pdf --captcha_time=20
   ```

6. Tune the edit distance you want to flag titles with if it's exceeded:
   ```bash
   python automatic_citation_checker.py myfile.pdf --max_edit_distance=5
   ```

## 📊 Output

### Summary:
- **References with no year featured**: References that do not contain a year (e.g., `2020`) are skipped and listed separately.
- **References not found**: References that could not be found on DBLP or Google Scholar are listed separately.
- **Flagged references**: References with an edit distance greater than the specified threshold (`--max_edit_distance`) are flagged and displayed in detail.

### Full Table:
The script prints a full table of processed references, including:
- `StudentRef`: The original reference from the PDF.
- `Source`: The source of the citation (`DBLP`, `Scholar`, or `Error`).
- `Citation`: The citation retrieved from DBLP or Google Scholar.
- `EditDistance`: The edit distance between the original reference and the retrieved citation.

## 📝Notes

- The script uses **edit distance** to compare references. A lower edit distance indicates a closer match.
- If a reference does not contain a year, it is skipped, and its edit distance is set to `999998`.
- If a reference cannot be found on DBLP or Google Scholar, its edit distance is set to `999999`.
- Keep an eye out for captchas when using Google Scholar (usually at the start only). The script will wait for you to solve them.
- The script saves the output to a `.csv`; if you're tweaking things, please don't forget to overwrite using the `--overwrite_csv` flag.

## ⚠️ Limitations

- The script relies on Google Scholar and DBLP for citation data. If these services block requests or fail to return results, the script may not work as expected.
- Automatic detection of the references section assumes the section starts with "References" and ends before "Appendix" (if present). This may not work for all PDFs.

## 🚀 Future Improvements

- Add support for more robust reference detection.
- Improve handling of captchas.
- Add support for additional citation databases.

Feel free to contribute or suggest improvements (via [Issues](https://github.com/tcsai/hallucinated_reference_checker/issues))!