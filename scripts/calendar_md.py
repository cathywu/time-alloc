"""
Script for CalendarSolver functionality with integrated markdown parser.
"""
import time
from datetime import datetime

import numpy as np

from timealloc.tasks import Tasks
from timealloc.calendar_solver import CalendarSolver
import timealloc.util_time as tutil
from timealloc.util_time import NUMSLOTS

MODIFIERS = ['after', 'before', 'at', 'on']

# User specified input files
# time_allocation_fname = "scratch/time-allocation-2018-09-28-simple.md"
time_allocation_fname = "scratch/time-allocation-2018-09-30.md"
tasks_fname = "scratch/tasks-2018-09-30.md"

tasks = Tasks(time_allocation_fname, tasks_fname)

# Plan from now
# TODO(cathywu) specify a plan from time
start = datetime.today()
weekday = (start.weekday() + 2) % 7
offset = weekday * tutil.SLOTS_PER_DAY + start.hour * tutil.SLOTS_PER_HOUR

tasks.display()

params = tasks.get_ip_params()
cal = CalendarSolver(tasks.utilities, params)

# Solve
print("Optimizing...")
start_ts = time.time()
cal.optimize()
solve_time = time.time() - start_ts

# Display the results
cal.visualize()
cal.display()
cal.get_diagnostics()
print('Solve time', solve_time)
