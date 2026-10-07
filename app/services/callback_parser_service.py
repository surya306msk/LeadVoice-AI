import re
import pytz
from datetime import datetime, timedelta
from typing import Optional, Tuple
from app.models.schemas import CallbackParseResponse

class CallbackParserService:
    def __init__(self):
        self.tz = pytz.timezone("Asia/Kolkata")
        
        # Default times
        self.vague_times = {
            "morning": (10, 0),    # 10:00 AM
            "afternoon": (15, 0),  # 3:00 PM
            "evening": (18, 0),    # 6:00 PM
            "night": (20, 0)       # 8:00 PM
        }

    async def parse_callback(
        self,
        callback_expression: str,
        reference_time: Optional[datetime] = None
    ) -> CallbackParseResponse:
        """
        Parses a natural language callback expression relative to a reference time.
        """
        expr = callback_expression.strip().lower()
        
        # 1. Determine reference time in Asia/Kolkata
        if reference_time is None:
            ref = datetime.now(self.tz)
        else:
            if reference_time.tzinfo is None:
                ref = self.tz.localize(reference_time)
            else:
                ref = reference_time.astimezone(self.tz)

        # Basic cleanup - do NOT strip 'in' if it's part of a relative date expression (e.g. 'in two days')
        expr_clean = re.sub(r'^(call me|please call|call|schedule a call for|schedule a call|schedule|callback)\s+', '', expr)
        expr_clean = re.sub(r'^(at|on)\s+', '', expr_clean)

        # Try to resolve date and time
        parsed_date, date_assumption = self._resolve_date(expr_clean, ref)
        parsed_time, time_assumption = self._resolve_time(expr_clean, ref)

        # Handle ambiguous expression (neither date nor time could be resolved)
        if parsed_date is None and parsed_time is None:
            return CallbackParseResponse(
                callback_requested=True,
                original_expression=callback_expression,
                scheduled_at=None,
                timezone="Asia/Kolkata",
                confidence=0.3,
                assumption="A specific callback date and time could not be determined."
            )

        # If we have a date but no explicit time, default to 10:00 AM
        if parsed_date is not None and parsed_time is None:
            parsed_time = (10, 0)
            time_assumption = "Default callback time was set to 10:00 AM"

        # If we have a time but no explicit date, resolve relative to reference time
        if parsed_date is None and parsed_time is not None:
            target_dt = ref.replace(hour=parsed_time[0], minute=parsed_time[1], second=0, microsecond=0)
            if target_dt > ref:
                parsed_date = ref.date()
                date_assumption = "Today"
            else:
                parsed_date = (ref + timedelta(days=1)).date()
                date_assumption = "Tomorrow"

        # Combine date and time
        target_datetime = datetime.combine(parsed_date, datetime.min.time())
        target_datetime = self.tz.localize(target_datetime)
        target_datetime = target_datetime.replace(hour=parsed_time[0], minute=parsed_time[1])

        # Combine assumptions
        assumptions = []
        if date_assumption:
            assumptions.append(date_assumption)
        if time_assumption:
            assumptions.append(time_assumption)
            
        assumption_text = " and ".join(assumptions) + "."

        return CallbackParseResponse(
            callback_requested=True,
            original_expression=callback_expression,
            scheduled_at=target_datetime,
            timezone="Asia/Kolkata",
            confidence=0.9,
            assumption=assumption_text
        )

    def _resolve_date(self, expr: str, ref: datetime) -> Tuple[Optional[datetime.date], Optional[str]]:
        # 1. Relative dates
        if "day after tomorrow" in expr:
            return (ref + timedelta(days=2)).date(), "Day after tomorrow"
        if "tomorrow" in expr:
            return (ref + timedelta(days=1)).date(), "Tomorrow"
        if "today" in expr:
            return ref.date(), "Today"

        # "in X days" / "in one day" / "in two days"
        match_in_days = re.search(r'(?:in\s+)?(\d+|one|two|three|four|five)\s+days?', expr)
        if match_in_days:
            num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            val = match_in_days.group(1)
            days = int(val) if val.isdigit() else num_map.get(val, 1)
            return (ref + timedelta(days=days)).date(), f"In {days} days"

        # 2. Weekdays
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
        }
        for name, day_num in weekdays.items():
            if name in expr:
                is_next = "next" in expr
                days_ahead = day_num - ref.weekday()
                
                if days_ahead < 0:
                    days_ahead += 7
                elif days_ahead == 0:
                    # Today is the target day.
                    if "this" in expr:
                        days_ahead = 0
                    else:
                        days_ahead = 7
                
                if is_next and ("next " + name) in expr:
                    if day_num >= ref.weekday():
                        # Target day is later this week, so "next [Day]" means next week's occurrence
                        days_ahead += 7
                
                target_date = (ref + timedelta(days=days_ahead)).date()
                return target_date, f"{name.capitalize()}"

        return None, None

    def _resolve_time(self, expr: str, ref: datetime) -> Tuple[Optional[Tuple[int, int]], Optional[str]]:
        # 1. Explicit time parsing (e.g. 6 PM, 6:30 PM, 10 AM, 14:00, 18:30)
        match_time = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', expr)
        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2)) if match_time.group(2) else 0
            meridiem = match_time.group(3)

            # E.g. "14:00" -> meridiem is None, but hour > 12
            if meridiem:
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
            
            return (hour, minute), f"Time set to {hour:02d}:{minute:02d}"

        # 2. Vague times (morning, afternoon, evening, night)
        for name, time_val in self.vague_times.items():
            if name in expr:
                hour_name = "AM" if time_val[0] < 12 else "PM"
                hr_12 = time_val[0] if time_val[0] <= 12 else time_val[0] - 12
                return time_val, f"{name.capitalize()} was interpreted as {hr_12}:00 {hour_name}"

        return None, None
