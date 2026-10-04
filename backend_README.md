# storm-hackathon-2026

# CSV to JSON converter

A small Python program that turns any CSV file into a JSON file. You don't need to tell it anything about the file. It reads the column names from the first row, works out how the values are separated and how the file is encoded, and decides whether each column holds numbers, true/false values or text. It prints what it decided, so you can check.

## Requirements

Python 3.6 or newer (any current version works). The program only uses Python's built-in modules, so there is nothing else to install.

To check that Python is installed, open a terminal and run:

```
python3 --version
```

On Windows, run `python --version` instead. If neither works, install Python from [python.org](https://www.python.org/downloads/).

## Usage

1. Put `main.py` and your CSV file in the same folder.
2. Open a terminal in that folder.
3. Run:

```
   python3 main.py yourfile.csv
```

   On Windows, type `python` (or `py`) instead of `python3`.

The program prints a summary of what it found and writes `yourfile.json` to the folder you ran the command from.

- **Existing files are replaced.** If `yourfile.json` already exists, it's overwritten, and the summary says so.
- **Nothing is written if the CSV can't be read.** If the program stops with an error, any existing JSON file is left as it was.
- **File names with spaces** need quotes: `python3 main.py "my data.csv"`.
- **CSV files in other folders.** Give the file's path instead of its name, for example `python3 main.py ~/Downloads/data.csv`. Dragging the file into the terminal window types its path for you. The JSON still goes in the folder you ran the command from, not next to the CSV.

## Example

`people.csv`:

```
name,age,member,zip
Ana,34,true,02134
Ben,,false,90210
```

Running `python3 main.py people.csv` prints:

```
Read people.csv: 2 rows, 4 columns, comma-separated, UTF-8
  numbers:    age
  true/false: member
  text:       name, zip
Wrote /path/to/your/folder/people.json
```

and creates `people.json`:

```json
[
  {
    "name": "Ana",
    "age": 34,
    "member": true,
    "zip": "02134"
  },
  {
    "name": "Ben",
    "age": null,
    "member": false,
    "zip": "90210"
  }
]
```

Ben's empty age became `null`, and the ZIP codes stayed as text, so `02134` keeps its leading zero.

## What it works out by itself

- **Column names:** taken from the first row that isn't blank.
- **Separator:** commas, semicolons, tabs or pipes (the `|` character).
- **Encoding:** UTF-8 (with or without the hidden marker Excel adds), UTF-16 (Excel's "Unicode Text" format) and Windows-1252 (Excel's plain "CSV" format on Windows).
- **Column types:** numbers, true/false or text, as described below.

### Column types

Each column's type is decided by looking at every value in it, so a column never ends up half numbers and half text.

- **Numbers:** every value is a plain number, like `42`, `-3.5`, `.5` or `1e-05`. Whole numbers are written as integers and the rest as decimals.
- **true/false:** every value is `true` or `false`, in upper or lower case (Excel writes `TRUE` and `FALSE`). These become JSON `true` and `false`.
- **Text:** anything else, written exactly as it appears in the file.
- **Empty:** every value is missing.

In any column, missing values become `null`. These count as missing, in upper or lower case: an empty cell, `NA`, `N/A`, `NaN`, `null`, `inf` and `-inf`.

Some values look like numbers but are usually codes or IDs, so they're kept as text, along with the rest of their column:

- a leading zero, like `02134` or `007`
- a leading `+`, like `+16045551234`
- 16 or more digits, like `1234567890123456789` (many programs can't store that many digits exactly)

Values with other characters in them, such as `$5`, `12%`, `1,234` or `2024-11-03`, are text too.

## Messy files

The program tidies up common problems:

- Spaces around values are removed.
- Blank lines, and rows with nothing but separators (`,,,`), are skipped.
- If the header row appears again further down, as happens when several CSV files are joined together, the repeat is skipped.
- Blank column names become `column_1`, `column_2` and so on, by position. Repeated names get a number: two columns called `value` become `value` and `value_2`.
- A separator at the end of a line is ignored.
- If a row has fewer values than there are columns, the missing ones become `null`, and the summary lists the line numbers so you can check them.
- If a row has more values than there are columns, the program stops and gives the line number, because it can't tell which column the extra value belongs to. This usually means a value contains a comma but isn't in quotes: `Smith, John` should be written as `"Smith, John"`.

## Limitations

- The first row must contain the column names.
- IDs or phone numbers that look like ordinary numbers (no leading zero or `+`) become numbers.
- Numbers written with a decimal comma (`3,5` instead of `3.5`) stay as text.
- It reads CSV files only. Save Excel workbooks (`.xlsx`) as CSV first.
- The whole file is read into memory. That's fine for normal files; 100,000 rows take a few seconds.
- It needs the CSV's name when it starts, so run it from a terminal. Pressing Run in an editor without passing a file name only shows the "Usage" message.

## Troubleshooting

| Message | What to do |
|---|---|
| `command not found: python` | On Mac and Linux, type `python3` instead of `python`. |
| `'python' is not recognized...` (Windows) | Try `py` instead. If that doesn't work either, install Python from python.org and tick "Add python.exe to PATH" during setup. |
| `Usage: ...` | Give exactly one CSV file name after `main.py`. |
| `Can't find yourfile.csv` | Check the spelling, and that the terminal is in the right folder. `ls` (Mac and Linux) or `dir` (Windows) lists the files there. |
| `... isn't a text file` | The file is probably an Excel workbook. Open it in Excel and save it as CSV. |
| `... is empty` | The file has no rows in it. |
| `Line N has more values than there are columns` | Open the CSV, go to that line, and put double quotes around the value that contains a comma (or whichever separator the file uses). |
| `Couldn't read ... as a CSV file` | Python's `csv` module hit something it can't handle, such as a single value longer than 131,072 characters. |

## How it works

`main.py` is split into small functions that each do one job. `main()` runs them in this order:

1. `read_text()` reads the file's bytes and decodes them into text, as UTF-16, UTF-8 or Windows-1252.
2. `detect_delimiter()` uses Python's `csv.Sniffer` on the first 50,000 characters to find the separator.
3. `read_rows()` splits the text into the header and data rows with the `csv` module, and tidies them up.
4. `unique_names()` fixes blank and repeated column names.
5. `column_kind()` decides each column's type.
6. `convert()` turns each value into a number, true/false, `null` or text.

Finally, `main()` writes the JSON file (indented by 2 spaces, saved as UTF-8, with characters like `é` kept as they are) and prints the summary. The code is commented throughout if you want the details.