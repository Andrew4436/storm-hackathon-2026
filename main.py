"""
main.py: convert any CSV file into a JSON file.

WHAT IT DOES
------------
You give it a CSV file (a table saved as plain text: one row per line, with the
values separated by commas or a similar character) and it writes a JSON file
holding a list of objects, one object per row. The CSV's column names become
the keys of each object. For example, this CSV:

    name,age,member
    Ana,34,true
    Ben,,false

becomes this JSON (squashed onto fewer lines here; the real file puts each
value on its own line):

    [
      {"name": "Ana", "age": 34, "member": true},
      {"name": "Ben", "age": null, "member": false}
    ]

You don't have to tell it anything about the columns. It works out by itself:
  * the column names, from the first row of the file
  * the separator between values: comma, semicolon, tab or pipe (|)
  * the text encoding: UTF-8, UTF-16, or Windows-1252 (used by Excel on Windows)
  * what each column holds: numbers, true/false values, or text
and it prints what it decided, so you can check.

HOW TO RUN IT
-------------
Open a terminal in the folder that holds this file and your CSV, and type:

    python3 main.py yourfile.csv

(On Windows, type python instead of python3.)

The JSON is saved in the folder you ran the command from, with the same name as
the CSV but ending in .json: yourfile.csv -> yourfile.json. If a file with that
name already exists, it is replaced.

THINGS IT CAN'T GUESS
---------------------
  * The first row has to be the column names.
  * Values that look like ordinary numbers become numbers, even if they're
    really IDs or phone numbers. It only keeps them as text when they have a
    leading zero (like 02134), start with a + sign, or are 16 or more digits.
  * Numbers written with a decimal comma (3,5 instead of 3.5) stay as text.

HOW THE CODE IS ORGANISED
-------------------------
The work is split into small functions that each do one job. main(), near the
bottom of the file, calls them in this order:
  1. read_text()         reads the file's bytes and turns them into text
  2. detect_delimiter()  works out which character separates the values
  3. read_rows()         splits the text into the header row and the data rows
  4. unique_names()      tidies up the column names
  5. column_kind()       decides what kind of data each column holds
  6. convert()           turns each value's text into a number, true/false,
                         null or text
Then main() writes the JSON file and prints a summary of what it found.
"""

# =============================================================================
# IMPORTS
# =============================================================================
# "import" loads a module: a collection of ready-made tools. All of these come
# with Python itself (they're part of its "standard library"), so there's
# nothing extra to install.

import codecs  # constants for the invisible markers some text files start with
import csv     # reads CSV text correctly, including values inside quotes
import io      # lets a piece of text be read as if it were a file
import json    # writes Python data out in JSON format
import math    # maths tools; we use math.isfinite() to spot infinity
import re      # "regular expressions": patterns that describe what text looks like
import sys     # the words typed on the command line, and stopping with a message
from pathlib import Path  # Path objects make file paths easy to work with


# =============================================================================
# SETTINGS AND PATTERNS
# =============================================================================
# These are set up once, here at the top, and used by the functions below.
# Writing a name in CAPITALS is a Python convention meaning "this is a
# constant": a value that's set once and never changed while the program runs.

# --- Values that mean "missing" ----------------------------------------------
# Programs write an empty cell in different ways: Excel leaves it blank (""),
# R writes NA, pandas can write nan, and so on. Any cell holding one of these
# becomes null in the JSON (null is JSON's word for "no value").
#
# Cells are lowercased before they're compared with this list (see
# column_kind and convert below), so "NaN", "NAN" and "nan" all count. That's
# why everything here is written in lowercase.
#
# "inf" and "-inf" mean infinity. JSON has no way to store infinity, so those
# become null too.
#
# The curly brackets make this a "set": an unordered collection that can
# answer "is this value in here?" very quickly.
MISSING = {"", "na", "n/a", "nan", "null", "inf", "-inf"}

# --- What a number looks like ------------------------------------------------
# A regular expression ("regex") is a pattern describing what a piece of text
# should look like. re.compile() turns a pattern into an object that can be
# used again and again. The r in front of the quotes makes a "raw string":
# Python leaves the backslashes alone, so the regex receives them as written
# (in a regex, \d means "any digit").
#
# NUMBER matches a plain number. Reading the pattern from left to right:
#
#   -?               An optional minus sign. "?" means "the thing before me
#                    may appear once, or not at all".
#   (                Start of a group holding two choices, separated by "|",
#                    which means "or".
#     \d+\.?\d*      Choice 1: one or more digits (\d+), then an optional
#                    decimal point (\.?), then any number of digits, including
#                    none (\d*). The backslash before the dot means a real dot;
#                    a bare . in a regex means "any character".
#                    Examples: 42   3.5   7.
#     |              or
#     \.\d+          Choice 2: a decimal point followed by digits, like .5
#   )                End of the group.
#   ([eE][+-]?\d+)?  An optional exponent (scientific notation): e or E, an
#                    optional + or -, then digits. 1e-05 means 1 x 10 to the
#                    power -5, which is 0.00001. Programs often write very
#                    small or very large numbers this way.
#
# These match:                     42   -3.5   .5   7.   1e-05   0
# These don't, so they stay text:  +5   1,234   $5   12%   2024-11   1.2.3
#
# A leading + is left out on purpose: values like +16045551234 are usually
# phone numbers, not amounts.
NUMBER = re.compile(r"-?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")  # 42, -3.5, .5, 1e-05

# WHOLE_NUMBER matches whole numbers only: an optional minus sign, then digits,
# and nothing else (42, -7, 0). Those become Python "ints" (whole numbers).
# Every other number becomes a "float", a number with a fractional part,
# like 3.5.
WHOLE_NUMBER = re.compile(r"-?\d+")

# --- Things that look like numbers but aren't --------------------------------
# CODE matches values that look like numbers but are really labels or IDs:
#
#   -?          An optional minus sign.
#   (0\d.*      A 0 followed by another digit, then anything at all (.* means
#               "any characters, as many as there are"): 007, 02134.
#               Real amounts aren't written like that, but ZIP codes, product
#               codes and ID numbers often are. Turning "02134" into the
#               number 2134 would quietly lose the leading zero.
#   |\d{16,})   Or: 16 or more digits in a row ({16,} means "16 or more").
#               Numbers that long are nearly always IDs, such as account or
#               tracking numbers. Many programs, including JavaScript in web
#               pages, can only store about 15 or 16 digits exactly, so
#               treating these as numbers could change their last digits.
#
# If even one value in a column matches CODE, the whole column stays as text
# (see column_kind below).
CODE = re.compile(r"-?(0\d.*|\d{16,})")

# --- Names for the separators ------------------------------------------------
# A dictionary links keys to values: here, each separator character to a
# readable name for the messages the program prints. "\t" is how Python
# writes the tab character.
DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}


# =============================================================================
# STEP 1: READ THE FILE AND TURN ITS BYTES INTO TEXT
# =============================================================================
# "def" creates a function: a named block of code that runs whenever it's
# called, like read_text(csv_path) in main() below. The names in brackets
# (here, path) are the inputs it receives. The line in triple quotes just
# inside it is its "docstring", a short description of what it does. "return"
# ends the function and hands a result back to the code that called it.

def read_text(path):
    """Read the file's text and report which encoding it turned out to be in."""
    # Files store text as bytes: numbers from 0 to 255. An "encoding" is the
    # rule for turning those bytes into letters. Most files today use UTF-8,
    # but Excel can save in other encodings, so we read the raw bytes first and
    # then work out which rule fits.
    #
    # path.read_bytes() opens the file, reads all of it as bytes, and closes it.
    raw = path.read_bytes()

    # Some files start with a few invisible bytes called a "byte order mark"
    # (BOM) that say which encoding they use. UTF-16 files usually start with
    # the bytes FF FE or FE FF; codecs.BOM_UTF16_LE and codecs.BOM_UTF16_BE are
    # those two markers. Excel's "Unicode Text" save option makes UTF-16
    # files, with tabs between the values.
    #
    # startswith() usually checks for one thing; given a tuple (several items
    # in round brackets), it checks whether the bytes start with any of them.
    #
    # This check has to come before the "is it really text?" check below,
    # because UTF-16 stores ordinary letters with a 0 byte beside each one,
    # which would make the file look like a binary file.
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        # decode() turns bytes into text using the encoding named.
        #
        # A function can hand back several results at once by separating them
        # with commas. Here we return the text and the encoding's name, which
        # main() shows in its summary.
        return raw.decode("utf-16"), "UTF-16"  # Excel's "Unicode Text" format

    # A 0 byte almost never appears in text, but binary files such as Excel
    # workbooks (.xlsx), images and zip files are full of them. b"\x00" is a
    # single 0 byte (the b in front means bytes rather than text).
    # raw[:4096] is a "slice": the first 4,096 bytes, which is plenty to tell.
    if b"\x00" in raw[:4096]:
        # sys.exit() prints the message and stops the program right here.
        #
        # The f in front of the quotes makes an "f-string": anything inside
        # curly brackets is replaced with its value, so {path.name} becomes
        # the file's name, like sales.xlsx.
        #
        # Two strings written next to each other are joined into one. That
        # lets a long message be split over two lines of code.
        sys.exit(f"{path.name} isn't a text file. If it's an Excel workbook, "
                 "save it as CSV first.")

    # try/except: run the code under "try", and if it fails with the error
    # named after "except", run the code under "except" instead of crashing.
    try:
        # Decode as UTF-8. The "-sig" version also removes the invisible BOM
        # (bytes EF BB BF) that Excel puts at the start of files saved as
        # "CSV UTF-8". Without it, the first column's name would start with a
        # hidden character and wouldn't match the name you see.
        return raw.decode("utf-8-sig"), "UTF-8"  # -sig drops the marker Excel adds
    except UnicodeDecodeError:
        # The bytes weren't valid UTF-8. The most likely alternative is
        # Windows-1252 (also called cp1252), which Excel on Windows uses for
        # its plain "CSV (Comma delimited)" option in English and most Western
        # European setups. It stores letters like é and symbols like €
        # differently from UTF-8.
        #
        # errors="replace" means any byte that still can't be read becomes
        # the symbol � instead of stopping the program.
        return raw.decode("cp1252", errors="replace"), "Windows-1252"  # Excel on Windows


# =============================================================================
# STEP 2: WORK OUT WHICH CHARACTER SEPARATES THE VALUES
# =============================================================================

def detect_delimiter(text):
    """Work out whether values are separated by commas, semicolons, tabs or pipes."""
    # "CSV" stands for "comma-separated values", but plenty of CSV files use
    # something else. Where a comma is the decimal point (3,5 rather than
    # 3.5), Excel separates values with semicolons instead. Files exported
    # from databases often use tabs or the | character.
    #
    # We only need to look at the start of the file to tell. 50_000 is just
    # 50000: Python lets you put underscores in numbers to make them easier to
    # read. text[:50_000] means "the first 50,000 characters", or the whole
    # text if it's shorter than that.
    sample = text[:50_000]

    # If the file is longer than the sample, the cut probably landed in the
    # middle of a line. That half line would look different from the others
    # and could throw off the detection, so we drop it. rsplit("\n", 1) splits
    # the text once, at the last line break ("\n"), and [0] keeps the part
    # before it.
    if len(text) > len(sample):
        sample = sample.rsplit("\n", 1)[0]  # end the sample on a whole line

    try:
        # csv.Sniffer is a tool in Python's csv module that guesses a file's
        # format. Mostly it looks for a character that appears the same number
        # of times on every line, because that's what a separator does. We
        # tell it to consider only these four characters, which makes its
        # guess more reliable. sniff() returns a description of the format,
        # and .delimiter picks out the separator from it.
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        # The Sniffer gives up (by raising csv.Error) when none of the four
        # fits. That happens with a single-column file, which has no
        # separators at all. Commas are the safest thing to assume.
        return ","  # no clear pattern (for example, a single column): assume commas


# =============================================================================
# STEP 3: SPLIT THE TEXT INTO ROWS AND VALUES
# =============================================================================

def read_rows(text, delimiter):
    """Split the text into the header and the data rows, tidying common problems."""
    # Why not just split each line at every comma? Because a CSV value can
    # contain commas, quotes and even line breaks, as long as the value is
    # wrapped in double quotes, with any quote inside it doubled:
    #
    #     1,"Smith, John","She said ""hi""","two
    #     lines"
    #
    # That's one row with four values. Splitting at commas by hand would
    # cut "Smith, John" in two. The csv module knows all these rules.
    #
    # csv.reader wants something it can read line by line, like an open file.
    # io.StringIO wraps our text so it behaves like one. newline="" keeps the
    # line breaks exactly as they are, which the csv module needs to handle
    # values that contain line breaks (the csv module's documentation
    # recommends it).
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)

    # Three variables set up in one line:
    #   header       the column names. It starts as None (Python's way of
    #                saying "nothing yet") until we reach the first row.
    #   rows         an empty list that will collect every data row
    #   short_lines  line numbers of rows that had too few values, so main()
    #                can mention them in its summary
    header, rows, short_lines = None, [], []

    # Each time round this loop, the reader hands us the next row as a list of
    # strings, one per value. For example, the line   Ana, 34 ,true
    # arrives as   ["Ana", " 34 ", "true"].
    for values in reader:
        # Remove spaces from both ends of every value: " 34 " becomes "34".
        # This is a "list comprehension": it builds a new list by doing
        # something (v.strip()) to each item (v) of another list (values).
        values = [v.strip() for v in values]

        # any() is True if at least one value isn't empty (an empty string
        # counts as False). So "not any(values)" means every value is empty:
        # a blank line, or a row of nothing but separators like ",,,", which
        # Excel sometimes leaves at the end of a file. "continue" skips the
        # rest of the loop and moves straight on to the next row.
        if not any(values):
            continue  # blank line

        # The first row that isn't blank is the header: the column names.
        # "is None" is how you check whether something is None.
        if header is None:
            header = values
            continue

        # A row identical to the header is the header repeated. That happens
        # when several CSV files, each with its own header line, have been
        # stuck together into one. It isn't data, so skip it.
        if values == header:
            continue  # the header repeated, e.g. from files joined together

        # values[len(header):] is a slice: every value after the last column.
        # For a normal row that's an empty list. If any of those extra values
        # has something in it, the row doesn't fit the columns. The usual cause
        # is a separator inside a value that should have been in quotes:
        #
        #     name,city
        #     Smith, John,Paris      <- 3 values, but only 2 columns
        #
        # There's no way to know which column the extra value belongs to, so
        # we stop and say which line to fix, rather than produce wrong data.
        if any(values[len(header):]):
            # .get() looks the separator up in DELIMITER_NAMES, so "," gives
            # "comma". Its second input is a fallback for characters that
            # aren't in the dictionary: repr() shows the character in quotes.
            name = DELIMITER_NAMES.get(delimiter, repr(delimiter))
            # reader.line_num is the line where the row we just read ends,
            # counting from 1 at the top of the file, so the message points
            # to the right place.
            sys.exit(f"Line {reader.line_num} has more values than there are columns "
                     f"(a {name} inside a value that isn't in quotes?)")

        # If we got here, any extra values are empty. They come from a
        # separator at the end of the line: "1,2,3," has an empty fourth value.
        # values[:len(header)] keeps only as many values as there are columns.
        values = values[:len(header)]  # drop empty extras left by trailing separators

        # Some programs leave out empty values at the end of a row, so "1,2"
        # might appear in a file with three columns. We pad the row with empty
        # strings so it has a value for every column; empty strings become
        # null later on. [""] * 2 makes ["", ""], and += adds those to the end
        # of the list. We also note the line number so main() can mention it.
        if len(values) < len(header):
            short_lines.append(reader.line_num)
            values += [""] * (len(header) - len(values))  # these become null

        # The row now has exactly one value per column. Add it to the list.
        rows.append(values)

    # Hand all three results back to main(). If the file had no rows that
    # weren't blank, header is still None, and main() reports that the file
    # is empty.
    return header, rows, short_lines


# =============================================================================
# STEP 4: TIDY UP THE COLUMN NAMES
# =============================================================================

def unique_names(header):
    """Name blank columns and make repeated names unique, so no column is lost."""
    # Each row becomes a JSON object, and an object can't have two keys with
    # the same name. If a CSV had two columns called "value", the second would
    # overwrite the first and its data would be lost. A column with no name at
    # all is also common: pandas (a popular Python library for working with
    # data) saves its row numbers in a first column with a blank header.
    # So, for example:
    #
    #     ["", "value", "value"]   becomes   ["column_1", "value", "value_2"]
    names = []

    # enumerate() hands out a counter alongside each item. start=1 makes it
    # count from 1, like spreadsheet columns, instead of Python's usual 0.
    # So i is the column's position and name is the text of its header.
    for i, name in enumerate(header, start=1):
        # "or" gives back the value on its left unless that value is empty,
        # in which case it gives back the value on its right. So a blank name
        # becomes "column_" followed by the column's position: "column_1".
        base = name or f"column_{i}"

        # Start with the name as it is. n is the number to try adding next.
        name, n = base, 2

        # While that name is already taken, try base_2, then base_3, and so
        # on. Both variables change together: the new name is built using the
        # current n, and then n goes up by one.
        while name in names:
            name, n = f"{base}_{n}", n + 1

        # This name is free, so claim it.
        names.append(name)
    return names


# =============================================================================
# STEP 5: DECIDE WHAT KIND OF DATA EACH COLUMN HOLDS
# =============================================================================

def column_kind(values):
    """Look at every value in a column and decide what the column holds."""
    # In a CSV, everything is text, even numbers: the file holds the
    # characters "3" and "4", not the number 34. This function looks at one
    # whole column and decides whether its values should become numbers,
    # true/false values, or stay as text.
    #
    # values is one column's values from every row. For an "age" column it
    # might be ["34", "", "28"].
    #
    # Deciding for the whole column, rather than value by value, keeps each
    # column consistent. Take a ZIP code column holding "02134" and "90210".
    # Deciding value by value would give the text "02134" in one row and the
    # number 90210 in the next. Deciding for the column keeps both as text.

    # Leave out the missing values: they'll become null whatever kind the
    # column is, so they shouldn't count in the decision.
    present = [v for v in values if v.lower() not in MISSING]

    # Nothing left? Then every value in the column is missing, or the file
    # has no data rows. This has to be checked first, because all() (used
    # below) says True for an empty list, which would wrongly call an empty
    # column true/false.
    if not present:
        return "empty"

    # all() is True only if the check is true for every value; it stops as
    # soon as one fails. So this asks: is every value "true" or "false", in
    # any mix of capitals (Excel writes TRUE and FALSE)?
    if all(v.lower() in ("true", "false") for v in present):
        return "true/false"

    # Is every value a plain number? fullmatch() means the WHOLE value must fit
    # the pattern, not just part of it, so "12abc" doesn't count. And none of
    # them may be a code that only looks like a number, such as 02134.
    if all(NUMBER.fullmatch(v) and not CODE.fullmatch(v) for v in present):
        return "numbers"

    # Anything else stays as text. That's the safe choice: nothing can be
    # lost, because text is exactly what was in the file.
    return "text"


# =============================================================================
# STEP 6: CONVERT EACH VALUE
# =============================================================================

def convert(value, kind):
    """Turn one cell's text into the JSON value its column calls for."""
    # value is one cell's text, like "34", and kind is what column_kind
    # decided about its column, like "numbers". This returns the Python value
    # that will go into the JSON. When the JSON is written:
    #
    #     None           becomes   null
    #     True / False   become    true / false
    #     34, 3.5        stay      34, 3.5
    #     "some text"    stays     "some text"

    # Missing values become None (null) whatever kind the column is.
    if value.lower() in MISSING:
        return None

    if kind == "numbers":
        # Whole numbers become ints: int("34") gives 34.
        if WHOLE_NUMBER.fullmatch(value):
            return int(value)
        # Everything else becomes a float: float("3.5") gives 3.5, and
        # float("1e-05") gives 0.00001 (which Python writes as 1e-05).
        number = float(value)
        # A number too big for the computer to hold, like 1e400, becomes
        # infinity. JSON can't store infinity, so we use None (null) instead.
        # This line is a "conditional expression": it gives back number if
        # math.isfinite(number) is True, and None otherwise.
        return number if math.isfinite(number) else None  # JSON has no infinity

    if kind == "true/false":
        # value.lower() == "true" is itself either True or False, which is
        # exactly what we want: "TRUE" gives True, "False" gives False.
        return value.lower() == "true"

    # Text columns (and anything else): keep the text exactly as it is.
    return value


# =============================================================================
# SMALL HELPERS FOR THE SUMMARY MESSAGES
# =============================================================================

def plural(n, word):
    # Puts a number in front of a word, adding "s" unless the number is 1:
    #     plural(1, "row")  gives  "1 row"
    #     plural(3, "row")  gives  "3 rows"
    return f"{n} {word}" + ("" if n == 1 else "s")


def shorten(items, limit):
    """List items with commas, cutting long lists short."""
    # Joins the items into one piece of text, but stops after `limit` of them
    # so that a file with hundreds of columns doesn't print a wall of text:
    #     shorten(["a", "b", "c"], 5)       gives  "a, b, c"
    #     shorten(["a", "b", "c", "d"], 2)  gives  "a, b and 2 more"
    #
    # str() turns each item into text. We need that because line numbers
    # are passed in too, and join() only works with text.
    items = [str(item) for item in items]
    more = f" and {len(items) - limit} more" if len(items) > limit else ""
    # ", ".join(...) glues the items together with ", " between each pair.
    return ", ".join(items[:limit]) + more


# =============================================================================
# THE MAIN PROGRAM: RUNS ALL THE STEPS IN ORDER
# =============================================================================

def main():
    # --- Get the CSV file's name from the command line -----------------------
    # sys.argv is a list of the words you typed to run the program, starting
    # with the program's own file name. For
    #     python3 main.py sales.csv
    # it is ["main.py", "sales.csv"], so sys.argv[1] is the CSV's name.
    # (Lists count from 0, so [1] is the second item.)
    #
    # If there aren't exactly two words, show how to use the program and stop.
    # (The message says csv_to_json.py because that was this file's original
    # name. You can change it to "Usage: python3 main.py input.csv".)
    if len(sys.argv) != 2:
        sys.exit("Usage: python csv_to_json.py input.csv")

    # Path() turns the file name into a Path object, which knows useful things
    # about the file: its name, its extension, whether it exists, and so on.
    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        sys.exit(f"Can't find {csv_path}")

    # --- Steps 1 to 3: read the file, find the separator, split into rows ----
    # read_text returns two things, so we catch them in two variables.
    text, encoding = read_text(csv_path)
    delimiter = detect_delimiter(text)

    # The csv module raises csv.Error when it hits something it can't read,
    # such as a single value too large to handle. Catch that and explain it in
    # one line, instead of letting Python print a long error report.
    # "as error" keeps the error so its message can go into ours.
    try:
        header, rows, short_lines = read_rows(text, delimiter)
    except csv.Error as error:
        sys.exit(f"Couldn't read {csv_path.name} as a CSV file: {error}")

    # read_rows leaves header as None if every line in the file was blank.
    if header is None:
        sys.exit(f"{csv_path.name} is empty")

    # --- Steps 4 to 6: tidy the names, decide each column's kind, convert ----
    columns = unique_names(header)

    # Decide each column's kind. Reading from the inside out:
    #   [row[i] for row in rows]      collects the value in position i from
    #                                 every row: that's column i. (row[0] is a
    #                                 row's first value, row[1] its second...)
    #   column_kind(...)              decides what that column holds
    #   for i in range(len(columns))  does this for every column position.
    #                                 range(3) gives 0, 1, 2.
    # The result is one kind per column, e.g. ["text", "numbers", "true/false"].
    kinds = [column_kind([row[i] for row in rows]) for i in range(len(columns))]

    # Build one dictionary per row; each becomes one object in the JSON.
    # zip() walks through several lists side by side, taking one item from
    # each at a time. For columns ["name", "age"], kinds ["text", "numbers"]
    # and the row ["Ana", "34"], it gives ("name", "text", "Ana") and then
    # ("age", "numbers", "34").
    # The part in curly brackets is a "dictionary comprehension": it turns
    # those into the dictionary {"name": "Ana", "age": 34}. The square
    # brackets around it do the same for every row, giving a list of them.
    records = [
        {column: convert(value, kind) for column, kind, value in zip(columns, kinds, row)}
        for row in rows
    ]

    # --- Write the JSON file -------------------------------------------------
    # Path.cwd() is the "current working directory": the folder you ran the
    # command from. csv_path.stem is the CSV's name without its extension
    # ("sales.csv" gives "sales"). The / between them joins a folder and a
    # file name into one path, giving something like <your folder>/sales.json.
    # The JSON always goes in the current folder, even if you gave the CSV's
    # path somewhere else.
    json_path = Path.cwd() / f"{csv_path.stem}.json"

    # Check whether the file already exists, so the summary can say it was
    # replaced. This must happen before writing, since writing creates it.
    replacing = json_path.exists()

    # open(..., "w") opens the file for writing. If the file already exists,
    # its old contents are erased first; that's how it gets replaced.
    #
    # Every check that can stop the program comes before this point, so if
    # the CSV can't be read, an existing JSON file is left untouched.
    #
    # "with" closes the file automatically when the indented block ends, even
    # if something goes wrong while writing. encoding="utf-8" saves it as
    # UTF-8, the standard encoding for JSON.
    with open(json_path, "w", encoding="utf-8") as f:
        # json.dump writes the Python data into the file as JSON:
        #   indent=2            puts each value on its own line, indented by
        #                       2 spaces, so the file is easy to read
        #   ensure_ascii=False  writes letters like é and € as they are,
        #                       instead of as codes like é
        json.dump(records, f, indent=2, ensure_ascii=False)

    # --- Print a summary -----------------------------------------------------
    # This shows what the program decided, so you can check its guesses.
    # For example:
    #     Read sales.csv: 3 rows, 4 columns, comma-separated, UTF-8
    #       numbers:    price, quantity
    #       true/false: in_stock
    #       text:       name
    #     Wrote /Users/you/project/sales.json
    separator = DELIMITER_NAMES.get(delimiter, repr(delimiter))
    print(f"Read {csv_path.name}: {plural(len(rows), 'row')}, "
          f"{plural(len(columns), 'column')}, {separator}-separated, {encoding}")

    # One line for each kind of column that appears in the file.
    for kind in ("numbers", "true/false", "text", "empty"):
        # The names of the columns that were given this kind.
        names = [c for c, k in zip(columns, kinds) if k == kind]
        if names:
            # {kind + ':':<12} adds a colon to the kind and pads it with
            # spaces to 12 characters wide (< means "line it up on the left"),
            # so the lists of column names all start in the same place.
            print(f"  {kind + ':':<12}{shorten(names, 12)}")

    # If any rows were padded with nulls, say which ones, so you can check.
    if short_lines:
        where = "line" if len(short_lines) == 1 else "lines"
        print(f"  Note: {plural(len(short_lines), 'row')} had too few values "
              f"({where} {shorten(short_lines, 5)}); the missing ones are null")

    # Another conditional expression: add the note only if a file was replaced.
    print(f"Wrote {json_path}" + (" (replaced the existing file)" if replacing else ""))


# =============================================================================
# START THE PROGRAM
# =============================================================================
# Python sets the special variable __name__ to "__main__" when you run this
# file directly (python3 main.py ...), so main() runs. If another Python file
# imports this one to reuse its functions, __name__ is set to something else,
# and main() doesn't run by itself.
if __name__ == "__main__":
    main()