# CLAUDE.md

Important: please abide by my ~/.claude/CLAUDE.md file for my standard setup instructions.

I want to create a new Python project called "hve". The acronym stands for "highest volume ever". In "setup mode", the project creates or updates a SQLite database with a row for each stock symbol in the data universe that includes the date and volume for the highest volume ever experienced for that stock. In "realtime mode", the project monitors volume every 30 minutes to see if current volume for today exceeds the "highest volume ever", comparing the values in the database. In "historical mode", the project will identify any stock symbols that have experienced highest volume ever events on or after a date that is passed in as an argument.

## Setup Mode

Setup mode occurs whenever:

- The SQLite database does not exist yet
- The data is "stale" **

The logic of the application should always check these two conditions and not continue to "realtime mode" or "historical mode" until these two conditions are satisfied.

** "Stale" data means that the data from yesterday or earlier has not updated new "highest volume ever" events in the database for stock symbols. So, if I have not run the application for several days, the application should go back to the last known "run", and should query Polygon.io for the missing days, and if there are new "highest volume ever" events, it should update the date and volume for the given stock symbol.

If the SQLite database does not exist yet, the logic should create a database and table, and use the instructions in the `Data universe` section, below, to identify the "highest volume ever", and record it. Since this could take a very long time, send an email notification when this long running operation is complete.

Setup mode runs regardless of market hours to ensure the database is always current when needed.

Display the progress of "setup mode" as a progress bar in the console window, if possible.


## Realtime mode

To run in realtime mode, the user would use the command:

`python main.py`

If it is running on a weekend or holiday, or after 3pm on a weekday, assuming it is not in "setup mode" (above) the application should exit.

Since "realtime mode" will run for hours (from early in the morning until end of trading day) show a heart-beat in the console every minute as you monitor the current time in preparation for the next 30-minute "run".

## Historical mode

To run in historical mode, the user would use the command:

`python main.py historical 9-16-2025`

The example above will find all "highest volume ever" events on September 16th, 2025 and later.

The application will exit as soon as it has displayed the results to the console, created daily .txt files, and sent an email.


## Data universe

The data to be used for this project is daily OHLCV data and 1-minute snapshot data from Polygon.io (as outlined in the standard setup instructions). 

Only use "common stocks" from the NYSE and NASDAQ for this project.

When working in "realtime mode", you will use the 1-minute snapshot data. The snapshot JSON payload will have a bunch of data for each stock symbol. You need the "day" > "v" for a given symbol as shown in this snippet of JSON:

```json
{
  "tickers": [
    {
      "ticker": "HYMCL",
      "todaysChangePerc": -31.746031746031743,
      "todaysChange": -0.004,
      "updated": 1758321060000000000,
      "day": {
        "o": 0.0125,
        "h": 0.0125,
        "l": 0.0052,
        "c": 0.0082,
        "v": 384413,
```

When working in "setup mode", you will use the daily OHLCV data. To build the SQLite database, you will need to look through all daily OHLVC as far back as you can go. This is "all time", NOT just within the past year, NOT just within the past 5-years. You should look back as far as Polygon.io has data for a given stock symbol to find the highest volume ever.

When working in "historical mode", you merely need the SQLite database since you'll query all "highest volume ever" events that have occurred since a given date.


## Email

In "realtime mode", the application will identify stocks where the current volume for the current day is greater than the previous "highest volume ever" value stored in the database. Each "hit" should be added to a list, then sent via an email, one email for each 30-minutes. Use the following to send an email:

Subject line: Highest volume ever - 1:30 PM

(Use the correct time of day, formatted like my example, above)

Body: Create a table with the symbol, the old highest volume date and volume, today's volume, and today's gain / loss percentage.


In "historical mode", the application will identify stocks that experienced a "highest volume ever" event since the date passed in as a command line argument. Use the following to send an email:

Subject line: Highest volume ever events - Since 9/16/2025

(Use the correct date, formatted like my example, above)

Body: Create a table with the symbol, the highest volume date and volume. Sort by date descending, then symbol ascending.



## Parallel processing

You should automatically detect the number of cores available to the application and use multiple cores to query Polygon.io since this is an IO-bound operation. I have a paid Polygon.io subscription and there are no limits to the number of calls in a given minute. Optimize for IO-bound calls.


## Answers to clarifying questions

Question: 1. Database schema: Should the SQLite table store just the symbol, date, and volume for the highest volume ever? Or should it also track additional metadata like the stock's name, exchange, etc.?

Answer: Do not store additional data. Only store the minimum data that is required and nothing more.

Question: 2. Time zone handling: The global instructions mention CST for display, but should the database store timestamps in UTC/GMT (as received from Polygon.io) and only convert to CST for display purposes?

Answer: You shouldn't need the notion of "time" in the database. I only care about the DAY for "highest volume ever" events. But if there's ever an occassion when you need to store a time value, ALWAYS use Central Standard Time.

Question: 3. Historical data depth: When building the initial database in setup mode, how far back should I go? Should I use a reasonable limit (like 10-20 years) or truly attempt to get "all time" data which could be extremely expensive and time-consuming?

Answer: "All time" means "all time" -- to the very beginning of time. I know Polygon.io has a limit. Please go back as far in time as Polygon.io allows. You will need to implement paging logic for this.

Question: 4. Error handling for delisted stocks: What should happen if a stock symbol in the database has been delisted and no longer appears in current market data?

Answer: I am only interested in CURRENT ACTIVE stocks. When you get a list of all symbols, you can check whether the symbol is active or not (it's where you obtain the stock type as "common stock" from Polygon.io).

Question: 5. Market hours validation: For the 3pm cutoff, should this be 3pm CST or market close time (which varies seasonally between 3pm and 4pm CST)?

Answer: This is a more complex question than initially meets the eye. First, all times are always expressed in Central Standard Time (CST), unless otherwise noted.And it is true that CST does observe Daylight Savings Time. This shouldn't be a problem if you use the local datetime on the computer which will always be the correct datetime. However, there are a couple of days a year where the market closes early. You can use Polygon's "market status" endpoint to determine what time to shut down the application. You will likely need to convert that value to CST.

Question: 6. Weekend/holiday detection: Should I use the Polygon.io market status API to determine if the market is closed, or implement my own calendar logic?

Answer: Use Polygon.io's market status API.

Question: Data staleness tracking: To determine if data is "stale" (missing updates for recent days), should I store a separate metadata table that tracks the last successful update date for the entire database, or should I determine staleness by checking if any symbols are missing recent daily data?

Answer: I don't care which approach you take as long as it is accurate. I'll leave the implementation details for you to decide.

## File Output

In "historical mode", in addition to console output and email notifications, create separate .txt files per day in the date range. Name the files using the format YYYY-MM-DD-ever.txt (e.g., 2025-09-16-ever.txt) so files sort correctly in the filesystem. Write the symbols to each file, one per row, sorted alphabetically. Overwrite the files if they already exist.

