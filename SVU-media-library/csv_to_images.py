import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from random import *
from PIL import Image
import pandas as pd
import json

# ensures program doesn't give up on a large image
Image.MAX_IMAGE_PIXELS = 1000000000

threads = 6
task_count = 0

# gets csv of images into dataframe
file  = input('File path: ')
df = pd.read_csv(file)

url_list = list(df['Link to image'])
name_list = list(df['Object'])
size = (250,173)

# retrieves image from web
def get_img(url, name):
    response = requests.get(url)

    # writes image into a binary file
    with open(f'{name}.jpg', 'wb') as file:
        file.write(response.content)
    print(f'created {name}')

    # converts to jpg type
    native = Image.open(f'{name}.jpg')
    native.save(f'{name}.jpg', 'JPEG')

# resizes image into a thumbnail and UHD version
def resize_img(name):

    # ensures image is in correct format to be written
    img = Image.open(f'{name}.jpg')#.convert('RGB')

    # creates 250x173 thumbnail
    thumbnail = img.resize(size)
    thumbnail.save(f'{name}_Thumbnail.jpg', 'JPEG')
    print(f'created thumbnail of {name}')

    # finds which size to scale by
    width, height = img.size
    width = int(width)
    height = int(height)
    width_reduced = width/16
    height_reduced = height/9

    # creates HD version
    if height_reduced >= width_reduced:
        UHD_img = img.resize((int(width*2160/height),2160))
        HD_img = img.resize((int(width*1080/height),1080))
    else:
        UHD_img = img.resize((3840,int(height*3840/width)))
        HD_img = img.resize((1920,int(height*1920/width)))
    if height >= 16000 or width >= 16000:
        UHD_img.save(f'{name}.jpg','JPEG')
    UHD_img.save(f'{name}_UHD.jpg', 'JPEG')
    HD_img.save(f'{name}_HD.jpg', 'JPEG')
    print('created UHD image')


# writes json metadata file
def write_json(url, pos, name):

    # sets up json template
    data =  {
    "contentID": 1,
    "mediaName": "",
    "mediaDescription": "",
    "mediaType": "Image",
    "mediaSize": 1,
    "fileLocation": "",
    "mediaTopics": ["All"],
    "MetadataTags": "",
    "Attribution": ""
    }

    # cleaning metadata tags
    tester = str(df.iat[pos,8]).split(",")
    tester = [item.strip() for item in tester]
    print(tester)
    tags = ",".join(tester)
    tags = tags.strip(",")

    # assigns metadata values
    data["mediaName"] = str(name)
    data["mediaDescription"] = str(df.iat[pos,1])
    data["MetadataTags"] = f"{tags},astral"
    data["Attribution"] = f"Credit: {str(df.iat[pos,7])}"
    
    # writes json file
    with open(f"{name}.json", "x") as outfile:
        outfile.write("[\n")
        json.dump(data, outfile, indent = 4)
        outfile.write("\n")
        outfile.write("]")
    print(f'wrote json {url}')

# runs each process in the correct order
def main(url):

    # gets position of current image in csv
    pos = url_list.index(url)

    # formats name of image
    name = str(name_list[pos])
    name = "".join(name.split())
    name = name.strip('\'\" ')

    # main processes
    get_img(url, name)
    resize_img(name)
    write_json(url, pos, str(name))

# multithreading executor
with ThreadPoolExecutor() as executor:
    task_list = {executor.submit(main, url): url for url in url_list}
    for task in concurrent.futures.as_completed(task_list):
        
        # counts how many images have been completed
        task_count += 1
        tasks_total = len(url_list)
        