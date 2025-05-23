# hallucinated_reference_checker
Quick and dirty script for checking if a pdf's references can also be found via Google Scholar, or if they have been hallucinated.

You need selenium (4.32.0 or higher) and pypdf (5.5.0 or higher) to be installed for this, as well as a FireFox browser, though you can also modify the script to work with a different one.

## How does it work?

1. Insert the script in a folder with the pdf(s) you want to check.
2. Add the name of the pdf in question to `pdf_name`
3. Add the page range where the references are found to `references_page_range`
4. Run script

This will open a FireFox browser for you. Keep an eye out for captchas - you'll have to fill these in yourself to circumvent them, at least for now. The script gets the citation of the top Google Scholar result in APA form, and print it so you can compare the pdf's citation with it. It waits for your input keys to continue to the next citation. 

6. Press ENTER if the citation matches/looks fine
7. Press N or some other key if something seems suspicious.

*The script provides an output table with the original citations, Scholar's top result, and your rating.*

NOTE: This is really a simplistic solution, but it can be adapted to not need the page numbers to be filled in, or to automatically determine if the citation and the top scholar result are similar enough. For now, I hope it is somewhat helpful, and look forward to tips to improve it.

