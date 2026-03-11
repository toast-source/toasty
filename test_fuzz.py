import sys
import os
from thefuzz import process, fuzz

custom_dict = [
    "Attack", "Ready", "Groggy", "End", "Loop", "Channeling", "Break",
    "Idle", "Walk", "Run", "Jump", "Fall", "Hit", "Dead", "Skill",
    "Ultimate", "Phase", "Start", "Intro", "Outro", "Chase"
]

dict_lower = {w.lower(): w for w in custom_dict}
choices = list(dict_lower.keys())

word_lower = 'attck'
best_match = process.extractOne(word_lower, choices, scorer=fuzz.ratio)
print("Fuzz ratio for 'attck':", best_match)

word_lower = 'powerwave'
best_match2 = process.extractOne(word_lower, choices, scorer=fuzz.ratio)
print("Fuzz ratio for 'powerwave':", best_match2)
