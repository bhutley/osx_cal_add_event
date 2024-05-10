#!/usr/bin/env python3
"""
A script to add an event to an OS/X Calendar.
Originally based on a gist I wrote in 2017: https://gist.github.com/bhutley/2614f4d41d4e1f8b6377ac03285beeaa
Then was contacted by Mike Youell in 2024 who had updated it to support timed events.
I have updated to use the EventKit framework instead of the CalendarStore framework,
I have also simplified the calling interface I think.
"""
from typing import Optional
import objc
import argparse
from EventKit import EKEventStore, EKEntityTypeEvent, EKCalendar, EKEvent, EKSpanThisEvent
from Cocoa import NSDate
import datetime


def parse_date(date_str: str) -> (datetime.datetime, bool):
    """Parse a date string in the format YYYY-MM-DD, YYYY-MM-DDTHH:MM, or YYYY-MM-DD HH:MM.
    Returns a tuple of a datetime object and a boolean indicating if the time is included.
    """
    date_str = date_str.strip()

    time_included = False
    if 'T' in date_str or ' ' in date_str:
        time_included = True
        parse_format = "%Y-%m-%dT%H:%M" if 'T' in date_str else "%Y-%m-%d %H:%M"
    else:
        parse_format = "%Y-%m-%d"
    return datetime.datetime.strptime(date_str, parse_format), time_included


def parse_duration(duration_str: str) -> datetime.timedelta:
    """Parse a duration string in the format HH:MM, or [1-9]m or [1-9]h.
    Returns a timedelta object.
    """
    duration_str = duration_str.strip()
    if ':' in duration_str:
        hours, minutes = duration_str.split(':')
        return datetime.timedelta(hours=int(hours), minutes=int(minutes))

    if duration_str[-1] == 'm':
        return datetime.timedelta(minutes=int(duration_str[:-1]))
    if duration_str[-1] == 'h':
        return datetime.timedelta(hours=int(duration_str[:-1]))
    raise ValueError(f"Invalid duration string: {duration_str}")


def resolve_calendar_by_name(store: EKEventStore, calendar_name: str) -> Optional[EKCalendar]:
    calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
    for cal in calendars:
        if cal.title() == calendar_name:
            return cal
    return None


def create_event(store: EKEventStore, calendar: EKCalendar, is_all_day_event: bool, start_dt: datetime.datetime, end_dt: datetime.datetime, title: str) -> EKEvent:
    """
    Create and save a new event in the iCloud Home calendar.

    Returns:
        CalEvent: The newly created event object if the event was saved successfully.

    Raises:
        Exception: If an error occurs while saving the event to the calendar.
    """

    ns_date_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
    ns_date_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())

    new_event = EKEvent.eventWithEventStore_(store)

    new_event.setValue_forKey_(calendar, 'calendar')
    new_event.setValue_forKey_(ns_date_start, 'startDate')
    new_event.setValue_forKey_(ns_date_end, 'endDate')
    new_event.setValue_forKey_(title, 'title')
    new_event.setValue_forKey_(is_all_day_event, 'allDay')

    # Save the event
    res, err = store.saveEvent_span_error_(new_event, 0, None)

    # Check for errors
    if err is not None:
        raise Exception("Failed to save the EKEvent: %@", err)

    return new_event


if __name__ == "__main__":
    objc.options.verbose = True

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-e', '--end-date', type=str, required=False, default="", help='End date of event')
    parser.add_argument('-d', '--duration', type=str, required=False, default="", help='Duration of event')
    parser.add_argument('-c', '--calendar', type=str, required=False, default="Home",
                        help='Calendar to add event to. Default is "Home"')
    parser.add_argument('date', type=str,
                        help='Date of event. Must be in the format YYYY-MM-DD, YYYY-MM-DDTHH:MM, or YYYY-MM-DD HH:MM')
    parser.add_argument('title', type=str, help='Title of event')
    args = parser.parse_args()

    start_date = args.date
    title = args.title

    # Create an event store object
    store = EKEventStore.alloc().init()

    home_cal = resolve_calendar_by_name(store, args.calendar)
    if home_cal is None:
        print(f"Couldn't find a calendar with the name: {args.calendar}")
        print("Available calendars:")
        calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
        for cal in calendars:
            print(f"  {cal.title()} ({cal.type()})")
        exit(1)

    try:
        start, was_time_included = parse_date(start_date)
    except ValueError as e:
        print(f"Error parsing date: {start_date}: {e}")
        print("Date must be in the format YYYY-MM-DD, YYYY-MM-DDTHH:MM, or YYYY-MM-DD HH:MM")
        parser.print_help()
        exit(1)

    end_date_time_included = False
    if args.end_date:
        try:
            end, end_date_time_included = parse_date(args.end_date)
        except ValueError as e:
            print(f"Error parsing end date: {args.end_date}: {e}")
            print("Date must be in the format YYYY-MM-DD, YYYY-MM-DDTHH:MM, or YYYY-MM-DD HH:MM")
            parser.print_help()
            exit(1)
    elif args.duration and was_time_included:
        try:
            duration = parse_duration(args.duration)
        except ValueError as e:
            print(f"Error parsing duration: {args.duration}: {e}")
            print("Duration must be in the format HH:MM, or #m or #h")
            print("e.g. 1h, 30m, 1:30")
            parser.print_help()
            exit(1)
        end = start + duration
        end_date_time_included = True
    else:
        end = start

    if was_time_included and not end_date_time_included:
        print("Error: Start time was included but end time was not.")
        parser.print_help()
        exit(1)

    if end < start:
        print("Error: End date is before start date.")
        parser.print_help()
        exit(1)

    event = create_event(store, home_cal, not was_time_included, start, end, title)

