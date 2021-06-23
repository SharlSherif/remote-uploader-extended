import re

def is_in_array(arr, item):
    try:
        indx = arr.index(item)
        return indx
    except:
        print("not found")
        return 1


def find(arr, id):
    for x in arr:
        if x["id"] == id:
            return x


def clean_str(string):
    return re.sub('\s[^0-9a-zA-Z]+', ' ', str(string))

