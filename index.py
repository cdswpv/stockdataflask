import sqlite3
from flask import Flask, render_template, request, url_for, flash, redirect, abort
from datetime import datetime, timedelta
import pygal, re, csv
from pygal.style import Style
import requests

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'your secret key'

@app.route("/", methods=['GET', 'POST'])
def stocks():
    if request.method == 'POST':
        
        global symbol
        symbol = request.form['symbol']

        global chartType
        chartType = request.form['chartType']

        global timeSeries
        timeSeries = setTimeSeries(request.form['timeSeries'])

        global startDate
        startDate = request.form['startDate']
        #startDate = request.form['startDate']
        #flash(startDate)

        global endDate
        endDate = request.form['endDate']
        #endDate = request.form['endDate']
        #flash(endDate)

        global api
        api = "ARJ4YHDD7BSSD94B"

        
        if symbol == "":
            flash("Symbol is required")
        elif chartType == "":
            flash("Select a Chart Type")
        elif timeSeries == "":
            flash("Select a Time Series")
        elif startDate == "":
            flash("Select a Start Date")
        elif endDate == "":
            flash("Select an End Date")
        elif endDate <= startDate:
            #Generate error and pass to the page
            flash("ERROR: End date cannot be earlier than the Start date")
        else:
            #query the api using form data
            startDate = convertDate(request.form['startDate'])
            endDate = convertDate(request.form['endDate'])
            pullStock()

            #use bar/line or whatever the graph functions will accept
            if chartType == '1':
                chart = create_bar_graph()
            elif chartType == '2':
                chart = create_line_graph()
        
            return render_template("stock.html", chart = chart, symbolList = getSymbols())
    return render_template("stock.html", symbolList = getSymbols())

def getSymbols():
    localList = []
    with open('stocks.csv', 'r') as csvFile:
        csvReader = csv.reader(csvFile)
        next(csvReader)
        for row in csvReader:
            localList.append(row[0])
    return localList

def pullStock():
    interval = "&interval=15min" if timeSeries == "TIME_SERIES_INTRADAY" else ""
    url = f"https://www.alphavantage.co/query?function={timeSeries}&symbol={symbol}{interval}&apikey={api}"
    r = requests.get(url)
    global stockData
    stockData = r.json()

def convertDate(date):
    return datetime.strptime(date, '%Y-%m-%d').strftime("%Y-%m-%d")

def create_line_graph():
    '''
    Creates a Line Graph of given data and displays in the user's default browser.
    '''
    return create_graph(stockData, pygal.Line())

def create_bar_graph():
    '''
    Creates a Bar Graph of given data and displays in the user's default browser.
    '''
    return create_graph(stockData, pygal.Bar())

def create_graph(json: dict, graph: pygal.Graph):
    '''
    Creates a graph from the given data and displays it in the user's default browser.

    Parameters:
        json: A dictionary representation of the data JSON.
        graph: A pygal graph object (pygal.Bar() & pygal.Line() are known to work)
    '''
    dates = []
    options = { "Open": [], "High": [], "Low": [], "Close": [] }

    #   Extracts the data points from the JSON, now reformatted and sorted
    data = extract_data(json)
    #   Creates a function to format the dates properly
    datetime = string_to_datetime()

    #   Formats data from JSON to be used by graph
    for item in data:
        dates.append(datetime(item["date"]))
        options["Open"].append(float(item["1. open"]))
        options["High"].append(float(item["2. high"]))
        options["Low"].append(float(item["3. low"]))
        options["Close"].append(float(item["4. close"]))

    #   Add data and labels to graph
    for opt in options: graph.add(opt, options[opt])
    graph.x_labels = dates
    graph.title = create_title()

    #   Styles the graph
    graph_styling(graph, len(dates))

    #   Renders the graph as an SVG in the user's default browser
    return graph.render_data_uri()

def string_to_datetime():

    previous = datetime(1, 1, 1)

    def convert(date: str):
        #   Stores the previous day as a static variable
        nonlocal previous

        if (timeSeries == "TIME_SERIES_INTRADAY"):
            #   For Intraday graphs:
            day = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
            if (day.date() == previous.date()):
                #   Format the date as HH:MM:SS
                format = '%H:%M:%S'
            else:
                #   Unless the data point is the start of a new day
                #   In that case format as YY-MM-DD HH:MM:SS
                format = '%Y-%m-%d %H:%M:%S'
                previous = day

            return day.strftime(format)
        else:
            #   For all other graph types, format is YYYY-MM-DD
            return datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d')
    return convert

def get_date(item: dict):
    '''
    Gets the value of "date" from a dictionary (used for sorting)
    '''
    return item["date"]


def extract_data(json: dict):
    '''
    Reformats the JSON response into an array containing each data point as a self contained dictionary.

    Parameters:
        json: A dictionary representing the response from the API

    Returns:
        Array of the newly minted data points. list[dict[str, Any]]
    '''
    #   Finds the "Time Series" key within the dictionary, whether it is "Time Series (Daily)", "... (Monthly)", or "... (15min)"
    #   Loops through keys, checks if they match, then will return the first (and only) instance
    try:
        time_series = [k for k in json.keys() if re.match(r".*Time Series.*", k)][0]
    except IndexError:
        raise ValueError("Could not find data for this query")

    #   Takes each line that looks like this: "YYYY-MM-DD": {"key1": "value1", "key2": "value2"}
    #   Converts it to this {"date": "YYYY-MM-DD", "key1": "value1", "key2": "value2"}
    #   And places them all into a list
    data_points = [{"date": k, **v} for k, v in json[time_series].items()]

    #   Sorts the list using the get_date function and returns it
    data_points.sort(key = get_date)

    #   Finds index of Begin Date and End date
    start = get_date_index(data_points, startDate)
    end = get_date_index(data_points, endDate)

    #   Gets the data between the given dates
    return segment_data(data_points, start, end)


def create_title():
    '''
    Creates the title for the graph using data from app.py.
    
    Returns:
        Title as string.
    '''
    return f"Stock Data for {symbol}: startDate to {endDate}"

def graph_styling(graph: pygal.Graph, point_count: int):
    '''
        Adds styling to the graph object. It has no bearing on the functions of the program, only the readability of the final graph.

        Parameters:
            graph: a pygal graph
            point_count: an int representing the number of data points on the graph
    '''
    #   Make larger graphs more readable
    if (point_count > 100):
        graph.x_labels_major_every = 10
        graph.show_minor_x_labels = False

    #   Many elements use the number of points on the graph to make elements proportional.
    graph.style = Style(
        label_font_size = point_count/3,
        major_label_font_size = point_count/3,
        stroke_width = 15,
        legend_font_size = point_count/2,
        title_font_size = point_count,
        tooltip_font_size = point_count/3
    )
    graph.dots_size = 15
    graph.x_label_rotation = 90
    graph.width = point_count * 50
    graph.height = point_count * 25 
    graph.legend_box_size = point_count/3


def get_date_index(data: list, date: str):
    '''
    Finds the index of the item with the given data

    Parameters:
        data: list of all data points
        date: string representing date to be searched for in formate YYYY-MM-DD

    Returns:
        int representing index of the item in the list OR -1 to represent the date not existing
    '''

    #   If it is weekly data try to find a date near the requested date
    if (timeSeries == "TIME_SERIES_WEEKLY"):
        date: datetime = datetime.strptime(date, "%Y-%m-%d")
        dates = [date]
        for i in range(-3,4):
            week_day = (date + timedelta(days=i)).strftime("%Y-%m-%d")
            print(week_day)
            for k in range(len(data)):
                if week_day in data[k]["date"]:
                    return k
        return -1

    #   If monthly only check the month and year fields
    if (timeSeries == "TIME_SERIES_MONTHLY"):
        date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m")

    #   Iterate through data to find index of date in data
    for i in range(len(data)):
        if date in data[i]["date"]:
            return i
    return -1


def segment_data(data:list, start:int, end:int):
    '''
    Retrieves the segement of the data between two index points

    Parameters:
        data: the list of the dictionary data points

    '''
    start = start if start != -1 else 0
    end = end if end != -1 else len(data)
    return [data[i] for i in range(start, end)]

def setTimeSeries(x):
    if x == "1":
        return "TIME_SERIES_INTRADAY"
    elif x == "2":
        return "TIME_SERIES_DAILY_ADJUSTED"
    elif x == "3":
        return "TIME_SERIES_WEEKLY"
    elif x == "4":
        return "TIME_SERIES_MONTHLY"

app.run(host='0.0.0.0')