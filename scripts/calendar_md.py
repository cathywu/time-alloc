"""
Script for CalendarSolver functionality with integrated markdown parser.
"""
import time

import numpy as np

from timealloc.calendar_solver import CalendarSolver
from timealloc.task_parser import TaskParser
import timealloc.util_time as tutil


DEFAULT_CHUNK_MIN = 2  # in IP slot units
DEFAULT_CHUNK_MAX = 20  # in IP slot units
MODIFIERS = ['after', 'before', 'at', 'on']
num_timeslots = 24 * 7 * tutil.SLOTS_PER_HOUR

# User specified input files
time_allocation_fname = "scratch/time-allocation-2018-09-03.md"
tasks_fname = "scratch/tasks-2018-09-27.md"

tasks = TaskParser(time_allocation_fname, tasks_fname)

task_names = list(tasks.tasks.keys())
num_work_tasks = len(task_names)

category_names = list(tasks.time_alloc.keys())[:2]
task_names += category_names

for i, task in enumerate(task_names):
    print(i, task)

num_categories = len(category_names)
num_tasks = num_work_tasks + num_categories

# TODO clean up
task_duration = 336*np.ones(num_tasks)  # initialize task duration as 1 slot
task_chunk_min = DEFAULT_CHUNK_MIN * np.ones(num_tasks)
# FIXME(cathywu) 10 is currently not supported, so these constraints should be
#  off by default
task_chunk_max = DEFAULT_CHUNK_MAX * np.ones(num_tasks)

# Special setup for default tasks (default task for each category)
task_chunk_min[num_work_tasks:] = 0  # these tasks can be slotted in however
task_chunk_max[num_work_tasks:] = 300

# num_tasks-by-num_categories matrix
task_category = np.zeros((num_tasks, num_categories))
# FIXME(cathywu) this is temporary for initially supporting categories
category_min = np.ones(num_categories)
category_max = 336*np.ones(num_categories)  # FIXME(cathywu) support this
for i, cat in enumerate(category_names):
    if 'total' in tasks.time_alloc[cat]:
        category_min[i] = tasks.time_alloc[cat]['total'] * tutil.SLOTS_PER_HOUR

# work_category = category_names.index("Work")
work_category = 0  # FIXME override
work_tasks = range(num_work_tasks)
task_category[work_tasks, work_category] = 1
for i in range(num_categories):
    task_category[num_work_tasks+i, i] = 1
print("Task category", task_category)

# FIXME(cathywu) have non-uniform utilities
utilities = np.ones((num_timeslots, num_tasks, num_categories))
# Fewer points for scheduling default tasks
utilities[:, num_work_tasks:, :] = 0.5  # TODO parameterize this

# Working hours
# TODO(cathywu) remove this for full scheduling version
stime = tutil.text_to_struct_time("8:30am")
work_mask = tutil.struct_time_to_slot_mask(stime, modifier="after")
stime = tutil.text_to_struct_time("9:30pm")
mask = tutil.struct_time_to_slot_mask(stime, modifier="before")
work_mask = np.array(np.logical_and(work_mask, mask), dtype=int)

# Contiguous (0) or spread (1) scheduling
task_spread = np.zeros(num_tasks)

print("Number of tasks", num_tasks)
# Task specific time constraints mask
# Assume first num_work_tasks entries are for work entries
# TODO(cathywu) refactor this
overall_mask = np.ones((24*7*tutil.SLOTS_PER_HOUR, num_tasks))
for i, task in enumerate(tasks.tasks.keys()):
    total = tasks.tasks[task]["total"]
    task_duration[i] = tutil.hour_to_ip_slot(total)

    for key in tasks.tasks[task]:
        sub_mask = np.ones(24*7*tutil.SLOTS_PER_HOUR)
        if key in MODIFIERS:
            sub_mask = np.zeros(24*7*tutil.SLOTS_PER_HOUR)
            modifier = key
            attributes = tasks.tasks[task][key].split('; ')
            for attr in attributes:
                # print(task, key, attr)
                try:
                    stime = tutil.text_to_struct_time(attr)
                    mask = tutil.struct_time_to_slot_mask(stime,
                                                          modifier=modifier,
                                                          duration=tutil.hour_to_ip_slot(
                                                              total))
                except UnboundLocalError:
                    try:
                        dtime = tutil.text_to_datetime(attr, weekno=39,
                                                       year=2018)
                        mask = tutil.datetime_to_slot_mask(dtime,
                                                           modifier=modifier,
                                                           duration=tutil.hour_to_ip_slot(
                                                               total))
                    except UnboundLocalError:
                        raise (NotImplementedError,
                               "{} {} not supported".format(modifier, attr))
                sub_mask = np.logical_or(sub_mask, mask)
            overall_mask[:, i] = np.array(
                np.logical_and(overall_mask[:,i], sub_mask), dtype=int)
        elif key == "chunks":
            chunks = tasks.tasks[task][key].split('-')
            task_chunk_min[i] = tutil.hour_to_ip_slot(float(chunks[0]))
            task_chunk_max[i] = tutil.hour_to_ip_slot(float(chunks[-1]))
        elif key == "total":
            pass
        elif key == 'spread':
            task_spread[i] = True
        elif key == 'display name':
            # Use tasks display names if provided
            # TODO(cathywu) Use full task names for eventual gcal events?
            task_names[i] = tasks.tasks[task]['display name']
        else:
            print('Not yet handled key ({}) for {}'.format(key, task))

    # FIXME(cathywu) remove this later, this is for the "simplified IP"
    overall_mask[:, i] = np.array(np.logical_and(overall_mask[:,i], work_mask),
                                  dtype=int)
    # print(overall_mask.reshape((7,int(overall_mask.size/7))))

print('Chunks', task_chunk_min, task_chunk_max)

# Permit the scheduling of short tasks
# TODO(cathywu) Permit the grouping of small tasks into larger ones? Like an
# errands block
for i in range(num_tasks):
    if task_chunk_min[i] > task_duration[i]:
        task_chunk_min[i] = task_duration[i]

# Prepare the IP
params = {
    'num_timeslots': num_timeslots,
    'num_categories': num_categories,
    'category_names': category_names,
    'category_min': category_min,
    'category_max': category_max,
    'task_category': task_category,
    'num_tasks': num_tasks,  # for category "work", privileged category 0
    'task_duration': task_duration,
    'task_valid': overall_mask,
    'task_chunk_min': task_chunk_min,
    'task_chunk_max': task_chunk_max,
    'task_names': task_names,
    'task_spread': task_spread,
}
cal = CalendarSolver(utilities, params)

# Solve
print("Optimizing...")
start_ts = time.time()
cal.optimize()
solve_time = time.time() - start_ts

# Display the results
cal.visualize()

cal.display()
array = np.reshape([y for (x,y) in cal.instance.A.get_values().items()],
                   (num_timeslots, num_tasks))
print("Schedule (timeslot x task):")
print(array)
print('Solve time', solve_time)
