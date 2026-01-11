import json


d1={1:1,3:3}
lst=[1,2,3]
with open("temp.json","w") as file:
    json.dump({"dictionary":d1,"list":lst},file)