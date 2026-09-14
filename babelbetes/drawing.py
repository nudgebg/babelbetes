# File: drawing.py
# Author Jan Wrede
# Copyright (c) 2025 nudgebg
# Licensed under the MIT License. See LICENSE file for details.
from datetime import timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from babelbetes import pandas_helper
from babelbetes.pandas_helper import get_hour_of_day
    
colors = {'Bolus': 'red', 'Basal': 'blue', 'CGM': 'darkgray'}


def default_figure(width=8,height=4):
    f = plt.figure(figsize=(width,height))
    ax = f.gca()
    return f, ax

def create_axis():
    """Creates a new figure and axis for plotting.
    
    Returns:
        figure (matplotlib.figure.Figure): The created figure.
        axes (matplotlib.axes.Axes): The created axis.

    """
    fig, ax = plt.figure(figsize=(10, 2)), plt.gca()
    return fig, ax

def format_time_axis(ax, major_interval_days=1, minor_interval_hours=2,major_format='%-d/%-m/%Y', minor_format='%H:%M:%S'):
    """
    Formats the x-axis of the given matplotlib axis for time series plots.
    Sets major ticks to days and minor ticks to hours, with appropriate formatting.

    Args:
        ax (matplotlib.axes.Axes): The axis to format.
    """
    # Minor ticks: every 2 hours, show time
    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=minor_interval_hours))
    ax.xaxis.set_minor_formatter(mdates.DateFormatter(minor_format))

    # Major ticks: every day, show date
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=major_interval_days))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(major_format))

    # Rotate and style tick labels
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, weight='bold', fontsize=8)
    plt.setp(ax.xaxis.get_minorticklabels(), rotation=45, fontsize=8)

def parse_duration(duration_str):
    """
    Parses a duration string in the format "HH:MM:SS" and returns a timedelta object.
    
    Args:
        duration_str (str): A string representing the duration in the format "HH:MM:SS".
    Returns:
        timedelta: A timedelta object representing the parsed duration.
    """
    hours, minutes, seconds = map(int, duration_str.split(":"))
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

def drawCGM(ax, datetimes, values, color=colors['CGM'], unit='mg/dL',target_range=True, **kwargs):
    """Draws CGM (Continuous Glucose Monitoring) data on the given axes.

    Args:
        ax (matplotlib.axes.Axes): The axes on which to draw the CGM data.
        datetimes (list of datetime): List of datetime objects representing the time points.
        values (list of float): List of glucose values corresponding to the datetime points.
        color (str, optional): Color for the CGM plot. Defaults to colors['CGM'].
        **kwargs (dict): Additional keyword arguments to customize the plot.
    """
    defaults = {'color': color, 'label': 'CGM', 's': 10}
    defaults.update(kwargs)
    
    if unit == 'mmol/L':
        values = values * 18.01559
    elif unit != 'mg/dL':
        raise ValueError(f'Unknown unit: {unit}')
    if target_range:
        ax.axhspan(70, 180, color='lightgreen', alpha=0.2)

    ax.scatter(datetimes, values, **defaults)
    ax.set_ylabel('Glucose (mg/dL)')
    ax.legend()

def drawBasal(ax, datetimes, rates, color=colors['Basal'], **kwargs):
    """Draws the basal rates on the given axes.
    
    Args:
        ax (matplotlib.axes.Axes): The axes on which to draw the basal rates.
        datetimes (list of datetime): List of datetime objects representing the time points.
        rates (list of float): List of basal rates corresponding to the datetime points.
        color (str, optional): Color for the basal rates plot. Defaults to colors['Basal'].
        **kwargs (dict): Additional keyword arguments to customize the plot.
    """
    defaults = {'color': color, 'fill': True, 'alpha': 0.5, 'edgecolor': 'blue', 'label': 'basal'}
    defaults.update(kwargs)
    ax.stairs(rates[:-1], datetimes, **defaults)

    # add stems for the rates without marker (no label, the bars carry it)
    defaults = {'markerfmt': ' ', 'basefmt':' '}
    defaults.update(kwargs)
    defaults.pop('label', None)
    ax.stem(datetimes, rates, **defaults)

def drawBoluses(ax, datetimes, boluses, **kwargs):
    """ Draws insulin boluses events on a given matplotlib axis.

    Args:
        ax (matplotlib.axes.Axes): The axis on which to draw the boluses.
        datetimes (list of datetime.datetime): List of datetime objects representing the times of the boluses.
        boluses (list of float): List of bolus values corresponding to the datetimes.
        **kwargs (dict): Additional keyword arguments passed to the ax.bar() method.
    """
    if len(boluses) > 0:
        defaults= {'width': timedelta(minutes=15), 'color': colors['Bolus'], 'label': 'boluses', 'align': 'center'}
        defaults.update(kwargs)
        ax.bar(datetimes, boluses, **defaults)
        
        # Add end caps to the boluses
        ax.scatter(datetimes, boluses, marker='^', color=defaults['color'], s=20)

def drawExtendedBoluses(ax, datetimes, boluses_units, duration, color=colors['Bolus'], **kwargs):
    """Draws extended boluses on the given axes.

    Args:
        ax (matplotlib.axes.Axes): The axes on which to draw the boluses.
        datetimes (list of datetime): List of datetime objects representing the times of the boluses.
        boluses_units (list of float): List of bolus units corresponding to each datetime.
        duration (list of numpy.timedelta): List of delivery duration for each bolus.
        color (str, optional): Color of the boluses. Default is colors['Bolus'].
        **kwargs (dict): Additional keyword arguments to pass to the bar function.
    """
    for i in range(len(datetimes)):
        duration_hours = duration[i]/np.timedelta64(1, 'h')
        ax.bar(datetimes[i], boluses_units[i]/duration_hours, width=duration[i], color=color, align='edge', alpha=0.5, label='extended boluses', **kwargs)

def drawTempBasal(ax, datetimes, temp_basal_rates, temp_basal_durations, temp_basal_types, color=colors['Basal'], **kwargs):
    """Draws temporary basal rates on the given axes.

    Args:
        ax (matplotlib.axes.Axes): The axes on which to draw the temporary basal rates.
        datetimes (list of datetime): List of datetime objects representing the times of the temporary basal rates.
        temp_basal_rates (list of float): List of temporary basal rates corresponding to the datetimes.
        temp_basal_durations (list of numpy.timedelta): List of temporary basal durations corresponding to the datetimes.
        color (str, optional): Color of the temporary basal rates. Default is colors['Basal'].
        **kwargs (dict): Additional keyword arguments passed to the ax.bar() method.
    """
    colors = np.where(temp_basal_types == 'Percent', 'yellow', 'orange')
    widths = np.array([parse_duration(dur) for dur in temp_basal_durations])
    ax.bar(datetimes, 10, color=colors, width=widths, align='edge', label='temp basal amount', alpha=0.2, edgecolor='black')
    # add the temp basal amount as text above the bars
    for i in range(len(datetimes)):
        ax.text(datetimes[i] + widths[i] / 2, 5, f"{temp_basal_rates[i]} {temp_basal_types[i]}", fontsize=8, color='gray', rotation=90)
    
def drawAbsoluteBasalRates(ax, datetimes, rate, **kwargs):
    """
    Draws the absolute basal rates on the given axes.
    
    Args:
        ax (matplotlib.axes.Axes): The axes on which to draw the basal rates.
        datetimes (array-like): An array of datetime objects representing the time points.
        rate (array-like): An array of basal rates corresponding to the time points.
        **kwargs (dict): Additional keyword arguments to customize the plot. Possible keys include:  
        
            - 'hatch' (str): The hatch pattern for the plot. Default is '//'.
            - 'label' (str): The label for the plot. Default is 'true basal rate'.
            - 'edgecolor' (str): The edge color for the plot. Default is 'black'.
    """

    if len(datetimes)>0: 
        formatters = {'hatch':'//', 'label':'true basal rate', 'edgecolor':'black'}
        formatters.update(kwargs)
        i_sorted = np.argsort(datetimes)
        ax.stairs(rate[i_sorted][:-1], datetimes[i_sorted],  **formatters)

def drawSuspendTimes(ax, start_date, duration):
    """ Draws a bar on the given axis to represent suspend times.

    Args:
        ax (matplotlib.axes.Axes): The axis on which to draw the bar.
        start_date (datetime-like): The starting date and time for the bar.
        duration (np.timedelta): The duration for which the bar extends.
    """

    ax.bar(start_date, 10, width=duration, alpha=0.2, edgecolor='red', color='red', label='Suspend',align='edge')

def drawMovingAverage(ax, df, datetime_col, value_col, aggregator='mean', **kwargs):
    assert df[value_col].isna().sum() == 0, f'{value_col} contains NaN values'

    df = df.copy()
    
    df['hod'] = get_hour_of_day(df[datetime_col])
    ma  = df[['hod',value_col]].sort_values('hod').rolling(window=len(df)//128, 
                                                                          min_periods=len(df)//256, 
                                                                          on='hod', center=True).agg(aggregator)    
    ma = ma.sample(len(df)//10)

    args =  {'color':'darkgray', 'marker':'o', 's':10, 'label': f'MA of {value_col}'}
    args.update(kwargs)
    ax.scatter(ma['hod'], ma[value_col], **args)
    ax.set_xlabel('Hour of Day')
    ax.set_xticks(np.arange(0,24,4))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):02d}:00'))
    ax.legend()


def drawMidnightLines(ax, datetimes, color='gray', linestyle='--', alpha=0.5, **kwargs):
    """Draws vertical lines at every midnight spanned by the given datetimes.

    One line is drawn per day, from the midnight starting the first datetime's
    day to the midnight starting the last datetime's day, inclusive of both.

    Args:
        ax (matplotlib.axes.Axes): The axes on which to draw the lines.
        datetimes (array-like of datetime): The datetimes whose spanned days' midnights should be drawn.
        color (str, optional): Line color. Defaults to 'gray'.
        linestyle (str, optional): Line style. Defaults to '--'.
        alpha (float, optional): Line transparency. Defaults to 0.5.
        **kwargs (dict): Additional keyword arguments passed to ax.axvline().
    """
    datetimes = pd.to_datetime(pd.Series(datetimes))
    midnights = pd.date_range(datetimes.min().normalize(), datetimes.max().normalize(), freq='D')

    defaults = {'color': color, 'linestyle': linestyle, 'alpha': alpha}
    defaults.update(kwargs)
    for midnight in midnights:
        ax.axvline(midnight, **defaults)

def draw_presence_matrix(ax, df, x_col, y_col, offset=0, **kwargs):
    """
    Scatter plots unique available x_values for y_col groups in a DataFrame.
    Args:
        ax (matplotlib.axes.Axes): The matplotlib Axes object to plot on. 
        df (pd.DataFrame): The input DataFrame containing the data to plot.
        x_col (str): The column name in the DataFrame representing the x-axis values (e.g., datetime).
        y_col (str): The column name in the DataFrame representing the y-axis values used for grouping (e.g., patient IDs).
        offset (int, optional): An offset to apply to the y-axis values. Defaults to 0.
        **kwargs: Additional keyword arguments to pass to the `ax.scatter` method.
    Returns:
        None
    """
    
    availability = df.groupby([y_col])[x_col].unique().reset_index().explode(x_col)

    # Plot with scatter
    args = {'color': 'blue', 's': 1}
    args.update(kwargs)
    ax.scatter(availability[x_col], availability[y_col] + offset, **args)
    
    #add y ticks for all values
    y_tick_positions = availability[y_col].unique().astype('float')
    ax.set_yticks(y_tick_positions)