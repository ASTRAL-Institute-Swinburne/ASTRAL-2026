import json
from pathlib import Path
import pandas as pd

# get paths to json files + existing csv
folder = Path(input("Path to json folder: "))
library = Path(input("Path to media library csv: "))

# create dataframes
df = pd.DataFrame()
media_df = pd.read_csv(library)

# iterate through each file in folder
for file_path in folder.iterdir():
    if file_path.is_file():

        # check if file is a json
        if file_path.name.split(".")[-1] == "json":

            # read in file and ignore encoding errors
            with open(str(file_path), 'r', errors='ignore') as file:

                # read in file as one string
                lines = file.readlines()
                lines = lines[1:-1]
                lines = "\n".join(lines)

            # turn string into dictionary
            data = json.loads(lines)

            # replace media name with name used for json file
            data["mediaName"] = file_path.name.split(".")[0]

            # add json data to dataframe
            new_line = pd.DataFrame(data)
            if len(new_line) > 1:
                new_line = new_line.head(1)
            print(new_line)
            df = pd.concat([df, new_line])

# restructure dataframe columns to match media library csv
df = df.rename(columns={"mediaName":"Object", "mediaDescription":"Description", "MetadataTags":"Keywords", "Attribution":"Credit"})
df = df.drop(columns=["contentID","mediaType","mediaSize","fileLocation","mediaTopics"])


df.to_csv("Automagic images/Testing zone/test_jsons.csv", index=False)

# add new json data to media library csv
df_concat = pd.concat([media_df,df]).fillna("null")
df_concat.drop(df_concat.columns[df_concat.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
df_concat.to_csv("Automagic images/Testing zone/test.csv", index=False)
