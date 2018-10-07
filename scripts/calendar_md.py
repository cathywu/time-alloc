"""
Script for CalendarSolver functionality with integrated markdown parser.
"""
import time

import numpy as np

from timealloc.calendar_solver import CalendarSolver
from timealloc.task_parser import TaskParser
import timealloc.util_time as tutil
from timealloc.util_time import NUMSLOTS

DEFAULT_CHUNK_MIN = 2  # in IP slot units
DEFAULT_CHUNK_MAX = 20  # in IP slot units
MODIFIERS = ['after', 'before', 'at', 'on']

# User specified input files
# time_allocation_fname = "scratch/time-allocation-2018-09-28-simple.md"
time_allocation_fname = "scratch/time-allocation-2018-09-30.md"
tasks_fname = "scratch/tasks-2018-09-30.md"

tasks = TaskParser(time_allocation_fname, tasks_fname)

# Currently, there are 3 types of tasks: work, other, and category defaults
work_task_names = list(tasks.work_tasks.keys())
num_work_tasks = len(work_task_names)
other_task_names = list(tasks.other_tasks.keys())
num_other_tasks = len(other_task_names)
category_names = list(tasks.time_alloc.keys())
num_categories = len(category_names)

# Collect all the task names
task_names = work_task_names
task_names += other_task_names
task_names += category_names  # use category name as default task name
num_tasks = num_work_tasks + num_other_tasks + num_categories

# TODO clean up
task_duration = NUMSLOTS * np.ones(num_tasks)  # initialize task duration as 1 slot
task_chunk_min = DEFAULT_CHUNK_MIN * np.ones(num_tasks)
# FIXME(cathywu) 10 is currently not supported, so these constraints should be
#  off by default
task_chunk_max = DEFAULT_CHUNK_MAX * np.ones(num_tasks)

# Special setup for default tasks (default task for each category)
task_chunk_min[num_work_tasks:] = 0  # these tasks can be slotted in however
task_chunk_max[num_work_tasks:] = NUMSLOTS

# num_tasks-by-num_tasks matrices
# FIXME(cathywu) currently not used
before = np.zeros((num_tasks, num_tasks))
after = np.zeros((num_tasks, num_tasks))

# num_tasks-by-num_categories matrix
task_category = np.zeros((num_tasks, num_categories))
category_min = np.zeros(num_categories)
category_max = NUMSLOTS * np.ones(num_categories)

# FIXME(cathywu) have non-uniform utilities
utilities = 0.5 * np.ones((NUMSLOTS, num_tasks))
# Fewer points for scheduling 'other' tasks
utilities[:, num_work_tasks:] = 0.333  # TODO parameterize this
# Fewer points for scheduling default tasks
utilities[:, num_work_tasks + num_other_tasks:] = 0  # TODO parameterize this

# Completion bonus for fully scheduling tasks
completion_bonus = 0.5 * np.ones(num_tasks)
completion_bonus[num_work_tasks:] = 0.333
completion_bonus[num_work_tasks + num_other_tasks:] = 0

# Cognitive load for each task [-1, 1]
cognitive_load = np.zeros(num_tasks)

# contiguous (0) or spread (1) scheduling; default is contiguous (0)
task_spread = np.zeros(num_tasks)
# by default, categories are allowed to be assigned on any timeslots
category_masks = np.ones((NUMSLOTS, num_categories))
# by default, no categories need to be assigned on any particular days
category_days = np.zeros((7, num_categories))
# by default, each category is required on 0 days
category_days_total = np.zeros(num_categories)

# Task specific time constraints mask
# Assume first num_work_tasks entries are for work entries
overall_mask = np.ones((NUMSLOTS, num_tasks))

# CATEGORIES
# Read out per-category attributes
offset = num_work_tasks + num_other_tasks
for k, cat in enumerate(category_names):
    task_category[offset + k, k] = 1  # categories for default tasks

    for key in tasks.time_alloc[cat]:
        if key == "when":
            for clause in tasks.time_alloc[cat][key]:
                sub_mask = tutil.modifier_mask(clause, category_min[k])
                category_masks[:, k] = np.array(
                    np.logical_and(category_masks[:, k], sub_mask), dtype=int)
        elif key == "chunks":
            chunks = tasks.time_alloc[cat][key].split('-')
            task_chunk_min[offset + k] = tutil.hour_to_ip_slot(
                float(chunks[0]))
            task_chunk_max[offset + k] = tutil.hour_to_ip_slot(
                float(chunks[-1]))
        elif key == "total":
            pass
        elif key == "min":
            category_min[k] = tasks.time_alloc[cat][key] * \
                              tutil.SLOTS_PER_HOUR
        elif key == "max":
            category_max[k] = tasks.time_alloc[cat][key] * \
                              tutil.SLOTS_PER_HOUR
        elif key == "days":
            category_days[:, k], category_days_total[k] = tutil.parse_days(
                tasks.time_alloc[cat][key])
        elif key == "cognitive load":
            cognitive_load[offset + k] = float(tasks.time_alloc[cat][key])
        elif key == "before":
            other_task = tasks.time_alloc[cat][key]
            other_task_ind = category_names.index(other_task)
            before[offset + k, offset + other_task_ind] = 1
        elif key == "after":
            other_task = tasks.time_alloc[cat][key]
            other_task_ind = category_names.index(other_task)
            after[offset + k, offset + other_task_ind] = 1
        else:
            print('Not yet handled key ({}) for {}'.format(key, cat))
overall_mask[:, -num_categories:] = category_masks

# OTHER TASKS
offset = num_work_tasks
for i, task in enumerate(other_task_names):
    total = tasks.other_tasks[task]["total"]
    task_duration[offset+i] = tutil.hour_to_ip_slot(total)

    for key in tasks.other_tasks[task]:
        if key == "when":
            for clause in tasks.other_tasks[task][key]:
                sub_mask = tutil.modifier_mask(clause, total)
                overall_mask[:, offset+i] = np.array(
                    np.logical_and(overall_mask[:, offset+i], sub_mask),
                    dtype=int)
        elif key == "categories":
            categories = tasks.other_tasks[task][key].split(", ")
            for cat in categories:
                cat_id = category_names.index(cat)
                task_category[offset + i, cat_id] = 1
                category_mask = category_masks[:, cat_id]
                overall_mask[:, offset + i] = np.array(
                    np.logical_and(overall_mask[:, offset + i], category_mask),
                    dtype=int)
        elif key == "chunks":
            chunks = tasks.other_tasks[task][key].split('-')
            task_chunk_min[offset+i] = tutil.hour_to_ip_slot(float(chunks[0]))
            task_chunk_max[offset+i] = tutil.hour_to_ip_slot(float(chunks[-1]))
        elif key == "total":
            pass
        elif key == 'spread':
            task_spread[offset+i] = True
        elif key == "cognitive load":
            cognitive_load[offset + i] = float(tasks.other_tasks[task][key])
        elif key == 'completion':
            if tasks.other_tasks[task][key] == 'off':
                completion_bonus[offset + i] = 0
                utilities[:, offset + i] = 0.667
        elif key == 'display name':
            # Use tasks display names if provided
            # TODO(cathywu) Use full task names for eventual gcal events?
            task_names[offset+i] = tasks.other_tasks[task]['display name']
        else:
            print('Not yet handled key ({}) for {}'.format(key, task))

# WORK TASKS
# Working hours
work_category = category_names.index("Work")
work_mask = category_masks[:, work_category]
work_tasks = range(num_work_tasks)

print("Number of tasks", num_tasks)
# Task specific time constraints mask
offset = 0
for i, task in enumerate(tasks.work_tasks.keys()):
    total = tasks.work_tasks[task]["total"]
    task_duration[i] = tutil.hour_to_ip_slot(total)
    # toggle work category
    task_category[offset + i, work_category] = 1

    for key in tasks.work_tasks[task]:
        if key == "when":
            for clause in tasks.work_tasks[task][key]:
                sub_mask = tutil.modifier_mask(clause, total)
                overall_mask[:, i] = np.array(
                    np.logical_and(overall_mask[:, i], sub_mask), dtype=int)
        elif key == "categories":
            # other categories
            categories = tasks.work_tasks[task][key].split(", ")
            for cat in categories:
                cat_id = category_names.index(cat)
                task_category[offset + i, cat_id] = 1
                category_mask = category_masks[:, cat_id]
                overall_mask[:, offset + i] = np.array(
                    np.logical_and(overall_mask[:, offset + i], category_mask),
                    dtype=int)
        elif key == "chunks":
            chunks = tasks.work_tasks[task][key].split('-')
            task_chunk_min[i] = tutil.hour_to_ip_slot(float(chunks[0]))
            task_chunk_max[i] = tutil.hour_to_ip_slot(float(chunks[-1]))
        elif key == "total":
            pass
        elif key == 'spread':
            task_spread[i] = True
        elif key == "cognitive load":
            cognitive_load[offset + i] = float(tasks.work_tasks[task][key])
        elif key == 'completion':
            if tasks.work_tasks[task][key] == 'off':
                completion_bonus[offset + i] = 0
                utilities[:, offset + i] = 1
        elif key == 'display name':
            # Use tasks display names if provided
            # TODO(cathywu) Use full task names for eventual gcal events?
            task_names[i] = tasks.work_tasks[task]['display name']
        else:
            print('Not yet handled key ({}) for {}'.format(key, task))

    overall_mask[:, i] = np.array(np.logical_and(overall_mask[:, i], work_mask),
                                  dtype=int)
    # print(overall_mask.reshape((7,int(overall_mask.size/7))))

# Assert that all tasks have at least 1 category
assert np.prod(task_category.sum(axis=1)) > 0, "There are tasks without " \
                                               "categories"

print("All task names:")
for i, task in enumerate(task_names):
    print(i, task)

print("Category min/max:")
print(category_min)
print(category_max)

print('Chunks min/max:')
print(task_chunk_min)
print(task_chunk_max)

# Permit the scheduling of short tasks
# TODO(cathywu) Permit the grouping of small tasks into larger ones? Like an
# errands block
for i in range(num_tasks):
    if task_chunk_min[i] > task_duration[i]:
        task_chunk_min[i] = task_duration[i]

# Prepare the IP
params = {
    'num_timeslots': NUMSLOTS,
    'num_categories': num_categories,
    'category_names': category_names,
    'category_min': category_min,
    'category_max': category_max,
    'category_days': category_days,  # e.g. M T W Sa Su
    'category_total': category_days_total,  # e.g. 3 of 5 days
    'task_category': task_category,
    'num_tasks': num_tasks,  # for category "work", privileged category 0
    'task_duration': task_duration,
    'task_valid': overall_mask,
    'task_chunk_min': task_chunk_min,
    'task_chunk_max': task_chunk_max,
    'task_names': task_names,
    'task_spread': task_spread,
    'task_completion_bonus': completion_bonus,
    'task_cognitive_load': cognitive_load,
    'task_before': before,
    'task_after': after,
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
cal.get_diagnostics()
print('Solve time', solve_time)
