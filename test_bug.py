import sys
import os
sys.path.append(os.getcwd())
from main import format_tag_name, load_dictionary

custom_dict = load_dictionary()
print("Dictionary:", custom_dict)

test_word = "chase_attck_End"
result = format_tag_name(test_word, custom_dict)
print(f"Result for {test_word}:", result)

import wordninja
print("wordninja split 'attck':", wordninja.split('attck'))
